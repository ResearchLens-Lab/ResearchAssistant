import React from "react";

const layouts = {
  library: { heading: "w-52", cards: 6, cardHeight: "h-44" },
  project: { heading: "w-64", cards: 3, cardHeight: "h-36" },
  upload: { heading: "w-56", cards: 1, cardHeight: "h-64" },
  chat: { heading: "w-48", cards: 2, cardHeight: "h-56" },
  compare: { heading: "w-60", cards: 3, cardHeight: "h-48" },
  graph: { heading: "w-52", cards: 2, cardHeight: "h-56" },
  dashboard: { heading: "w-48", cards: 4, cardHeight: "h-36" },
  search: { heading: "w-56", cards: 5, cardHeight: "h-28" },
  settings: { heading: "w-48", cards: 2, cardHeight: "h-52" },
  tools: { heading: "w-48", cards: 3, cardHeight: "h-36" },
};

export function ResearchRouteLoading({ kind = "library" }) {
  const layout = layouts[kind] || layouts.library;
  return (
    <main aria-busy="true" aria-label={`Loading ${kind === "chat" ? "Research Desk" : kind === "compare" ? "comparison" : kind}`} className="page-shell space-y-6">
      <div className="space-y-2"><div className="h-3 w-24 animate-pulse rounded bg-sky-100" /><div className={`h-8 max-w-full animate-pulse rounded bg-slate-200 ${layout.heading}`} /><div className="h-4 w-96 max-w-full animate-pulse rounded bg-slate-100" /></div>
      <div className={`grid gap-4 ${kind === "chat" || kind === "graph" ? "lg:grid-cols-[minmax(15rem,0.8fr)_minmax(0,2fr)]" : kind === "upload" ? "grid-cols-1" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
        {Array.from({ length: layout.cards }, (_, index) => <section key={index} className={`space-y-3 rounded-xl border border-slate-200 bg-white p-4 ${layout.cardHeight}`}><div className="h-4 w-2/5 animate-pulse rounded bg-slate-200" /><div className="h-3 w-full animate-pulse rounded bg-slate-100" /><div className="h-3 w-4/5 animate-pulse rounded bg-slate-100" /><div className="h-16 animate-pulse rounded-lg bg-sky-50" />{kind === "chat" && index === 1 && <p className="text-xs text-sky-700">Preparing your research workspace…</p>}</section>)}
      </div>
    </main>
  );
}
