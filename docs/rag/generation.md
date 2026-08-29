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
