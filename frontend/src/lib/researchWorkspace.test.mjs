import test from "node:test";
import assert from "node:assert/strict";
import { aggregateConversationSources, applyChatStreamEvent, filterConversations, formatRelativeTime, groupConversationsByDate, batchIngestStatus, buildProjectCreatePayload, buildResearchBrief, documentType, formatUploadSize, hasIndexedSources, indexedPaperIds, isRetryableIngestionError, mergeUploadFiles, parseComparisonMarkdown, projectHref, summarizeClaimChecks, togglePaperSelection, validateUploadFiles } from "./researchWorkspace.mjs";

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

test("creating a project sends only its trimmed title and uses the returned id for its route", () => {
  assert.deepEqual(buildProjectCreatePayload("  Algorithms  "), { title: "Algorithms" });
  assert.equal(projectHref("project id"), "/papers/project%20id");
});

test("indexed source availability ignores uploaded, processing and failed files", () => {
  assert.equal(hasIndexedSources([{ processing_status: "uploaded" }, { processing_status: "processing" }, { processing_status: "failed" }]), false);
  assert.equal(hasIndexedSources([{ processing_status: "indexed" }]), true);
});

test("upload validation allows files up to 100 MB and rejects unsupported or oversized files", () => {
  assert.equal(validateUploadFiles([{ name: "paper.pdf", size: 10 }, { name: "appendix.zip", size: 20 }]), null);
  assert.match(validateUploadFiles([{ name: "notes.exe", size: 10 }]), /Supported formats/);
  assert.match(validateUploadFiles([{ name: "empty.txt", size: 0 }]), /Empty files/);
  assert.equal(validateUploadFiles([{ name: "paper.pdf", size: 100 * 1024 * 1024 }], 100 * 1024 * 1024), null);
  assert.match(validateUploadFiles([{ name: "paper.pdf", size: 101 * 1024 * 1024 }], 100 * 1024 * 1024), /100 MB/);
  assert.match(validateUploadFiles([{ name: "paper.pdf", size: 400 * 1024 * 1024 }, { name: "notes.txt", size: 101 * 1024 * 1024 }], 100 * 1024 * 1024), /100 MB/);
  assert.equal(validateUploadFiles([{ name: "large.pdf", size: 1024 * 1024 * 1024 }]), null);
  assert.match(validateUploadFiles([{ name: "large.pdf", size: 1024 * 1024 * 1024 + 1 }]), /1 GB/);
});

test("upload queue merges newly selected files, avoids duplicate selections and formats sizes", () => {
  const first = { name: "one.pdf", size: 1536, lastModified: 1 };
  const second = { name: "two.md", size: 1024 * 1024, lastModified: 2 };
  const queue = mergeUploadFiles([first], [first, second]);
  assert.deepEqual(queue, [first, second]);
  assert.equal(formatUploadSize(second.size), "1.0 MB");
  assert.equal(formatUploadSize(first.size), "2 KB");
});

test("batch status reflects per-file server outcomes including ZIP expansion", () => {
  assert.equal(batchIngestStatus([{ processing_status: "indexed" }, { processing_status: "indexed" }], []), "indexed");
  assert.equal(batchIngestStatus([{ processing_status: "indexed" }, { processing_status: "failed" }], [{ filename: "bad.csv" }]), "partial");
  assert.equal(batchIngestStatus([], [{ filename: "bad.zip" }]), "failed");
});

test("OCR-unavailable and permanent file errors do not offer pointless retries", () => {
  assert.equal(isRetryableIngestionError("PDF contains no extractable text; scanned PDFs require OCR, which is not enabled."), false);
  assert.equal(isRetryableIngestionError("PDF is password-protected and cannot be opened without a password."), false);
  assert.equal(isRetryableIngestionError("The RAG service timed out."), true);
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
  const final = applyChatStreamEvent(draft, { type: "completed", data: { answer: "accepted [S1]", sources: [{ source_id: "S1" }], metadata: { answer_mode: "evidence_fallback", generation_reason: "quota_exhausted", generation_provider: "gemini", research: { claim_verification: {} } } } });
  assert.equal(final.content, "accepted [S1]");
  assert.equal(final.provisional, false);
  assert.equal(final.sources[0].source_id, "S1");
  assert.equal(final.meta.answer_mode, "evidence_fallback");
  assert.equal(final.meta.generation_reason, "quota_exhausted");
});

test("groupConversationsByDate groups sessions into Today, Yesterday, Previous 7 days, and Older", () => {
  const base = new Date("2026-11-03T18:00:00Z");
  const conversations = [
    { id: "1", title: "Today Conv", updated_at: "2026-11-03T14:00:00Z" },
    { id: "2", title: "Yesterday Conv", updated_at: "2026-11-02T10:00:00Z" },
    { id: "3", title: "5 Days Ago Conv", updated_at: "2026-10-29T10:00:00Z" },
    { id: "4", title: "Older Conv", updated_at: "2026-10-15T10:00:00Z" },
  ];
  const groups = groupConversationsByDate(conversations, base);
  assert.equal(groups.length, 4);
  assert.equal(groups[0].label, "Today");
  assert.equal(groups[0].items[0].id, "1");
  assert.equal(groups[1].label, "Yesterday");
  assert.equal(groups[1].items[0].id, "2");
  assert.equal(groups[2].label, "Previous 7 days");
  assert.equal(groups[2].items[0].id, "3");
  assert.equal(groups[3].label, "Older");
  assert.equal(groups[3].items[0].id, "4");
});

test("formatRelativeTime formats elapsed minutes, hours, days, and older dates accurately", () => {
  const base = new Date("2026-11-03T18:00:00Z");
  assert.equal(formatRelativeTime("2026-11-03T17:59:30Z", base), "Just now");
  assert.equal(formatRelativeTime("2026-11-03T17:45:00Z", base), "15m ago");
  assert.equal(formatRelativeTime("2026-11-03T15:00:00Z", base), "3h ago");
  assert.equal(formatRelativeTime("2026-11-02T15:00:00Z", base), "Yesterday");
  assert.equal(formatRelativeTime("2026-10-31T15:00:00Z", base), "3d ago");
});

test("filterConversations filters conversation titles case-insensitively", () => {
  const convs = [
    { id: "1", title: "Neural Attention Mechanism" },
    { id: "2", title: "Quantum Computing Algorithms" },
    { id: "3", title: "Distributed Consensus" },
  ];
  assert.equal(filterConversations(convs, "neural").length, 1);
  assert.equal(filterConversations(convs, "ALGO").length, 1);
  assert.equal(filterConversations(convs, "").length, 3);
});

test("aggregateConversationSources deduplicates sources across multi-turn assistant messages", () => {
  const messages = [
    { role: "user", content: "Q1" },
    { role: "assistant", sources: [{ source_id: "S1", chunk_id: "c1", filename: "book.pdf" }] },
    { role: "user", content: "Q2" },
    { role: "assistant", sources: [
      { source_id: "S1", chunk_id: "c1", filename: "book.pdf" },
      { source_id: "S2", chunk_id: "c2", filename: "paper.pdf" },
    ] },
  ];
  const aggregated = aggregateConversationSources(messages);
  assert.equal(aggregated.length, 2);
  assert.deepEqual(aggregated.map((s) => s.source_id), ["S1", "S2"]);
});

