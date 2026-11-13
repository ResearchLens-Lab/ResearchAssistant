export function getSourceIdentity(source) {
  if (!source) return "";
  if (source.chunk_id) return `chunk:${source.chunk_id}`;
  const documentKey = source.document_id || source.paper_id || source.filename || "source";
  return `${documentKey}:${source.page_start || source.page || ""}:${source.page_end || ""}:${source.source_id || ""}`;
}
