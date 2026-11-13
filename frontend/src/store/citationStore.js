import { create } from "zustand";
import { getSourceIdentity } from "@/utils/sourceIdentity";

export const useCitationStore = create((set) => ({
  sources: [],
  researchTrace: null,
  activeSourceId: null,
  activeSourceKey: null,
  activeHighlight: null,
  activeQuestion: "",
  activeResearchPlan: null,
  activeTab: "sources", // 'sources' | 'library' | 'notes'
  isDrawerOpen: false,

  setSources: (sources) =>
    set((state) => {
      const next = sources || [];
      if (
        state.sources.length === next.length &&
        state.sources.every((s, i) => getSourceIdentity(s) === getSourceIdentity(next[i]))
      ) {
        return state;
      }
      const active = next.find((source) => getSourceIdentity(source) === state.activeSourceKey) || next[0] || null;
      return {
        sources: next,
        activeSourceId: active?.source_id || null,
        activeSourceKey: active ? getSourceIdentity(active) : null,
        activeHighlight: active && getSourceIdentity(active) === state.activeSourceKey ? state.activeHighlight : null,
      };
    }),

  setResearchTrace: (researchTrace) =>
    set((state) => {
      if (state.researchTrace === researchTrace) return state;
      return { researchTrace: researchTrace || null };
    }),

  setActiveSource: (sourceOrId, sourceKey = null) =>
    set((state) => {
      const sourceId = typeof sourceOrId === "object" ? sourceOrId?.source_id : sourceOrId;
      const matchingSource = typeof sourceOrId === "object" ? sourceOrId : state.sources.find((source) => source.source_id === sourceId);
      const key = sourceKey || (matchingSource ? getSourceIdentity(matchingSource) : sourceId ? `source:${sourceId}` : null);
      return state.activeSourceId === sourceId && state.activeSourceKey === key
        ? state
        : {
            activeSourceId: sourceId || null,
            activeSourceKey: key,
            activeHighlight: key === state.activeSourceKey ? state.activeHighlight : null,
          };
    }),

  setActiveTab: (tab) =>
    set((state) => (state.activeTab === tab ? state : { activeTab: tab })),

  openSource: (sourceId, highlight = null, sourceKey = null, question = "", researchPlan = null) =>
    set((state) => {
      const sameHighlight = state.activeHighlight === highlight || (
        state.activeHighlight?.headingText === highlight?.headingText &&
        state.activeHighlight?.claimText === highlight?.claimText &&
        state.activeHighlight?.fullText === highlight?.fullText
      );
      if (
        state.activeSourceId === sourceId &&
        state.activeSourceKey === sourceKey &&
        sameHighlight &&
        state.activeTab === "sources" &&
        state.isDrawerOpen && state.activeQuestion === question && state.activeResearchPlan === researchPlan
      ) return state;
      return {
        activeSourceId: sourceId,
        activeSourceKey: sourceKey,
        activeHighlight: highlight,
        activeQuestion: question || "",
        activeResearchPlan: researchPlan || null,
        activeTab: "sources",
        isDrawerOpen: true,
      };
    }),

  openInspector: () => set({ isDrawerOpen: true }),

  openDrawer: () => set((state) => (state.isDrawerOpen ? state : { isDrawerOpen: true })),

  closeDrawer: () => set((state) => (!state.isDrawerOpen ? state : { isDrawerOpen: false })),

  clearSources: () =>
    set((state) => {
      if (state.sources.length === 0 && !state.activeSourceId && !state.activeSourceKey && !state.isDrawerOpen && !state.researchTrace && !state.activeHighlight && !state.activeQuestion && !state.activeResearchPlan) {
        return state;
      }
      return {
        sources: [],
        researchTrace: null,
        activeSourceId: null,
        activeSourceKey: null,
        activeHighlight: null,
        activeQuestion: "",
        activeResearchPlan: null,
        isDrawerOpen: false,
      };
    }),
}));
