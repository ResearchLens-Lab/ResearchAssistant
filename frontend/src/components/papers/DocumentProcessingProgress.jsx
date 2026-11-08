"use client";

import { useEffect, useState } from "react";
import {
  formatElapsedSeconds,
  getDocumentProgressModel,
  calculateSmoothedETA,
  parseUtcTimestamp,
} from "@/lib/documentProgress.mjs";

export function DocumentProcessingProgress({ document, compact = false }) {
  const model = getDocumentProgressModel(document);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!model.isActive) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [model.isActive]);

  const started = parseUtcTimestamp(document?.processing_started_at);
  const finished = parseUtcTimestamp(document?.processing_heartbeat_at);
  const elapsed = started ? Math.max(0, Math.floor(((model.isActive ? now : finished || now) - started) / 1000)) : 0;

  const completed = Number(document?.processing_completed_units || 0);
  const total = Number(document?.processing_total_units || 0);

  const eta = model.isActive
    ? calculateSmoothedETA({
        progress: model.progress,
        completedUnits: completed,
        totalUnits: total,
        elapsedSeconds: elapsed,
      })
    : null;

  return (
    <div className={compact ? "space-y-1.5" : "space-y-2"}>
      <div className="flex items-center justify-between gap-2 text-[11px]">
        <span className="font-medium capitalize text-slate-700">{model.label}</span>
        <span className="shrink-0 tabular-nums text-slate-500">
          {model.isActive ? (
            <>
              <span className="font-semibold text-sky-700">{model.progress}%</span>
              <span className="text-slate-500 ml-1.5 font-normal">
                · {eta?.countdownText || "estimating..."}
              </span>
            </>
          ) : model.isComplete ? (
            <span className="text-emerald-700 font-medium">100% · Done in {formatElapsedSeconds(elapsed)}</span>
          ) : model.isCancelled ? (
            <span className="text-amber-700 font-medium">Cancelled</span>
          ) : (
            <span className="text-rose-700 font-medium">Failed</span>
          )}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={`${document?.filename || "Source"}: ${model.label}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={model.progress}
        className="h-2 overflow-hidden rounded-full bg-sky-100"
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ease-out ${
            model.isFailed
              ? "bg-rose-500"
              : model.isCancelled
              ? "bg-amber-400"
              : model.isComplete
              ? "bg-emerald-500"
              : "bg-sky-500"
          }`}
          style={{ width: `${model.isCancelled ? 100 : model.progress}%` }}
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-2 text-[10px] text-slate-500">
        <span>
          {model.progressLabel} progress
          {elapsed > 0 && <span className="text-slate-400 ml-1">· elapsed {formatElapsedSeconds(elapsed)}</span>}
        </span>
        {model.workDetail && <span>{model.workDetail}</span>}
      </div>
      {eta?.etaText && !compact && model.isActive && (
        <div className="text-[10px] text-sky-600 font-medium text-right">
          {eta.etaText}
        </div>
      )}
    </div>
  );
}
