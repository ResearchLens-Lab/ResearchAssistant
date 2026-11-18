import { parseResearchTimestamp, researchDayKey, shiftResearchDay } from "../utils/researchTime.mjs";

export function projectHref(paperId) {
  return `/papers/${encodeURIComponent(paperId)}`;
}

export function buildProjectCreatePayload(title = "", description = "") {
  const payload = { title: String(title).trim() };
  const trimmedDesc = String(description).trim();
  if (trimmedDesc) {
    payload.description = trimmedDesc;
  }
  return payload;
}

export function indexedPaperIds(entries = []) {
  return entries
    .filter(({ documents = [] }) => hasIndexedSources(documents))
    .map(({ paper }) => paper?.id)
    .filter(Boolean);
}

export function hasIndexedSources(documents = []) {
  return documents.some(
    (doc) => doc.processing_status === "indexed" || ((doc.processing_status === "needs_review" || doc.processing_status === "partial") && (doc.chunk_count || 0) > 0)
  );
}

export function togglePaperSelection(current = [], paperId) {
  if (!paperId) return current;
  const set = new Set(current);
  if (set.has(paperId)) set.delete(paperId);
  else set.add(paperId);
  return Array.from(set);
}

export function summarizeClaimChecks(metadata = {}) {
  const items = metadata?.claim_verification?.items || [];
  if (!items.length) {
    return { available: false, supported: 0, partial: 0, issues: 0 };
  }
  let supported = 0;
  let partial = 0;
  let issues = 0;
  for (const item of items) {
    if (item.status === "supported") supported += 1;
    else if (item.status === "partial") partial += 1;
    else issues += 1;
  }
  return { available: true, supported, partial, issues };
}

