const TAG = /\[(S\d+)\]/g;

export function buildCitationIndex(content, sources = []) {
  const order = [];
  for (const m of String(content || "").matchAll(TAG)) if (!order.includes(m[1])) order.push(m[1]);
  const numberById = new Map(order.map((id, i) => [id, i + 1]));
  const byId = new Map((sources || []).map((s) => [s.source_id, s]));
  const cited = order.map((id) => byId.get(id)).filter(Boolean);
  const docs = new Set(cited.map((s) => s.document_id || s.paper_id || s.filename).filter(Boolean));
  return { numberById, cited, citedCount: cited.length, documentCount: docs.size };
}

export function formatPages(source) {
  const a = source?.page_start ?? source?.page;
  const b = source?.page_end;
  if (a == null) return "";
  return b != null && b !== a ? `pp. ${a}–${b}` : `p. ${a}`;
}

export function plausibleHeading(text) {
  const t = String(text || "").trim();
  return t && t.length <= 70 && t.split(/\s+/).length <= 10 ? t : "";
}

export function stripSourceLines(content) { // stopgap until the composer stops emitting them
  return String(content || "")
    .replace(/[ \t]*[_*]{1,2}Source:[^\n]*$/gim, "")
    .replace(/^[ \t]*Source:[^\n]*\n?/gim, "")
    .replace(/\n+#{2,4}\s*Confidence Assessment[\s\S]*?(?=\n#{1,4}\s|$)/i, "");
}

export function getSourceIdentity(source) {
  if (!source) return "";
  if (source.chunk_id) return `chunk:${source.chunk_id}`;
  const documentKey = source.document_id || source.paper_id || source.filename || "source";
  return `${documentKey}:${source.page_start || source.page || ""}:${source.page_end || ""}:${source.source_id || ""}`;
}

export function filterSourcesByScopedAnswer(message, fallbackSources = []) {
  if (!message) return [];
  const sources = (message.sources && message.sources.length > 0) ? message.sources : fallbackSources;
  const { cited } = buildCitationIndex(message.content, sources);
  const citedKeys = new Set(cited.map((s) => getSourceIdentity(s)).filter(Boolean));
  return sources.filter((s) => citedKeys.has(getSourceIdentity(s)));
}

