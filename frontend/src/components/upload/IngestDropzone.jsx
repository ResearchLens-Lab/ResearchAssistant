"use client";

import React, { useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { papersService } from "@/services/papers.service";
import { documentsService } from "@/services/documents.service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { IngestPipelineVisualizer } from "./IngestPipelineVisualizer";
import { IngestConfigPanel } from "./IngestConfigPanel";
import {
  UploadCloud,
  FileText,
  AlertCircle,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export function IngestDropzone() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [authors, setAuthors] = useState("");
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [venue, setVenue] = useState("");
  const [abstract, setAbstract] = useState("");

  const [dragActive, setDragActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [ingestStatus, setIngestStatus] = useState(null);
  const [createdPaperId, setCreatedPaperId] = useState(null);
  const [chunkCount, setChunkCount] = useState(null);

  const handleFile = (selectedFile) => {
    setErrorMessage(null);
    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setErrorMessage("Only valid PDF files are supported.");
      return;
    }
    if (selectedFile.size > 25 * 1024 * 1024) {
      setErrorMessage("File exceeds the maximum allowed size of 25 MB.");
      return;
    }

    setFile(selectedFile);
    if (!title) {
      const cleanTitle = selectedFile.name.replace(/\.pdf$/i, "").replace(/[_-]/g, " ");
      setTitle(cleanTitle.charAt(0).toUpperCase() + cleanTitle.slice(1));
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const ingestMutation = useMutation({
    mutationFn: async () => {
      if (!file || !title.trim()) {
        throw new Error("Please provide a paper title and select a PDF file.");
      }

      setIngestStatus("processing");

      // 1. Create Paper record
      const authorsList = authors
        .split(",")
        .map((a) => a.trim())
        .filter(Boolean);

      const paper = await papersService.create({
        title: title.trim(),
        authors: authorsList.length > 0 ? authorsList : undefined,
        publication_year: year ? parseInt(year, 10) : undefined,
        venue: venue.trim() || undefined,
        abstract: abstract.trim() || undefined,
      });

      setCreatedPaperId(paper.id);

      // 2. Upload Document & Ingest to RAG
      const doc = await documentsService.upload(file, paper.id);
      setChunkCount(doc.chunk_count || null);
      setIngestStatus(doc.processing_status);

      return { paper, doc };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
    onError: (err) => {
      setIngestStatus("failed");
      setErrorMessage(err.message || "Failed to ingest paper into RAG vectorstore.");
    },
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-6 max-w-6xl mx-auto">
      {/* Left 2 Columns: Dropzone & Metadata */}
      <div className="lg:col-span-2 space-y-6">
        <div>
          <h2 className="text-base font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Ingest Research Paper
          </h2>
          <p className="text-xs text-zinc-500">
            Upload PDF papers. Academic sections, page ranges, and chunk embeddings will be automatically indexed.
          </p>
        </div>

        {/* Drag & Drop Canvas */}
        <div
          onDragEnter={() => setDragActive(true)}
          onDragLeave={() => setDragActive(false)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-colors ${
            dragActive
              ? "border-blue-600 bg-blue-50/50"
              : file
              ? "border-emerald-400 bg-emerald-50/20"
              : "border-zinc-300 bg-zinc-50/50 hover:border-zinc-400 hover:bg-zinc-100/50 dark:border-zinc-800 dark:bg-zinc-900"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) handleFile(e.target.files[0]);
            }}
          />

          {file ? (
            <div className="flex flex-col items-center space-y-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                <FileText className="h-5 w-5" />
              </div>
              <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                {file.name}
              </p>
              <p className="text-[11px] font-mono text-zinc-500">
                {(file.size / (1024 * 1024)).toFixed(2)} MB • Ready for section-aware ingestion
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-2 text-[11px] h-6"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
              >
                Change PDF
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                <UploadCloud className="h-5 w-5" />
              </div>
              <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                Drop PDF research papers here, or browse
              </p>
              <p className="text-[11px] text-zinc-400 font-mono">
                Supports PDF up to 25 MB • Text layer validated
              </p>
            </div>
          )}
        </div>

        {/* Paper Metadata Form */}
        <div className="rounded-lg border border-zinc-200 bg-white p-5 space-y-4 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Paper Metadata
          </h3>

          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-700">
              Paper Title <span className="text-red-500">*</span>
            </label>
            <Input
              placeholder="e.g. Attention Is All You Need"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-zinc-700">
                Authors (comma separated)
              </label>
              <Input
                placeholder="Ashish Vaswani, Noam Shazeer, ..."
                value={authors}
                onChange={(e) => setAuthors(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-zinc-700">
                  Year
                </label>
                <Input
                  type="number"
                  placeholder="2024"
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-medium text-zinc-700">
                  Venue
                </label>
                <Input
                  placeholder="NeurIPS, ICML..."
                  value={venue}
                  onChange={(e) => setVenue(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-medium text-zinc-700">
              Abstract (Optional excerpt)
            </label>
            <textarea
              rows={3}
              placeholder="Paste abstract here to enhance metadata search..."
              value={abstract}
              onChange={(e) => setAbstract(e.target.value)}
              className="w-full rounded-md border border-zinc-200 bg-white p-2.5 text-xs text-zinc-900 placeholder:text-zinc-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-900 dark:border-zinc-800 dark:bg-zinc-950"
            />
          </div>

          {errorMessage && (
            <div className="flex items-center gap-2 rounded-md bg-red-50 p-2.5 text-xs text-red-700 border border-red-200">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Action Trigger */}
          <div className="pt-2 flex items-center justify-between">
            <span className="text-[11px] text-zinc-400 font-mono">
              Creates paper record & indexes into ChromaDB
            </span>

            <Button
              type="button"
              variant="workbench"
              onClick={() => ingestMutation.mutate()}
              disabled={!file || !title.trim() || ingestMutation.isPending}
              className="gap-1.5 px-4"
            >
              {ingestMutation.isPending ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Ingesting to RAG...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Start RAG Ingestion</span>
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Live Ingestion Pipeline Result */}
        {ingestStatus && (
          <div className="space-y-3">
            <IngestPipelineVisualizer
              status={ingestStatus}
              filename={file?.name || "paper.pdf"}
              chunkCount={chunkCount}
              fileSize={file?.size}
              error={errorMessage}
            />

            {ingestStatus === "indexed" && createdPaperId && (
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm" asChild className="gap-1">
                  <Link href={`/papers/${createdPaperId}`}>
                    <span>Open in Reader</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </Button>

                <Button variant="workbench" size="sm" asChild className="gap-1">
                  <Link href={`/chat?paper_id=${createdPaperId}`}>
                    <span>Ask AI in Chat</span>
                  </Link>
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right 1 Column: RAG Configuration Inspector */}
      <div>
        <IngestConfigPanel />
      </div>
    </div>
  );
}
