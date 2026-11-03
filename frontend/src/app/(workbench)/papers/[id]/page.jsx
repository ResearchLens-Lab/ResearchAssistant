"use client";

import React, { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { usePaperDetails } from "@/hooks/usePapers";
import { useCitationStore } from "@/store/citationStore";
import { PaperMetadataHeader } from "@/components/reader/PaperMetadataHeader";
import { GroundedSummaryCard } from "@/components/reader/GroundedSummaryCard";
import { DocumentAttachmentsList } from "@/components/reader/DocumentAttachmentsList";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { Button } from "@/components/ui/button";
import { ChevronLeft, AlertCircle } from "lucide-react";
import Link from "next/link";
import { hasIndexedSources } from "@/lib/researchWorkspace.mjs";

export default function PaperDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const paperId = params.id;

  const {
    paper,
    isLoading,
    isError,
    error,
    documents,
    isLoadingDocuments,
    isDocumentsError,
    documentsError,
    refetchDocuments,
    summarize,
    summaryData,
    isSummarizing,
    summaryError,
  } = usePaperDetails(paperId);

  const { setSources, openDrawer, isDrawerOpen, closeDrawer } = useCitationStore();
  const evidenceAvailable = hasIndexedSources(documents);
  const currentSummary = summaryData?.paper_id === paperId ? summaryData : null;

  useEffect(() => {
    setSources(currentSummary?.sources || []);
  }, [currentSummary, setSources]);

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 max-w-6xl mx-auto">
        <div className="h-6 w-32 rounded bg-zinc-200 animate-pulse" />
        <div className="h-40 rounded-lg bg-zinc-200 animate-pulse" />
        <div className="h-64 rounded-lg bg-zinc-200 animate-pulse" />
      </div>
    );
  }

  if (isError || !paper) {
    return (
      <div className="flex h-96 flex-col items-center justify-center p-8 text-center space-y-3">
        <AlertCircle className="h-8 w-8 text-red-500" />
        <h3 className="text-sm font-bold text-zinc-900">Paper not found</h3>
        <p className="text-xs text-zinc-500">
          {error?.message || "You may not have permission to view this paper."}
        </p>
        <Button variant="outline" size="sm" asChild>
          <Link href="/papers">← Back to Paper Library</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="relative flex h-[calc(100dvh-4rem)] w-full overflow-hidden bg-[var(--rl-canvas)]">
      {/* Left / Center Reading Room Canvas */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild className="h-7 px-2 text-xs gap-1">
            <Link href="/papers">
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Back to Library</span>
            </Link>
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="workbench" size="sm" disabled={!evidenceAvailable || isLoadingDocuments || isDocumentsError} title={isDocumentsError ? "Retry loading project sources" : !evidenceAvailable ? "Add and index a source before asking a grounded question" : undefined} onClick={() => router.push(`/chat?paper_id=${paperId}`)}>Ask in Research Desk</Button>
          <Button variant="soft" size="sm" asChild><Link href={`/papers/upload?paper_id=${paperId}`}>Add sources</Link></Button>
          <Button variant="outline" size="sm" disabled={!evidenceAvailable || isLoadingDocuments || isDocumentsError} title={isDocumentsError ? "Project source status could not be loaded" : !evidenceAvailable ? "Add and index a source to inspect evidence" : undefined} onClick={() => { setSources(currentSummary?.sources || []); openDrawer(); }}>View Evidence Trail</Button>
          {!evidenceAvailable && !isLoadingDocuments && !isDocumentsError && <span className="self-center text-xs text-slate-500">Add and index a source to inspect evidence</span>}
          {isDocumentsError && <span role="alert" className="self-center text-xs text-rose-700">Could not load source status. Retry below.</span>}
        </div>

        {/* Paper Header Metadata */}
        <PaperMetadataHeader paper={paper} />

        {/* RAG Grounded Summary */}
        <GroundedSummaryCard
          summary={currentSummary}
          isLoading={isSummarizing}
          onGenerate={summarize}
          error={summaryError}
          hasIndexedSources={evidenceAvailable}
          isCheckingSources={isLoadingDocuments}
          isSourceError={isDocumentsError}
        />

        {/* Document Attachments */}
        <DocumentAttachmentsList
          documents={documents}
          isLoading={isLoadingDocuments}
          isError={isDocumentsError}
          error={documentsError}
          onRetry={refetchDocuments}
        />
      </div>

      {/* Right Evidence Inspector */}
      {isDrawerOpen && <div role="dialog" aria-modal="true" aria-label="Evidence Trail" className="fixed inset-x-0 bottom-0 top-16 z-40 flex justify-end bg-slate-950/35" onClick={closeDrawer} onKeyDown={(event) => { if (event.key === "Escape") closeDrawer(); }}><div className="h-full w-[min(26rem,94vw)] shadow-xl" onClick={(event) => event.stopPropagation()}><SourceInspectorRail onClose={closeDrawer} /></div></div>}
    </div>
  );
}
