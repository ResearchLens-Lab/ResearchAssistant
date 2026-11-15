"""Pipelines module exports with lazy loading for model-backed ingestion."""

from rag.pipelines.query_pipeline import QueryPipeline

__all__ = [
    "IngestionPipeline",
    "IngestResult",
    "QueryPipeline",
]


def __getattr__(name: str):
    if name in ("IngestionPipeline", "IngestResult"):
        from rag.pipelines.ingest_pipeline import IngestionPipeline, IngestResult
        return {"IngestionPipeline": IngestionPipeline, "IngestResult": IngestResult}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
