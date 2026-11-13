import { parseResearchTimestamp, RESEARCH_TIME_ZONE } from "./researchTime.mjs";

export function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export function formatDate(dateString) {
  if (!dateString) return "";
  try {
    const d = parseResearchTimestamp(dateString);
    if (!d) return dateString;
    return new Intl.DateTimeFormat("en-US", {
      timeZone: RESEARCH_TIME_ZONE,
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(d);
  } catch {
    return dateString;
  }
}

export function formatScore(score) {
  if (score === undefined || score === null) return "--";
  return `${(score * 100).toFixed(0)}%`;
}

export function truncateText(text, maxLength = 120) {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trim()}...`;
}
