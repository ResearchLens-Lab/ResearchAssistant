export function extractCitationTags(text) {
  if (!text) return [];
  const regex = /\[(S\d+)\]/g;
  const matches = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (!matches.includes(match[1])) {
      matches.push(match[1]);
    }
  }
  return matches;
}

export function parseTextWithCitations(text) {
  if (!text) return [];
  const regex = /\[(S\d+)\]/g;
  const segments = [];
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        type: "text",
        content: text.slice(lastIndex, match.index),
      });
    }
    segments.push({
      type: "citation",
      sourceId: match[1],
      raw: match[0],
    });
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push({
      type: "text",
      content: text.slice(lastIndex),
    });
  }

  return segments;
}
