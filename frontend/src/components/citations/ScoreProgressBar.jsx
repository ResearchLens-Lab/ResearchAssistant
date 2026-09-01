import React from "react";
import { cn } from "@/utils/cn";

export function ScoreProgressBar({ score, className }) {
  const percentage = score !== undefined && score !== null ? Math.round(score * 100) : 0;

  return (
    <div className={cn("flex items-center gap-2 text-[11px] font-mono", className)}>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        <div
          className="h-full bg-blue-600 transition-all duration-300 rounded-full"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-zinc-500 font-semibold shrink-0">
        {score !== null && score !== undefined ? score.toFixed(2) : "--"}
      </span>
    </div>
  );
}