export function buildResearchBrief(messages = [], title = "Research Brief") {
  const lines = [`# ${title}`, ""];
  const sourceMap = new Map();

  for (const message of messages) {
    if (message.role === "user") {
      lines.push(`## Q: ${message.content.trim()}`, "");
    } else if (message.role === "assistant") {
      lines.push(message.content.trim(), "");
      for (const source of message.sources || []) {
        if (source.source_id && !sourceMap.has(source.source_id)) {
          sourceMap.set(source.source_id, source);
        }
      }
    }
  }

  if (sourceMap.size) {
    lines.push("## Cited Sources", "");
    for (const [id, source] of sourceMap.entries()) {
      const pageInfo = source.page_start ? ` (page ${source.page_start})` : "";
      lines.push(`- **[${id}]** ${source.filename || "Source"}${pageInfo}: ${source.text ? source.text.slice(0, 160) + "…" : ""}`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

export function parseComparisonMarkdown(raw = "") {
  if (!raw || !raw.includes("|")) return null;
  const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
  const tableLines = lines.filter((l) => l.startsWith("|") && l.endsWith("|"));
  if (tableLines.length < 2) return null;

  const parseRow = (line) => line.slice(1, -1).split("|").map((cell) => cell.trim());
  const headers = parseRow(tableLines[0]);
  const dataRows = tableLines.slice(2).map(parseRow);

  const nonTable = lines.filter((l) => !l.startsWith("|"));
  const synthesis = nonTable.join("\n\n").trim();

  return { headers, rows: dataRows, synthesis };
}

export function documentType(filename = "") {
  const ext = filename.split(".").pop()?.toUpperCase() || "";
  return ext || "DOCUMENT";
}

export function batchIngestStatus(documents = [], failures = []) {
  if (failures.length && !documents.length) return "failed";
  const isDocReady = (d) => d.processing_status === "indexed" || ((d.processing_status === "needs_review" || d.processing_status === "partial") && (d.chunk_count || 0) > 0);
  const allIndexed = documents.length > 0 && documents.every(isDocReady) && !failures.length;
  if (allIndexed) return "indexed";
  const anyProcessing = documents.some((d) => d.processing_status === "processing" || d.processing_status === "uploaded");
  if (anyProcessing) return "processing";
  if (documents.some(isDocReady)) return "partial";
  if (documents.some((d) => d.processing_status === "cancelled")) return "cancelled";
  return "failed";
}

export function isRetryableIngestionError(error = "") {
  return !/(OCR,?\s*which is not enabled|password-protected|does not appear to be a valid PDF|Unsupported document format|Invalid or unsafe ZIP archive|Unsafe archive|exceeds (?:the )?(?:maximum|upload|per-file|total))/i.test(error);
}

export const MAX_UPLOAD_FILE_SIZE_BYTES = 1024 * 1024 * 1024; // 1 GiB
export const MAX_UPLOAD_BATCH_SIZE_BYTES = 1024 * 1024 * 1024; // 1 GiB
export const MAX_UPLOAD_BATCH_FILES = 100;

export function validateUploadFiles(files = [], maxBytes = MAX_UPLOAD_FILE_SIZE_BYTES) {
  const supported = /\.(pdf|docx|txt|md|markdown|tex|csv|xlsx|pptx|html?|json|zip)$/i;
  if (files.some((file) => !supported.test(file.name || ""))) return "Supported formats: PDF, DOCX, TXT, Markdown, TeX, CSV, XLSX, PPTX, HTML, JSON, and ZIP.";
  if (files.some((file) => !file.size)) return "Empty files cannot be uploaded.";
  if (files.some((file) => file.size > maxBytes)) {
    const limitDisplay = maxBytes >= 1024 * 1024 * 1024
      ? `${(maxBytes / (1024 * 1024 * 1024)).toFixed(0)} GB`
      : `${Math.floor(maxBytes / (1024 * 1024))} MB`;
    return `Each file must be no larger than ${limitDisplay}.`;
  }
  if (files.length > MAX_UPLOAD_BATCH_FILES) return `Choose no more than ${MAX_UPLOAD_BATCH_FILES} files at a time.`;
  if (files.reduce((total, file) => total + file.size, 0) > MAX_UPLOAD_BATCH_SIZE_BYTES) {
    const batchLimitDisplay = MAX_UPLOAD_BATCH_SIZE_BYTES >= 1024 * 1024 * 1024
      ? `${(MAX_UPLOAD_BATCH_SIZE_BYTES / (1024 * 1024 * 1024)).toFixed(0)} GB`
      : `${Math.floor(MAX_UPLOAD_BATCH_SIZE_BYTES / (1024 * 1024))} MB`;
    return `The selected files exceed the ${batchLimitDisplay} total batch limit.`;
  }
  return null;
}

export function mergeUploadFiles(current = [], incoming = []) {
  const byIdentity = new Map(current.map((file) => [`${file.name}:${file.size}:${file.lastModified}`, file]));
  for (const file of incoming) byIdentity.set(`${file.name}:${file.size}:${file.lastModified}`, file);
  return [...byIdentity.values()];
}

export function formatUploadSize(bytes = 0) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function applyChatStreamEvent(message, event) {
  if (!message || !event) return message;

  const currentSummary = message.activity_summary || message.meta?.activity_summary || {};

  switch (event.type) {
    case "status":
      return {
        ...message,
        progress: event.data?.message || message.progress,
      };

    case "query_plan":
      return {
        ...message,
        activity_summary: {
          ...currentSummary,
          query_plan: event.data,
          concept: event.data?.primary_concept,
          intent: event.data?.intent,
          resolved_question: event.data?.resolved_question,
        },
      };

    case "retrieval_started":
      return {
        ...message,
        progress: `Searching indexed passages for '${event.data?.concept || "evidence"}'…`,
      };

    case "sources_found":
      return {
        ...message,
        progress: `Found ${event.data?.count || 0} relevant evidence passages…`,
      };

    case "evidence_batch": {
      const incomingSources = event.data?.sources || [];
      return {
        ...message,
        sources: incomingSources.length > 0 ? incomingSources : message.sources,
        progress: `Collected ${incomingSources.length} evidence passages…`,
      };
    }

    case "retrieval_summary":
      return {
        ...message,
        activity_summary: {
          ...currentSummary,
          retrieval_summary: event.data,
          documents_count: event.data?.documents_count,
          passages_count: event.data?.passages_count,
          confidence_tier: event.data?.confidence_tier,
          confidence_score: event.data?.confidence_score,
        },
        progress: `Selected ${event.data?.passages_count || 0} passages across ${event.data?.documents_count || 0} sources…`,
      };

    case "generation_started":
      return {
        ...message,
        progress: "Synthesizing answer with grounded citations…",
      };

    case "generation_fallback":
      return {
        ...message,
        progress: "Composing structured evidence-grounded synthesis…",
      };

    case "section_started":
      return {
        ...message,
        currentSection: event.data?.title || "",
        progress: `Writing: ${event.data?.title || "section"}…`,
      };

    case "content_delta":
    case "token": {
      const delta = event.data?.text || "";
      return {
        ...message,
        content: (message.content || "") + delta,
        provisional: true,
        progress: message.progress || "Drafting research response…",
      };
    }

    case "section_completed":
      return {
        ...message,
        progress: "Continuing synthesis…",
      };

    case "citation_update": {
      const newCitations = event.data?.citations || [];
      return {
        ...message,
        sources: newCitations.length > 0 ? newCitations : message.sources,
      };
    }

    case "completed": {
      const metadata = event.data?.metadata || {};
      const researchMeta = metadata.research || metadata.research_intelligence || {};
      const completedSummary = {
        ...currentSummary,
        concept: currentSummary.concept || researchMeta?.intent?.primary_concept,
        confidence_tier: metadata.confidence_tier || currentSummary.confidence_tier,
        confidence_score: metadata.confidence_score || currentSummary.confidence_score,
      };
      return {
        ...message,
        content: event.data?.answer || message.content || "",
        sources: event.data?.sources || message.sources || [],
        activity_summary: completedSummary,
        meta: {
          research: researchMeta,
          research_intelligence: metadata.research_intelligence || {},
          activity_summary: completedSummary,
          answer_mode: metadata.answer_mode,
          generation_reason: metadata.generation_reason,
          generation_provider: metadata.generation_provider,
          cache_hit: metadata.cache_hit,
          follow_up_suggestions: metadata.follow_up_suggestions || [],
          confidence_tier: metadata.confidence_tier,
          confidence_score: metadata.confidence_score,
          retrieval_summary: metadata.retrieval_summary,
          weak_matches: metadata.weak_matches || [],
          error_kind: metadata.error_kind,
        },
        progress: "Research complete",
        provisional: false,
        pending: false,
      };
    }

    default:
      return message;
  }
}


export function groupConversationsByDate(conversations = [], now = new Date()) {
  const todayItems = [];
  const yesterdayItems = [];
  const last7DaysItems = [];
  const olderItems = [];

  const today = researchDayKey(now);
  const yesterday = shiftResearchDay(today, -1);
  const startOf7Days = shiftResearchDay(today, -6);

  for (const conv of conversations) {
    const rawTime = conv.updated_at || conv.created_at;
    const date = parseResearchTimestamp(rawTime);
    const day = date ? researchDayKey(date) : "";
    if (day === today) {
      todayItems.push(conv);
    } else if (day === yesterday) {
      yesterdayItems.push(conv);
    } else if (day && day >= startOf7Days) {
      last7DaysItems.push(conv);
    } else {
      olderItems.push(conv);
    }
  }

  const groups = [];
  if (todayItems.length) groups.push({ label: "Today", items: todayItems });
  if (yesterdayItems.length) groups.push({ label: "Yesterday", items: yesterdayItems });
  if (last7DaysItems.length) groups.push({ label: "Previous 7 days", items: last7DaysItems });
  if (olderItems.length) groups.push({ label: "Older", items: olderItems });
  return groups;
}

export function formatRelativeTime(dateString, now = new Date()) {
  if (!dateString) return "";
  const date = new Date(dateString);
  const diffMs = now.getTime() - date.getTime();
  if (diffMs < 0 || isNaN(diffMs)) return "Just now";

  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "Just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay === 1) return "Yesterday";
  if (diffDay < 7) return `${diffDay}d ago`;

  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function filterConversations(conversations = [], query = "") {
  if (!query || !query.trim()) return conversations;
  const q = query.trim().toLowerCase();
  return conversations.filter((c) => (c.title || "Untitled research").toLowerCase().includes(q));
}

export function aggregateConversationSources(messages = []) {
  const map = new Map();
  for (const msg of messages) {
    if (msg.role === "assistant" && Array.isArray(msg.sources)) {
      for (const src of msg.sources) {
        const key = src.chunk_id || `${src.document_id || src.paper_id || src.filename}:${src.page_start || src.page || ""}:${src.page_end || ""}:${src.source_id || ""}`;
        if (!map.has(key)) {
          map.set(key, src);
        }
      }
    }
  }
  return Array.from(map.values());
}
