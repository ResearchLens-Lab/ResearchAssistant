"""Offline-first command-line entry point for bounded research workflows.

Examples (run from the repository root):
  python -m backend.app.services.research_intelligence_cli analyze --owner-id ID --question "..."
  python -m backend.app.services.research_intelligence_cli synthesize --owner-id ID --question "..." --document-ids DOC --result-limit 12 --offline
  python -m backend.app.services.research_intelligence_cli lookup --owner-id ID --doi 10.xxxx/example --check-external
"""
import argparse
import asyncio
import json

from backend.app.database.session import get_session_factory
from backend.app.services.research_intelligence import ResearchIntelligenceService


def parser():
    root = argparse.ArgumentParser(description="ResearchLens deterministic intelligence workflows")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("readiness", "analyze", "synthesize", "claim", "compare", "contradictions", "gaps", "verify", "lookup", "quality-review", "history", "report", "inspect-evidence"):
        p = sub.add_parser(name); p.add_argument("--owner-id", required=True); p.add_argument("--offline", action="store_true")
        p.add_argument("--max-depth", type=int, default=2)
        if name in ("analyze", "synthesize", "claim", "gaps"): p.add_argument("--question", required=name != "gaps")
        if name in ("synthesize", "claim", "gaps"):
            p.add_argument("--document-ids", nargs="*"); p.add_argument("--paper-ids", nargs="*")
        if name == "compare": p.add_argument("--paper-ids", nargs="+", required=True)
        if name == "contradictions": p.add_argument("--document-ids", nargs="*")
        if name == "verify": p.add_argument("--paper-id", required=True); p.add_argument("--check-external", action="store_true")
        if name == "quality-review":
            p.add_argument("--paper-id", required=True); p.add_argument("--profile-json", required=True)
            p.add_argument("--evidence-ids", nargs="*")
        if name == "lookup":
            p.add_argument("--doi"); p.add_argument("--title"); p.add_argument("--authors", nargs="*")
            p.add_argument("--year", type=int); p.add_argument("--check-external", action="store_true")
        if name in ("synthesize", "gaps", "contradictions"): p.add_argument("--result-limit", type=int, default=20)
        if name == "history": p.add_argument("--result-limit", type=int, default=50)
        if name == "report": p.add_argument("--run-id", required=True)
        if name == "inspect-evidence": p.add_argument("--run-id", required=True); p.add_argument("--evidence-id", required=True)
    return root


async def run(args):
    if args.command == "lookup" and not args.check_external:
        raise SystemExit("External lookup is opt-in; add --check-external to send only the DOI or public title.")
    if args.command == "lookup" and args.offline:
        raise SystemExit("--offline cannot be combined with the explicit external lookup command.")
    if args.command == "verify" and args.offline and args.check_external:
        raise SystemExit("--offline cannot be combined with --check-external.")
    factory = get_session_factory()
    async with factory() as db:
        service = ResearchIntelligenceService(db)
        if args.command == "analyze": result = await service.analyze_question(args.owner_id, args.question)
        elif args.command == "synthesize": result = await service.synthesize(args.owner_id, args.question, args.paper_ids, args.document_ids, args.result_limit)
        elif args.command == "claim": result = await service.assess_claim(args.owner_id, args.question, args.paper_ids, args.document_ids)
        elif args.command == "compare": result = await service.compare(args.owner_id, args.paper_ids)
        elif args.command == "contradictions": result = await service.analyze_contradictions(args.owner_id, args.document_ids)
        elif args.command == "gaps": result = await service.gaps(args.owner_id, args.question, args.paper_ids, args.document_ids)
        elif args.command == "verify": result = await service.verify_source(args.owner_id, args.paper_id, check_external=args.check_external and not args.offline)
        elif args.command == "lookup": result = await service.external_lookup(args.owner_id, doi=args.doi,
            title=args.title, authors=args.authors, year=args.year)
        elif args.command == "quality-review": result = await service.quality_review(args.owner_id, args.paper_id,
            json.loads(args.profile_json), args.evidence_ids, args.owner_id)
        elif args.command == "readiness":
            from sqlalchemy import func, select
            from backend.app.models.document import Document
            from backend.app.models.paper import Paper
            count = await db.scalar(select(func.count(Document.id)).join(Paper, Paper.id == Document.paper_id).where(
                Paper.owner_id == args.owner_id, Document.processing_status == "indexed"))
            result = {"indexed_documents": count or 0, "offline_local_workflows": True}
        elif args.command == "inspect-evidence": result = await service.inspect_run_evidence(args.owner_id, args.run_id, args.evidence_id)
        elif args.command == "history": result = await service.history(args.owner_id, args.result_limit)
        else: result = await service.inspect(args.owner_id, args.run_id)
        await db.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def main():
    asyncio.run(run(parser().parse_args()))


if __name__ == "__main__": main()
