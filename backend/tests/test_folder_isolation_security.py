"""Security regression tests for project folder isolation, path traversal, and folder sync."""

from pathlib import Path
import pytest

from backend.app.core.config import get_settings
from backend.tests.conftest import VALID_PDF, create_paper


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect Path.home() to tmp_path so tests never touch real ~/Documents."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    return home_dir


async def _upload(client, headers, paper_id, filename, content, content_type):
    return await client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, content, content_type)},
        data={"paper_id": paper_id},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_cross_user_same_title_projects_do_not_leak_documents(
    client, auth_headers, second_user_headers, isolated_home, monkeypatch
):
    """Two users each with a project titled 'Thesis': listing B's documents never returns A's files."""
    monkeypatch.setattr("backend.app.services.paper_service.os.startfile", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr("backend.app.services.paper_service.subprocess.Popen", lambda *a, **kw: None)

    paper_a = await create_paper(client, auth_headers, title="Thesis")
    paper_b = await create_paper(client, second_user_headers, title="Thesis")

    upload_resp = await _upload(
        client, auth_headers, paper_a["id"], "a_secret.pdf", VALID_PDF, "application/pdf"
    )
    assert upload_resp.status_code == 201, upload_resp.text

    open_resp = await client.post(
        f"/api/v1/papers/{paper_a['id']}/open-folder",
        headers=auth_headers,
    )
    assert open_resp.status_code == 200, open_resp.text

    list_b = await client.get(
        f"/api/v1/papers/{paper_b['id']}/documents",
        headers=second_user_headers,
    )
    assert list_b.status_code == 200, list_b.text
    assert list_b.json() == []


@pytest.mark.asyncio
async def test_same_user_duplicate_title_projects_keep_separate_folders(
    client, auth_headers, isolated_home, monkeypatch
):
    """Same user, two projects with the same title: their documents and folders stay separate."""
    monkeypatch.setenv("DESKTOP_RUNTIME", "true")
    get_settings.cache_clear()

    paper_1 = await create_paper(client, auth_headers, title="Thesis")
    paper_2 = await create_paper(client, auth_headers, title="Thesis")
    assert paper_1["folder_name"] != paper_2["folder_name"]

    up1 = await _upload(
        client, auth_headers, paper_1["id"], "first.pdf", VALID_PDF, "application/pdf"
    )
    assert up1.status_code == 201, up1.text

    # Sync paper 2's folder; it must NOT pick up paper 1's file
    sync_2 = await client.post(
        f"/api/v1/papers/{paper_2['id']}/sync-folder",
        headers=auth_headers,
    )
    assert sync_2.status_code == 200, sync_2.text
    assert sync_2.json()["added_count"] == 0

    docs_1 = await client.get(f"/api/v1/papers/{paper_1['id']}/documents", headers=auth_headers)
    docs_2 = await client.get(f"/api/v1/papers/{paper_2['id']}/documents", headers=auth_headers)
    assert [d["filename"] for d in docs_1.json()] == ["first.pdf"]
    assert docs_2.json() == []


@pytest.mark.asyncio
async def test_upload_path_traversal_does_not_escape_project_folder(
    client, auth_headers, isolated_home
):
    """An upload named ../evil.json does not write outside the project folder."""
    paper = await create_paper(client, auth_headers, title="Traversal Check")
    payload = b'{"hello": "world"}'

    resp = await _upload(
        client, auth_headers, paper["id"], "../evil.json", payload, "application/json"
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["filename"] == "evil.json"

    base_research = isolated_home / "Documents" / "Personal Research"
    # Must NOT exist outside the project folder
    assert not (base_research / "evil.json").exists()
    assert not (isolated_home / "Documents" / "evil.json").exists()
    # Must exist inside the project's isolated folder
    expected_copy = base_research / paper["folder_name"] / "evil.json"
    assert expected_copy.is_file()
    assert expected_copy.read_bytes() == payload


@pytest.mark.asyncio
async def test_upload_copies_file_into_project_folder(client, auth_headers, isolated_home):
    """upload() copies the uploaded file into the isolated project folder (verifies shutil import)."""
    paper = await create_paper(client, auth_headers, title="Copy Verification")

    resp = await _upload(
        client, auth_headers, paper["id"], "notes.txt", b"Local research notes.", "text/plain"
    )
    assert resp.status_code == 201, resp.text

    expected_path = (
        isolated_home / "Documents" / "Personal Research" / paper["folder_name"] / "notes.txt"
    )
    assert expected_path.is_file()
    assert expected_path.read_bytes() == b"Local research notes."


@pytest.mark.asyncio
async def test_sync_folder_requires_desktop_mode_and_validates_files(
    client, auth_headers, isolated_home, monkeypatch
):
    """sync-folder is blocked in web mode (403) and enforces upload validation in desktop mode."""
    paper = await create_paper(client, auth_headers, title="Sync Validation")

    # Web mode (default: desktop_runtime=False, local_folder_sync_enabled=False) -> 403
    denied = await client.post(
        f"/api/v1/papers/{paper['id']}/sync-folder",
        headers=auth_headers,
    )
    assert denied.status_code == 403, denied.text

    # Enable desktop mode
    monkeypatch.setenv("DESKTOP_RUNTIME", "true")
    get_settings.cache_clear()

    proj_dir = isolated_home / "Documents" / "Personal Research" / paper["folder_name"]
    proj_dir.mkdir(parents=True, exist_ok=True)
    # Invalid PDF (missing %PDF- signature) must be rejected by validate_document_file
    (proj_dir / "bad.pdf").write_bytes(b"not a real pdf")
    # Valid TXT file must be ingested
    (proj_dir / "valid.txt").write_text("Valid UTF-8 research content.", encoding="utf-8")

    # GET /documents must NOT auto-ingest
    before_sync = await client.get(
        f"/api/v1/papers/{paper['id']}/documents",
        headers=auth_headers,
    )
    assert before_sync.status_code == 200
    assert before_sync.json() == []

    # Explicit POST /sync-folder ingests only the valid file
    sync_resp = await client.post(
        f"/api/v1/papers/{paper['id']}/sync-folder",
        headers=auth_headers,
    )
    assert sync_resp.status_code == 200, sync_resp.text
    assert sync_resp.json()["added_count"] == 1

    after_sync = await client.get(
        f"/api/v1/papers/{paper['id']}/documents",
        headers=auth_headers,
    )
    assert [d["filename"] for d in after_sync.json()] == ["valid.txt"]


@pytest.mark.asyncio
async def test_renaming_project_preserves_folder_name(client, auth_headers, isolated_home):
    """Renaming a project's title keeps its stored folder_name stable."""
    paper = await create_paper(client, auth_headers, title="Original Title")
    original_folder = paper["folder_name"]

    patch_resp = await client.patch(
        f"/api/v1/papers/{paper['id']}",
        json={"title": "Renamed Title"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["folder_name"] == original_folder
