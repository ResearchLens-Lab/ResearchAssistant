"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle, ArrowUpRight, BookOpen, CheckCircle2, CircleHelp, FileSearch,
  FileText, Focus, LoaderCircle, Map as MapIcon, Minus, Plus, Search, Sparkles, X,
} from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { chatService } from "@/services/chat.service";
import { papersService } from "@/services/papers.service";
import { knowledgeGraphService } from "@/services/knowledgeGraph.service";
import { openAuthenticatedPdfSource } from "@/services/documents.service";
import { useCitationStore } from "@/store/citationStore";
import { GroundedAnswer } from "@/components/chat/GroundedAnswer";
import { SourceInspectorRail } from "@/components/citations/SourceInspectorRail";

function buildResearchTurns(messages = []) {
  const turns = [];
  let pendingQuestion = null;
  let savedSummary = null;
  for (const message of messages) {
    if (message.role === "user") pendingQuestion = message;
    else if (message.role === "assistant") {
      const question = pendingQuestion?.content || "Research response";
      const summaryPrompt = question.toLowerCase().startsWith("summarize the selected source's main subject") || message.meta?.task === "summarize" || message.metadata?.task === "summarize" || question.trim() === "/summary";
      if (summaryPrompt) savedSummary = { answer: message.content, sources: message.sources || [], metadata: message.meta || message.metadata || {} };
      else turns.push({
          id: String(message.id), question, userMessage: pendingQuestion, message,
          research: message.meta?.research || message.metadata?.research || {},
        });
      pendingQuestion = null;
    }
  }
  if (pendingQuestion) turns.push({ id: String(pendingQuestion.id), question: pendingQuestion.content, userMessage: pendingQuestion, message: null, research: {} });
  return { turns, savedSummary };
}

function shortText(value, max = 48) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function messageTimestamp(message) {
  const value = message?.created_at || message?.createdAt || message?.timestamp;
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

function sourceKey(source, index) {
  return String(source.source_id || source.chunk_id || source.id || `${source.document_id || source.paper_id || source.filename || "source"}-${source.page_start || source.page || 1}-${index}`);
}

function displayTitle(title, turns) {
  const rawTitle = String(title || turns[0]?.question || "Research session").trim();
  const cleaned = rawTitle.replace(/^\/(?:table|pie|flowchart|compare|summary)\b\s*/i, "").trim();
  return cleaned ? cleaned[0].toLocaleUpperCase() + cleaned.slice(1) : "Research session";
}

function wrapWords(value, maxChars = 20, maxLines = 3) {
  const words = String(value || "").trim().split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length > maxChars && line) { lines.push(line); line = word; }
    else line = candidate;
    if (lines.length === maxLines) break;
  }
  if (line && lines.length < maxLines) lines.push(line);
  if (words.join(" ").length > lines.join(" ").length && lines.length) lines[lines.length - 1] = shortText(lines[lines.length - 1], maxChars - 1);
  return lines;
}

function makeMindMap(turns, title, summaryExists, width, height) {
  const center = { x: width / 2, y: height / 2 };
  const count = Math.max(turns.length, 1);
  const questionRadius = count <= 4 ? 88 : count <= 8 ? 76 : 62;
  const spacing = 190; // Spacing >= 180px for collision-free layout

  let questions = [];
  if (count <= 6) {
    const radius = Math.min(width * 0.38, height / 2 - questionRadius - 28, 195 + count * 12);
    questions = turns.map((turn, index) => {
      const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count;
      return { id: `question:${turn.id}`, type: "question", turn, index, x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius, angle, radius: questionRadius };
    });
  } else {
    const cols = Math.ceil(Math.sqrt(count));
    const startX = center.x - ((cols - 1) * spacing) / 2;
    const startY = center.y - ((Math.ceil(count / cols) - 1) * spacing) / 2;
    questions = turns.map((turn, index) => {
      const row = Math.floor(index / cols);
      const col = index % cols;
      const x = startX + col * spacing;
      const y = startY + row * spacing;
      const angle = Math.atan2(y - center.y, x - center.x);
      return { id: `question:${turn.id}`, type: "question", turn, index, x, y, angle, radius: questionRadius };
    });
  }

  const evidenceMap = new Map();
  turns.forEach((turn, index) => {
    (turn.message?.sources || []).forEach((source, sourceIndex) => {
      const id = sourceKey(source, sourceIndex);
      const record = evidenceMap.get(id) || { id: `evidence:${id}`, type: "evidence", source, turns: [], anchorTurn: turn.id, anchorIndex: sourceIndex };
      record.turns.push(turn.id);
      evidenceMap.set(id, record);
    });
  });

  const evidence = [...evidenceMap.values()].map((node) => {
    const question = questions.find((item) => item.turn.id === node.anchorTurn);
    if (count > 6) {
      const offsetAngle = (node.anchorIndex * Math.PI) / 3;
      const dist = 110;
      return {
        ...node,
        x: (question?.x ?? center.x) + Math.cos(offsetAngle) * dist,
        y: (question?.y ?? center.y) + Math.sin(offsetAngle) * dist,
      };
    }
    const localCount = question?.turn.message?.sources?.length || 1;
    const slot = node.anchorIndex - (localCount - 1) / 2;
    const tangentOffset = slot * Math.min(150, 600 / Math.max(localCount, 1));
    const inward = 42;
    const radial = question?.angle ?? 0;
    const tangent = radial + Math.PI / 2;
    return {
      ...node,
      x: (question?.x ?? center.x) - Math.cos(radial) * inward + Math.cos(tangent) * tangentOffset,
      y: (question?.y ?? center.y) - Math.sin(radial) * inward + Math.sin(tangent) * tangentOffset,
    };
  });
  const summaryAngle = -Math.PI / 2 + Math.PI / count;
  const summaryDist = count > 6 ? 220 : 155;
  const summary = summaryExists ? [{ id: "summary", type: "summary", x: center.x + Math.cos(summaryAngle) * summaryDist, y: center.y + Math.sin(summaryAngle) * summaryDist, title: "Research summary" }] : [];
  return { title: displayTitle(title, turns), center, width, height, questions, evidence, summary };
}

