import { apiClient } from "./api.client";

export const searchService = {
  async search(params) {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.author) query.set("author", params.author);
    if (params.year) query.set("year", params.year.toString());
    query.set("page", (params.page || 1).toString());
    query.set("page_size", (params.page_size || 20).toString());

    return apiClient(`/search?${query.toString()}`, {
      method: "GET",
    });
  },
};
