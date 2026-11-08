"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenCheck, FileSearch, GitCompareArrows, Sparkles } from "lucide-react";

const FEATURES = [
  { icon: BookOpenCheck, text: "Ask questions across your indexed papers" },
  { icon: FileSearch, text: "Follow citations to the source passage" },
  { icon: GitCompareArrows, text: "Compare findings across selected sources" },
];

export default function AuthLayout({ children }) {
  const pathname = usePathname();
  const isRegister = pathname === "/register";
  return (
    <main className="grid min-h-dvh w-full min-w-0 grid-cols-1 bg-[var(--rl-canvas)] lg:h-dvh lg:min-h-0 lg:grid-cols-[minmax(320px,0.85fr)_1.15fr] lg:grid-rows-[minmax(0,1fr)]">
      <section className="relative hidden min-h-0 flex-col justify-between overflow-y-auto bg-[#e8f3fc] p-6 lg:flex lg:p-8 xl:p-10">
        <Link href="/" className="relative z-10 flex items-center gap-3 text-[var(--rl-ink)]">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-[var(--rl-primary)] shadow-sm"><Sparkles className="h-5 w-5" aria-hidden="true" /></span>
          <span className="text-lg font-semibold tracking-tight">ResearchLens</span>
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
          <ol className="auth-story-vignette grid grid-cols-3 gap-2" aria-label="Sources, research question, and cited evidence">
            {[
              { icon: BookOpenCheck, label: "Sources" },
              { icon: Sparkles, label: "Question" },
              { icon: FileSearch, label: "Evidence" },
            ].map(({ icon: Icon, label }) => <li key={label} className="rounded-xl border border-white/80 bg-white/70 p-2.5 text-center shadow-sm">
              <Icon className="mx-auto h-4 w-4 text-[var(--rl-primary)]" aria-hidden="true" />
              <span className="mt-1.5 block text-[11px] font-medium text-[var(--rl-muted)]">{label}</span>
            </li>)}
          </ol>
        </div>
        <p className="relative z-10 text-xs text-[var(--rl-muted)]">Your private research workspace</p>
      </section>
      <section className="flex min-h-dvh w-full min-w-0 flex-col items-center overflow-y-auto p-4 sm:p-6 lg:h-dvh lg:min-h-0 lg:p-5">
        <div className="my-auto w-full min-w-0 max-w-md shrink-0">
          <Link href="/" className="mb-6 flex items-center justify-center gap-2 text-sm font-semibold text-[var(--rl-ink)] lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><Sparkles className="h-5 w-5" aria-hidden="true" /></span>
            ResearchLens
          </Link>
          {children}
        </div>
      </section>
    </main>
  );
}
