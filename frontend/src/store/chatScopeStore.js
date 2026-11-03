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
    set((state) => {
      const next = paperIds || [];
      if (
        state.selectedPaperIds.length === next.length &&
        state.selectedPaperIds.every((id, i) => id === next[i])
      ) {
        return state;
      }
      return {
        selectedPaperIds: next,
      };
    }),

  clearSelection: () =>
    set((state) => {
      if (state.selectedPaperIds.length === 0) return state;
      return { selectedPaperIds: [] };
    }),
}));
