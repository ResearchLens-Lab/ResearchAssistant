import { create } from "zustand";

export const useCitationStore = create((set) => ({
  sources: [],
  researchTrace: null,
  activeSourceId: null,
  activeTab: "sources", // 'sources' | 'library' | 'notes'
  isDrawerOpen: false,

  setSources: (sources) =>
    set((state) => {
      const next = sources || [];
      if (
        state.sources.length === next.length &&
        state.sources.every((s, i) => s.source_id === next[i]?.source_id)
      ) {
        return state;
      }
      return {
        sources: next,
        activeSourceId: next.length > 0 ? next[0].source_id : null,
      };
    }),

  setResearchTrace: (researchTrace) =>
    set((state) => {
      if (state.researchTrace === researchTrace) return state;
      return { researchTrace: researchTrace || null };
    }),

  setActiveSource: (sourceId) =>
    set((state) => (state.activeSourceId === sourceId ? state : { activeSourceId: sourceId })),

  setActiveTab: (tab) =>
    set((state) => (state.activeTab === tab ? state : { activeTab: tab })),

  openSource: (sourceId) =>
    set({
      activeSourceId: sourceId,
      activeTab: "sources",
      isDrawerOpen: true,
    }),

  openDrawer: () => set((state) => (state.isDrawerOpen ? state : { isDrawerOpen: true })),

  closeDrawer: () => set((state) => (!state.isDrawerOpen ? state : { isDrawerOpen: false })),

  clearSources: () =>
    set((state) => {
      if (state.sources.length === 0 && !state.activeSourceId && !state.isDrawerOpen && !state.researchTrace) {
        return state;
      }
      return {
        sources: [],
        researchTrace: null,
        activeSourceId: null,
        isDrawerOpen: false,
      };
    }),
}));
