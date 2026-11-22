"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function Error({ error, reset }) {
  useEffect(() => {
    console.error("Application workbench error:", error);
    // Auto-recover from chunk loading and stale asset mismatches (e.g. after restart on dynamic port)
    const isChunkOrNetwork =
      /Loading chunk .* failed/i.test(error?.message || "") ||
      error?.name === "ChunkLoadError" ||
      /failed to fetch/i.test(error?.message || "");

    if (isChunkOrNetwork) {
      const lastReload = sessionStorage.getItem("rl_chunk_reload_ts");
      const now = Date.now();
      if (!lastReload || now - parseInt(lastReload, 10) > 8000) {
        sessionStorage.setItem("rl_chunk_reload_ts", String(now));
        window.location.reload();
      }
    }
  }, [error]);

  const handleReload = () => {
    try {
      sessionStorage.removeItem("rl_chunk_reload_ts");
    } catch {}
    window.location.reload();
  };

  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center bg-zinc-50 p-4 text-center space-y-4 font-sans">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <h2 className="text-base font-bold text-zinc-900">
          Something went wrong in the workbench
        </h2>
        <p className="text-xs text-zinc-500 max-w-sm">
          {error?.message || "An unexpected error occurred during rendering."}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => reset()} className="text-xs">
          Try Again
        </Button>
        <Button variant="workbench" size="sm" onClick={handleReload} className="text-xs gap-1.5">
          <RefreshCw className="h-3 w-3" />
          <span>Reload Workbench</span>
        </Button>
      </div>
    </div>
  );
}

