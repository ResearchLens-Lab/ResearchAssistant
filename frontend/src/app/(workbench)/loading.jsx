import React from "react";

export default function WorkbenchLoading() {
  return (
    <main aria-label="Loading research workspace" aria-busy="true" className="page-shell space-y-6">
      <div className="space-y-2">
        <div className="h-3 w-28 animate-pulse rounded bg-sky-100" />
        <div className="h-8 w-64 max-w-full animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-96 max-w-full animate-pulse rounded bg-slate-100" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1, 2, 3].map((item) => <section key={item} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
          <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
          <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-slate-100" />
          <div className="h-20 animate-pulse rounded-lg bg-sky-50" />
        </section>)}
      </div>
    </main>
  );
}
