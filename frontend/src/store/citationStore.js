import { create } from "zustand";

export const useCitationStore = create((set) => ({
  sources: [],
  activeSourceId: null,
  activeTab: "sources", // 'sources' | 'library' | 'notes'
  isDrawerOpen: false,

  setSources: (sources) =>
    set({
      sources: sources || [],
      activeSourceId: sources && sources.length > 0 ? sources[0].source_id : null,
    }),

  setActiveSource: (sourceId) =>
    set({
      activeSourceId: sourceId,
    }),

  setActiveTab: (tab) =>
    set({
      activeTab: tab,
    }),

  openSource: (sourceId) =>
    set({
      activeSourceId: sourceId,
      activeTab: "sources",
      isDrawerOpen: true,
    }),

  closeDrawer: () => set({ isDrawerOpen: false }),

  clearSources: () =>
    set({
      sources: [],
      activeSourceId: null,
      isDrawerOpen: false,
    }),
}));
