# Performance and Resource Budget

## Known workload

The independent default path uses local parsing, chunking, deterministic rules and SQLite FTS5; it does not need a GPU, model download or generative provider. Upload processing currently runs synchronously in backend service paths, and the product does not yet have a unified desktop scheduler with pause/resume. Optional legacy embedding/Chroma/provider modes have different storage, network and memory behavior and should be omitted from the core desktop installation unless explicitly selected.

No hardware minimum is advertised by this document. Measure the packaged application on named Windows configurations before release claims.

## Profiles

| Profile | Default behavior | User controls |
|---|---|---|
| Low-resource CPU | One parse/index task at a time; bounded pages/text in memory; FTS5 retrieval; defer large batch imports; no OCR/model service. | Pause/cancel queue; max CPU usage goal; schedule only while open. |
| Standard CPU | Small bounded concurrency for independent documents; cached extraction; incremental indexing; bounded candidate retrieval. | Concurrency selector, pause/cancel and per-project indexing. |
| Optional OCR/accelerated | Separate opt-in component; download/install only with disclosure, size, provenance and removal. | Explicit enable, resource limits, progress and stop. |

## Engineering limits to establish empirically

Set maximum import file size, PDF page count, archive expansion, extracted characters, table size, parallel parser count, FTS batch size, search candidate count, memory, cache size and job retry count from benchmarks and hostile-input tests. Use streaming/page-wise parsing where supported; keep the original unchanged. Bound SQLite transactions and queue writes through one writer. Apply per-stage deadlines, cancellation checkpoints, heartbeat and stale-job recovery.

## Measurement plan

Use synthetic reproducible corpora in temporary paths: small (single typical paper), medium project, large text-heavy PDF, image-heavy scan (only OCR-enabled), malformed/hostile file, and duplicate/revised version. Record cold/warm startup, import throughput, peak working set, CPU time, idle CPU, disk amplification, FTS search latency, answer latency, cancellation time, backup/restore time and recovery behavior. Measure single and bounded concurrent imports. Do not benchmark against developer Chroma or SQLite stores.

## User-facing truth

Document extraction, indexing, retrieval, PDF rendering and backup use local CPU, memory and disk. No promise of zero workload is appropriate. Show per-task state, estimated versus measured progress honestly, current resource profile, pause/cancel, disk space warnings and whether work will continue after close. Default is no closed-app processing.
