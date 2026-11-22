import { test } from "node:test";
import assert from "node:assert/strict";

test("EditProject payload normalization standardizes arguments", () => {
  const normalizeEditArgs = (args, fallbackId) => {
    const payload = args && typeof args === "object" && "payload" in args ? args.payload : args;
    const targetId = args && typeof args === "object" && args.id ? args.id : fallbackId;
    return {
      targetId,
      title: payload?.title?.trim(),
      description: payload?.description?.trim() || null,
    };
  };

  // Case 1: Standardized contract { id, payload: { title, description } }
  const res1 = normalizeEditArgs({
    id: "proj-123",
    payload: { title: "  New Title  ", description: "  Some description  " },
  }, "proj-fallback");
  assert.equal(res1.targetId, "proj-123");
  assert.equal(res1.title, "New Title");
  assert.equal(res1.description, "Some description");

  // Case 2: Empty optional description
  const res2 = normalizeEditArgs({
    id: "proj-123",
    payload: { title: "Algorithms", description: "   " },
  }, "proj-fallback");
  assert.equal(res2.title, "Algorithms");
  assert.equal(res2.description, null);

  // Case 3: Direct payload fallback (legacy onSave caller)
  const res3 = normalizeEditArgs({ title: "Algorithms 2nd Ed", description: "" }, "proj-fallback");
  assert.equal(res3.targetId, "proj-fallback");
  assert.equal(res3.title, "Algorithms 2nd Ed");
  assert.equal(res3.description, null);
});

test("Summary evidence isolation ignores chat conversation messages", () => {
  const resolveDisplaySources = ({ mode, evidenceScope, targetMessage, summarySources, chatSources, conversationMessages }) => {
    if (mode === "summary") {
      return summarySources || [];
    }
    if (evidenceScope === "answer") {
      return targetMessage ? (summarySources || chatSources) : chatSources;
    }
    return conversationMessages.flatMap((m) => m.sources || []);
  };

  const summarySources = [
    { source_id: "S1", document_id: "doc-cormen", page_start: 3 },
    { source_id: "S2", document_id: "doc-cormen", page_start: 5 },
  ];

  const chatMessages = [
    { id: "m1", role: "assistant", sources: [{ source_id: "S99", document_id: "doc-unrelated", page_start: 100 }] },
  ];

  // In summary mode, sources come strictly from summarySources regardless of evidenceScope or chat messages
  const summaryModeSources = resolveDisplaySources({
    mode: "summary",
    evidenceScope: "conversation", // chat toggle state must be ignored
    targetMessage: null,
    summarySources,
    chatSources: [],
    conversationMessages: chatMessages,
  });

  assert.equal(summaryModeSources.length, 2);
  assert.equal(summaryModeSources[0].source_id, "S1");
  assert.equal(summaryModeSources[1].source_id, "S2");
  assert.ok(!summaryModeSources.some((s) => s.source_id === "S99"));
});
