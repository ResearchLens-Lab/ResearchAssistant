import Link from "next/link";
import { ArrowRight, BookOpen, Check, FileSearch, GitCompareArrows, HelpCircle } from "lucide-react";
import { ResearchLensLogo } from "@/components/brand/ResearchLensLogo";

const CAPABILITIES = [
  {
    icon: BookOpen,
    title: "Bring your sources together",
    description: "Add supported documents to a research project and see the real processing status for each file.",
  },
  {
    icon: FileSearch,
    title: "Follow the evidence",
    description: "Ask questions about indexed sources, inspect returned passages, and open an authorized PDF at its cited page when available.",
  },
  {
    icon: GitCompareArrows,
    title: "Compare what papers report",
    description: "Generate a cited comparison from selected indexed papers, with missing and conflicting evidence called out where the response provides it.",
  },
];

export default function HomePage() {
  return (
    <main className="min-h-dvh bg-[var(--rl-canvas)]">
      <header className="border-b border-[var(--rl-border)] bg-white/90 px-4 sm:px-6">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-3 rounded-lg text-[var(--rl-ink)]" aria-label="ResearchLens home">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)] shadow-2xs">
              <ResearchLensLogo className="h-5 w-5" />
            </span>
            <div className="flex flex-col leading-tight">
              <span className="text-base font-semibold tracking-tight">ResearchLens</span>
              <span className="text-[10px] text-[var(--rl-muted)]">Find the evidence. Understand the research.</span>
            </div>
          </Link>
          <nav aria-label="Main navigation" className="flex items-center gap-2">
            <Link href="/login" className="inline-flex min-h-10 items-center rounded-lg px-3 text-sm font-medium text-[var(--rl-muted)] hover:bg-[var(--rl-tint)] hover:text-[var(--rl-ink)]">Sign in</Link>
          </nav>
        </div>
      </header>

      <section className="px-4 pb-14 pt-14 sm:px-6 sm:pt-20 lg:pb-20 lg:pt-24">
        <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <div>
            <p className="eyebrow text-[var(--rl-primary)]">Evidence-first research workspace</p>
            <h1 className="mt-4 max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-[var(--rl-ink)] sm:text-5xl lg:text-6xl">Turn a library of papers into a clear line of evidence.</h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-[var(--rl-muted)] sm:text-lg sm:leading-8">Ask focused questions across your indexed sources. Read the answer alongside its citations, inspect the passages, and compare what selected papers report.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/register" className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-[var(--rl-primary)] px-5 text-sm font-semibold text-white shadow-sm hover:bg-[#1f659c]">Start a research project <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
              <Link href="/login" className="inline-flex min-h-11 items-center rounded-lg border border-[var(--rl-border)] bg-white px-5 text-sm font-semibold text-[var(--rl-ink)] hover:bg-[var(--rl-tint)]">Sign in</Link>
            </div>
            <p className="mt-4 text-xs leading-5 text-[var(--rl-muted)]">Begin with your own indexed documents. Answers depend on the passages the system can retrieve.</p>
          </div>

          <div className="surface-card p-5 sm:p-7" aria-label="Research workflow overview">
            <div className="flex items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-4">
              <div><p className="eyebrow text-[var(--rl-primary)]">A traceable workflow</p><h2 className="mt-1 text-lg font-semibold text-[var(--rl-ink)]">From source to answer</h2></div>
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><FileSearch className="h-5 w-5" aria-hidden="true" /></span>
            </div>
            <ol className="mt-5 space-y-3" aria-label="Sources to research question to evidence">
              <li className="workflow-stage flex items-center gap-3 rounded-xl bg-[var(--rl-tint)] p-4">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-[var(--rl-primary)]"><BookOpen className="h-4 w-4" aria-hidden="true" /></span>
                <span><strong className="block text-sm font-semibold text-[var(--rl-ink)]">Indexed sources</strong><span className="mt-0.5 block text-xs text-[var(--rl-muted)]">Files are available for research after indexing.</span></span>
              </li>
              <li className="workflow-connector flex justify-center text-[var(--rl-sky)]" aria-hidden="true"><span className="h-5 border-l border-dashed border-[var(--rl-sky)]" /></li>
              <li className="workflow-stage flex items-center gap-3 rounded-xl bg-[var(--rl-tint)] p-4">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-[var(--rl-primary)]"><HelpCircle className="h-4 w-4" aria-hidden="true" /></span>
                <span><strong className="block text-sm font-semibold text-[var(--rl-ink)]">Research question</strong><span className="mt-0.5 block text-xs text-[var(--rl-muted)]">Scope the question to selected projects.</span></span>
              </li>
              <li className="workflow-connector flex justify-center text-[var(--rl-sky)]" aria-hidden="true"><span className="h-5 border-l border-dashed border-[var(--rl-sky)]" /></li>
              <li className="workflow-stage flex items-center gap-3 rounded-xl border border-sky-100 bg-white p-4">
                <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--rl-selected)] text-[var(--rl-primary)]"><FileSearch className="h-4 w-4" aria-hidden="true" /><Check className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-white text-[var(--rl-primary)]" aria-hidden="true" /></span>
                <span><strong className="block text-sm font-semibold text-[var(--rl-ink)]">Answer with source passages</strong><span className="mt-0.5 block text-xs text-[var(--rl-muted)]">Inspect citations and the available evidence checks.</span></span>
              </li>
            </ol>
          </div>
        </div>
      </section>

      <section className="border-y border-[var(--rl-border)] bg-white px-4 py-14 sm:px-6 lg:py-16">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-2xl"><p className="eyebrow text-[var(--rl-primary)]">Research, connected to sources</p><h2 className="mt-2 text-2xl font-semibold text-[var(--rl-ink)] sm:text-3xl">Keep the evidence in view as you work.</h2></div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {CAPABILITIES.map(({ icon: Icon, title, description }) => <article key={title} className="rounded-2xl border border-[var(--rl-border)] bg-[var(--rl-canvas)] p-5 sm:p-6">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-[var(--rl-primary)]"><Icon className="h-5 w-5" aria-hidden="true" /></span>
              <h3 className="mt-4 text-base font-semibold text-[var(--rl-ink)]">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--rl-muted)]">{description}</p>
            </article>)}
          </div>
        </div>
      </section>

      <footer className="px-4 py-10 text-center sm:px-6">
        <p className="text-sm text-[var(--rl-muted)]">ResearchLens · Your sources, your research questions, traceable answers.</p>
        <div className="mt-3 flex justify-center text-sm font-medium text-[var(--rl-primary)]"><Link href="/login" className="underline underline-offset-4">Sign in</Link></div>
      </footer>
    </main>
  );
}
