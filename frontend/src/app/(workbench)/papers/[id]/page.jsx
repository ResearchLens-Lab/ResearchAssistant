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
    summarize,
    summaryData,
    isSummarizing,
    summaryError,
    uploadDocument,
    isUploadingDocument,
  } = usePaperDetails(paperId);

  const { setSources } = useCitationStore();

  useEffect(() => {
    if (summaryData?.sources) {
      setSources(summaryData.sources);
    }
  }, [summaryData, setSources]);

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
    <div className="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-white dark:bg-zinc-950">
      {/* Left / Center Reading Room Canvas */}
      <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild className="h-7 px-2 text-xs gap-1">
            <Link href="/papers">
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Back to Library</span>
            </Link>
          </Button>
        </div>

        {/* Paper Header Metadata */}
        <PaperMetadataHeader paper={paper} />

        {/* RAG Grounded Summary */}
        <GroundedSummaryCard
          summary={summaryData}
          isLoading={isSummarizing}
          onGenerate={summarize}
          error={summaryError}
        />

        {/* Document Attachments */}
        <DocumentAttachmentsList
          documents={documents}
          isLoading={isLoadingDocuments}
          onUpload={uploadDocument}
          isUploading={isUploadingDocument}
        />
      </div>

      {/* Right Evidence Inspector */}
      <SourceInspectorRail />
    </div>
  );
}
