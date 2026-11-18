"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenCheck, FileSearch, GitCompareArrows, HelpCircle } from "lucide-react";
import { ResearchLensLogo } from "@/components/brand/ResearchLensLogo";

const FEATURES = [
  { icon: BookOpenCheck, text: "Ask questions across your indexed papers" },
  { icon: FileSearch, text: "Follow citations to the source passage" },
  { icon: GitCompareArrows, text: "Compare findings across selected sources" },
];

export default function AuthLayout({ children }) {
  const pathname = usePathname();
  const isRegister = pathname === "/register";
  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-[var(--rl-canvas)]">
      {/* 40px drag strip top padding for window buttons */}
      <div
        style={{ WebkitAppRegion: "drag", paddingRight: "140px" }}
        className="h-10 w-full shrink-0 select-none z-50"
        aria-hidden="true"
      />
      <main className="grid min-h-0 flex-1 w-full min-w-0 grid-cols-1 bg-[var(--rl-canvas)] lg:grid-cols-[minmax(320px,0.85fr)_1.15fr] lg:grid-rows-[minmax(0,1fr)]">
        <section className="relative hidden min-h-0 flex-col justify-between overflow-y-auto bg-[#e8f3fc] p-6 lg:flex lg:p-8 xl:p-10">
          <Link href="/" className="relative z-10 flex items-center gap-3 text-[var(--rl-ink)]">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-[var(--rl-primary)] shadow-sm">
              <ResearchLensLogo className="h-6 w-6" />
            </span>
            <div className="flex flex-col leading-tight">
              <span className="text-lg font-semibold tracking-tight">ResearchLens</span>
              <span className="text-[11px] text-[var(--rl-muted)]">Find the evidence. Understand the research.</span>
            </div>
          </Link>
          <div className="auth-story-content relative z-10 max-w-lg space-y-5">
            <div>
              <p className="eyebrow text-[var(--rl-primary)]">A clearer way to work with literature</p>
              <h1 className="mt-4 text-4xl font-semibold leading-tight text-[var(--rl-ink)] xl:text-5xl">{isRegister ? "Keep every research answer close to its source." : "Welcome back to your research workspace."}</h1>
              <p className="mt-5 max-w-md text-base leading-7 text-[var(--rl-muted)]">Bring your documents together, ask focused questions, and inspect the passages behind the response.</p>
            </div>
            <ul className="space-y-3">
              {FEATURES.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-3 text-sm font-medium text-[var(--rl-ink)]">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-[var(--rl-primary)]"><Icon className="h-4 w-4" aria-hidden="true" /></span>
                  {text}
                </li>
              ))}
            </ul>
          </div>
          <p className="relative z-10 text-xs text-[var(--rl-muted)]">Your private research workspace</p>
        </section>
        <section className="flex min-h-0 flex-1 w-full min-w-0 flex-col items-center overflow-y-auto p-4 sm:p-6 lg:p-5">
          <div className="my-auto w-full min-w-0 max-w-md shrink-0">
            <Link href="/" className="mb-6 flex items-center justify-center gap-2 text-sm font-semibold text-[var(--rl-ink)] lg:hidden">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><ResearchLensLogo className="h-5 w-5" /></span>
              ResearchLens
            </Link>
            {children}
          </div>
        </section>
      </main>
    </div>
  );
}
