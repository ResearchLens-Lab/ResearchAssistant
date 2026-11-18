"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { usePaperDetails } from "@/hooks/usePapers";
import { useCitationStore } from "@/store/citationStore";
import { PaperMetadataHeader } from "@/components/reader/PaperMetadataHeader";
import { GroundedSummaryCard } from "@/components/reader/GroundedSummaryCard";
import { DocumentAttachmentsList } from "@/components/reader/DocumentAttachmentsList";
import { SourceVerificationCard } from "@/components/papers/SourceVerificationCard";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { EditPaperModal } from "@/components/papers/EditPaperModal";
import { AddSourcesModal } from "@/components/upload/AddSourcesModal";
import { Button } from "@/components/ui/button";
import { ChevronLeft, AlertCircle, UploadCloud, ArrowRight } from "lucide-react";
import Link from "next/link";
import { hasIndexedSources } from "@/lib/researchWorkspace.mjs";
import { papersService } from "@/services/papers.service";
import { useQueryClient } from "@tanstack/react-query";
import { useChatScopeStore } from "@/store/chatScopeStore";

export default function PaperDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const paperId = params.id;

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isAddSourcesOpen, setIsAddSourcesOpen] = useState(false);

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
  const { setLastViewedPaperId } = useChatScopeStore();
  const evidenceAvailable = hasIndexedSources(documents);
  const currentSummary = summaryData?.paper_id === paperId ? summaryData : null;

  useEffect(() => {
    if (paperId) {
      setLastViewedPaperId(paperId);
    }
  }, [paperId, setLastViewedPaperId]);

  useEffect(() => {
    setSources(currentSummary?.sources || []);
  }, [currentSummary, setSources]);

  const handleSaveProject = async (updatedFields) => {
    const updated = await papersService.update(paperId, updatedFields);
    queryClient.invalidateQueries({ queryKey: ["paper", paperId] });
    queryClient.invalidateQueries({ queryKey: ["papers"] });
    return updated;
  };

  if (isLoading) {
    return (
      <div className="p-6 sm:p-8 space-y-5 max-w-7xl mx-auto">
        <div className="h-6 w-36 rounded-full bg-slate-200/80 animate-pulse" />
        <div className="h-28 rounded-2xl bg-slate-200/70 animate-pulse" />
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 h-80 rounded-2xl bg-slate-200/60 animate-pulse" />
          <div className="lg:col-span-7 h-80 rounded-2xl bg-slate-200/60 animate-pulse" />
        </div>
      </div>
    );
  }

  if (isError || !paper) {
    return (
      <div className="flex h-96 flex-col items-center justify-center p-8 text-center space-y-3">
        <AlertCircle className="h-8 w-8 text-rose-500" />
        <h3 className="text-base font-bold text-slate-900">Research project not found</h3>
        <p className="text-xs text-slate-500 max-w-sm">
          {error?.message || "You may not have permission to view this project or it may have been removed."}
        </p>
        <Button variant="outline" size="sm" asChild className="rounded-full">
          <Link href="/papers">← Back to Your Project Library</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="page-shell space-y-5">
      {/* Top Navigation & Action Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200/70">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              asChild
              className="h-8 px-2.5 text-xs gap-1.5 text-slate-600 hover:text-slate-900 hover:bg-white rounded-full transition-colors"
            >
              <Link href="/papers">
                <ChevronLeft className="h-3.5 w-3.5" />
                <span>Back to Your Project Library</span>
              </Link>
            </Button>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="workbench"
              size="sm"
              disabled={!evidenceAvailable || isLoadingDocuments || isDocumentsError}
              title={
                isDocumentsError
                  ? "Retry loading project sources"
                  : !evidenceAvailable
                  ? "Add and index a source before asking a grounded question"
                  : undefined
              }
              onClick={() => router.push(`/chat?paper_id=${paperId}`)}
              className="h-8 text-xs rounded-full"
            >
              <span>Ask in Research Desk</span>
              <ArrowRight className="h-3 w-3 ml-1" />
            </Button>

            <Button
              variant="soft"
              size="sm"
              onClick={() => setIsAddSourcesOpen(true)}
              className="h-8 text-xs bg-sky-50 text-[#1d6fc4] hover:bg-sky-100 rounded-full"
            >
              <UploadCloud className="h-3.5 w-3.5 mr-1.5" />
              <span>Add sources</span>
            </Button>

            <Button
              variant="outline"
              size="sm"
              disabled={!evidenceAvailable || isLoadingDocuments || isDocumentsError}
              title={
                isDocumentsError
                  ? "Project source status could not be loaded"
                  : !evidenceAvailable
                  ? "Add and index a source to inspect evidence"
                  : undefined
              }
              onClick={() => {
                setSources(currentSummary?.sources || []);
                openDrawer();
              }}
              className="h-8 text-xs rounded-full"
            >
              Evidence & Citations
            </Button>
          </div>
        </div>

        {/* Paper Header Metadata with Title, Description, and inline Edit */}
        <PaperMetadataHeader paper={paper} onEdit={() => setIsEditOpen(true)} />

        {/* Split 2-Column Desktop Grid Layout: Left Column Sticky to Prevent Empty Space When Scrolling */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column (5 cols): Project Sources & Bibliographic Verification (Sticky Pinned) */}
          <div className="lg:col-span-5 space-y-3 lg:sticky lg:top-3 self-start">
            <DocumentAttachmentsList
              documents={documents}
              isLoading={isLoadingDocuments}
              isError={isDocumentsError}
              error={documentsError}
              onRetry={refetchDocuments}
            />

            <SourceVerificationCard
              paper={paper}
              onDoiUpdated={() => {
                queryClient.invalidateQueries({ queryKey: ["paper", paperId] });
              }}
            />
          </div>

          {/* Right Column (7 cols): RAG Grounded Summary */}
          <div className="lg:col-span-7 min-w-0">
            <GroundedSummaryCard
              summary={currentSummary}
              isLoading={isSummarizing}
              onGenerate={summarize}
              error={summaryError}
              hasIndexedSources={evidenceAvailable}
              isCheckingSources={isLoadingDocuments}
              isSourceError={isDocumentsError}
              onAskInDesk={() => router.push(`/chat?paper_id=${paperId}`)}
            />
          </div>
        </div>

      {/* Right Evidence Inspector Drawer */}
      {isDrawerOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Evidence Trail"
          className="fixed inset-x-0 bottom-0 top-16 z-40 flex justify-end bg-slate-950/35"
          onClick={closeDrawer}
          onKeyDown={(event) => {
            if (event.key === "Escape") closeDrawer();
          }}
        >
          <div
            className="h-full w-[min(26rem,94vw)] shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <SourceInspectorRail onClose={closeDrawer} />
          </div>
        </div>
      )}

      {/* Edit Project Modal */}
      <EditPaperModal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        paper={paper}
        onSave={handleSaveProject}
      />

      {/* Add Sources Modal */}
      <AddSourcesModal
        isOpen={isAddSourcesOpen}
        onClose={() => setIsAddSourcesOpen(false)}
        preselectedPaperId={paperId}
        papers={[paper]}
        onSuccess={() => refetchDocuments()}
      />
    </div>
  );
}
