"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { buildProjectCreatePayload } from "@/lib/researchWorkspace.mjs";

export function CreatePaperModal({
  isOpen,
  onClose,
  onSubmit,
  isLoading,
}) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [formError, setFormError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    setFormError("");
    try {
      const created = await onSubmit(buildProjectCreatePayload(title));
      onClose();
      setTitle("");
      if (created?.id) router.push(`/papers/${created.id}`);
    } catch (error) {
      setFormError(error.message || "The research project could not be created.");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open && !isLoading) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
        <DialogTitle>Create a research project</DialogTitle>
          <DialogDescription>
            Add a title now. You can attach source documents to this project next.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3 py-2">
          {formError && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{formError}</p>}
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-700">
              Project title <span className="text-red-500">*</span>
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Algorithms"
              maxLength={500}
              required
            />
          </div>


          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="workbench"
              disabled={!title.trim() || isLoading}
            >
              {isLoading ? "Creating…" : "Create project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
