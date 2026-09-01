"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

export default function Error({ error, reset }) {
  useEffect(() => {
    console.error("Application runtime error:", error);
  }, [error]);

  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center bg-zinc-50 p-4 text-center space-y-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-red-100 text-red-600">
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
      <Button variant="workbench" size="sm" onClick={() => reset()}>
        Try Again
      </Button>
    </div>
  );
}
