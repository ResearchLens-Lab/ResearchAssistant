"""Trusted local operator CLI for Phase 6 research memory."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.app.core.config import get_settings
from backend.app.services.research_memory_service import ResearchMemoryService


def _csv(text: str | None) -> list[str]: return [x.strip() for x in (text or "").split(",") if x.strip()]


async def _run(args):
    engine = create_async_engine(args.db_url or get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        svc = ResearchMemoryService(db)
        owner = args.owner_id
        if args.command == "status": result = await svc.status(owner)
        elif args.command == "preview": result = await svc.formation_preview(owner, _csv(args.node_ids), _csv(args.relationship_ids), args.allow_private)
        elif args.command == "form":
            if not args.confirm: raise ValueError("form requires --confirm after reviewing preview")
            result = await svc.form(owner, _csv(args.node_ids), _csv(args.relationship_ids), args.allow_private); await db.commit()
        elif args.command == "retrieve": result = await svc.search(owner, args.query, limit=args.limit)
        elif args.command == "review-association":
            result = await svc.review_association(owner, args.association_id, args.action, owner); await db.commit()
        elif args.command == "associations":
            result = await svc.list_associations(owner, args.status, args.limit)
        elif args.command == "history": result = await svc.history(owner, args.memory_id, args.limit)
        elif args.command == "contradictions":
            result = await svc.list_contradictions(owner, args.status, args.limit)
        elif args.command == "resolve-contradiction":
            result = await svc.resolve_contradiction(owner, args.id, args.outcome, {"reviewer_context": args.context}, owner); await db.commit()
        elif args.command == "create-gap":
            result = await svc.create_gap(owner, args.question, args.gap_type, {"selected_documents": _csv(args.documents)},
                args.reason, [], owner); await db.commit()
        elif args.command == "gaps":
            from sqlalchemy import select
            from backend.app.models.research_memory import MemoryResearchGap
            result = list((await db.scalars(select(MemoryResearchGap).where(MemoryResearchGap.owner_id == owner,
                MemoryResearchGap.status == args.status.upper()).order_by(MemoryResearchGap.discovered_at.desc()).limit(args.limit))).all())
        elif args.command == "resolve-gap":
            result = await svc.resolve_gap(owner, args.id, args.status, args.memory_id, owner); await db.commit()
        elif args.command == "audit": result = await svc.audit(owner); await db.commit()
        else: raise ValueError("unsupported command")
        print(json.dumps(result, ensure_ascii=False, default=lambda v: v.__dict__ if hasattr(v, "__dict__") else str(v), indent=2))
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-id", required=True, help="Trusted local operator only; API uses authenticated owner")
    parser.add_argument("--db-url", help="Override configured database for isolated/local use")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    for name in ["preview", "form"]:
        p = sub.add_parser(name); p.add_argument("--node-ids", default=""); p.add_argument("--relationship-ids", default="")
        p.add_argument("--allow-private", action="store_true")
        if name == "form": p.add_argument("--confirm", action="store_true")
    p = sub.add_parser("retrieve"); p.add_argument("--query", required=True); p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("review-association"); p.add_argument("--association-id", required=True); p.add_argument("--action", choices=["confirm", "reject", "review"], required=True)
    p = sub.add_parser("associations"); p.add_argument("--status", default="CANDIDATE"); p.add_argument("--limit", type=int, default=100)
    p = sub.add_parser("history"); p.add_argument("--memory-id", required=True); p.add_argument("--limit", type=int, default=100)
    p = sub.add_parser("contradictions"); p.add_argument("--status", default="CANDIDATE"); p.add_argument("--limit", type=int, default=100)
    p = sub.add_parser("resolve-contradiction"); p.add_argument("--id", required=True); p.add_argument("--outcome", required=True,
        choices=["TRUE_CONFLICT", "CONTEXTUAL_DIFFERENCE", "NOT_A_CONTRADICTION", "UNRESOLVED"]); p.add_argument("--context", default="")
    p = sub.add_parser("create-gap"); p.add_argument("--question", required=True); p.add_argument("--gap-type", required=True,
        choices=["LIBRARY_EVIDENCE_GAP", "DOCUMENT_INFORMATION_GAP", "CONFLICT_UNRESOLVED", "POTENTIAL_RESEARCH_GAP"])
    p.add_argument("--reason", required=True); p.add_argument("--documents", default="")
    p = sub.add_parser("gaps"); p.add_argument("--status", default="OPEN"); p.add_argument("--limit", type=int, default=100)
    p = sub.add_parser("resolve-gap"); p.add_argument("--id", required=True); p.add_argument("--status", required=True, choices=["RESOLVED", "REOPENED"]); p.add_argument("--memory-id")
    sub.add_parser("audit")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__": main()
