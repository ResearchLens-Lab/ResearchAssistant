"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, FlaskConical, GitCompareArrows, UploadCloud } from "lucide-react";
import { UserDropdown } from "./UserDropdown";
import { ResearchLensLogo } from "@/components/brand/ResearchLensLogo";
import { cn } from "@/utils/cn";
import { usePapers } from "@/hooks/usePapers";
import { AddSourcesModal } from "@/components/upload/AddSourcesModal";

const PRIMARY_DESTINATIONS = [
  { label: "Library", href: "/papers", icon: BookOpen },
  { label: "Research Desk", href: "/chat", icon: FlaskConical },
  { label: "Compare & Reports", href: "/compare", icon: GitCompareArrows },
];

export function TopNav() {
  const pathname = usePathname();
  const [addSourcesOpen, setAddSourcesOpen] = useState(false);
  const { papers = [] } = usePapers(1, 50);

  return (
    <header className="sticky top-0 z-30 shrink-0 border-b border-slate-200/70 bg-white/95 px-4 backdrop-blur-sm sm:px-6">
      <div className="mx-auto grid h-16 w-full max-w-[1440px] grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-4">
        {/* Brand identity matching reference */}
        <Link href="/papers" className="flex min-w-0 shrink-0 items-center gap-3 justify-self-start group" aria-label="ResearchLens Library">
          <span className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200/90 bg-white text-slate-700 shadow-2xs transition-transform group-hover:scale-105">
            <ResearchLensLogo className="h-4.5 w-4.5" />
          </span>
          <span className="hidden flex-col leading-tight sm:flex">
            <span className="text-[15px] font-semibold tracking-tight text-slate-900">ResearchLens</span>
            <span className="text-[11px] italic font-serif text-slate-400">Find the evidence. Understand the research.</span>
          </span>
        </Link>

        {/* Clean typographic navigation matching reference */}
        <nav aria-label="Main navigation" className="flex min-w-0 items-center justify-self-center gap-6 whitespace-nowrap sm:gap-8">
          {PRIMARY_DESTINATIONS.map(({ label, href }) => {
            const active = href === "/papers"
              ? pathname === "/papers" || pathname.startsWith("/papers/") || pathname === "/dashboard"
              : pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "text-xs sm:text-sm transition-colors py-1",
                  active
                    ? "font-semibold text-slate-900 border-b-2 border-slate-900"
                    : "font-normal text-slate-500 hover:text-slate-900"
                )}
              >
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right action area */}
        <div className="flex shrink-0 items-center justify-self-end gap-2">
          <button
            type="button"
            onClick={() => setAddSourcesOpen(true)}
            className="inline-flex h-9 items-center justify-center rounded-full bg-[#1d6fc4] px-4 text-white shadow-xs transition-all hover:bg-[#185ea8] hover:-translate-y-0.5 active:translate-y-0 text-xs font-semibold gap-1.5"
            aria-label="Add sources"
          >
            <UploadCloud className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Add sources</span>
          </button>
          <UserDropdown />
        </div>
      </div>
      <AddSourcesModal isOpen={addSourcesOpen} onClose={() => setAddSourcesOpen(false)} papers={papers} />
    </header>
  );
}
