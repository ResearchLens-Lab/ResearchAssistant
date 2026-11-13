from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.config import get_settings
from backend.app.services.knowledge_graph_service import KnowledgeGraphService
from rag.document_intelligence.store import ExtractionStore


def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"): return value.isoformat()
    if hasattr(value, "__table__"):
        return {column.name: _json_value(getattr(value, column.key)) for column in value.__table__.columns}
    if isinstance(value, list): return [_json_value(item) for item in value]
    if isinstance(value, dict): return {key: _json_value(item) for key, item in value.items()}
    return value


def _print(value: Any) -> None:
    print(json.dumps(_json_value(value), ensure_ascii=False, indent=2))


def _add_owner(command: argparse.ArgumentParser) -> None:
    command.add_argument("--owner-id", required=True, help="Restrict all operations to this library owner")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local, owner-scoped ResearchLens knowledge graph tools")
    parser.add_argument("--db-url", help="Override configured DATABASE_URL")
    parser.add_argument("--evidence-store", default="rag/document_intelligence/local_data")
    parser.add_argument("--ontology-json", help="Optional JSON extensions: node_types and relationships")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("import-dry-run", "import"):
        cmd = commands.add_parser(name)
        _add_owner(cmd); cmd.add_argument("--document-id", required=True); cmd.add_argument("--run-id", required=True)
        cmd.add_argument("--allow-private", action="store_true")
        if name == "import": cmd.add_argument("--confirm", action="store_true", help="Required to write graph candidates")
    candidates = commands.add_parser("candidates"); _add_owner(candidates)
    candidates.add_argument("--status", default="pending", choices=["pending", "approved", "rejected", "rolled_back"])
    candidates.add_argument("--limit", type=int, default=100); candidates.add_argument("--offset", type=int, default=0)
    candidates.add_argument("--allow-private", action="store_true")
    show = commands.add_parser("candidate"); _add_owner(show); show.add_argument("--candidate-id", required=True); show.add_argument("--allow-private", action="store_true")
    review = commands.add_parser("review-candidate"); _add_owner(review); review.add_argument("--candidate-id", required=True)
    review.add_argument("--action", choices=["approve-node", "reject"], required=True); review.add_argument("--reviewer", required=True)
    review.add_argument("--node-type"); review.add_argument("--name"); review.add_argument("--existing-node-id")
    review.add_argument("--allow-private", action="store_true")
    edge = commands.add_parser("add-edge"); _add_owner(edge); edge.add_argument("--candidate-id", required=True)
    edge.add_argument("--source-node-id", required=True); edge.add_argument("--relationship", required=True)
    edge.add_argument("--target-node-id", required=True); edge.add_argument("--reviewer", required=True)
    edge.add_argument("--allow-private", action="store_true")
    rollback = commands.add_parser("rollback-import"); _add_owner(rollback); rollback.add_argument("--import-run-id", required=True)
    rollback.add_argument("--reviewer", required=True); rollback.add_argument("--reason", required=True)
    search = commands.add_parser("search"); _add_owner(search); search.add_argument("--query", default="")
    search.add_argument("--type"); search.add_argument("--identifier"); search.add_argument("--limit", type=int, default=50); search.add_argument("--offset", type=int, default=0)
    node = commands.add_parser("node"); _add_owner(node); node.add_argument("--node-id", required=True)
    correction = commands.add_parser("correct-node"); _add_owner(correction); correction.add_argument("--node-id", required=True)
    correction.add_argument("--name", required=True); correction.add_argument("--type", required=True); correction.add_argument("--reviewer", required=True)
    correction.add_argument("--identifiers-json")
    edge_status = commands.add_parser("edge-status"); _add_owner(edge_status); edge_status.add_argument("--relationship-id", required=True)
    edge_status.add_argument("--status", choices=["current", "disputed", "superseded", "retracted"], required=True)
    edge_status.add_argument("--reviewer", required=True); edge_status.add_argument("--reason", required=True)
    edge_correct = commands.add_parser("correct-edge"); _add_owner(edge_correct); edge_correct.add_argument("--relationship-id", required=True)
    edge_correct.add_argument("--source-node-id", required=True); edge_correct.add_argument("--relationship", required=True)
    edge_correct.add_argument("--target-node-id", required=True); edge_correct.add_argument("--reviewer", required=True)
    for name in ("evidence", "relationships", "neighborhood"):
        cmd = commands.add_parser(name); _add_owner(cmd); cmd.add_argument("--node-id", required=True)
        if name != "neighborhood": cmd.add_argument("--allow-private", action="store_true")
        if name == "neighborhood":
            cmd.add_argument("--depth", type=int, default=1); cmd.add_argument("--relationship-types")
            cmd.add_argument("--node-types"); cmd.add_argument("--max-results", type=int, default=100); cmd.add_argument("--allow-private", action="store_true")
    path = commands.add_parser("path"); _add_owner(path); path.add_argument("--source-id", required=True); path.add_argument("--target-id", required=True)
    path.add_argument("--max-depth", type=int, default=4); path.add_argument("--relationship-types"); path.add_argument("--node-types"); path.add_argument("--allow-private", action="store_true")
    audit = commands.add_parser("audit"); _add_owner(audit)
    suggestions = commands.add_parser("identity-suggestions"); _add_owner(suggestions); suggestions.add_argument("--node-id", required=True); suggestions.add_argument("--threshold", type=float, default=.84)
    alias = commands.add_parser("add-alias"); _add_owner(alias); alias.add_argument("--node-id", required=True); alias.add_argument("--alias", required=True); alias.add_argument("--reviewer", required=True)
    reject_match = commands.add_parser("reject-match"); _add_owner(reject_match); reject_match.add_argument("--source-node-id", required=True)
    reject_match.add_argument("--target-node-id", required=True); reject_match.add_argument("--reviewer", required=True); reject_match.add_argument("--reason", required=True)
    merge = commands.add_parser("merge-nodes"); _add_owner(merge); merge.add_argument("--primary-id", required=True); merge.add_argument("--duplicate-id", required=True)
    merge.add_argument("--reviewer", required=True); merge.add_argument("--reason", required=True)
    undo = commands.add_parser("undo-merge"); _add_owner(undo); undo.add_argument("--decision-id", required=True); undo.add_argument("--reviewer", required=True); undo.add_argument("--reason", required=True)
    history = commands.add_parser("history"); _add_owner(history); history.add_argument("--target-id"); history.add_argument("--decision-id")
    return parser


