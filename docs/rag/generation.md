# Grounded LLM Generation & Prompts

**Path**: `rag/generation/`

## Purpose
Synthesizes grounded research answers strictly using supplied context passages while attributing claims with inline citation tags (`[S1]`, `[S2]`).

## Key Components

### 1. `prompts.py`
Academic prompt templates:
- `RESEARCH_QA_SYSTEM_PROMPT`: Rules enforcing evidence grounding and refusal when evidence is absent.
- `SUMMARIZATION_SYSTEM_PROMPT`: Generates 7 standard sections (Overview, Problem, Methodology, Datasets, Findings, Limitations, Conclusion).
- `COMPARISON_SYSTEM_PROMPT`: Multi-paper comparison with explicit paper attribution.
- `METHODOLOGY_PROMPT` & `LIMITATIONS_PROMPT`.

### 2. `llm_client.py`
- `BaseLLMClient`: Abstract interface.
- `MockGroundedLLMClient`: Deterministic offline generator that extracts evidence from context blocks for fast CI/local testing.
- `OpenAILLMClient`: Cloud LLM client calling OpenAI Chat Completion API.
- `LLMClientFactory`: Instantiates configured client.

### 3. `response_parser.py`
`ResponseParser`: Extracts cleaned answer text and identifies inline citation tags (`[S1]`, `[S2]`).

### 4. `generator.py`
`GroundedGenerator`: Coordinates prompt rendering, LLM execution, and response parsing.

Research answers use deterministic citation identity and selected-scope checks, then a bounded claim filter before serialization. The default lexical/numeric claim heuristic does not prove semantic entailment; an optional schema-checked LLM judge can be enabled with `CLAIM_VERIFICATION_USE_LLM=true`. The compatible JSON endpoint remains available, and `POST /api/v1/chat/stream` emits authenticated pipeline progress. Answer-token streaming is not implemented because configured providers expose no streaming interface. See [Phase 3 status](phase3-status.md).
