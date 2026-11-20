import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { papersService } from "@/services/papers.service";
import { documentsService } from "@/services/documents.service";

export function usePapers(page = 1, pageSize = 20) {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ["papers", page, pageSize],
    queryFn: () => papersService.list(page, pageSize),
  });

  const createPaperMutation = useMutation({
    mutationFn: (payload) => papersService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });

  const updatePaperMutation = useMutation({
    mutationFn: ({ id, payload }) => papersService.update(id, payload),
    onSuccess: (updatedPaper) => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paper", updatedPaper.id] });
    },
  });

  const deletePaperMutation = useMutation({
    mutationFn: (id) => papersService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });

  return {
    papers: data?.items || [],
    pagination: {
      total: data?.total || 0,
      page: data?.page || page,
      pageSize: data?.page_size || pageSize,
      totalPages: data?.total_pages || 1,
    },
    isLoading,
    isFetching,
    isError,
    error,
    createPaper: createPaperMutation.mutateAsync,
    isCreating: createPaperMutation.isPending,
    createError: createPaperMutation.error,
    updatePaper: updatePaperMutation.mutateAsync,
    isUpdating: updatePaperMutation.isPending,
    deletePaper: deletePaperMutation.mutateAsync,
    isDeleting: deletePaperMutation.isPending,
  };
}

export function usePaperDetails(paperId) {
  const queryClient = useQueryClient();

  const paperQuery = useQuery({
    queryKey: ["paper", paperId],
    queryFn: () => papersService.getById(paperId),
    enabled: !!paperId,
    initialData: () => {
      const queries = queryClient.getQueriesData({ queryKey: ["papers"] });
      for (const [_, cached] of queries) {
        if (cached?.items) {
          const found = cached.items.find((p) => p.id === paperId);
          if (found) return found;
        }
      }
      return undefined;
    },
  });

  const documentsQuery = useQuery({
    queryKey: ["paperDocuments", paperId],
    queryFn: () => papersService.getDocuments(paperId),
    enabled: !!paperId,
    refetchInterval: (query) => {
      const docs = query.state.data;
      if (!Array.isArray(docs)) return false;
      const hasActive = docs.some((doc) => {
        const s = doc.processing_status;
        const stage = doc.processing_stage;
        return (
          s === "processing" ||
          s === "uploaded" ||
          s === "extracting" ||
          s === "ocr_processing" ||
          s === "indexing" ||
          (stage && stage !== "ready" && stage !== "failed" && stage !== "cancelled")
        );
      });
      return hasActive ? 2500 : false;
    },
  });

  const summarizeMutation = useMutation({
    mutationFn: (focusArea) => papersService.summarize(paperId, focusArea),
  });

  const uploadDocumentMutation = useMutation({
    mutationFn: (file) => documentsService.upload(file, paperId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paperDocuments", paperId] });
      queryClient.invalidateQueries({ queryKey: ["paperDocumentsByPapers"] });
      queryClient.invalidateQueries({ queryKey: ["paper", paperId] });
    },
  });

  return {
    paper: paperQuery.data,
    isLoading: paperQuery.isLoading,
    isError: paperQuery.isError,
    error: paperQuery.error,
    documents: documentsQuery.data || [],
    isLoadingDocuments: documentsQuery.isLoading,
    isDocumentsError: documentsQuery.isError,
    documentsError: documentsQuery.error,
    refetchDocuments: documentsQuery.refetch,
    summarize: summarizeMutation.mutateAsync,
    summaryData: summarizeMutation.data || paperQuery.data?.summary_json || null,
    isSummarizing: summarizeMutation.isPending,
    summaryError: summarizeMutation.error,
    uploadDocument: uploadDocumentMutation.mutateAsync,
    isUploadingDocument: uploadDocumentMutation.isPending,
  };
}
