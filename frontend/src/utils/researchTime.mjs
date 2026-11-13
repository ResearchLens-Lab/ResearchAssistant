export const RESEARCH_TIME_ZONE = "Asia/Kolkata";

export function parseResearchTimestamp(value) {
  if (!value) return null;
  const raw = value instanceof Date ? value.toISOString() : String(value);
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw);
  const date = new Date(hasZone ? raw : `${raw}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function researchDayKey(value) {
  const date = parseResearchTimestamp(value);
  if (!date) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: RESEARCH_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const fields = Object.fromEntries(parts.map(({ type, value: part }) => [type, part]));
  return `${fields.year}-${fields.month}-${fields.day}`;
}

export function shiftResearchDay(dayKey, days) {
  const date = new Date(`${dayKey}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function formatResearchTimestamp(value, {
  todayPrefix = "Today",
  yesterdayPrefix = "Yesterday",
} = {}) {
  const date = parseResearchTimestamp(value);
  if (!date) return "";

  const today = researchDayKey(new Date());
  const day = researchDayKey(date);
  const time = new Intl.DateTimeFormat("en-US", {
    timeZone: RESEARCH_TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
  if (day === today) return todayPrefix ? `${todayPrefix}, ${time}` : time;
  if (day === shiftResearchDay(today, -1)) return yesterdayPrefix ? `${yesterdayPrefix}, ${time}` : time;
  const dateLabel = new Intl.DateTimeFormat("en-US", {
    timeZone: RESEARCH_TIME_ZONE,
    month: "short",
    day: "numeric",
  }).format(date);
  return `${dateLabel}, ${time}`;
}
