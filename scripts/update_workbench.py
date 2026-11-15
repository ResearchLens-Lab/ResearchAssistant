from pathlib import Path

path = Path("frontend/src/components/chat/ThreePaneChatWorkbench.jsx")
text = path.read_text(encoding="utf-8")

# 1. Update default answerMode
text = text.replace(
    'const [answerMode, setAnswerMode] = useState("DOCUMENTS_GENERAL");',
    'const [answerMode, setAnswerMode] = useState("EVIDENCE_FIRST");'
)

# 2. Add conversationSources useMemo and activeEvidenceCount
target_sync = """  // 5. Aggregate all conversation sources across assistant turns
  useEffect(() => {
    if (!isLoadingMessages && messages.length > 0) {
      const lastAssistantMsg = [...messages]
        .reverse()
        .find((m) => m.role === "assistant" && !m.pending);

      if (lastAssistantMsg && lastAssistantMsg.id !== lastSyncedMsgIdRef.current) {
        lastSyncedMsgIdRef.current = lastAssistantMsg.id;
        const allAggregated = aggregateConversationSources(messages);
        setSources(
          allAggregated.length > 0 ? allAggregated : lastAssistantMsg.sources || []
        );
        setResearchTrace(lastAssistantMsg.meta?.research || null);
      }
    }
  }, [messages, isLoadingMessages, setSources, setResearchTrace]);"""

replacement_sync = """  // 5. Aggregate all conversation sources across assistant turns
  const conversationSources = useMemo(() => {
    return aggregateConversationSources(messages);
  }, [messages]);

  const activeEvidenceCount = conversationSources.length > 0 ? conversationSources.length : sources.length;

  useEffect(() => {
    if (!isLoadingMessages && messages.length > 0) {
      if (conversationSources.length > 0) {
        setSources(conversationSources);
      }
      const lastAssistantMsg = [...messages]
        .reverse()
        .find((m) => m.role === "assistant" && !m.pending);

      if (lastAssistantMsg && lastAssistantMsg.id !== lastSyncedMsgIdRef.current) {
        lastSyncedMsgIdRef.current = lastAssistantMsg.id;
        setResearchTrace(lastAssistantMsg.meta?.research || null);
      }
    }
  }, [messages, isLoadingMessages, conversationSources, setSources, setResearchTrace]);"""

text = text.replace(target_sync, replacement_sync)

# 3. Update Evidence toolbar button
target_btn = """              className={`hidden lg:inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs border transition-colors ${
                isRightSidebarOpen || sources.length > 0
                  ? "border-slate-300 bg-slate-50 text-[var(--rl-ink)]"
                  : "border-slate-200 text-slate-500 hover:bg-slate-50"
              }`}
            >
              <PanelRight className="h-3.5 w-3.5" />
              <span>Evidence ({sources.length})</span>
            </button>"""

replacement_btn = """              className={`hidden lg:inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs border transition-colors ${
                isRightSidebarOpen || activeEvidenceCount > 0
                  ? "border-slate-300 bg-slate-50 text-[var(--rl-ink)]"
                  : "border-slate-200 text-slate-500 hover:bg-slate-50"
              }`}
            >
              <PanelRight className="h-3.5 w-3.5" />
              <span>Evidence ({activeEvidenceCount})</span>
            </button>"""

text = text.replace(target_btn, replacement_btn)

path.write_text(text, encoding="utf-8")
print("frontend/src/components/chat/ThreePaneChatWorkbench.jsx updated.")

# Update frontend/src/components/chat/ChatInputBar.jsx
input_bar_path = Path("frontend/src/components/chat/ChatInputBar.jsx")
ib_text = input_bar_path.read_text(encoding="utf-8")
ib_text = ib_text.replace(
    'answerMode = "DOCUMENTS_GENERAL"',
    'answerMode = "EVIDENCE_FIRST"'
)
target_select = """            <select aria-label="Answer mode" value={answerMode} onChange={(event) => onAnswerModeChange?.(event.target.value)} disabled={isLoading} className="h-8 rounded-lg border border-[var(--rl-border)] bg-white px-2 text-xs font-medium text-[var(--rl-ink)]">
              <option value="DOCUMENTS_GENERAL">Documents + general knowledge</option>
              <option value="DOCUMENTS_ONLY">Documents only</option>
            </select>"""

replacement_select = """            <select aria-label="Answer mode" value={answerMode} onChange={(event) => onAnswerModeChange?.(event.target.value)} disabled={isLoading} className="h-8 rounded-lg border border-[var(--rl-border)] bg-white px-2 text-xs font-medium text-[var(--rl-ink)]">
              <option value="EVIDENCE_FIRST">Evidence-first · Deterministic (Default)</option>
              <option value="DOCUMENTS_ONLY">Documents only · Strict citations</option>
              <option value="OPTIONAL_LOCAL_AI">Optional Local AI · Qwen</option>
              <option value="DOCUMENTS_GENERAL">Documents + general knowledge</option>
            </select>"""

ib_text = ib_text.replace(target_select, replacement_select)
input_bar_path.write_text(ib_text, encoding="utf-8")
print("frontend/src/components/chat/ChatInputBar.jsx updated.")

# Update frontend/src/components/chat/MessageItem.jsx
msg_item_path = Path("frontend/src/components/chat/MessageItem.jsx")
m_text = msg_item_path.read_text(encoding="utf-8")
m_target = """              if (mode === "independent_documents_only") {
                label = "Independent · no model calls";
                badgeVariant = "grounded";"""

m_replacement = """              if (mode === "independent_documents_only" || mode === "EVIDENCE_FIRST" || mode === "INDEPENDENT") {
                label = "Evidence-First (Deterministic)";
                badgeVariant = "grounded";
              } else if (mode === "DOCUMENTS_ONLY" || mode === "evidence_only") {
                label = "Documents Only (Strict)";
                badgeVariant = "grounded";"""

m_text = m_text.replace(m_target, m_replacement)
msg_item_path.write_text(m_text, encoding="utf-8")
print("frontend/src/components/chat/MessageItem.jsx updated.")

# Update frontend/src/hooks/useChat.js
chat_hook_path = Path("frontend/src/hooks/useChat.js")
ch_text = chat_hook_path.read_text(encoding="utf-8")
ch_target = """          generation_skipped: "Answering with a directly retrieved passage…","""

ch_replacement = """          retrieval_started: "Searching selected sources with SQLite FTS5…",
          evidence_ready: "Evidence collected; composing response…",
          generation_skipped: event.data?.reason === "deterministic_structured_composition"
            ? "Composing deterministic evidence-based response…"
            : "Answering with verified document evidence…","""

ch_text = ch_text.replace(ch_target, ch_replacement)
chat_hook_path.write_text(ch_text, encoding="utf-8")
print("frontend/src/hooks/useChat.js updated.")

# Update frontend/src/lib/researchWorkspace.mjs
workspace_path = Path("frontend/src/lib/researchWorkspace.mjs")
rw_text = workspace_path.read_text(encoding="utf-8")
rw_target = """cache_hit: event.data?.metadata?.cache_hit }, progress: "Saved answer · evidence check complete", provisional: false };"""

rw_replacement = """cache_hit: event.data?.metadata?.cache_hit, follow_up_suggestions: event.data?.metadata?.follow_up_suggestions || [] }, progress: "Saved answer · evidence check complete", provisional: false };"""

rw_text = rw_text.replace(rw_target, rw_replacement)
workspace_path.write_text(rw_text, encoding="utf-8")
print("frontend/src/lib/researchWorkspace.mjs updated with follow_up_suggestions.")
