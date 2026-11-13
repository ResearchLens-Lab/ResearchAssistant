"use client";

import React, { useState, useEffect } from "react";
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
import { Pencil, AlertCircle, Loader2 } from "lucide-react";

export function EditPaperModal({
  isOpen,
  onClose,
  paper,
  onSubmit,
  isLoading = false,
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (paper && isOpen) {
      setTitle(paper.title || "");
      setDescription(paper.description || paper.abstract || "");
      setSubmitted(false);
      setFormError("");
      setIsSubmitting(false);
    }
  }, [paper, isOpen]);

  const handleClose = () => {
    if (!isSubmitting && !isLoading) {
      setSubmitted(false);
      setFormError("");
      onClose();
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitted(true);
    setFormError("");

    const trimmedTitle = title.trim();
    const trimmedDesc = description.trim();

    if (!trimmedTitle) {
      setFormError("Project title is required.");
      return;
    }
    if (!trimmedDesc) {
      setFormError("Project description is required.");
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit({
        id: paper.id,
        payload: {
          title: trimmedTitle,
          description: trimmedDesc,
        },
      });
      onClose();
    } catch (error) {
      setIsSubmitting(false);
      setFormError(error?.message || "Failed to update research project. Please try again.");
    }
  };

  const titleInvalid = submitted && !title.trim();
  const descInvalid = submitted && !description.trim();

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) handleClose(); }}>
      <DialogContent className="max-w-lg rounded-2xl border-zinc-200/90 bg-white p-6 shadow-[0_24px_64px_-16px_rgba(0,0,0,0.22)] font-serif dark:border-zinc-800 dark:bg-zinc-900">
        <DialogHeader className="space-y-1.5 pb-2 text-left">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-50 text-[var(--rl-primary)] shadow-2xs dark:bg-sky-950/50">
              <Pencil className="h-4.5 w-4.5" />
            </span>
            <DialogTitle className="text-xl font-bold tracking-tight text-zinc-900 font-serif dark:text-zinc-100">
              Edit project
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-zinc-500 leading-relaxed font-serif dark:text-zinc-400">
            Update your project title and literature scope description.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate className="space-y-4 py-2 font-serif">
          {formError && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
              <span className="leading-snug">{formError}</span>
            </div>
          )}

          {/* Project Title Field */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="edit-project-title" className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                Project title <span className="text-rose-500">*</span>
              </label>
              <span className="text-[10px] text-zinc-400 font-mono">
                {title.length}/500
              </span>
            </div>
            <Input
              id="edit-project-title"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (formError) setFormError("");
              }}
              placeholder="e.g. Cybersecurity Research"
              maxLength={500}
              autoFocus
              disabled={isSubmitting || isLoading}
              className={`h-9 text-xs bg-white font-serif dark:bg-zinc-850 ${
                titleInvalid ? "border-rose-400 focus-visible:ring-rose-400" : ""
              }`}
            />
            {titleInvalid && (
              <p className="text-[11px] text-rose-600 font-medium">Please enter a project title.</p>
            )}
          </div>

          {/* Project Description Field */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="edit-project-description" className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                Project description <span className="text-rose-500">*</span>
              </label>
              <span className="text-[10px] text-zinc-400 font-mono">
                {description.length}/2000
              </span>
            </div>
            <textarea
              id="edit-project-description"
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
                if (formError) setFormError("");
              }}
              placeholder="Describe the research topic, its purpose and what you want to explore..."
              rows={4}
              maxLength={2000}
              disabled={isSubmitting || isLoading}
              className={`w-full rounded-lg border border-zinc-200 bg-white p-3 text-xs leading-relaxed text-zinc-900 shadow-2xs outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 font-serif dark:border-zinc-800 dark:bg-zinc-850 dark:text-zinc-100 ${
                descInvalid ? "border-rose-400 focus:border-rose-400 focus:ring-rose-400" : ""
              }`}
            />
            {descInvalid ? (
              <p className="text-[11px] text-rose-600 font-medium">Please describe your research scope.</p>
            ) : (
              <p className="text-[11px] text-zinc-400">
                A clear description frames your literature scope and helps organize citations across papers.
              </p>
            )}
          </div>

          <DialogFooter className="gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isSubmitting || isLoading}
              className="h-9 px-4 text-xs font-semibold font-serif"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || isLoading}
              className="h-9 gap-1.5 px-5 text-xs font-semibold bg-[#1d6fc4] hover:bg-[#185ea8] text-white shadow-xs font-serif"
            >
              {isSubmitting || isLoading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Saving…</span>
                </>
              ) : (
                <span>Save changes</span>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

