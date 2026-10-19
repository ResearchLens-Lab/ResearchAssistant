import test from "node:test";
import assert from "node:assert/strict";
import { applyChatStreamEvent, batchIngestStatus, buildResearchBrief, documentType, indexedPaperIds, parseComparisonMarkdown, summarizeClaimChecks, togglePaperSelection, validateUploadFiles } from "./researchWorkspace.mjs";

test("comparison parser preserves generated citations and synthesis", () => {
  const parsed = parseComparisonMarkdown("| Paper | Finding |\n|---|---|\n| A | 12% [S1] |\n\nDifferent settings explain the values.");
  assert.deepEqual(parsed.headers, ["Paper", "Finding"]);
  assert.deepEqual(parsed.rows, [["A", "12% [S1]"]]);
  assert.match(parsed.synthesis, /Different settings/);
});

test("comparison parser falls back when response has no matrix", () => {
  assert.equal(parseComparisonMarkdown("Insufficient evidence."), null);
});

test("brief export includes saved questions, answers, evidence IDs and locators", () => {
  const brief = buildResearchBrief([
    { role: "user", content: "What was measured?" },
    { role: "assistant", content: "Accuracy was 91% [S1].", sources: [{ source_id: "S1", filename: "study.pdf", page_start: 4, text: "Accuracy was 91%." }] },
  ], "Test brief");
  assert.match(brief, /What was measured\?/);
  assert.match(brief, /91% \[S1\]/);
  assert.match(brief, /study\.pdf.*page 4/);
});

test("claim status is not inferred from citation identity", () => {
  assert.equal(summarizeClaimChecks({}).available, false);
  assert.deepEqual(summarizeClaimChecks({ claim_verification: { items: [{ status: "supported" }, { status: "partial" }, { status: "contradicted" }] } }),
    { available: true, supported: 1, partial: 1, issues: 1 });
});

test("document type is derived from the actual filename", () => {
  assert.equal(documentType("methods.csv"), "CSV");
});

test("multiple file upload accepts supported files and ZIP but rejects invalid batches", () => {
  assert.equal(validateUploadFiles([{ name: "paper.pdf", size: 10 }, { name: "appendix.zip", size: 20 }]), null);
  assert.match(validateUploadFiles([{ name: "notes.exe", size: 10 }]), /Supported formats/);
  assert.match(validateUploadFiles([{ name: "paper.pdf", size: 26 * 1024 * 1024 }]), /25 MB/);
});

test("batch status reflects per-file server outcomes including ZIP expansion", () => {
  assert.equal(batchIngestStatus([{ processing_status: "indexed" }, { processing_status: "indexed" }], []), "indexed");
  assert.equal(batchIngestStatus([{ processing_status: "indexed" }, { processing_status: "failed" }], [{ filename: "bad.csv" }]), "partial");
  assert.equal(batchIngestStatus([], [{ filename: "bad.zip" }]), "failed");
});

test("source scope selection includes only papers with indexed documents", () => {
  const entries = [
    { paper: { id: "ready" }, documents: [{ processing_status: "indexed" }] },
    { paper: { id: "pending" }, documents: [{ processing_status: "processing" }] },
  ];
  assert.deepEqual(indexedPaperIds(entries), ["ready"]);
  assert.deepEqual(togglePaperSelection(["ready"], "pending"), ["ready", "pending"]);
  assert.deepEqual(togglePaperSelection(["ready", "pending"], "ready"), ["pending"]);
});

test("streamed draft is replaced by the authoritative final persisted answer", () => {
  const draft = applyChatStreamEvent({ content: "", sources: [] }, { type: "token", data: { text: "provisional " } });
  assert.equal(draft.content, "provisional ");
  assert.equal(draft.provisional, true);
  const final = applyChatStreamEvent(draft, { type: "completed", data: { answer: "accepted [S1]", sources: [{ source_id: "S1" }], metadata: { research: { claim_verification: {} } } } });
  assert.equal(final.content, "accepted [S1]");
  assert.equal(final.provisional, false);
  assert.equal(final.sources[0].source_id, "S1");
});
