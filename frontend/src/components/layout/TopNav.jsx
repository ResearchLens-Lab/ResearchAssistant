"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, FlaskConical, GitCompareArrows, Plus, Sparkles } from "lucide-react";
import { UserDropdown } from "./UserDropdown";
import { cn } from "@/utils/cn";

const PRIMARY_DESTINATIONS = [
  { label: "Library", href: "/papers", icon: BookOpen },
  { label: "Research Desk", href: "/chat", icon: FlaskConical },
  { label: "Compare & Reports", href: "/compare", icon: GitCompareArrows },
];

export function TopNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 shrink-0 border-b border-[var(--rl-border)] bg-white/95 px-3 backdrop-blur-sm sm:px-5">
      <div className="mx-auto flex h-16 w-full max-w-[1600px] items-center gap-3 sm:gap-6">
        <Link href="/papers" className="flex shrink-0 items-center gap-2.5 rounded-lg" aria-label="ResearchLens Library">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="hidden flex-col leading-tight sm:flex">
            <span className="text-[15px] font-semibold tracking-tight text-[var(--rl-ink)]">ResearchLens</span>
            <span className="text-[10px] font-medium tracking-wide text-[var(--rl-muted)]">EVIDENCE-FIRST RESEARCH</span>
          </span>
        </Link>

        <nav aria-label="Main navigation" className="flex min-w-0 flex-1 items-center justify-center gap-1 overflow-x-auto">
          {PRIMARY_DESTINATIONS.map(({ label, href, icon: Icon }) => {
            const active = href === "/papers"
              ? pathname === "/papers" || pathname.startsWith("/papers/") || pathname === "/dashboard"
              : pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-flex min-h-10 shrink-0 items-center gap-2 rounded-full px-3 text-xs font-medium transition-colors sm:px-4 sm:text-sm",
                  active
                    ? "bg-[var(--rl-selected)] text-[var(--rl-primary)]"
                    : "text-[var(--rl-muted)] hover:bg-[var(--rl-tint)] hover:text-[var(--rl-ink)]"
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                <span className="hidden md:inline">{label}</span>
                <span className="md:hidden">{label === "Research Desk" ? "Desk" : label === "Compare & Reports" ? "Compare" : label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          {!pathname.startsWith("/papers") && <Link
            href="/papers/upload"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-[var(--rl-primary)] text-white transition-colors hover:bg-[#1f659c] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-sky)] focus-visible:ring-offset-2 sm:w-auto sm:gap-2 sm:px-4"
            aria-label="Add sources"
            title="Add sources"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            <span className="hidden text-sm font-medium md:inline">Add sources</span>
          </Link>}
          <UserDropdown />
        </div>
      </div>
    </header>
  );
}
