import { create } from "zustand";

export const useChatScopeStore = create((set) => ({
  selectedPaperIds: [],

  togglePaper: (paperId) =>
    set((state) => ({
      selectedPaperIds: state.selectedPaperIds.includes(paperId)
        ? state.selectedPaperIds.filter((id) => id !== paperId)
        : [...state.selectedPaperIds, paperId],
    })),

  selectPapers: (paperIds) =>
    set({
      selectedPaperIds: paperIds || [],
    }),

  clearSelection: () =>
    set({
      selectedPaperIds: [],
    }),
}));
