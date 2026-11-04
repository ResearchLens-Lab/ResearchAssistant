"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowDown, ArrowRight, ArrowUpRight, BookOpenCheck, CheckCircle2, CircleHelp, FileSearch, GitBranch, LoaderCircle, Map, PanelRight, Sparkles } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { chatService } from "@/services/chat.service";
import { useCitationStore } from "@/store/citationStore";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";
import { GroundedAnswer } from "@/components/chat/GroundedAnswer";

const STATUS_STYLE = {
  supported: "bg-emerald-50 text-emerald-800",
  partial: "bg-amber-50 text-amber-900",
  contradicted: "bg-rose-50 text-rose-800",
  unsupported: "bg-slate-100 text-slate-700",
  invalid_reference: "bg-slate-100 text-slate-700",
};

function buildResearchTurns(messages) {
  const turns = [];
  let pendingQuestion = null;
  for (const message of messages) {
    if (message.role === "user") {
      pendingQuestion = message;
    } else if (message.role === "assistant") {
      turns.push({
        id: message.id,
        question: pendingQuestion?.content || "Research response",
        userMessage: pendingQuestion,
        message,
        research: message.meta?.research || message.metadata?.research || {},
      });
      pendingQuestion = null;
    }
  }
  if (pendingQuestion) turns.push({ id: pendingQuestion.id, question: pendingQuestion.content, userMessage: pendingQuestion, message: null, research: {} });
  return turns;
}

