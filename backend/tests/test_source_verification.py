import httpx
import pytest

from backend.app.models.paper import Paper
from backend.app.services.source_verification import SourceVerificationService, normalize_doi


class RegistryClient:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    async def get(self, url, **kwargs):
        self.urls.append((url, kwargs))
        for prefix, response in self.responses.items():
            if prefix in url:
                return response
        return httpx.Response(404)


@pytest.mark.asyncio
async def test_verification_matches_bibliography_without_sending_document_content():
    crossref = httpx.Response(200, json={"message": {
        "DOI": "10.1000/ABC", "title": ["A Study of Retrieval"],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "published-print": {"date-parts": [[2024]]},
        "container-title": ["Journal of Computing"], "publisher": "Example Press",
    }})
    openalex = httpx.Response(200, json={
        "doi": "https://doi.org/10.1000/abc", "title": "A Study of Retrieval",
        "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
        "publication_year": 2024,
        "primary_location": {"source": {"display_name": "Journal of Computing"}},
        "open_access": {"is_oa": True, "oa_url": "https://example.org/paper"},
        "is_retracted": False,
    })
    client = RegistryClient({"api.crossref.org": crossref, "api.openalex.org": openalex})
    paper = Paper(id="p1", owner_id="u1", title="A Study of Retrieval", authors=["Ada Lovelace"],
                  publication_year=2024, doi="https://doi.org/10.1000/ABC", venue="Journal of Computing",
                  abstract="private abstract must not be sent")

    result = await SourceVerificationService(client).verify(paper)

    assert result["status"] == "VERIFIED METADATA"
    assert result["metadata_mismatches"] == []
    assert result["open_access"] is True
    assert "private abstract" not in str(client.urls)
    assert all("10.1000" in url for url, _ in client.urls)


@pytest.mark.asyncio
async def test_verification_reports_mismatches_and_never_calls_source_fake():
    client = RegistryClient({
        "api.crossref.org": httpx.Response(200, json={"message": {
            "title": ["Different Title"], "author": [{"family": "Other"}],
            "published": {"date-parts": [[2020]]},
            "update-to": [{"update-type": "retraction"}],
        }}),
        "api.openalex.org": httpx.Response(404),
    })
    paper = Paper(id="p1", owner_id="u1", title="Expected Title", authors=["Ada Lovelace"],
                  publication_year=2024, doi="10.1000/example")

    result = await SourceVerificationService(client).verify(paper)

    assert result["status"] == "RETRACTION/CORRECTION FLAG"
    assert set(result["metadata_mismatches"]) == {"title", "authors", "publication_year"}
    assert result["retraction_flag"] is True
    assert "fake" not in result.get("message", "").casefold()


def test_doi_normalization_rejects_non_doi_and_strips_resolver():
    assert normalize_doi(" https://doi.org/10.1234/AbC. ") == "10.1234/abc"
    assert normalize_doi("not a DOI") is None
