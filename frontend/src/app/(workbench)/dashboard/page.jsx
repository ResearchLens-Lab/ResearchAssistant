"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { documentsService } from "@/services/documents.service";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  FileText,
  CheckCircle2,
  XCircle,
  Layers,
  Cpu,
  Search,
  UploadCloud,
  HardDrive,
  ShieldCheck,
  ArrowRight,
  Database,
  Terminal,
} from "lucide-react";

export default function DashboardPage() {
  const { data: overview, isLoading, isError, refetch } = useQuery({
    queryKey: ["systemOverview"],
    queryFn: () => documentsService.getSystemOverview(),
    refetchInterval: 10_000,
    retry: 1,
  });

  const metrics = overview?.metrics || {
    total_documents: 0,
    completed_ingestion_jobs: 0,
    failed_jobs: 0,
    total_indexed_chunks: 0,
  };

  const rag = overview?.rag || {
    mode: "local",
    retrieval_mode: "hybrid",
    embedding_provider: "fastembed",
    embedding_model: "BAAI/bge-small-en-v1.5",
    embedding_dimension: 384,
    llm_enabled: false,
    llm_provider: "local",
  };

  const limits = overview?.limits || {
    max_upload_file_mb: 1024,
    max_upload_batch_mb: 1024,
  };

  return (
    <div className="page-shell space-y-8 py-6">
      {/* Header section */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-zinc-200/80 pb-5 dark:border-zinc-800">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              System Overview & RAG Diagnostics
            </h1>
            <Badge variant="outline" className="border-emerald-500/40 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 font-mono text-xs">
              <span className="mr-1.5 h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              LOCAL-FIRST ACTIVE
            </Badge>
          </div>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Independent, locally-grounded research intelligence engine operating without external paid APIs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href="/papers">
              <FileText className="mr-1.5 h-4 w-4" />
              Document Library
            </Link>
          </Button>
          <Button variant="workbench" size="sm" asChild>
            <Link href="/papers/upload">
              <UploadCloud className="mr-1.5 h-4 w-4" />
              Upload Sources
            </Link>
          </Button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Documents */}
        <Card className="border-zinc-200/80 shadow-sm dark:border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
              Total Documents
            </CardTitle>
            <FileText className="h-4 w-4 text-zinc-400" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
                {metrics.total_documents}
              </div>
            )}
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              Registered across research projects
            </p>
          </CardContent>
        </Card>

        {/* Completed Ingestion Jobs */}
        <Card className="border-zinc-200/80 shadow-sm dark:border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
              Completed Ingestions
            </CardTitle>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                {metrics.completed_ingestion_jobs}
              </div>
            )}
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              Indexed in Chroma & SQLite FTS5
            </p>
          </CardContent>
        </Card>

        {/* Total Indexed Chunks */}
        <Card className="border-zinc-200/80 shadow-sm dark:border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
              Total Indexed Chunks
            </CardTitle>
            <Layers className="h-4 w-4 text-sky-500" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-sky-600 dark:text-sky-400 font-mono">
                {metrics.total_indexed_chunks}
              </div>
            )}
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              Section-aware & page-tracked
            </p>
          </CardContent>
        </Card>

        {/* Failed Jobs */}
        <Card className="border-zinc-200/80 shadow-sm dark:border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
              Failed Jobs
            </CardTitle>
            <XCircle className="h-4 w-4 text-rose-500" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
                {metrics.failed_jobs}
              </div>
            )}
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              {metrics.failed_jobs > 0 ? "Retry available from document library" : "All ingested documents healthy"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Architecture & Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: RAG Configuration */}
        <Card className="lg:col-span-2 border-zinc-200/80 shadow-sm dark:border-zinc-800">
          <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-[var(--rl-primary)]" />
                  Active RAG Engine & Model Configuration
                </CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  Parameters governing local embedding, vector storage, and extractive answers
                </CardDescription>
              </div>
              <Badge variant="secondary" className="font-mono text-xs">
                {rag.mode?.toUpperCase()} MODE
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-lg border border-zinc-200/60 bg-zinc-50/50 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/50 space-y-1">
                <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase">Embedding Model</span>
                <p className="text-sm font-semibold font-mono text-zinc-800 dark:text-zinc-200">{rag.embedding_model}</p>
                <p className="text-xs text-zinc-500">Dimensions: {rag.embedding_dimension} · FastEmbed ONNX (CPU)</p>
              </div>

              <div className="rounded-lg border border-zinc-200/60 bg-zinc-50/50 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/50 space-y-1">
                <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase">Retrieval Strategy</span>
                <p className="text-sm font-semibold font-mono text-zinc-800 dark:text-zinc-200 capitalize">{rag.retrieval_mode} Retrieval</p>
                <p className="text-xs text-zinc-500">Dense vectors + SQLite FTS5 BM25 with RRF</p>
              </div>

              <div className="rounded-lg border border-zinc-200/60 bg-zinc-50/50 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/50 space-y-1">
                <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase">Generation Mode</span>
                <p className="text-sm font-semibold font-mono text-zinc-800 dark:text-zinc-200">
                  {rag.llm_enabled ? "Local Synthesis Engine" : "Extractive Grounded Answers"}
                </p>
                <p className="text-xs text-zinc-500">
                  {rag.llm_enabled ? "Local synthesis enabled with extractive fallback" : "Zero hallucination · 100% extractive with page citations"}
                </p>
              </div>

              <div className="rounded-lg border border-zinc-200/60 bg-zinc-50/50 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/50 space-y-1">
                <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase">Upload Capacities</span>
                <p className="text-sm font-semibold font-mono text-zinc-800 dark:text-zinc-200">
                  {limits.max_upload_batch_mb} MB Batch / {limits.max_upload_file_mb} MB File
                </p>
                <p className="text-xs text-zinc-500">Streaming disk uploads · Multi-file supported</p>
              </div>
            </div>

            <div className="rounded-lg bg-sky-50/60 border border-sky-100 p-3 text-xs text-sky-900 dark:bg-sky-950/20 dark:border-sky-900/40 dark:text-sky-300 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold">
                <ShieldCheck className="h-4 w-4 text-sky-600 dark:text-sky-400" />
                No-API-Key Local Guarantee
              </div>
              <p>
                This application is fully autonomous. Document parsing, chunking, local ONNX embeddings, BM25 keyword matching, vector search, reciprocal rank fusion, and extractive answer generation function locally with zero external network calls or fees.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Right Column: Storage & System Controls */}
        <Card className="border-zinc-200/80 shadow-sm dark:border-zinc-800 flex flex-col justify-between">
          <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
            <CardTitle className="text-base font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <Database className="h-4 w-4 text-[var(--rl-primary)]" />
              Storage & Data Stores
            </CardTitle>
            <CardDescription className="text-xs mt-0.5">
              Dual persistent indexing stores
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4 space-y-4 flex-1">
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
                <span className="text-zinc-500">Vector Store</span>
                <span className="font-semibold text-zinc-800 dark:text-zinc-200">ChromaDB (.chroma)</span>
              </div>
              <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
                <span className="text-zinc-500">Lexical Index</span>
                <span className="font-semibold text-zinc-800 dark:text-zinc-200">SQLite FTS5 (BM25)</span>
              </div>
              <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
                <span className="text-zinc-500">Relational Database</span>
                <span className="font-semibold text-zinc-800 dark:text-zinc-200">PostgreSQL (Alembic 0004)</span>
              </div>
              <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
                <span className="text-zinc-500">Embedding Cache</span>
                <span className="font-semibold text-zinc-800 dark:text-zinc-200">SQLite Vector Cache</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">Supported Formats</span>
                <span className="font-semibold text-zinc-800 dark:text-zinc-200">PDF, DOCX, XLSX, PPTX, CSV, TXT, MD, HTML</span>
              </div>
            </div>

            <div className="pt-4 border-t border-zinc-100 dark:border-zinc-800 space-y-2">
              <Button variant="default" size="sm" asChild className="w-full justify-between">
                <Link href="/search">
                  Open Research Chat
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
