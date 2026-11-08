# ResearchLens Phase 3.1 status

## Claim verification and repair

The production `RAGGateway`/`QueryPipeline` flow performs selected-paper retrieval, citation identity/scope validation, provenance checks, and then claim verification before returning a response to `ChatService` for persistence. The optional LLM judge assesses cited excerpts for material claim support using a schema-checked result constrained to retrieved source IDs; it is off by default and is not exercised with a real model in automated tests. The deterministic fallback is still a lexical/numeric heuristic, not semantic entailment. Citation identity and support remain separate.

A single correction request is made when verification finds unsupported, invalid-reference, or contradicted material. The repaired answer is re-run through citation resolution and claim verification. Only the verifier's safe projection can be persisted; unresolved numerical errors are omitted and the response is qualified. Unit/integration tests cover successful correction and safe failure after one attempt. Claim metadata is persisted without model chain-of-thought.

## Provider streaming and persistence

`BaseLLMClient` exposes `supports_streaming` and `generate_stream`. `OpenAILLMClient` parses incremental chat-completion SSE deltas; mock/other clients retain a one-shot fallback and do not emit fabricated tokens. Tokens are marked provisional in authenticated `ChatStreamEvent` frames. The final completion contains the answer after citation checks, claim checks, correction, and persistence; the browser replaces draft text with this final answer. If RAG fails, no assistant response is persisted and the stream emits a generic error. Cancellation suppresses further token forwarding and prevents persistence; an already-running synchronous provider read can continue until a read/overall timeout because worker-thread cancellation is cooperative.

Tests cover OpenAI SSE framing with a fake HTTP stream, generator token forwarding, mock fallback, authenticated API event ordering, final persistence, and repair behavior. No credentialed OpenAI request or manual browser disconnect/cancellation session was run, so real provider/network behavior remains unverified.

## Evaluation

The benchmark now has 54 labeled query cases and executes both paths on the same five-document fixture corpus. Cases cover direct facts, equations, concepts, multiple passages/papers, missing evidence, conflict, follow-up, false assumptions, injection-like source text, numbers, and fixture locators. The cases expand 22 underlying fixture-fact anchors with alternate phrasings, so this count is not 54 independent scientific facts. Exact PDF-page correctness, retrieval duplicate rate, and token usage remain unmeasured. Metrics and the generated execution results are documented in [evaluation.md](evaluation.md) and [phase3_1_mock.json](reports/phase3_1_mock.json).

## Frontend validation and dependency audit

The separate root `package-lock.json` is retained for the root Neon package; the frontend keeps its own package and lockfile. Setting `outputFileTracingRoot` to the frontend directory resolves Next's ambiguous multiple-lockfile trace root without moving/deleting either package. ESLint 10 flat config, a scoped JavaScript `checkJs` TypeScript command, and normal Next build checks are configured. Type checking currently includes the modified chat hook/service and generated Next route types; legacy app-wide JavaScript is not all included because whole-app `checkJs` exposed hundreds of pre-existing component typing errors. ESLint runs four parser-level correctness rules, not the full Next recommended preset.

`npm audit --omit=dev` reports zero production vulnerabilities. The full audit reports 8 findings (3 moderate, 5 high, 0 critical) in the Tailwind 3 development/build chain: `braces`, `chokidar`, `fast-glob`, `micromatch`, `postcss-nested`, `postcss-selector-parser`, and `tailwindcss`, reached through Tailwind 3.4.19 and typography 0.5.x. The available broad npm fix is Tailwind 4, a major configuration/plugin migration; it was not applied because this phase does not include a Tailwind migration. Next 15.5.28 is installed; the previous Next critical audit item is absent.

## Full-path testing limits

The automated suite covers backend upload/ZIP and access-control tests, RAG ingestion/retrieval/citation tests, and backend chat persistence/stream tests. It does not replace the requested manual multi-file browser journey. No live browser session was run to inspect original PDF pages, refresh the UI, or exercise live-provider disconnects.
