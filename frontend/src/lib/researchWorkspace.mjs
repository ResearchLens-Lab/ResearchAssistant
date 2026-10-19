export function parseComparisonMarkdown(markdown = "") {
  const lines = markdown.split(/\r?\n/);
  const tableStart = lines.findIndex((line, index) => line.includes("|") && lines[index + 1]?.match(/^\s*\|?\s*:?-{3,}/));
  if (tableStart < 0) return null;
  const cells = (line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
  const headers = cells(lines[tableStart]);
  const rows = [];
  let index = tableStart + 2;
  for (; index < lines.length && lines[index].includes("|"); index += 1) {
    const values = cells(lines[index]);
    if (values.length === headers.length) rows.push(values);
  }
  return { headers, rows, synthesis: lines.slice(index).join("\n").trim() };
}

export function summarizeClaimChecks(research = {}) {
  const items = research?.claim_verification?.items || [];
  if (!items.length) return { available: false, supported: 0, partial: 0, issues: 0 };
  return {
    available: true,
    supported: items.filter((item) => item.status === "supported").length,
    partial: items.filter((item) => item.status === "partial").length,
    issues: items.filter((item) => ["unsupported", "invalid_reference", "contradicted"].includes(item.status)).length,
  };
}

export function buildResearchBrief(messages = [], title = "Research brief") {
  const assistantMessages = messages.filter((message) => message.role === "assistant" && message.content?.trim());
  const sections = [`# ${title || "Research brief"}`, "", `Generated from ${assistantMessages.length} saved research response${assistantMessages.length === 1 ? "" : "s"}.`, ""];
  const sourceMap = new Map();
  for (const message of assistantMessages) {
    const answer = message.content.trim();
    const question = messages
      .slice(0, messages.indexOf(message))
      .reverse()
      .find((candidate) => candidate.role === "user")?.content?.trim();
    sections.push(`## Research question\n\n${question || "Question not available"}`, `## Findings\n\n${answer}`);
    const research = message.meta?.research;
    if (research?.sufficiency?.status && research.sufficiency.status !== "adequate") {
      sections.push(`_Evidence coverage: ${research.sufficiency.status}. This response may not cover every part of the question._`);
    }
    const checks = summarizeClaimChecks(research);
    if (checks.available) {
      sections.push(`**Claim review:** ${checks.supported} supported, ${checks.partial} partial, ${checks.issues} needing review. ${research.claim_verification.method?.includes("heuristic") ? "The configured check is lexical/numeric and does not establish semantic entailment." : "Provider-based support checks are fallible."}`);
    }
    for (const source of message.sources || []) {
      const id = source.source_id || source.chunk_id;
      if (id) sourceMap.set(id, source);
    }
  }
  if (sourceMap.size) {
    sections.push("## Sources");
    for (const [id, source] of sourceMap) {
      const locator = source.locator || (source.page_start ? `page ${source.page_start}${source.page_end && source.page_end !== source.page_start ? `–${source.page_end}` : ""}` : "locator not provided");
      sections.push(`- **[${id}] ${source.filename || source.title || "Source document"}** — ${locator}${source.section ? `, ${source.section}` : ""}${source.text ? `\n  > ${source.text.trim().replace(/\s+/g, " ")}` : ""}`);
    }
  }
  return `${sections.join("\n\n").trim()}\n`;
}

export function documentType(filename = "") {
  const extension = filename.split(".").pop()?.toUpperCase();
  return extension && extension !== filename.toUpperCase() ? extension : "FILE";
}

export function indexedPaperIds(entries = []) {
  return entries.filter(({ documents = [] }) => documents.some((document) => document.processing_status === "indexed")).map(({ paper }) => paper.id);
}

export function togglePaperSelection(selectedIds = [], paperId) {
  return selectedIds.includes(paperId) ? selectedIds.filter((id) => id !== paperId) : [...selectedIds, paperId];
}

export function batchIngestStatus(documents = [], failures = []) {
  const indexed = documents.filter((document) => document.processing_status === "indexed").length;
  if (documents.length > 0 && indexed === documents.length && failures.length === 0) return "indexed";
  if (indexed > 0) return "partial";
  return "failed";
}

export function validateUploadFiles(files = [], maxBytes = 25 * 1024 * 1024) {
  const supported = /\.(pdf|docx|txt|md|markdown|csv|xlsx|pptx|html?|json|zip)$/i;
  if (files.some((file) => !supported.test(file.name || ""))) return "Supported formats: PDF, DOCX, TXT, Markdown, CSV, HTML, JSON, and ZIP.";
  if (files.some((file) => file.size > maxBytes)) return "Each file must be no larger than 25 MB.";
  return null;
}

export function applyChatStreamEvent(message, event) {
  if (event.type === "token") return { ...message, content: message.content + (event.data?.text || ""), progress: "Draft answer · checking evidence…", provisional: true };
  if (event.type === "completed") return { ...message, content: event.data?.answer || "", sources: event.data?.sources || [], meta: { research: event.data?.metadata?.research || {} }, progress: "Saved answer · evidence check complete", provisional: false };
  return message;
}