function curve(from, to, bend = 0) {
  const mx = (from.x + to.x) / 2;
  const my = (from.y + to.y) / 2;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.max(Math.hypot(dx, dy), 1);
  const offset = Math.min(54, length * 0.12) * (bend || 1);
  const cx = mx - (dy / length) * offset;
  const cy = my + (dx / length) * offset;
  return `M ${from.x} ${from.y} Q ${cx} ${cy} ${to.x} ${to.y}`;
}

export default function ResearchMapPage() {
  const { conversations = [], isLoadingConversations } = useChat();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const canvasRef = useRef(null);
  const svgRef = useRef(null);
  const [canvasSize, setCanvasSize] = useState({ width: 1200, height: 760 });
  const [conversationId, setConversationId] = useState(searchParams.get("conversation_id") || "");
  const [summaryResult, setSummaryResult] = useState(null);
  const [summaryProgress, setSummaryProgress] = useState("");
  const [selectedId, setSelectedId] = useState("session");
  const [hoveredId, setHoveredId] = useState(null);
  const [search, setSearch] = useState("");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [drag, setDrag] = useState(null);
  const [collapsed, setCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState("turns");
  const [selectedPaper, setSelectedPaper] = useState("all");
  const [selectedChapter, setSelectedChapter] = useState("all");
  const [selectedConcept, setSelectedConcept] = useState(null);
  const { setSources, setResearchTrace, isDrawerOpen, openDrawer, closeDrawer } = useCitationStore();

  const conceptNodesQuery = useQuery({
    queryKey: ["kg-nodes", search, selectedPaper],
    queryFn: () => knowledgeGraphService.getNodes({
      q: search,
      paper_id: selectedPaper !== "all" ? selectedPaper : undefined,
      limit: 120,
    }),
    enabled: activeTab === "concepts",
  });

  const papersQuery = useQuery({
    queryKey: ["papers-list"],
    queryFn: () => papersService.list(1, 50),
    enabled: activeTab === "concepts",
  });

  const conceptEvidenceQuery = useQuery({
    queryKey: ["kg-node-evidence", selectedConcept?.id],
    queryFn: () => knowledgeGraphService.getNodeEvidence(selectedConcept.id),
    enabled: !!selectedConcept?.id,
  });

  const conceptRelsQuery = useQuery({
    queryKey: ["kg-node-rels", selectedConcept?.id],
    queryFn: () => knowledgeGraphService.getNodeRelationships(selectedConcept.id),
    enabled: !!selectedConcept?.id,
  });

  useEffect(() => {
    const element = canvasRef.current;
    if (!element) return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setCanvasSize((current) => Math.abs(current.width - width) > 1 || Math.abs(current.height - height) > 1 ? { width, height } : current);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!conversationId && conversations.length) setConversationId(conversations[0].id);
  }, [conversationId, conversations]);
  useEffect(() => {
    closeDrawer(); setSources([]); setResearchTrace(null); setSummaryResult(null); setSummaryProgress(""); setSelectedId("session"); setZoom(1); setPan({ x: 0, y: 0 });
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
  const parsedMessages = useMemo(() => buildResearchTurns(messages), [messages]);
  const turns = parsedMessages.turns;
  const activeSummary = summaryResult || parsedMessages.savedSummary;
  const scopedSources = (conversationQuery.data?.paper_ids || []).length;
  const summaryMutation = useMutation({
    mutationFn: async () => {
      const paperId = conversationQuery.data?.paper_ids?.[0];
      if (paperId) {
        return papersService.summarize(paperId);
      }
      return chatService.streamQuestion({
        conversation_id: conversationId,
        paper_ids: conversationQuery.data?.paper_ids || [],
        answer_mode: "DOCUMENTS_ONLY",
        question: "/summary",
      });
    },
    onMutate: () => { setSummaryResult(null); setSummaryProgress("Generating summary…"); },
    onSuccess: (result) => { setSummaryResult(result); queryClient.invalidateQueries({ queryKey: ["messages", conversationId] }); queryClient.invalidateQueries({ queryKey: ["conversations"] }); },
    onSettled: () => setSummaryProgress(""),
  });

  const map = useMemo(() => makeMindMap(turns, conversationQuery.data?.title, !!activeSummary, canvasSize.width, canvasSize.height), [turns, conversationQuery.data?.title, activeSummary, canvasSize]);

  const rawConcepts = Array.isArray(conceptNodesQuery.data) ? conceptNodesQuery.data : [];
  const filteredConcepts = useMemo(() => {
    return rawConcepts.filter((c) => {
      if (selectedPaper !== "all") {
        const pId = c.metadata_json?.paper_id || c.metadata?.paper_id;
        if (pId && pId !== selectedPaper) return false;
      }
      return true;
    });
  }, [rawConcepts, selectedPaper]);

  const conceptMap = useMemo(() => {
    const center = { x: canvasSize.width / 2, y: canvasSize.height / 2 };
    const count = filteredConcepts.length;
    if (count === 0) return { nodes: [], edges: [], center };

    const radius = Math.min(canvasSize.width * 0.38, canvasSize.height / 2 - 80, 180 + count * 10);
    const nodes = filteredConcepts.map((c, i) => {
      const angle = -Math.PI / 2 + (Math.PI * 2 * i) / count;
      const occ = c.metadata_json?.occurrence_count || c.occurrence_count || 1;
      const r = Math.min(48, Math.max(26, 20 + occ * 3));
      return {
        id: c.id,
        concept: c,
        name: c.canonical_name,
        type: c.node_type || "CONCEPT",
        x: center.x + Math.cos(angle) * (i % 2 === 0 ? radius : radius * 0.72),
        y: center.y + Math.sin(angle) * (i % 2 === 0 ? radius : radius * 0.72),
        r,
      };
    });

    const edges = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const descA = (a.concept.description || "").toLowerCase();
        const nameB = a.concept.canonical_name.toLowerCase();
        if (
          descA.includes(nameB) ||
          (a.concept.first_document_id &&
            a.concept.first_document_id === b.concept.first_document_id &&
            Math.abs(i - j) <= 2)
        ) {
          edges.push({
            id: `${a.id}-${b.id}`,
            from: a,
            to: b,
            type: descA.includes("is a")
              ? "specializes"
              : descA.includes("see section")
              ? "references"
              : "defined_in",
          });
        }
      }
    }
    return { nodes, edges, center };
  }, [filteredConcepts, canvasSize]);
  const allNodes = [...map.questions, ...map.evidence, ...map.summary];
  const selectedNode = selectedId === "session" ? { id: "session", type: "session" } : allNodes.find((node) => node.id === selectedId) || null;
  const hoveredNode = allNodes.find((node) => node.id === hoveredId) || null;
  const selectedTurn = selectedNode?.type === "question" ? selectedNode.turn : selectedNode?.type === "evidence" ? turns.find((turn) => turn.id === selectedNode.turns[0]) : null;
  const matchingIds = useMemo(() => {
    const query = search.trim().toLowerCase();
    return new Set(query ? map.questions.filter(({ turn }) => turn.question.toLowerCase().includes(query)).map(({ id }) => id) : []);
  }, [map.questions, search]);

  const inspectSources = useCallback((entry) => {
    if (!entry) return;
    setSources(entry.message?.sources || []); setResearchTrace(entry.research || {}); openDrawer();
  }, [setSources, setResearchTrace, openDrawer]);
  const focusNode = (node) => { setSelectedId(node.id); if (node.type === "evidence") setSelectedId(node.id); };
  const fitView = () => {
    const boundsNodes = [...map.questions.map((node) => ({ x: node.x, y: node.y, rx: node.radius, ry: node.radius })), ...map.evidence.map((node) => ({ x: node.x, y: node.y, rx: 82, ry: 38 })), ...map.summary.map((node) => ({ x: node.x, y: node.y, rx: 60, ry: 60 })), { x: map.center.x, y: map.center.y, rx: 120, ry: 120 }];
    const left = Math.min(...boundsNodes.map((node) => node.x - node.rx));
    const right = Math.max(...boundsNodes.map((node) => node.x + node.rx));
    const top = Math.min(...boundsNodes.map((node) => node.y - node.ry));
    const bottom = Math.max(...boundsNodes.map((node) => node.y + node.ry));
    const scale = Math.min(1.25, (map.width - 40) / Math.max(1, right - left), (map.height - 40) / Math.max(1, bottom - top));
    setZoom(scale);
    setPan({ x: (map.center.x - (left + right) / 2) * scale, y: (map.center.y - (top + bottom) / 2) * scale });
  };
  useEffect(() => { fitView(); }, [conversationId, canvasSize.width, canvasSize.height, turns.length, map.evidence.length, map.summary.length]);
  const zoomBy = (factor) => setZoom((current) => Math.min(2.4, Math.max(0.45, current * factor)));
  const handlePointerDown = (event) => {
    if (event.target === svgRef.current || event.target.dataset?.mapBackground === "true") {
      event.currentTarget.setPointerCapture(event.pointerId);
      setDrag({ x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y });
    }
  };
  const handlePointerMove = (event) => {
    if (drag) {
      const rect = svgRef.current?.getBoundingClientRect();
      const sx = rect?.width ? map.width / rect.width : 1;
      const sy = rect?.height ? map.height / rect.height : 1;
      setPan({ x: drag.panX + (event.clientX - drag.x) * sx, y: drag.panY + (event.clientY - drag.y) * sy });
    }
  };

  useEffect(() => {
    const firstMatch = map.questions.find((node) => matchingIds.has(node.id));
    if (firstMatch && search.trim()) {
      setSelectedId(firstMatch.id);
      setZoom(1.15);
      setPan({ x: (map.center.x - firstMatch.x) * 1.15, y: (map.center.y - firstMatch.y) * 1.15 });
    }
  }, [matchingIds, search, map]);

  const openEvidence = async (source) => {
    if (!source) return;
    const excerpt = source.evidence_excerpt || source.text || source.passage || "";
    await openAuthenticatedPdfSource(source, excerpt);
  };

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden px-4 py-3 sm:px-6">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--rl-selected)] text-[var(--rl-primary)]"><MapIcon className="h-5 w-5" /></span>
          <div className="min-w-0"><p className="eyebrow text-[var(--rl-primary)]">Research workspace</p><h1 className="truncate text-xl font-semibold text-[var(--rl-ink)]">{map.title}</h1><p className="text-xs text-[var(--rl-muted)]">{turns.length} {turns.length === 1 ? "question" : "questions"} · {map.evidence.length} cited sources</p></div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-[var(--rl-border)] bg-slate-100 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveTab("turns")}
              className={`rounded-md px-3 py-1.5 transition-colors ${activeTab === "turns" ? "bg-white font-semibold text-[var(--rl-primary)] shadow-sm" : "text-[var(--rl-muted)] hover:text-[var(--rl-ink)]"}`}
            >
              Research Map
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("concepts")}
              className={`rounded-md px-3 py-1.5 transition-colors ${activeTab === "concepts" ? "bg-white font-semibold text-[var(--rl-primary)] shadow-sm" : "text-[var(--rl-muted)] hover:text-[var(--rl-ink)]"}`}
            >
              Concepts
            </button>
          </div>
          {activeTab === "turns" ? (
            <>
              <button type="button" onClick={() => summaryMutation.mutate()} disabled={!conversationId || !scopedSources || summaryMutation.isPending} className="inline-flex h-9 items-center gap-2 rounded-lg bg-[var(--rl-primary)] px-3 text-xs font-medium text-white hover:bg-[#185ea8] disabled:opacity-50" title={!scopedSources ? "Add an indexed source to this conversation first" : "Create a cited summary using selected documents"}>
                {summaryMutation.isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{summaryMutation.isPending ? summaryProgress || "Summarizing…" : "Summarize"}
              </button>
              <Link href={conversationId ? `/chat/${conversationId}` : "/chat"} className="inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--rl-border)] bg-white px-3 text-xs font-medium text-[var(--rl-primary)] hover:bg-[var(--rl-tint)]">Open Research Desk <ArrowUpRight className="h-4 w-4" /></Link>
              <select aria-label="Saved conversation" value={conversationId} onChange={(event) => setConversationId(event.target.value)} disabled={isLoadingConversations || !conversations.length} className="h-9 max-w-[260px] min-w-[170px] rounded-lg border border-[var(--rl-border)] bg-white px-3 text-xs text-[var(--rl-ink)]">
                {!conversations.length && <option value="">No saved conversations</option>}
                {conversations.map((conversation) => <option key={conversation.id} value={conversation.id}>{conversation.title || "Untitled research"}</option>)}
              </select>
            </>
          ) : (
            <select aria-label="Filter by Paper" value={selectedPaper} onChange={(event) => setSelectedPaper(event.target.value)} className="h-9 max-w-[220px] rounded-lg border border-[var(--rl-border)] bg-white px-3 text-xs text-[var(--rl-ink)]">
              <option value="all">All Papers</option>
              {(papersQuery.data?.items || []).map((paper) => <option key={paper.id} value={paper.id}>{shortText(paper.title, 24)}</option>)}
            </select>
          )}
        </div>
      </header>

      {messageQuery.isError && <div role="alert" className="mt-2 flex shrink-0 items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-800"><AlertCircle className="h-4 w-4" />{messageQuery.error?.message || "Could not load this conversation."}</div>}
      {summaryMutation.isError && <div role="alert" className="mt-2 flex shrink-0 items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-800"><AlertCircle className="h-4 w-4" />{summaryMutation.error?.message || "The summary could not be generated."}</div>}

      <section className="relative mt-2 flex min-h-0 flex-1 overflow-hidden rounded-xl border border-[var(--rl-border)] bg-white shadow-sm" aria-label="Interactive research mind map">
        {activeTab === "concepts" ? (
          conceptNodesQuery.isLoading ? (
            <div className="m-auto flex items-center gap-2 text-sm text-[var(--rl-muted)]">
              <LoaderCircle className="h-4 w-4 animate-spin" />Loading concept graph…
            </div>
          ) : filteredConcepts.length === 0 ? (
            <div className="m-auto max-w-md px-6 text-center">
              <CircleHelp className="mx-auto h-9 w-9 text-[var(--rl-sky)]" />
              <h2 className="mt-3 text-base font-semibold text-[var(--rl-ink)]">
                {selectedPaper !== "all" ? "No concepts for this project" : "No concepts found"}
              </h2>
              <p className="mt-1 text-sm text-[var(--rl-muted)]">
                {selectedPaper !== "all"
                  ? "Select 'All Papers' or upload and index documents in this project to extract concepts."
                  : "Extracted concepts and relationships will appear here when documents are indexed."}
              </p>
            </div>
          ) : (
            <>
              <div ref={canvasRef} className="relative min-w-0 flex-1 overflow-hidden bg-[#f8fbfe]">
                <div className="absolute left-3 top-3 z-20 flex items-center gap-1 rounded-xl border border-[var(--rl-border)] bg-white/95 p-1 shadow-sm backdrop-blur-sm">
                  <label className="relative block w-40 sm:w-52">
                    <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-[var(--rl-muted)]" />
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Find a concept"
                      aria-label="Search concepts"
                      className="h-8 w-full rounded-lg bg-transparent pl-8 pr-2 text-xs outline-none focus:ring-2 focus:ring-[var(--rl-sky)]"
                    />
                  </label>
                  <span className="h-5 w-px bg-slate-200" />
                  <button type="button" onClick={() => zoomBy(1.2)} className="map-control" aria-label="Zoom in" title="Zoom in"><Plus className="h-4 w-4" /></button>
                  <button type="button" onClick={() => zoomBy(1 / 1.2)} className="map-control" aria-label="Zoom out" title="Zoom out"><Minus className="h-4 w-4" /></button>
                  <button type="button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); setSelectedConcept(null); }} className="map-control" aria-label="Reset map view" title="Reset view"><MapIcon className="h-4 w-4" /></button>
                </div>

                <svg
                  ref={svgRef}
                  viewBox={`0 0 ${conceptMap.center.x * 2 || 1200} ${conceptMap.center.y * 2 || 760}`}
                  className={`h-full w-full touch-none ${drag ? "cursor-grabbing" : "cursor-grab"}`}
                  role="img"
                  aria-label="Concept graph of algorithmic corpus"
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={() => setDrag(null)}
                  onPointerCancel={() => setDrag(null)}
                  onWheel={(event) => { if (event.deltaY) zoomBy(event.deltaY < 0 ? 1.08 : 1 / 1.08); }}
                >
                  <defs>
                    <pattern id="concept-dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#dceaf5" /></pattern>
                    <filter id="concept-node-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="#28628f" floodOpacity="0.12" /></filter>
                  </defs>
                  <rect data-map-background="true" width={conceptMap.center.x * 2 || 1200} height={conceptMap.center.y * 2 || 760} fill="url(#concept-dots)" />
                  <g transform={`translate(${pan.x} ${pan.y}) translate(${conceptMap.center.x} ${conceptMap.center.y}) scale(${zoom}) translate(${-conceptMap.center.x} ${-conceptMap.center.y})`}>
                    {/* Relation edges */}
                    {conceptMap.edges.map((edge) => (
                      <g key={edge.id}>
                        <path
                          d={curve(edge.from, edge.to, 0.5)}
                          fill="none"
                          stroke={edge.type === "specializes" ? "#9333ea" : edge.type === "references" ? "#0284c7" : "#0d9488"}
                          strokeWidth="2"
                          strokeDasharray={edge.type === "references" ? "4 4" : "none"}
                        />
                      </g>
                    ))}

                    {/* Concept nodes */}
                    {conceptMap.nodes.map((node) => {
                      const isSelected = selectedConcept?.id === node.id;
                      return (
                        <g
                          key={node.id}
                          tabIndex={0}
                          role="button"
                          aria-label={`Concept: ${node.name}`}
                          onClick={() => setSelectedConcept(node.concept)}
                          className="cursor-pointer outline-none"
                        >
                          <circle
                            cx={node.x}
                            cy={node.y}
                            r={node.r + (isSelected ? 4 : 0)}
                            fill={isSelected ? "#e0f2fe" : "white"}
                            stroke={isSelected ? "#0284c7" : "#0ea5e9"}
                            strokeWidth={isSelected ? 3.5 : 2}
                            filter="url(#concept-node-shadow)"
                          />
                          <text
                            x={node.x}
                            y={node.y + 4}
                            textAnchor="middle"
                            className="fill-slate-800 text-[11px] font-semibold"
                          >
                            {shortText(node.name, 16)}
                          </text>
                          <title>{node.name} ({node.type})</title>
                        </g>
                      );
                    })}
                  </g>
                </svg>
              </div>

              {/* Concept Details Drawer */}
              {selectedConcept && (
                <aside className="absolute inset-y-0 right-0 z-10 flex w-[min(24rem,32%)] shrink-0 flex-col border-l border-[var(--rl-border)] bg-white shadow-xl max-md:w-[min(24rem,90vw)] md:static md:shadow-none" aria-label="Concept details">
                  <div className="flex shrink-0 items-center justify-between border-b border-[var(--rl-border)] px-4 py-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-[var(--rl-ink)]">
                      <BookOpen className="h-4 w-4 text-[var(--rl-primary)]" />
                      Concept Details
                    </div>
                    <button type="button" onClick={() => setSelectedConcept(null)} aria-label="Close details" className="rounded-md p-1 text-slate-500 hover:bg-slate-100">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-4">
                    <div>
                      <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-800 uppercase tracking-wide">
                        {selectedConcept.node_type || "CONCEPT"}
                      </span>
                      <h2 className="mt-2 text-base font-semibold leading-6 text-[var(--rl-ink)]">
                        {selectedConcept.canonical_name}
                      </h2>
                    </div>

                    <div className="rounded-lg border border-[var(--rl-border)] bg-slate-50 p-3">
                      <p className="text-xs font-semibold text-slate-700">Definition / Description</p>
                      <p className="mt-1 text-xs leading-5 text-slate-600">
                        {selectedConcept.description || "Identified concept in algorithmic corpus."}
                      </p>
                    </div>

                    {/* Citations / Occurrences */}
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--rl-muted)]">
                        Corpus Occurrences
                      </h3>
                      <div className="mt-2 space-y-2">
                        {(conceptEvidenceQuery.data || []).map((ev, idx) => (
                          <div key={ev.id || idx} className="rounded-lg border border-[var(--rl-border)] bg-white p-3 shadow-xs">
                            <p className="text-xs font-semibold text-[var(--rl-ink)]">
                              Page {ev.page_number} {ev.section_id ? `· ${ev.section_id}` : ""}
                            </p>
                            <p className="mt-1 text-xs text-slate-600 line-clamp-3">
                              {ev.exact_text}
                            </p>
                            <button
                              type="button"
                              onClick={() => openEvidence({ document_id: ev.source_document_id, page_start: ev.page_number, text: ev.exact_text })}
                              className="mt-2 inline-flex h-7 items-center gap-1.5 rounded-md bg-[var(--rl-primary)] px-2.5 text-[11px] font-medium text-white hover:bg-[#185ea8]"
                            >
                              <FileText className="h-3 w-3" />Open PDF at cited page
                            </button>
                          </div>
                        ))}
                        {(!conceptEvidenceQuery.data || conceptEvidenceQuery.data.length === 0) && (
                          <p className="text-xs text-[var(--rl-muted)]">No explicit occurrences found.</p>
                        )}
                      </div>
                    </div>

                    {/* Relationships */}
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--rl-muted)]">
                        Relations
                      </h3>
                      <div className="mt-2 space-y-1.5">
                        {((conceptRelsQuery.data?.relationships) || []).map((rel, idx) => (
                          <div key={rel.id || idx} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-xs">
                            <span className="font-medium text-slate-700">{rel.target_canonical_name || "Related"}</span>
                            <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">{rel.relationship_type}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </aside>
              )}
            </>
          )
        ) : messageQuery.isLoading ? (
          <div className="m-auto flex items-center gap-2 text-sm text-[var(--rl-muted)]"><LoaderCircle className="h-4 w-4 animate-spin" />Loading saved research…</div>
        ) : turns.length === 0 ? (
          <div className="m-auto max-w-md px-6 text-center"><CircleHelp className="mx-auto h-9 w-9 text-[var(--rl-sky)]" /><h2 className="mt-3 text-base font-semibold text-[var(--rl-ink)]">No questions to map yet</h2><p className="mt-1 text-sm text-[var(--rl-muted)]">Ask a question in the Research Desk and your saved questions and cited evidence will appear here.</p><Link href={conversationId ? `/chat/${conversationId}` : "/chat"} className="mt-4 inline-flex h-9 items-center rounded-lg bg-[var(--rl-primary)] px-3 text-sm text-white">Open Research Desk</Link></div>
        ) : (
          <>
          <div ref={canvasRef} className="relative min-w-0 flex-1 overflow-hidden bg-[#f8fbfe]">
            <div className="absolute left-3 top-3 z-20 flex items-center gap-1 rounded-xl border border-[var(--rl-border)] bg-white/95 p-1 shadow-sm backdrop-blur-sm">
              <label className="relative block w-40 sm:w-52"><Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-[var(--rl-muted)]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a question" aria-label="Search questions" className="h-8 w-full rounded-lg bg-transparent pl-8 pr-2 text-xs outline-none focus:ring-2 focus:ring-[var(--rl-sky)]" /></label>
              <span className="h-5 w-px bg-slate-200" />
              <button type="button" onClick={() => zoomBy(1.2)} className="map-control" aria-label="Zoom in" title="Zoom in"><Plus className="h-4 w-4" /></button>
              <button type="button" onClick={() => zoomBy(1 / 1.2)} className="map-control" aria-label="Zoom out" title="Zoom out"><Minus className="h-4 w-4" /></button>
              <button type="button" onClick={fitView} className="map-control" aria-label="Fit map to screen" title="Fit to screen"><Focus className="h-4 w-4" /></button>
              <button type="button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); setSelectedId("session"); }} className="map-control" aria-label="Reset map view" title="Reset view"><MapIcon className="h-4 w-4" /></button>
              <button type="button" onClick={() => setCollapsed((value) => !value)} className={`map-control ${collapsed ? "!bg-[var(--rl-selected)] !text-[var(--rl-primary)]" : ""}`} aria-pressed={collapsed} title={collapsed ? "Expand evidence branches" : "Collapse evidence branches"}><BookOpen className="h-4 w-4" /></button>
            </div>
            <svg ref={svgRef} viewBox={`0 0 ${map.width} ${map.height}`} className={`h-full w-full touch-none ${drag ? "cursor-grabbing" : "cursor-grab"}`} role="img" aria-label="Radial map of this research conversation" onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={() => setDrag(null)} onPointerCancel={() => setDrag(null)} onWheel={(event) => { if (event.deltaY) zoomBy(event.deltaY < 0 ? 1.08 : 1 / 1.08); }}>
              <defs><pattern id="research-dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#dceaf5" /></pattern><filter id="map-node-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="#28628f" floodOpacity="0.12" /></filter></defs>
              <rect data-map-background="true" width={map.width} height={map.height} fill="url(#research-dots)" />
              <g transform={`translate(${pan.x} ${pan.y}) translate(${map.center.x} ${map.center.y}) scale(${zoom}) translate(${-map.center.x} ${-map.center.y})`}>
                {/* All connectors are drawn first so they stay behind their nodes. */}
                {map.questions.map((node) => {
                  const active = selectedId === node.id || (selectedNode?.type === "evidence" && selectedNode.turns.includes(node.turn.id));
                  return <path key={`root-${node.id}`} d={curve(map.center, node, node.index % 2 ? -1 : 1)} fill="none" stroke={active ? "#1d6fc4" : "#92c8ee"} strokeOpacity={selectedId && selectedId !== "session" && !active ? 0.25 : 1} strokeWidth={active ? 3 : 2} strokeDasharray="3 8" />;
                })}
                {!collapsed && map.evidence.map((node) => node.turns.map((turnId, index) => {
                  const question = map.questions.find((item) => item.turn.id === turnId);
                  const active = selectedId === node.id || (selectedNode?.type === "question" && selectedNode.turn.id === turnId);
                  return question ? <path key={`${node.id}-${turnId}`} d={curve(question, node, index % 2 ? -1 : 1)} fill="none" stroke={active ? "#1d6fc4" : "#bdd9ef"} strokeOpacity={selectedId && selectedId !== "session" && !active ? 0.18 : 1} strokeWidth={active ? 2.5 : 1.5} strokeDasharray="2 7" /> : null;
                }))}
                {map.summary.map((node) => <path key="summary-connector" d={curve(map.center, node)} fill="none" stroke="#69a8d8" strokeWidth="2" strokeDasharray="4 7" />)}

                <g tabIndex={0} role="button" aria-label={`Research session: ${map.title}. ${turns.length} questions.`} onClick={() => setSelectedId("session")} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId("session"); } }} className="cursor-pointer">
                  <circle cx={map.center.x} cy={map.center.y} r="116" fill="#eaf5fd" stroke="#1d6fc4" strokeWidth="3" filter="url(#map-node-shadow)" />
                  <circle cx={map.center.x} cy={map.center.y} r="102" fill="white" stroke="#b9dcf5" strokeWidth="1.5" />
                  <text x={map.center.x} y={map.center.y - 24} textAnchor="middle" className="fill-[#1d6fc4] text-[12px] font-semibold tracking-[2px]">RESEARCH SESSION</text>
                  <text x={map.center.x} y={map.center.y + 5} textAnchor="middle" className="fill-slate-900 text-[19px] font-semibold">{shortText(map.title, 23)}</text>
                  <text x={map.center.x} y={map.center.y + 32} textAnchor="middle" className="fill-slate-600 text-[13px]">{turns.length} {turns.length === 1 ? "question" : "questions"}</text>
                  <text x={map.center.x} y={map.center.y + 54} textAnchor="middle" className="fill-slate-500 text-[12px]">{map.evidence.length} cited sources</text>
                </g>

                {map.questions.map((node) => {
                  const selected = selectedId === node.id;
                  const match = matchingIds.has(node.id);
                  const radius = node.radius;
                  const questionLines = wrapWords(node.turn.question, 20, 3);
                  const answerPreview = shortText(node.turn.message?.content || "Awaiting saved answer", 28);
                  const connected = selectedId === node.id || (selectedNode?.type === "evidence" && selectedNode.turns.includes(node.turn.id));
                  return <g key={node.id} tabIndex={0} role="button" aria-label={`Turn ${node.index + 1}: ${node.turn.question}`} onClick={() => focusNode(node)} onMouseEnter={() => setHoveredId(node.id)} onMouseLeave={() => setHoveredId((current) => current === node.id ? null : current)} onFocus={() => setHoveredId(node.id)} onBlur={() => setHoveredId(null)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); focusNode(node); } }} className="cursor-pointer outline-none transition-opacity" opacity={selectedId && selectedId !== "session" && !connected ? 0.3 : 1}>
                    <circle cx={node.x} cy={node.y} r={radius + (selected ? 5 : 0)} fill={selected ? "#e5f3fc" : match ? "#eff8ff" : "white"} stroke={selected || match ? "#1d6fc4" : "#9bc9ea"} strokeWidth={selected ? 4 : match ? 3 : 2} filter="url(#map-node-shadow)" />
                    <text x={node.x} y={node.y - 51} textAnchor="middle" className="fill-[#1d6fc4] text-[11px] font-semibold tracking-[1px]">TURN {node.index + 1}</text>
                    <text x={node.x} y={node.y - 27} textAnchor="middle" className="fill-slate-800 text-[14px] font-semibold">{questionLines.map((line, lineIndex) => <tspan key={lineIndex} x={node.x} dy={lineIndex === 0 ? 0 : 17}>{line}</tspan>)}</text>
                    <text x={node.x} y={node.y + 39} textAnchor="middle" className="fill-slate-500 text-[11px]">{answerPreview}</text>
                    <text x={node.x} y={node.y + 58} textAnchor="middle" className="fill-[#1d6fc4] text-[11px] font-medium">{(node.turn.message?.sources || []).length} cited</text>
                    <title>{node.turn.question}</title>
                  </g>;
                })}

                {!collapsed && map.evidence.map((node) => {
                  const selected = selectedId === node.id;
                  const filename = node.source.filename || node.source.paper_title || node.source.title || "Cited document";
                  const pageStart = node.source.page_start || node.source.page;
                  const pageEnd = node.source.page_end || pageStart;
                  const pages = pageStart ? `p. ${pageStart}${pageEnd && pageEnd !== pageStart ? `–${pageEnd}` : ""}` : "page unavailable";
                  const connected = selectedId === node.id || (selectedNode?.type === "question" && node.turns.includes(selectedNode.turn.id)) || (selectedNode?.type === "evidence" && selectedNode.turns.some((turnId) => node.turns.includes(turnId)));
                  return <g key={node.id} tabIndex={0} role="button" aria-label={`${filename}, ${pages}`} onClick={() => focusNode(node)} onMouseEnter={() => setHoveredId(node.id)} onMouseLeave={() => setHoveredId((current) => current === node.id ? null : current)} onFocus={() => setHoveredId(node.id)} onBlur={() => setHoveredId(null)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); focusNode(node); } }} className="cursor-pointer transition-opacity" opacity={selectedId && selectedId !== "session" && !connected ? 0.3 : 1}>
                    <rect x={node.x - 76} y={node.y - 34} width="152" height="68" rx="14" fill={selected ? "#e5f3fc" : "white"} stroke={selected ? "#1d6fc4" : "#b7d7ef"} strokeWidth={selected ? 3 : 1.5} filter="url(#map-node-shadow)" />
                    <text x={node.x} y={node.y - 5} textAnchor="middle" className="fill-slate-800 text-[11px] font-semibold">{shortText(filename, 23)}</text>
                    <text x={node.x} y={node.y + 16} textAnchor="middle" className="fill-[#1d6fc4] text-[11px] font-medium">{pages}</text>
                    <title>{filename} · {pages}</title>
                  </g>;
                })}

                {map.summary.map((node) => <g key={node.id} tabIndex={0} role="button" aria-label="Research summary" onClick={() => setSelectedId(node.id)} onKeyDown={(event) => { if (event.key === "Enter") setSelectedId(node.id); }} className="cursor-pointer">
                  <circle cx={node.x} cy={node.y} r="58" fill="#f0f7fd" stroke="#7db7e2" strokeWidth="2.5" filter="url(#map-node-shadow)" /><text x={node.x} y={node.y - 4} textAnchor="middle" className="fill-[#1d6fc4] text-[13px] font-semibold">Summary</text><text x={node.x} y={node.y + 17} textAnchor="middle" className="fill-slate-500 text-[11px]">{activeSummary?.sources?.length || 0} passages</text>
                </g>)}
              </g>
            </svg>

            {hoveredNode && <div className="pointer-events-none absolute right-3 top-3 z-10 w-[min(24rem,calc(100%-1.5rem))] rounded-xl border border-[var(--rl-border)] bg-white/95 p-3 shadow-md backdrop-blur-sm" role="status">
              {hoveredNode.type === "question" ? <><p className="text-xs font-semibold text-[var(--rl-ink)]">Turn {hoveredNode.index + 1} · {hoveredNode.turn.question}</p><p className="mt-1 line-clamp-3 text-xs leading-5 text-[var(--rl-muted)]">{hoveredNode.turn.message?.content || "No saved answer yet."}</p><p className="mt-1 text-[11px] text-[var(--rl-muted)]">{messageTimestamp(hoveredNode.turn.userMessage)}{messageTimestamp(hoveredNode.turn.userMessage) ? " · " : ""}{(hoveredNode.turn.message?.sources || []).length} cited passages</p></> : hoveredNode.type === "evidence" ? <><p className="text-xs font-semibold text-[var(--rl-ink)]">{hoveredNode.source.filename || hoveredNode.source.paper_title || "Cited source"}</p><p className="mt-1 text-xs text-[var(--rl-muted)]">Page {hoveredNode.source.page_start || hoveredNode.source.page || "not recorded"}</p></> : <p className="text-xs font-semibold text-[var(--rl-ink)]">Research summary</p>}
            </div>}
          </div>

          {selectedNode && <aside className="absolute inset-y-0 right-0 z-10 flex w-[min(23rem,30%)] shrink-0 flex-col border-l border-[var(--rl-border)] bg-white shadow-[-10px_0_28px_-24px_rgba(15,53,87,0.45)] max-md:w-[min(23rem,88vw)] md:static md:shadow-none" aria-label="Selected map item details">
            <div className="flex shrink-0 items-center justify-between border-b border-[var(--rl-border)] px-4 py-3"><div className="flex items-center gap-2 text-sm font-semibold text-[var(--rl-ink)]"><FileSearch className="h-4 w-4 text-[var(--rl-primary)]" />{selectedNode.type === "question" ? `Turn ${selectedNode.index + 1}` : selectedNode.type === "evidence" ? "Cited source" : selectedNode.type === "summary" ? "Summary" : "Session overview"}</div><button type="button" onClick={() => setSelectedId(null)} aria-label="Close details" className="rounded-md p-1 text-slate-500 hover:bg-slate-100"><X className="h-4 w-4" /></button></div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {selectedNode.type === "question" && <><h2 className="text-base font-semibold leading-6 text-[var(--rl-ink)]">{selectedTurn.question}</h2><div className="mt-3 text-sm leading-6 text-[var(--rl-ink)]">{selectedTurn.message ? <GroundedAnswer compact content={selectedTurn.message.content} sources={selectedTurn.message.sources || []} /> : <p className="text-[var(--rl-muted)]">This question has no saved answer yet.</p>}</div><p className="mt-4 text-xs text-[var(--rl-muted)]">{(selectedTurn.message?.sources || []).length} cited passages</p>{selectedTurn.message?.sources?.length > 0 && <><div className="mt-3 space-y-2">{selectedTurn.message.sources.map((source, index) => <div key={sourceKey(source, index)} className="rounded-lg border border-[var(--rl-border)] bg-slate-50 p-3"><p className="break-words text-xs font-semibold text-[var(--rl-ink)]">{source.paper_title || source.filename || source.title || "Cited document"}</p><p className="mt-0.5 text-[11px] text-[var(--rl-muted)]">{source.filename || ""}{source.page_start || source.page ? ` · Page ${source.page_start || source.page}${source.page_end && source.page_end !== (source.page_start || source.page) ? `–${source.page_end}` : ""}` : ""}</p>{(source.evidence_excerpt || source.text || source.passage) && <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-xs leading-5 text-slate-600">{source.evidence_excerpt || source.text || source.passage}</p>}</div>)}</div><button type="button" onClick={() => inspectSources(selectedTurn)} className="mt-3 inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--rl-border)] px-3 text-xs font-medium text-[var(--rl-primary)] hover:bg-[var(--rl-tint)]"><BookOpen className="h-4 w-4" />Inspect evidence</button></>}
                <Link href={conversationId ? `/chat/${conversationId}` : "/chat"} className="mt-3 inline-flex h-9 items-center gap-2 rounded-lg bg-[var(--rl-primary)] px-3 text-xs font-medium text-white">Open in Research Desk <ArrowUpRight className="h-4 w-4" /></Link></>}
              {selectedNode.type === "evidence" && <><h2 className="break-words text-sm font-semibold text-[var(--rl-ink)]">{selectedNode.source.paper_title || selectedNode.source.title || selectedNode.source.filename || "Cited document"}</h2><p className="mt-1 break-all text-xs text-[var(--rl-muted)]">{selectedNode.source.filename || "Filename not recorded"}</p>{(selectedNode.source.authors || selectedNode.source.author) && <p className="mt-1 text-xs text-[var(--rl-muted)]">{Array.isArray(selectedNode.source.authors) ? selectedNode.source.authors.join(", ") : selectedNode.source.authors || selectedNode.source.author}</p>}<p className="mt-2 text-xs text-[var(--rl-muted)]">{selectedNode.source.page_start || selectedNode.source.page ? `Page ${selectedNode.source.page_start || selectedNode.source.page}${selectedNode.source.page_end && selectedNode.source.page_end !== (selectedNode.source.page_start || selectedNode.source.page) ? `–${selectedNode.source.page_end}` : ""}` : "Page not recorded"}</p><p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-700">{selectedNode.source.evidence_excerpt || selectedNode.source.text || selectedNode.source.passage || "No passage excerpt was saved for this citation."}</p><button type="button" onClick={() => openEvidence(selectedNode.source)} className="mt-4 inline-flex h-9 items-center gap-2 rounded-lg bg-[var(--rl-primary)] px-3 text-xs font-medium text-white hover:bg-[#185ea8]"><FileText className="h-4 w-4" />Open PDF at cited page</button>{selectedTurn && <button type="button" onClick={() => inspectSources(selectedTurn)} className="mt-2 inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--rl-border)] px-3 text-xs font-medium text-[var(--rl-primary)]"><CheckCircle2 className="h-4 w-4" />Inspect answer citations</button>}</>}
              {selectedNode.type === "summary" && <>{activeSummary?.answer ? <GroundedAnswer compact content={activeSummary.answer} sources={activeSummary.sources || []} /> : <p className="text-sm leading-6 text-[var(--rl-muted)]">No summary is available for this conversation yet. Use “Summarize” to create one from the selected source passages.</p>}{activeSummary?.sources?.length > 0 && <button type="button" onClick={() => { setSources(activeSummary.sources || []); setResearchTrace(activeSummary.metadata?.research || {}); openDrawer(); }} className="mt-3 inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--rl-border)] px-3 text-xs text-[var(--rl-primary)]">Inspect summary evidence</button>}</>}
              {selectedNode.type === "session" && <><h2 className="text-base font-semibold text-[var(--rl-ink)]">Session overview</h2><p className="mt-1 text-sm font-medium text-[var(--rl-ink)]">{map.title}</p><div className="mt-3 grid grid-cols-2 gap-2"><div className="rounded-lg bg-[var(--rl-tint)] p-3"><p className="text-lg font-semibold text-[var(--rl-primary)]">{turns.length}</p><p className="text-[11px] text-[var(--rl-muted)]">Questions</p></div><div className="rounded-lg bg-[var(--rl-tint)] p-3"><p className="text-lg font-semibold text-[var(--rl-primary)]">{map.evidence.length}</p><p className="text-[11px] text-[var(--rl-muted)]">Cited sources</p></div></div>{activeSummary?.answer && <div className="mt-4 rounded-lg border border-[var(--rl-border)] p-3"><p className="flex items-center gap-1.5 text-xs font-semibold text-[var(--rl-ink)]"><Sparkles className="h-3.5 w-3.5 text-[var(--rl-primary)]" />Research summary</p><p className="mt-2 line-clamp-5 text-xs leading-5 text-[var(--rl-muted)]">{shortText(activeSummary.answer, 260)}</p><button type="button" onClick={() => setSelectedId("summary")} className="mt-2 text-xs font-medium text-[var(--rl-primary)] hover:underline">Read summary</button></div>}<h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-[var(--rl-muted)]">Question branches</h3><div className="mt-2 space-y-1">{map.questions.map((node) => <button key={node.id} type="button" onClick={() => setSelectedId(node.id)} className="block w-full rounded-lg px-2.5 py-2 text-left text-xs leading-5 text-[var(--rl-ink)] hover:bg-[var(--rl-tint)]"><span className="mr-2 text-[var(--rl-primary)]">{node.index + 1}.</span>{node.turn.question}</button>)}</div><h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-[var(--rl-muted)]">Cited documents</h3>{map.evidence.length ? <div className="mt-2 space-y-1">{map.evidence.map((node) => <button key={node.id} type="button" onClick={() => setSelectedId(node.id)} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs text-[var(--rl-ink)] hover:bg-[var(--rl-tint)]"><FileText className="h-4 w-4 shrink-0 text-[var(--rl-primary)]" /><span className="min-w-0 flex-1 truncate">{node.source.filename || node.source.paper_title || node.source.title || "Cited document"}</span></button>)}</div> : <p className="mt-2 text-xs text-[var(--rl-muted)]">No citation records are saved for these answers.</p>}<Link href={conversationId ? `/chat/${conversationId}` : "/chat"} className="mt-5 inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--rl-border)] px-3 text-xs text-[var(--rl-primary)]">Open Research Desk <ArrowUpRight className="h-4 w-4" /></Link></>}
            </div>
          </aside>}
        </>)}
      </section>

      {isDrawerOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Evidence Trail"
          className="fixed inset-y-0 right-0 top-16 z-40 flex justify-end pointer-events-none"
        >
          <div
            className="h-full w-[min(26rem,94vw)] shadow-2xl border-l border-slate-200/90 pointer-events-auto bg-white"
            onClick={(event) => event.stopPropagation()}
          >
            <SourceInspectorRail onClose={closeDrawer} />
          </div>
        </div>
      )}
      <style jsx>{`.map-control{display:inline-flex;height:2rem;min-width:2rem;align-items:center;justify-content:center;gap:.35rem;border:1px solid var(--rl-border);border-radius:.5rem;background:white;padding:0 .5rem;color:var(--rl-ink);font-size:.7rem}.map-control:hover{background:var(--rl-tint)}`}</style>
    </div>
  );
}
