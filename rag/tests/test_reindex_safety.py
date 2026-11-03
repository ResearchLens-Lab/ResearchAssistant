import pytest

from scripts.reindex_documents import build_parser, build_selection


def test_reindex_cli_requires_explicit_document_scope():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_reindex_cli_defaults_to_dry_run_and_supports_explicit_scopes():
    parser = build_parser()
    one_document = parser.parse_args(["--document-id", "doc-1", "--dry-run"])
    all_documents = parser.parse_args(["--all", "--apply"])

    assert one_document.apply is False
    assert one_document.document_ids == ["doc-1"]
    assert one_document.dry_run is True
    assert all_documents.all is True
    assert all_documents.apply is True


def test_reindex_stale_resume_has_a_bounded_minimum_age():
    with pytest.raises(ValueError, match="at least 60"):
        build_selection(["doc-1"], False, True, 30)

    clauses, cutoff = build_selection(["doc-1"], False, True, 900)
    assert len(clauses) == 2
    assert cutoff is not None
