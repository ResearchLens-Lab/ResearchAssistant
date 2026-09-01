"use client";

import React, { useState } from "react";
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

export function CreatePaperModal({
  isOpen,
  onClose,
  onSubmit,
  isLoading,
}) {
  const [title, setTitle] = useState("");
  const [authors, setAuthors] = useState("");
  const [year, setYear] = useState("");
  const [venue, setVenue] = useState("");
  const [doi, setDoi] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [abstract, setAbstract] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    const authorsList = authors
      .split(",")
      .map((a) => a.trim())
      .filter(Boolean);

    await onSubmit({
      title: title.trim(),
      authors: authorsList.length > 0 ? authorsList : undefined,
      publication_year: year ? parseInt(year, 10) : undefined,
      venue: venue.trim() || undefined,
      doi: doi.trim() || undefined,
      source_url: sourceUrl.trim() || undefined,
      abstract: abstract.trim() || undefined,
    });

    onClose();
    setTitle("");
    setAuthors("");
    setAbstract("");
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add Research Paper Record</DialogTitle>
          <DialogDescription>
            Enter publication metadata. You can attach the PDF document next.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3 py-2">
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-700">
              Title <span className="text-red-500">*</span>
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Deep Residual Learning for Image Recognition"
              required
            />
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-700">
              Authors (comma separated)
            </label>
            <Input
              value={authors}
              onChange={(e) => setAuthors(e.target.value)}
              placeholder="Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-zinc-700">Year</label>
              <Input
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                placeholder="2016"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-medium text-zinc-700">Venue</label>
              <Input
                value={venue}
                onChange={(e) => setVenue(e.target.value)}
                placeholder="CVPR"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-700">DOI / URL</label>
            <Input
              value={doi}
              onChange={(e) => setDoi(e.target.value)}
              placeholder="10.1109/CVPR.2016.90"
            />
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-700">Abstract</label>
            <textarea
              rows={3}
              value={abstract}
              onChange={(e) => setAbstract(e.target.value)}
              placeholder="Paper abstract..."
              className="w-full rounded-md border border-zinc-200 bg-white p-2 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-900"
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
              {isLoading ? "Saving..." : "Create Paper Record"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
