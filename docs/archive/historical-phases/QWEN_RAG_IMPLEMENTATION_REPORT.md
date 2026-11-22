# ResearchAssistant Qwen RAG Implementation

## Configuration

- Ollama API: `http://127.0.0.1:11434`
- Model: `qwen3.5:0.8b` (verified with `/api/tags` and `/api/show`; reported parameter size 752.39M)
- Chat API: `/api/chat`; verified a real response with `think: false`. Only `message.content` is read; model thinking is neither streamed nor persisted.
- Local settings use Ollama, `LOCAL_QWEN`, 4096 context tokens, at most 512 output tokens, one inference at a time, and a 10-minute keep-alive. BGE embeddings remain unchanged.
- The chat request deadline is 240 seconds for slower CPU generation; the interface shows a local Qwen progress message and displays timeout errors.

## Behavior

- Retrieval and evidence sufficiency checks run before Qwen. Qwen receives the bounded selected passages with their original source IDs and page locators.
- Chat defaults to **Documents + general knowledge**; **Documents only** is selectable in the composer. Missing document evidence is labeled before any separate, uncited general answer. Unsupported or unavailable answers abstain clearly.
- Grounded model output passes citation-ID validation and claim evidence checks. Unsupported claims are removed; verified source records retain filenames, physical pages, sections, and citation IDs for the Source Inspector.
- A direct algorithm definition is answered from a matching textbook passage without waiting for CPU generation. Any added sorting example is labeled as illustrative and not document-derived.
- Short follow-ups now resolve against only the immediately preceding user question and answer. Retrieval queries keep that topic; reference-list pages are demoted unless the user asks for citations.
- Summary generation distinguishes a partial book overview from a research-paper summary, avoids using the previous chat turn as a summary retrieval query, filters bibliography/index passages from ordinary overviews, and requires inspectable citations. If model output cannot be cited, the result falls back to section-labeled source excerpts or an explicit evidence limitation.
- Markdown remains rendered by the existing safe React Markdown frontend. Follow-up actions continue the same conversation, source scope, and selected answer mode.
- Qwen inference is local. No paid/cloud inference or model downloads were introduced.

## Files changed

- RAG settings, Ollama client, query pipeline, and focused Qwen integration tests.
- Backend chat request/gateway/service plumbing and local app settings.
- Chat composer mode selector, model/source badges, and follow-up metadata persistence.
- `.env` and `backend/.env.local` local configuration (gitignored), `.env.example`, and this report.
- Reviewed the adjacent RAG-Anything repo. Its multimodal LightRAG graph pipeline would require a separate index, entity extraction, and extra parsing/model dependencies; it does not improve this text-only CLRS workflow enough to justify changing the existing hybrid index.

## Verification

- Ollama `/api/tags`, `/api/show`, and a real `/api/chat` request succeeded; the response contained `API_OK` and no `message.thinking` field.
- Real grounded Qwen query against an algorithm definition passage returned a cited answer. Unsupported example claims were removed, and the supplemental example is explicitly labeled as not from the documents.
- Backend/RAG tests: **231 passed** using isolated test settings (`APP_ENV=testing`, mock provider, extractive mode); no paid APIs were called.
- Frontend unit tests: **25 passed**. TypeScript typecheck and Next.js production build passed.
- `git diff --check` passed.

## Known limitations

- The 0.8B CPU model is slow on this laptop and may omit or misstate details. Cold generation took about 50 seconds in a real grounded query; answers are bounded and checked, but semantic support checking is a lexical heuristic, not a proof of entailment.
- The selected passages bound summaries; the model cannot guarantee full-document coverage when relevant passages are not retrieved.
- If Ollama is unavailable, grounded questions use the existing evidence fallback and general-knowledge requests show a local-model-unavailable message.
