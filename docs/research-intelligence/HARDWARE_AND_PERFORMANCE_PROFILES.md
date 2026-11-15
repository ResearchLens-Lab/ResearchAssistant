# Hardware and Performance Profiles

## Current resource behavior

The default independent path uses PyMuPDF/native parsers, chunking, Python rule extraction, local SQLite FTS5 and bounded candidate retrieval. It does not need a GPU, pretrained embedding download or generative model. Settings expose candidate/top-k/chunk/concurrency-related limits in several modules; upload processing is currently synchronous in `DocumentService._process` and can hold request work while parsing/indexing. Upload batching is bounded by file count/size and ZIP expansion checks, but no system-wide ingestion worker queue or user pause/resume scheduler was found.

The legacy optional path can load FastEmbed/Chroma or external providers and has materially different memory/network requirements. Do not conflate it with independent-mode resource claims.

## Recommended profiles

| Profile | Behavior | Guardrails |
|---|---|---|
| Low-resource CPU (default target) | One document parse/index job at a time; small candidate set; FTS5 only; batch SQLite writes; avoid loading all file bytes/pages together where parser supports streaming. | Soft memory/concurrency caps, progress, cancellation, bounded archive expansion, graceful SQLite timeout. |
| Standard CPU | Small bounded parallelism for independent files; moderate candidate count; optional deterministic rerank. | Per-process worker limit and measured memory ceiling. |
| Optional accelerated | Only user-configured optional local embedding/model services. | Explicit install/enable, visible model/provider, no silent download, same ownership/scope checks. |

Thresholds must be measured on supported hardware before hard defaults are advertised. Do not add background work without a visible processing state/control.

## Before implementation

Instrument elapsed time and peak memory for parse, normalize, chunk, index, retrieval and composition using small synthetic documents in temporary directories. Benchmark representative user-owned documents only with authorization. Add cancellation tests at each stage and prove failed replacement keeps the previous verified index. Avoid benchmarks that touch or recreate developer `.chroma`/SQLite data.

## Status

Bounded upload size/archive expansion, parser progress, cancellation signals and bounded query candidates exist. Low-resource/high-performance profile selection, background queue, pause/resume, stage-level memory budget and a validated hardware matrix are **not implemented or measured**.
