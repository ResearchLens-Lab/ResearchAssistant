import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildCitationIndex,
  formatPages,
  plausibleHeading,
  stripSourceLines,
  filterSourcesByScopedAnswer,
} from "./citationNumbering.mjs";

test("numbering follows first appearance", () => {
  const content = "First [S2], then [S1], then [S2] again and finally [S3].";
  const sources = [
    { source_id: "S1", filename: "doc1.pdf" },
    { source_id: "S2", filename: "doc2.pdf" },
    { source_id: "S3", filename: "doc3.pdf" },
  ];
  const { numberById, cited, citedCount, documentCount } = buildCitationIndex(content, sources);
  assert.equal(numberById.get("S2"), 1);
  assert.equal(numberById.get("S1"), 2);
  assert.equal(numberById.get("S3"), 3);
  assert.equal(citedCount, 3);
  assert.equal(documentCount, 3);
  assert.deepEqual(cited.map((s) => s.source_id), ["S2", "S1", "S3"]);
});

test("a tag with no matching source is excluded from cited", () => {
  const content = "Mentions [S1] and missing [S99].";
  const sources = [{ source_id: "S1", filename: "doc1.pdf" }];
  const { numberById, cited, citedCount, documentCount } = buildCitationIndex(content, sources);
  assert.equal(numberById.get("S1"), 1);
  assert.equal(numberById.get("S99"), 2);
  assert.equal(citedCount, 1);
  assert.equal(documentCount, 1);
  assert.deepEqual(cited.map((s) => s.source_id), ["S1"]);
});

test("formatPages for 25, 25-26 and missing", () => {
  assert.equal(formatPages({ page: 25 }), "p. 25");
  assert.equal(formatPages({ page_start: 25, page_end: 25 }), "p. 25");
  assert.equal(formatPages({ page_start: 25, page_end: 26 }), "pp. 25–26");
  assert.equal(formatPages({}), "");
  assert.equal(formatPages(null), "");
});

test("plausibleHeading rejects long tutorial sentence and accepts Introduction", () => {
  const longSentence = "Part I: All the chapters in Part I and the Appendices are written with a tutorial";
  assert.equal(plausibleHeading(longSentence), "");
  assert.equal(plausibleHeading("Introduction"), "Introduction");
});

test("buildCitationIndex returns all keys used by MessageItem without undefined", () => {
  const content = "Test [S1] passage.";
  const sources = [{ source_id: "S1", filename: "doc.pdf" }];
  const { numberById, cited, citedCount, documentCount } = buildCitationIndex(content, sources);
  assert.notEqual(numberById, undefined);
  assert.notEqual(cited, undefined);
  assert.notEqual(citedCount, undefined);
  assert.notEqual(documentCount, undefined);
  assert.equal(citedCount, 1);
  assert.equal(documentCount, 1);
});

test("stripSourceLines removes Source: lines and Confidence Assessment block", () => {
  const fixture = `### Direct Answer: No Formal Definition Found
The selected documents discuss 'divide and conquer' in context, but do not contain a canonical formal definition.

### Contextual Mentions from Retrieved Passages
> "CHAPTER 3.: DIVIDE-AND-CONQUER
Figure 3.6 Convex hull: an example
(1) obtain the vertices of the convex hull (these vertices are also called ez-
treme points), and (2) obtain the vertices of the conve" [S1]

*Source: Algorithms, CHAPTER 3.: DIVIDE-AND-CONQUER · p.202*

### Related Context
- Here is a simple algorithm for obtaining the extreme points of a given set S of points in the plane. [S1]
- To check whether a particular point p € S is extreme, look at each possible triplet of points and see whether p lies in the triangle formed by these three points. [S1]
- If p lies in any such triangle, it is not extreme; otherwise it is. [S1]

### Confidence Assessment
- **Confidence Tier:** PARTIAL (45%)
- **Notice:** No definitive subject-copula definition was established in the indexed text.

Evidence state: **PARTIAL** — Top retrieval score: 4.77; Mentions of 'divide and conquer' exist, but no definition sentences match.`;

  const stripped = stripSourceLines(fixture);
  assert.equal(stripped.includes("Source:"), false);
  assert.equal(stripped.includes("Confidence"), false);
  assert.equal(stripped.includes("%"), false);
  const s1Matches = stripped.match(/\[S1\]/g);
  assert.equal(s1Matches?.length, 4);
});

test("filterSourcesByScopedAnswer filters by getSourceIdentity of cited sources", () => {
  const sources = [
    { source_id: "S1", filename: "cormen.pdf", page: 51 },
    { source_id: "S2", filename: "cormen.pdf", page: 100 },
    { source_id: "S3", filename: "horowitz.pdf", page: 202 },
  ];
  const message1 = {
    content: "Divide and conquer divides the problem [S1] and combines [S3].",
    sources,
  };
  const filtered = filterSourcesByScopedAnswer(message1, sources);
  assert.equal(filtered.length, 2);
  assert.deepEqual(filtered.map((s) => s.source_id), ["S1", "S3"]);

  const emptyMsg = { content: "No citations here.", sources };
  assert.equal(filterSourcesByScopedAnswer(emptyMsg, sources).length, 0);
  assert.equal(filterSourcesByScopedAnswer(null, sources).length, 0);
});


