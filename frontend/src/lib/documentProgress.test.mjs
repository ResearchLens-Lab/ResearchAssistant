import test from "node:test";
import assert from "node:assert/strict";
import {
  formatElapsedSeconds,
  formatRemainingSeconds,
  formatCountdown,
  calculateSmoothedETA,
  getDocumentProgressModel,
  parseUtcTimestamp,
} from "./documentProgress.mjs";

test("document progress exposes the persisted stage and estimated percentage", () => {
  const model = getDocumentProgressModel({
    processing_status: "processing",
    processing_stage: "generating_embeddings",
    processing_progress: 47,
    processing_progress_type: "estimated",
    processing_completed_units: 64,
    processing_total_units: 160,
  });
  assert.equal(model.label, "Generating embeddings");
  assert.equal(model.progress, 47);
  assert.equal(model.progressLabel, "estimated");
  assert.equal(model.chunkDetail, "64 of 160 chunks indexed");
  assert.equal(model.isActive, true);
});

test("ready and failed sources never appear as active and percentages are bounded", () => {
  assert.equal(getDocumentProgressModel({ processing_status: "indexed", processing_progress: 55 }).progress, 100);
  const failed = getDocumentProgressModel({ processing_status: "failed", processing_progress: 140 });
  assert.equal(failed.progress, 99);
  assert.equal(failed.isFailed, true);
  assert.equal(failed.isActive, false);
});

test("elapsed time stays readable for short and long jobs", () => {
  assert.equal(formatElapsedSeconds(9), "9s");
  assert.equal(formatElapsedSeconds(83), "1m 23s");
});

test("countdown formatting counts down clearly with left suffix", () => {
  assert.equal(formatCountdown(2), "wrapping up...");
  assert.equal(formatCountdown(45), "~45s left");
  assert.equal(formatCountdown(75), "~1m 15s left");
  assert.equal(formatCountdown(300), "~5m left");
});

test("calculateSmoothedETA provides countdownText and etaText", () => {
  const eta = calculateSmoothedETA({
    progress: 50,
    completedUnits: 50,
    totalUnits: 100,
    elapsedSeconds: 50,
  });
  assert.equal(eta.countdownText, "~50s left");
  assert.equal(eta.etaText, "About 50s remaining");
  assert.equal(eta.secondsRemaining, 50);
});

test("parseUtcTimestamp handles naive ISO strings, Z-suffixed ISO strings, and invalid inputs", () => {
  assert.equal(parseUtcTimestamp(null), null);
  assert.equal(parseUtcTimestamp(""), null);

  // Both naive ISO string and explicit Z ISO string parse to the exact same UTC epoch timestamp
  const naive = parseUtcTimestamp("2026-11-03T12:00:00");
  const explicit = parseUtcTimestamp("2026-11-03T12:00:00Z");
  assert.equal(naive, explicit);
  assert.equal(new Date(naive).toISOString(), "2026-11-03T12:00:00.000Z");
});
