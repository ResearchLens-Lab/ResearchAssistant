import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchService } from "@/services/search.service";

export function useSearch(initialParams = {}) {
  const [params, setParams] = useState({
    page: 1,
    page_size: 20,
    ...initialParams,
  });

  const { data, isLoading, isFetching, isError, error } = useQuery({
    queryKey: ["search", params],
    queryFn: () => searchService.search(params),
    enabled: !!(params.q || params.author || params.year),
  });

  const updateSearch = (newParams) => {
    setParams((prev) => ({
      ...prev,
      ...newParams,
    }));
  };

  return {
    params,
    updateSearch,
    results: data?.items || [],
    pagination: {
      total: data?.total || 0,
      page: data?.page || params.page || 1,
      pageSize: data?.page_size || params.page_size || 20,
      totalPages: data?.total_pages || 1,
    },
    isLoading,
    isFetching,
    isError,
    error,
  };
}