def _custom_ontology(path: str | None) -> tuple[set[str], dict[str, tuple[set[str], set[str]]]]:
    if not path: return set(), {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    types = {str(item).upper() for item in data.get("node_types", [])}
    relations = {}
    for name, endpoints in data.get("relationships", {}).items():
        relations[name.upper()] = ({str(v).upper() for v in endpoints.get("source", [])},
                                   {str(v).upper() for v in endpoints.get("target", [])})
    return types, relations


async def _run(args: argparse.Namespace) -> None:
    from backend.app.services.knowledge_graph_service import GraphValidationError
    from backend.app.models.knowledge_graph import KGIdentityDecision, KGReviewEvent
    from sqlalchemy import select
    url = args.db_url or get_settings().database_url
    engine = create_async_engine(url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    custom_nodes, custom_edges = _custom_ontology(args.ontology_json)
    try:
        async with factory() as session:
            service = KnowledgeGraphService(session, ExtractionStore(args.evidence_store), custom_edges, custom_nodes)
            mutating = args.command in {"import", "review-candidate", "add-edge", "rollback-import", "add-alias", "reject-match", "merge-nodes", "undo-merge", "correct-node", "edge-status", "correct-edge"}
            if mutating:
                async with session.begin():
                    result = await _dispatch(args, service, session)
                _print(result)
            else:
                _print(await _dispatch(args, service, session))
    finally:
        await engine.dispose()


async def _dispatch(args: argparse.Namespace, service: KnowledgeGraphService, session) -> Any:
    owner = getattr(args, "owner_id", None)
    if args.command in {"import-dry-run", "import"}:
        if args.command == "import":
            if not args.confirm: raise GraphValidationError("Import writes require explicit --confirm")
            return await service.import_approved(owner, args.document_id, args.run_id, args.allow_private)
        return await service.import_plan(owner, args.document_id, args.run_id, args.allow_private)
    if args.command == "candidates":
        rows = await service.list_candidates(owner, args.status, args.limit, args.offset, args.allow_private)
        return [_json_value(row) for row in rows]
    if args.command == "candidate":
        row = await service.get_candidate(owner, args.candidate_id)
        if row.private_source and not args.allow_private: raise GraphValidationError("Private candidate evidence requires --allow-private")
        return row
    if args.command == "review-candidate":
        return await service.review_candidate(owner, args.candidate_id, args.action.replace("-", "_"), args.reviewer,
            args.node_type, args.name, args.existing_node_id, args.allow_private)
    if args.command == "add-edge":
        edge = await service.add_relationship(owner, args.candidate_id, args.source_node_id,
            args.relationship, args.target_node_id, args.reviewer, args.allow_private)
        return edge
    if args.command == "rollback-import": return await service.rollback_import(owner, args.import_run_id, args.reviewer, args.reason)
    if args.command == "search": return await service.search_nodes(owner, args.query, args.type, args.identifier, args.limit, args.offset)
    if args.command == "node": return await service.node_detail(owner, args.node_id)
    if args.command == "correct-node":
        identifiers = json.loads(args.identifiers_json) if args.identifiers_json else None
        return await service.correct_node(owner, args.node_id, args.name, args.type, args.reviewer, identifiers)
    if args.command == "edge-status": return await service.set_relationship_status(owner, args.relationship_id, args.status, args.reviewer, args.reason)
    if args.command == "correct-edge":
        return await service.correct_relationship(owner, args.relationship_id, args.source_node_id,
            args.relationship, args.target_node_id, args.reviewer)
    if args.command == "evidence": return await service.node_evidence(owner, args.node_id, args.allow_private)
    if args.command == "relationships": return await service.node_relationships(owner, args.node_id, args.allow_private)
    if args.command == "neighborhood":
        return await service.neighborhood(owner, args.node_id, args.depth,
            {v.strip().upper() for v in args.relationship_types.split(",")} if args.relationship_types else None,
            {v.strip().upper() for v in args.node_types.split(",")} if args.node_types else None,
            args.max_results, args.allow_private)
    if args.command == "path":
        return await service.find_path(owner, args.source_id, args.target_id, args.max_depth,
            {v.strip().upper() for v in args.relationship_types.split(",")} if args.relationship_types else None,
            args.allow_private, {v.strip().upper() for v in args.node_types.split(",")} if args.node_types else None)
    if args.command == "audit": return await service.audit(owner)
    if args.command == "identity-suggestions": return await service.identity_suggestions(owner, args.node_id, args.threshold)
    if args.command == "add-alias": return await service.add_alias(owner, args.node_id, args.alias, args.reviewer)
    if args.command == "reject-match": return await service.reject_identity_suggestion(owner, args.source_node_id, args.target_node_id, args.reviewer, args.reason)
    if args.command == "merge-nodes": return await service.merge_nodes(owner, args.primary_id, args.duplicate_id, args.reviewer, args.reason)
    if args.command == "undo-merge": return await service.undo_merge(owner, args.decision_id, args.reviewer, args.reason)
    if args.command == "history":
        if args.decision_id:
            decision = await session.scalar(select(KGIdentityDecision).where(KGIdentityDecision.owner_id == owner,
                KGIdentityDecision.id == args.decision_id))
            if decision is None: raise GraphValidationError("Unknown identity decision")
            return decision
        stmt = select(KGReviewEvent).where(KGReviewEvent.owner_id == owner)
        if args.target_id: stmt = stmt.where(KGReviewEvent.target_id == args.target_id)
        result = await session.execute(stmt.order_by(KGReviewEvent.created_at, KGReviewEvent.id).limit(200))
        return list(result.scalars().all())
    raise GraphValidationError(f"Unsupported command: {args.command}")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "import" and not args.confirm: parser.error("import requires --confirm")
    try: asyncio.run(_run(args))
    except Exception as exc:
        parser.exit(2, f"Graph command failed ({type(exc).__name__}): {exc}\n")


if __name__ == "__main__": main()
