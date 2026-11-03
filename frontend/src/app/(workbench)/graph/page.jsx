"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowUpRight, BookOpenCheck, CircleHelp, FileSearch, Map, PanelRight } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { chatService } from "@/services/chat.service";
import { useCitationStore } from "@/store/citationStore";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";

const STATUS_STYLE = {
  supported: "bg-emerald-50 text-emerald-800",
  partial: "bg-amber-50 text-amber-900",
  contradicted: "bg-rose-50 text-rose-800",
  unsupported: "bg-slate-100 text-slate-700",
  invalid_reference: "bg-slate-100 text-slate-700",
};

export default function ResearchMapPage() {
  const { conversations, isLoadingConversations } = useChat();
  const searchParams = useSearchParams();
  const [conversationId, setConversationId] = useState(searchParams.get("conversation_id") || "");
  const { setSources, setResearchTrace, isDrawerOpen, openDrawer, closeDrawer } = useCitationStore();
  useEffect(() => {
    if (!conversationId && conversations.length) setConversationId(conversations[0].id);
  }, [conversationId, conversations]);

  useEffect(() => {
    closeDrawer();
    setSources([]);
    setResearchTrace(null);
  }, [conversationId, closeDrawer, setSources, setResearchTrace]);

  const messageQuery = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => chatService.getMessages(conversationId, 1, 100),
    enabled: !!conversationId,
  });
  const messages = Array.isArray(messageQuery.data) ? messageQuery.data : messageQuery.data?.items || [];
  const savedResearch = useMemo(() => messages.flatMap((message, index) => {
    if (message.role !== "assistant" || !message.meta?.research) return [];
    const question = [...messages.slice(0, index)].reverse().find((item) => item.role === "user")?.content || "Research response";
    return [{ message, question, research: message.meta.research }];
  }), [messages]);

  const inspectSources = (entry) => {
    setSources(entry.message.sources || []);
    setResearchTrace(entry.research);
    openDrawer();
  };

  return (
    <div className="page-shell relative min-h-full space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--rl-border)] pb-5">
        <div>
          <p className="eyebrow text-[var(--rl-primary)]">Research Workspace</p>
          <h1 className="page-heading mt-1 flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><Map className="h-5 w-5" aria-hidden="true" /></span>Research Map</h1>
          <p className="page-description">Review saved questions, planned subquestions, and the evidence checks returned with each answer.</p>
        </div>
        <Link href={conversationId ? `/chat/${conversationId}` : "/chat"} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-[var(--rl-border)] bg-white px-4 text-sm font-medium text-[var(--rl-primary)] hover:bg-[var(--rl-tint)]">
          Open Research Desk <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </header>

      <section className="surface-card flex flex-wrap items-center gap-3 p-4">
        <label htmlFor="research-map-conversation" className="text-sm font-medium text-[var(--rl-ink)]">Saved conversation</label>
        <select id="research-map-conversation" value={conversationId} onChange={(event) => setConversationId(event.target.value)} disabled={isLoadingConversations || !conversations.length} className="min-h-10 min-w-0 flex-1 rounded-lg border border-[var(--rl-border)] bg-white px-3 text-sm text-[var(--rl-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-sky)]">
          {!conversations.length && <option value="">No saved conversations</option>}
          {conversations.map((conversation) => <option key={conversation.id} value={conversation.id}>{conversation.title || "Untitled research"}</option>)}
        </select>
      </section>

      {messageQuery.isError && <div role="alert" className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><AlertCircle className="h-4 w-4" />{messageQuery.error?.message || "Could not load this conversation."}</div>}
      {messageQuery.isLoading && <div className="surface-card h-28 animate-pulse" aria-label="Loading saved research" />}
      {!messageQuery.isLoading && !messageQuery.isError && savedResearch.length === 0 && <div className="surface-card px-6 py-14 text-center">
        <CircleHelp className="mx-auto h-8 w-8 text-[var(--rl-sky)]" aria-hidden="true" />
        <h2 className="mt-3 text-lg font-semibold text-[var(--rl-ink)]">No research checks saved here yet</h2>
        <p className="mx-auto mt-1 max-w-lg text-sm leading-6 text-[var(--rl-muted)]">Ask a question in the Research Desk. The map will show the plan and claim checks persisted with that answer when available.</p>
        <Link href={conversationId ? `/chat/${conversationId}` : "/chat"} className="mt-4 inline-flex min-h-10 items-center rounded-lg bg-[var(--rl-primary)] px-4 text-sm font-medium text-white hover:bg-[#1f659c]">Go to Research Desk</Link>
      </div>}

      <div className="space-y-5">
        {savedResearch.map((entry) => {
          const plan = entry.research.plan || {};
          const sufficiency = entry.research.sufficiency || {};
          const claims = entry.research.claim_verification?.items || [];
          const ledger = entry.research.evidence_ledger || [];
          return (
            <article key={entry.message.id} className="surface-card overflow-hidden">
              <div className="border-b border-[var(--rl-border)] px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="eyebrow text-[var(--rl-primary)]">Question · {plan.intent || "Research"}</p>
                  <button type="button" disabled={!entry.message.sources?.length} title={!entry.message.sources?.length ? "This saved answer has no citation records to inspect" : undefined} onClick={() => { inspectSources(entry); }} className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-[var(--rl-border)] px-3 text-xs font-medium text-[var(--rl-ink)] hover:bg-[var(--rl-tint)] disabled:cursor-not-allowed disabled:opacity-50"><PanelRight className="h-3.5 w-3.5" />Inspect evidence</button>
                </div>
                <h2 className="mt-2 text-lg font-semibold leading-7 text-[var(--rl-ink)]">{entry.question}</h2>
              </div>

              <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.7fr)]">
                <section>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--rl-ink)]"><BookOpenCheck className="h-4 w-4 text-[var(--rl-primary)]" />Research plan</h3>
                  {plan.subquestions?.length ? <ol className="mt-3 space-y-2">{plan.subquestions.map((subquestion, index) => <li key={`${subquestion}-${index}`} className="flex gap-2 text-sm leading-6 text-[var(--rl-muted)]"><span className="font-mono text-xs text-[var(--rl-primary)]">{index + 1}.</span><span>{subquestion}</span></li>)}</ol> : <p className="mt-2 text-sm text-[var(--rl-muted)]">No subquestions were recorded for this response.</p>}
                  {entry.research.plan && <p className="mt-3 text-xs text-[var(--rl-muted)]">Generated subquestions organize retrieval; they are not separate user-authored questions.</p>}
                </section>

                <section className="rounded-xl bg-[var(--rl-tint)] p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--rl-ink)]"><FileSearch className="h-4 w-4 text-[var(--rl-primary)]" />Evidence retrieval</h3>
                  <p className="mt-2 text-sm text-[var(--rl-muted)]">{ledger.length} evidence ledger entries recorded for this answer.</p>
                  {sufficiency.status && <p className="mt-2 text-xs text-[var(--rl-muted)]">Evidence check: <span className="font-medium text-[var(--rl-ink)]">{sufficiency.status}</span></p>}
                  {sufficiency.method && <p className="mt-2 text-xs leading-5 text-[var(--rl-muted)]">{sufficiency.method}</p>}
                </section>
              </div>

              {claims.length > 0 && <section className="border-t border-[var(--rl-border)] px-5 py-4">
                <h3 className="text-sm font-semibold text-[var(--rl-ink)]">Claim checks</h3>
                <ul className="mt-3 space-y-3">{claims.map((claim, index) => <li key={`${claim.claim_text}-${index}`} className="rounded-xl border border-[var(--rl-border)] p-3">
                  <div className="flex flex-wrap items-start gap-2"><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${STATUS_STYLE[claim.status] || "bg-slate-100 text-slate-700"}`}>{claim.status.replaceAll("_", " ")}</span><p className="min-w-0 flex-1 text-sm leading-6 text-[var(--rl-ink)]">{claim.claim_text}</p></div>
                  {claim.reason && <p className="mt-1.5 text-xs leading-5 text-[var(--rl-muted)]">{claim.reason}</p>}
                  {claim.source_ids?.length > 0 && <button type="button" onClick={() => inspectSources(entry)} className="mt-2 text-xs font-medium text-[var(--rl-primary)] underline underline-offset-4">Inspect {claim.source_ids.join(", ")}</button>}
                </li>)}</ul>
                <p className="mt-3 text-xs leading-5 text-[var(--rl-muted)]">{entry.research.claim_verification?.method || "Claim verification method not recorded."}</p>
              </section>}
            </article>
          );
        })}
      </div>

      {isDrawerOpen && <div role="dialog" aria-modal="true" aria-label="Evidence Trail" className="fixed inset-x-0 bottom-0 top-16 z-40 flex justify-end bg-slate-950/35" onClick={closeDrawer} onKeyDown={(event) => { if (event.key === "Escape") closeDrawer(); }}><div className="h-full w-[min(26rem,94vw)] shadow-xl" onClick={(event) => event.stopPropagation()}><SourceInspectorRail onClose={closeDrawer} /></div></div>}
    </div>
  );
}
