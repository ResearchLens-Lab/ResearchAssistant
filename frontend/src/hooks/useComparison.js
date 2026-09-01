import { useMutation } from "@tanstack/react-query";
import { papersService } from "@/services/papers.service";
import { useCitationStore } from "@/store/citationStore";

export function useComparison() {
  const { setSources } = useCitationStore();

  const compareMutation = useMutation({
    mutationFn: (payload) => papersService.compare(payload),
    onSuccess: (data) => {
      if (data?.sources) {
        setSources(data.sources);
      }
    },
  });

  return {
    comparePapers: compareMutation.mutateAsync,
    comparisonResult: compareMutation.data,
    isComparing: compareMutation.isPending,
    isError: compareMutation.isError,
    error: compareMutation.error,
    reset: compareMutation.reset,
  };
}