export default function ResearchMapPage() {
  const { conversations, isLoadingConversations } = useChat();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [conversationId, setConversationId] = useState(searchParams.get("conversation_id") || "");
  const [summaryResult, setSummaryResult] = useState(null);
  const [summaryProgress, setSummaryProgress] = useState("");
  const { setSources, setResearchTrace, isDrawerOpen, openDrawer, closeDrawer } = useCitationStore();

  useEffect(() => {
    if (!conversationId && conversations.length) setConversationId(conversations[0].id);
  }, [conversationId, conversations]);

  useEffect(() => {
    closeDrawer();
    setSources([]);
    setResearchTrace(null);
    setSummaryResult(null);
    setSummaryProgress("");
  }, [conversationId, closeDrawer, setSources, setResearchTrace]);

  const conversationQuery = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => chatService.getConversation(conversationId),
    enabled: !!conversationId,
    staleTime: 30_000,
  });
  const messageQuery = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => chatService.getMessages(conversationId, 1, 100),
    enabled: !!conversationId,
  });
  const messages = Array.isArray(messageQuery.data) ? messageQuery.data : messageQuery.data?.items || [];
  const turns = useMemo(() => buildResearchTurns(messages), [messages]);
  const summaryMutation = useMutation({
    mutationFn: () => chatService.streamQuestion({
        conversation_id: conversationId,
        paper_ids: conversationQuery.data?.paper_ids || [],
        answer_mode: "DOCUMENTS_ONLY",
        question: "Summarize the selected source's main subject, core ideas, organization, and progression of concepts using its passages. For a textbook, cover multiple substantive sections when evidence supports it. If the passages cover only part of the source, label this a partial overview and name the sections represented. Cite every factual point and use no knowledge outside the selected sources.",
      }, (event) => {
        const status = {
          planning_started: "Planning the summary…",
          planning_completed: "Summary plan ready",
          retrieval_started: "Searching selected books…",
          additional_retrieval: "Checking for supporting passages…",
          sources_found: `Found ${event.data?.count ?? 0} evidence passages`,
          evidence_ready: "Evidence collected; drafting summary…",
          generation_started: "Writing the source-grounded summary…",
          verification_started: "Checking citations…",
          verification_completed: "Finalizing evidence checks…",
        };
        if (status[event.type]) setSummaryProgress(status[event.type]);
      }),
    onMutate: () => { setSummaryResult(null); setSummaryProgress("Starting research summary…"); },
    onSuccess: (result) => {
      setSummaryResult(result);
      queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onSettled: () => setSummaryProgress(""),
  });

  const inspectSources = (entry) => {
    setSources(entry.message?.sources || []);
    setResearchTrace(entry.research);
    openDrawer();
  };
  const scopedSources = (conversationQuery.data?.paper_ids || []).length;

  return (
    <div className="page-shell relative min-h-full space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--rl-border)] pb-5">
        <div>
          <p className="eyebrow text-[var(--rl-primary)]">Research Workspace</p>
          <h1 className="page-heading mt-1 flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><Map className="h-5 w-5" aria-hidden="true" /></span>Research Map</h1>
          <p className="page-description">Follow the conversation from question to answer, retrieval plan, and cited evidence.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => summaryMutation.mutate()} disabled={!conversationId || !scopedSources || summaryMutation.isPending} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-[var(--rl-primary)] px-4 text-sm font-medium text-white hover:bg-[#1f659c] disabled:cursor-not-allowed disabled:opacity-50" title={!scopedSources ? "Add an indexed source to this conversation first" : "Create a cited summary using the selected documents"}>
            {summaryMutation.isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {summaryMutation.isPending ? (summaryProgress || "Summarizing…") : "Summarize this research"}
          </button>
          <Link href={conversationId ? `/chat/${conversationId}` : "/chat"} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-[var(--rl-border)] bg-white px-4 text-sm font-medium text-[var(--rl-primary)] hover:bg-[var(--rl-tint)]">Open Research Desk <ArrowUpRight className="h-4 w-4" aria-hidden="true" /></Link>
        </div>
      </header>

      <section className="surface-card flex flex-wrap items-center gap-3 p-4">
        <label htmlFor="research-map-conversation" className="text-sm font-medium text-[var(--rl-ink)]">Saved conversation</label>
        <select id="research-map-conversation" value={conversationId} onChange={(event) => setConversationId(event.target.value)} disabled={isLoadingConversations || !conversations.length} className="min-h-10 min-w-0 flex-1 rounded-lg border border-[var(--rl-border)] bg-white px-3 text-sm text-[var(--rl-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rl-sky)]">
          {!conversations.length && <option value="">No saved conversations</option>}
          {conversations.map((conversation) => <option key={conversation.id} value={conversation.id}>{conversation.title || "Untitled research"}</option>)}
        </select>
        <span className="text-xs text-[var(--rl-muted)]">{turns.length} {turns.length === 1 ? "turn" : "turns"} · {scopedSources} selected {scopedSources === 1 ? "source" : "sources"}</span>
      </section>

      {messageQuery.isError && <div role="alert" className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><AlertCircle className="h-4 w-4" />{messageQuery.error?.message || "Could not load this conversation."}</div>}
      {summaryMutation.isError && <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{summaryMutation.error?.message || "The summary could not be generated. Please try again."}</span></div>}
      {summaryResult && <section className="surface-card border-l-4 border-l-[var(--rl-primary)] p-5" aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 text-lg font-semibold text-[var(--rl-ink)]"><Sparkles className="h-5 w-5 text-[var(--rl-primary)]" />Source-grounded summary</h2><p className="mt-1 text-xs text-[var(--rl-muted)]">Based only on retrieved passages from the selected source scope</p></div><button type="button" disabled={!summaryResult.sources?.length} onClick={() => { setSources(summaryResult.sources || []); setResearchTrace(summaryResult.metadata?.research || {}); openDrawer(); }} className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-[var(--rl-border)] px-3 text-xs font-medium text-[var(--rl-ink)] hover:bg-[var(--rl-tint)] disabled:cursor-not-allowed disabled:opacity-50"><PanelRight className="h-3.5 w-3.5" />View evidence ({summaryResult.sources?.length || 0})</button></div>
        {!summaryResult.sources?.length && <div role="status" className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">No passages could be cited for this summary. The answer below is an evidence limitation, not a verified overview of the book.</div>}
        <div className="mt-4 min-w-0 text-sm leading-7 text-[var(--rl-ink)]"><GroundedAnswer compact content={summaryResult.answer} sources={summaryResult.sources || []} /></div>
        <p className="mt-4 border-t border-[var(--rl-border)] pt-3 text-xs text-[var(--rl-muted)]">Saved to this conversation · {summaryResult.sources?.length || 0} cited passages · {summaryResult.metadata?.research?.evidence_count ?? 0} evidence records checked</p>
      </section>}
      {messageQuery.isLoading && <div className="surface-card h-28 animate-pulse" aria-label="Loading saved research" />}
      {!messageQuery.isLoading && !messageQuery.isError && turns.length === 0 && <div className="surface-card px-6 py-14 text-center">
        <CircleHelp className="mx-auto h-8 w-8 text-[var(--rl-sky)]" aria-hidden="true" />
        <h2 className="mt-3 text-lg font-semibold text-[var(--rl-ink)]">No research turns saved here yet</h2>
        <p className="mx-auto mt-1 max-w-lg text-sm leading-6 text-[var(--rl-muted)]">Ask a question in the Research Desk. Each saved turn will appear here with its answer, plan, and evidence trail.</p>
        <Link href={conversationId ? `/chat/${conversationId}` : "/chat"} className="mt-4 inline-flex min-h-10 items-center rounded-lg bg-[var(--rl-primary)] px-4 text-sm font-medium text-white hover:bg-[#1f659c]">Go to Research Desk</Link>
      </div>}

      <div className="space-y-1">
        {turns.map((entry, index) => {
          const plan = entry.research.plan || {};
          const sufficiency = entry.research.sufficiency || {};
          const claims = entry.research.claim_verification?.items || [];
          const ledger = entry.research.evidence_ledger || [];
          const sources = entry.message?.sources || [];
          return <div key={entry.id} className="relative pl-8 sm:pl-10">
            {index < turns.length - 1 && <div aria-hidden="true" className="absolute bottom-0 left-[13px] top-8 w-px bg-[var(--rl-border)] sm:left-[17px]" />}
            <span aria-hidden="true" className="absolute left-1 top-5 flex h-6 w-6 items-center justify-center rounded-full border-2 border-[var(--rl-primary)] bg-white text-[10px] font-semibold text-[var(--rl-primary)] sm:left-1.5">{index + 1}</span>
            <article className="surface-card mb-5 overflow-hidden">
              <div className="border-b border-[var(--rl-border)] px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="eyebrow flex items-center gap-1.5 text-[var(--rl-primary)]"><GitBranch className="h-3.5 w-3.5" />{entry.message ? `Turn ${index + 1} · ${plan.intent || "Research"}` : "Awaiting answer"}</p>
                  {entry.message && <button type="button" disabled={!sources.length} title={!sources.length ? "This saved answer has no citation records to inspect" : undefined} onClick={() => inspectSources(entry)} className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-[var(--rl-border)] px-3 text-xs font-medium text-[var(--rl-ink)] hover:bg-[var(--rl-tint)] disabled:cursor-not-allowed disabled:opacity-50"><PanelRight className="h-3.5 w-3.5" />Inspect evidence ({sources.length})</button>}
                </div>
                <h2 className="mt-2 text-lg font-semibold leading-7 text-[var(--rl-ink)]">{entry.question}</h2>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] font-medium text-[var(--rl-muted)]" aria-label={`Research flow: question to answer to ${sources.length} evidence passages`}>
                  <span className="rounded-full bg-[var(--rl-tint)] px-2.5 py-1 text-[var(--rl-primary)]">Question</span><ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                  <span className="rounded-full bg-[var(--rl-tint)] px-2.5 py-1 text-[var(--rl-primary)]">Answer</span><ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                  <span className="rounded-full bg-[var(--rl-tint)] px-2.5 py-1">{sources.length} evidence {sources.length === 1 ? "passage" : "passages"}</span>
                </div>
              </div>

              <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.7fr)]">
                <section>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--rl-ink)]"><BookOpenCheck className="h-4 w-4 text-[var(--rl-primary)]" />Answer & research path</h3>
                  {entry.message ? <p className="mt-2 line-clamp-5 whitespace-pre-wrap text-sm leading-6 text-[var(--rl-muted)]">{entry.message.content}</p> : <p className="mt-2 text-sm text-[var(--rl-muted)]">This question has no saved answer yet.</p>}
                  {plan.subquestions?.length > 0 && <><p className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--rl-muted)]">Planned retrieval branches</p><ul className="mt-2 space-y-2">{plan.subquestions.map((subquestion, subIndex) => <li key={`${subquestion}-${subIndex}`} className="flex items-start gap-2 text-sm leading-6 text-[var(--rl-muted)]"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--rl-sky)]" /><span>{subquestion}</span></li>)}</ul></>}
                </section>

                <section className="rounded-xl bg-[var(--rl-tint)] p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--rl-ink)]"><FileSearch className="h-4 w-4 text-[var(--rl-primary)]" />Evidence & verification</h3>
                  <p className="mt-2 text-sm text-[var(--rl-muted)]">{sources.length} cited passages{ledger.length ? ` · ${ledger.length} retrieval records` : ""}</p>
                  {sufficiency.status && <p className="mt-2 text-xs text-[var(--rl-muted)]">Evidence check: <span className="font-medium text-[var(--rl-ink)]">{sufficiency.status}</span></p>}
                  {sufficiency.method && <p className="mt-2 text-xs leading-5 text-[var(--rl-muted)]">{sufficiency.method}</p>}
                  {sources.length > 0 ? <div className="mt-3 flex flex-wrap gap-1.5">{sources.map((source, sourceIndex) => <button key={`${source.id || source.source_id || sourceIndex}`} type="button" onClick={() => inspectSources(entry)} className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-white px-2.5 py-1 text-xs font-medium text-sky-800 hover:border-sky-400"><CheckCircle2 className="h-3 w-3" />{source.source_id || source.id || `Source ${sourceIndex + 1}`}</button>)}</div> : <p className="mt-3 text-xs text-[var(--rl-muted)]">No cited passages were saved for this answer.</p>}
                </section>
              </div>

              {claims.length > 0 && <section className="border-t border-[var(--rl-border)] px-5 py-4">
                <h3 className="text-sm font-semibold text-[var(--rl-ink)]">Claim checks</h3>
                <ul className="mt-3 space-y-3">{claims.map((claim, claimIndex) => <li key={`${claim.claim_text}-${claimIndex}`} className="rounded-xl border border-[var(--rl-border)] p-3">
                  <div className="flex flex-wrap items-start gap-2"><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${STATUS_STYLE[claim.status] || "bg-slate-100 text-slate-700"}`}>{(claim.status || "unreviewed").replaceAll("_", " ")}</span><p className="min-w-0 flex-1 text-sm leading-6 text-[var(--rl-ink)]">{claim.claim_text}</p></div>
                  {claim.reason && <p className="mt-1.5 text-xs leading-5 text-[var(--rl-muted)]">{claim.reason}</p>}
                  {claim.source_ids?.length > 0 && <button type="button" onClick={() => inspectSources(entry)} className="mt-2 text-xs font-medium text-[var(--rl-primary)] underline underline-offset-4">Inspect {claim.source_ids.join(", ")}</button>}
                </li>)}</ul>
                <p className="mt-3 text-xs leading-5 text-[var(--rl-muted)]">{entry.research.claim_verification?.method || "Claim verification method not recorded."}</p>
              </section>}
            </article>
            {index < turns.length - 1 && <div aria-hidden="true" className="-mt-3 mb-2 flex h-4 items-center pl-0.5 text-[var(--rl-sky)]"><ArrowDown className="h-4 w-4" /></div>}
          </div>;
        })}
      </div>

      {isDrawerOpen && <div role="dialog" aria-modal="true" aria-label="Evidence Trail" className="fixed inset-x-0 bottom-0 top-16 z-40 flex justify-end bg-slate-950/35" onClick={closeDrawer} onKeyDown={(event) => { if (event.key === "Escape") closeDrawer(); }}><div className="h-full w-[min(26rem,94vw)] shadow-xl" onClick={(event) => event.stopPropagation()}><SourceInspectorRail onClose={closeDrawer} /></div></div>}
    </div>
  );
}
