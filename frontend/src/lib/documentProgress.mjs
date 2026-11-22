const STAGE_LABELS = {
  uploaded: "Queued for processing",
  uploading: "Uploading",
  inspecting: "Inspecting document",
  extracting_text: "Extracting text",
  ocr_processing: "OCR processing",
  structuring: "Recovering structure",
  chunking: "Creating passages",
  generating_embeddings: "Generating embeddings",
  indexing: "Building search index",
  ready: "Document indexed",
  indexed: "Document indexed",
  partial: "Partially indexed",
  needs_review: "Needs review",
  failed: "Failed",
  cancelled: "Cancelled",
  processing: "Processing",
  validating: "Validating",
  queued: "Queued",
};

export function parseUtcTimestamp(ts) {
  if (!ts) return null;
  const str = String(ts).trim();
  if (!str) return null;
  // If no timezone offset (Z or +/-HH:MM) is present, treat as UTC by appending Z.
  // This prevents browser local timezone interpretation (e.g. UTC+5:30 adding 330 minutes).
  const hasTz = str.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(str);
  const parsed = Date.parse(hasTz ? str : `${str}Z`);
  return Number.isFinite(parsed) ? parsed : null;
}

export function getDocumentProgressModel(document) {
  const status = document?.processing_status || "uploaded";
  const stage = document?.processing_stage || status;
  let progress = Math.max(0, Math.min(100, Number(document?.processing_progress) || 0));
  
  const isIndexedLike = status === "indexed" || ((status === "needs_review" || status === "partial") && (document?.chunk_count || 0) > 0);
  // CRITICAL: Only show 100% when actually indexed
  if (isIndexedLike) {
    progress = 100;
  } else if (status === "cancelled" || status === "failed") {
    // Cap failed/cancelled at 99% to show incomplete
    progress = Math.min(progress, 99);
  } else {
    // For processing states, never reach 100% until indexed
    progress = Math.min(progress, 99);
  }

  const rawCompleted = Number(document?.processing_completed_units);
  const total = Number(document?.processing_total_units);
  const completed = Number.isFinite(rawCompleted) && Number.isFinite(total) && total > 0
    ? Math.min(rawCompleted, total)
    : rawCompleted;

  const chunkDetail = Number.isFinite(completed) && Number.isFinite(total) && total > 0
    ? `${completed} of ${total} ${document?.processing_unit === "pages" ? "pages read" : "chunks indexed"}`
    : null;

  let workDetail = chunkDetail;
  if (Number.isFinite(completed) && Number.isFinite(total) && total > 0) {
    if (stage === "ocr_processing") {
      workDetail = `Extracting scanned pages — ${completed} / ${total}`;
    } else if (stage === "extracting_text" || document?.processing_unit === "pages") {
      workDetail = `${completed} of ${total} pages extracted`;
    } else if (stage === "structuring") {
      workDetail = "Recovering chapters and sections...";
    } else if (stage === "chunking") {
      workDetail = "Creating searchable research passages...";
    } else if (stage === "indexing" || document?.processing_unit === "chunks") {
      workDetail = `${completed} of ${total} passages indexed`;
    }
  }

  let label = STAGE_LABELS[stage] || STAGE_LABELS[status] || (status === "cancelled" ? "Cancelled" : "Processing");
  if (stage === "ocr_processing" && Number.isFinite(completed) && Number.isFinite(total) && total > 0) {
    label = `Extracting scanned pages (${completed}/${total})`;
  } else if (stage === "structuring") {
    label = "Recovering chapters and sections";
  } else if (stage === "chunking") {
    label = "Creating searchable passages";
  } else if (stage === "indexing") {
    label = "Building local search index";
  }

  return {
    status,
    stage,
    label,
    progress,
    progressLabel: document?.processing_progress_type === "estimated" ? "estimated" : "measured",
    workDetail,
    chunkDetail,
    isActive: status === "processing" || status === "uploaded" || status === "validating" || status === "queued",
    isFailed: status === "failed",
    isCancelled: status === "cancelled",
    isComplete: status === "indexed" || status === "partial" || status === "needs_review",
  };
}

export function formatElapsedSeconds(seconds) {
  const safe = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return minutes ? `${minutes}m ${String(remainder).padStart(2, "0")}s` : `${remainder}s`;
}

export function formatRemainingSeconds(seconds) {
  const safe = Math.max(0, Math.round(Number(seconds) || 0));
  if (safe < 5) return "A few seconds remaining";
  if (safe < 60) return `About ${safe}s remaining`;
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  if (minutes < 5 && remainder > 10) {
    return `About ${minutes}m ${remainder}s remaining`;
  }
  return `About ${minutes}m remaining`;
}

export function formatCountdown(seconds) {
  const safe = Math.max(0, Math.round(Number(seconds) || 0));
  if (safe <= 2) return "wrapping up...";
  if (safe < 60) return `~${safe}s left`;
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  if (remainder > 5 && minutes < 5) {
    return `~${minutes}m ${remainder}s left`;
  }
  return `~${minutes}m left`;
}

export function calculateSmoothedETA({ progress, completedUnits, totalUnits, elapsedSeconds }) {
  // If not enough observation time or progress has occurred, avoid absurd small-sample estimates
  if (!elapsedSeconds || elapsedSeconds < 3 || !progress || progress < 5) {
    return { etaText: "Calculating remaining time...", countdownText: "estimating...", secondsRemaining: null };
  }

  // In early startup stages (progress <= 10% and few units processed), linear extrapolation is invalid
  if (progress <= 10 && (!completedUnits || completedUnits < 5)) {
    return { etaText: "Calculating remaining time...", countdownText: "estimating...", secondsRemaining: null };
  }

  // If already at completion boundary
  if (progress >= 99) {
    return { etaText: "Wrapping up...", countdownText: "wrapping up...", secondsRemaining: 2 };
  }

  let remainingSecs = null;

  // Prefer unit-based throughput rate if at least 5 units processed
  if (
    Number.isFinite(completedUnits) &&
    Number.isFinite(totalUnits) &&
    totalUnits > 0 &&
    completedUnits >= 5 &&
    completedUnits < totalUnits
  ) {
    const rate = completedUnits / elapsedSeconds;
    if (rate > 0) {
      remainingSecs = (totalUnits - completedUnits) / rate;
    }
  }

  // Fallback to progress-percentage extrapolation only when progress has genuinely advanced
  if (remainingSecs === null || remainingSecs < 0) {
    if (progress > 10) {
      remainingSecs = (elapsedSeconds / (progress / 100)) - elapsedSeconds;
    }
  }

  // Reject invalid or absurd estimates (> 15 minutes for local document ingestion)
  if (!Number.isFinite(remainingSecs) || remainingSecs <= 0 || remainingSecs > 900) {
    return { etaText: "Calculating remaining time...", countdownText: "estimating...", secondsRemaining: null };
  }

  return {
    etaText: formatRemainingSeconds(remainingSecs),
    countdownText: formatCountdown(remainingSecs),
    secondsRemaining: Math.round(remainingSecs),
  };
}
