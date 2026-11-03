"use client";

import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Loader2 } from "lucide-react";

const DELETION_STAGES = [
  { threshold: 20, label: "Locating project documents and indices..." },
  { threshold: 50, label: "Removing vector embeddings from ChromaDB..." },
  { threshold: 80, label: "Cleaning lexical search index..." },
  { threshold: 95, label: "Unlinking stored files and metadata..." },
  { threshold: 100, label: "Completing deletion..." },
];

export function DeletePaperDialog({
  isOpen,
  onClose,
  onConfirm,
  isLoading,
}) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let interval = null;
    if (isLoading) {
      setProgress(15);
      interval = window.setInterval(() => {
        setProgress((prev) => {
          if (prev < 35) return prev + 12;
          if (prev < 65) return prev + 8;
          if (prev < 88) return prev + 4;
          if (prev < 95) return prev + 1;
          return prev;
        });
      }, 350);
    } else {
      setProgress(0);
    }
    return () => {
      if (interval) window.clearInterval(interval);
    };
  }, [isLoading]);

  const currentStage = DELETION_STAGES.find((s) => progress <= s.threshold) || DELETION_STAGES[DELETION_STAGES.length - 1];

  // SVG Circular progress constants
  const size = 56;
  const strokeWidth = 4;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!isLoading) onClose(open); }}>
      <DialogContent className="max-w-sm">
        <DialogHeader className="space-y-3">
          <div className="mx-auto flex items-center justify-center">
            {isLoading ? (
              <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
                <svg
                  width={size}
                  height={size}
                  className="rotate-[-90deg] transition-all duration-300"
                >
                  {/* Background Track */}
                  <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    className="text-red-100"
                    fill="transparent"
                  />
                  {/* Progress Indicator */}
                  <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    className="text-red-600 transition-all duration-300 ease-out"
                    fill="transparent"
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                  />
                </svg>
                {/* Center Percentage Display */}
                <span className="absolute font-mono text-xs font-semibold text-red-600">
                  {progress}%
                </span>
              </div>
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-red-600">
                <AlertTriangle className="h-5 w-5" />
              </div>
            )}
          </div>

          <DialogTitle className="text-center text-base font-semibold">
            {isLoading ? "Deleting Research Project" : "Delete Research Paper"}
          </DialogTitle>

          <DialogDescription className="text-center text-xs text-zinc-600">
            {isLoading ? (
              <span className="inline-block animate-pulse font-medium text-zinc-700">
                {currentStage.label}
              </span>
            ) : (
              "This action will permanently delete this paper metadata, all attached PDF documents, and remove indexed vector chunks from ChromaDB."
            )}
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="mt-4 flex sm:justify-between gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={onConfirm}
            disabled={isLoading}
            className="flex-1 gap-1.5"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Deleting ({progress}%)</span>
              </>
            ) : (
              "Delete Permanently"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
