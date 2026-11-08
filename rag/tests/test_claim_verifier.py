from rag.research.claim_verifier import ClaimEvidenceVerifier
from rag.research.claim_verifier import LLMClaimJudge
from rag.retrieval.query import RetrievedSource


def source(source_id="S1", paper_id="p1", text="The model achieved 28.4 BLEU on English to German translation.", locator="page:4"):
    return RetrievedSource(source_id=source_id, chunk_id="chunk-1", paper_id=paper_id,
                          document_id="doc-1", page_start=4, page_end=4, locator=locator,
                          section="Results", text=text)


def test_supported_claim_keeps_valid_citation_and_locator():
    report = ClaimEvidenceVerifier().verify("The model achieved 28.4 BLEU on translation [S1].", [source()], ["p1"])
    item = report.items[0]
    assert item.status == "supported"
    assert item.evidence_ids == ["chunk-1"]
    assert item.source_ids == ["S1"]
    assert item.locators == ["page:4"]
    assert "[S1]" in report.verified_answer


def test_numeric_mismatch_is_not_retained_as_a_factual_claim():
    report = ClaimEvidenceVerifier().verify("The model achieved 31.2 BLEU on translation [S1].", [source()], ["p1"])
    assert report.items[0].status == "contradicted"
    assert "31.2" not in report.verified_answer


def test_claim_cited_to_other_paper_is_invalid_under_selected_scope():
    report = ClaimEvidenceVerifier().verify("The model achieved 28.4 BLEU on translation [S1].", [source(paper_id="other")], ["p1"])
    assert report.items[0].status == "invalid_reference"
    assert not report.verified_answer


def test_nonexistent_citation_and_uncited_claim_are_removed():
    answer = "The model achieved 28.4 BLEU on translation [S9].\nThe work used six layers in each encoder."
    report = ClaimEvidenceVerifier().verify(answer, [source()], ["p1"])
    assert [item.status for item in report.items] == ["invalid_reference", "unsupported"]
    assert not report.verified_answer


def test_real_source_that_does_not_establish_claim_is_removed():
    report = ClaimEvidenceVerifier().verify(
        "The clinical cohort received a weekly dosage schedule [S1].", [source()], ["p1"]
    )
    assert report.items[0].status == "unsupported"
    assert not report.verified_answer


def test_partial_lexical_support_is_explicitly_qualified():
    report = ClaimEvidenceVerifier().verify(
        "The model achieved BLEU using a novel auxiliary decoder design [S1].", [source()], ["p1"]
    )
    assert report.items[0].status == "partial"
    assert report.verified_answer.startswith("The available evidence partially supports")


def test_supported_claim_survives_beside_unsupported_claim():
    answer = "The model achieved 28.4 BLEU on translation [S1].\nThe clinical trial dosage was repeated weekly [S1]."
    report = ClaimEvidenceVerifier().verify(answer, [source()], ["p1"])
    assert [item.status for item in report.items] == ["supported", "unsupported"]
    assert "28.4 BLEU" in report.verified_answer
    assert "clinical trial dosage" not in report.verified_answer


def test_unanswerable_answer_with_no_claims_remains_empty():
    report = ClaimEvidenceVerifier().verify("The retrieved papers do not provide this information.", [], ["p1"])
    assert report.items[0].status == "unsupported"
    assert not report.verified_answer


def test_schema_checked_llm_judge_rejects_fabricated_evidence_ids():
    class FakeClient:
        def generate(self, *args, **kwargs):
            return '{"status":"supported","evidence_ids":["S999"],"reason":"looks supported"}'

    assert LLMClaimJudge(FakeClient()).judge("claim", [source()]) == "unsupported"


def test_schema_checked_llm_judge_requires_a_reference_for_support():
    class FakeClient:
        def generate(self, *args, **kwargs):
            return '{"status":"supported","evidence_ids":[],"reason":"supported"}'

    assert LLMClaimJudge(FakeClient()).judge("claim", [source()]) == "unsupported"


def test_semantic_judge_can_reject_a_valid_citation_that_does_not_support_claim():
    class FakeClient:
        def generate(self, system, prompt, **kwargs):
            assert "weekly clinical dosage" in prompt
            assert "28.4 BLEU" in prompt
            return '{"status":"unsupported","evidence_ids":["S1"],"reason":"The excerpt reports translation performance, not dosage."}'

    assert LLMClaimJudge(FakeClient()).judge("The paper reported a weekly clinical dosage.", [source()]) == "unsupported"


def test_locator_provenance_is_required():
    invalid = source(locator=None).model_copy(update={"document_id": "", "chunk_id": ""})
    report = ClaimEvidenceVerifier().verify("The model achieved 28.4 BLEU on translation [S1].", [invalid], ["p1"])
    assert report.items[0].status == "invalid_reference"
    assert not report.verified_answer


def test_fabricated_page_range_is_rejected():
    invalid = source().model_copy(update={"page_start": 9, "page_end": 4, "locator": None})
    report = ClaimEvidenceVerifier().verify("The model achieved 28.4 BLEU on translation [S1].", [invalid], ["p1"])
    assert report.items[0].status == "invalid_reference"
