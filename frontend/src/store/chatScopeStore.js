import { create } from "zustand";

const getInitialLastPaperId = () => {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem("researchlens_last_project_id") || localStorage.getItem("researchlens_last_project_id") || null;
  } catch {
    return null;
  }
};

export const useChatScopeStore = create((set, get) => ({
  selectedPaperIds: [],
  selectedDocumentIds: [],
  lastViewedPaperId: getInitialLastPaperId(),

  setLastViewedPaperId: (paperId) => {
    if (!paperId) return;
    try {
      if (typeof window !== "undefined") {
        sessionStorage.setItem("researchlens_last_project_id", paperId);
        localStorage.setItem("researchlens_last_project_id", paperId);
      }
    } catch {}
    set({ lastViewedPaperId: paperId });
  },

  togglePaper: (paperId, associatedDocIds = []) =>
    set((state) => {
      const isSelected = state.selectedPaperIds.includes(paperId);
      const nextPaperIds = isSelected
        ? state.selectedPaperIds.filter((id) => id !== paperId)
        : [...state.selectedPaperIds, paperId];

      let nextDocIds = [...state.selectedDocumentIds];
      if (associatedDocIds && associatedDocIds.length > 0) {
        if (isSelected) {
          // Deselect associated documents
          nextDocIds = nextDocIds.filter((id) => !associatedDocIds.includes(id));
        } else {
          // Select all associated documents
          const docSet = new Set([...nextDocIds, ...associatedDocIds]);
          nextDocIds = Array.from(docSet);
        }
      }

      return {
        selectedPaperIds: nextPaperIds,
        selectedDocumentIds: nextDocIds,
        lastViewedPaperId: !isSelected ? paperId : state.lastViewedPaperId,
      };
    }),

  toggleDocument: (documentId, paperId = null) =>
    set((state) => {
      const isDocSelected = state.selectedDocumentIds.includes(documentId);
      const nextDocIds = isDocSelected
        ? state.selectedDocumentIds.filter((id) => id !== documentId)
        : [...state.selectedDocumentIds, documentId];

      let nextPaperIds = [...state.selectedPaperIds];
      if (paperId && !isDocSelected && !nextPaperIds.includes(paperId)) {
        nextPaperIds.push(paperId);
      }

      return {
        selectedDocumentIds: nextDocIds,
        selectedPaperIds: nextPaperIds,
      };
    }),

  selectDocuments: (documentIds) =>
    set({ selectedDocumentIds: documentIds || [] }),

  clearDocumentSelection: () =>
    set({ selectedDocumentIds: [] }),

  selectPapers: (paperIds, docIds = null) =>
    set((state) => {
      const next = paperIds || [];
      const nextDocs = docIds !== null ? docIds : state.selectedDocumentIds;
      return {
        selectedPaperIds: next,
        selectedDocumentIds: nextDocs,
        lastViewedPaperId: next.length > 0 ? next[0] : state.lastViewedPaperId,
      };
    }),

  clearSelection: () =>
    set({ selectedPaperIds: [], selectedDocumentIds: [] }),
}));
