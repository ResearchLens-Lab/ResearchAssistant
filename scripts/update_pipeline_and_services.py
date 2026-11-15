from pathlib import Path

# 1. Update rag/pipelines/query_pipeline.py
pipeline_path = Path("rag/pipelines/query_pipeline.py")
text = pipeline_path.read_text(encoding="utf-8")

# Update signature of answer_question
target_sig = """        progress_callback: Optional[Callable[[dict], None]] = None,
        answer_mode: Optional[str] = None,
    ) -> RAGResult:"""

replacement_sig = """        progress_callback: Optional[Callable[[dict], None]] = None,
        answer_mode: Optional[str] = None,
        paper_metadata: Optional[Dict[str, Any]] = None,
    ) -> RAGResult:"""

if target_sig in text:
    text = text.replace(target_sig, replacement_sig)

# Update routing in answer_question
target_routing = """        if settings.rag_engine_mode == "independent":
            assert self._independent_engine is not None
            return self._independent_engine.answer(
                question=question,
                paper_ids=selected_ids or None,
                document_ids=(filters.document_ids if filters else None),
                section_names=(filters.sections if filters else None),
                top_k=k,
                conversation_context=conversation_context,
                progress_callback=progress_callback,
                user_id=user_id,
            )"""

replacement_routing = """        use_independent = (
            settings.rag_engine_mode == "independent"
            or answer_mode in ("EVIDENCE_FIRST", "DOCUMENTS_ONLY", "INDEPENDENT")
        ) and answer_mode not in ("OPTIONAL_LOCAL_AI", "LOCAL_QWEN")

        if use_independent:
            if self._independent_engine is None:
                from rag.independent.engine import IndependentResearchEngine
                self._independent_engine = IndependentResearchEngine()
            return self._independent_engine.answer(
                question=question,
                paper_ids=selected_ids or None,
                document_ids=(filters.document_ids if filters else None),
                section_names=(filters.sections if filters else None),
                top_k=k,
                conversation_context=conversation_context,
                progress_callback=progress_callback,
                user_id=user_id,
                paper_metadata=paper_metadata,
            )

        if self.retriever is None:
            self.retriever = ResearchRetriever()"""

if target_routing in text:
    text = text.replace(target_routing, replacement_routing)

pipeline_path.write_text(text, encoding="utf-8")
print("rag/pipelines/query_pipeline.py updated.")

# 2. Update backend/app/integrations/rag_client.py
client_path = Path("backend/app/integrations/rag_client.py")
c_text = client_path.read_text(encoding="utf-8")

c_target = """        progress_callback: Optional[Callable[[dict], None]] = None,
        answer_mode: str = "DOCUMENTS_GENERAL",
    ) -> Dict[str, Any]:"""

c_replacement = """        progress_callback: Optional[Callable[[dict], None]] = None,
        answer_mode: str = "EVIDENCE_FIRST",
        paper_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:"""

if c_target in c_text:
    c_text = c_text.replace(c_target, c_replacement)

c_call_target = """            progress_callback=progress_callback,
            answer_mode=answer_mode,
        )"""

c_call_replacement = """            progress_callback=progress_callback,
            answer_mode=answer_mode,
            paper_metadata=paper_metadata,
        )"""

if c_call_target in c_text:
    c_text = c_text.replace(c_call_target, c_call_replacement)

client_path.write_text(c_text, encoding="utf-8")
print("backend/app/integrations/rag_client.py updated.")

# 3. Update backend/app/integrations/rag_gateway.py
gateway_path = Path("backend/app/integrations/rag_gateway.py")
g_text = gateway_path.read_text(encoding="utf-8")

g_target = """        progress_callback: Optional[Callable[[dict], None]] = None,
        answer_mode: str = "DOCUMENTS_GENERAL",
    ) -> dict[str, Any]:"""

g_replacement = """        progress_callback: Optional[Callable[[dict], None]] = None,
        answer_mode: str = "EVIDENCE_FIRST",
        paper_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:"""

if g_target in g_text:
    g_text = g_text.replace(g_target, g_replacement)

g_call_target = """            answer_mode=answer_mode,
            **({"conversation_context": conversation_context} if conversation_context else {}),
            **({"progress_callback": progress_callback} if progress_callback else {}),
        )"""

g_call_replacement = """            answer_mode=answer_mode,
            paper_metadata=paper_metadata,
            **({"conversation_context": conversation_context} if conversation_context else {}),
            **({"progress_callback": progress_callback} if progress_callback else {}),
        )"""

if g_call_target in g_text:
    g_text = g_text.replace(g_call_target, g_call_replacement)

gateway_path.write_text(g_text, encoding="utf-8")
print("backend/app/integrations/rag_gateway.py updated.")

# 4. Update backend/app/services/chat_service.py
chat_svc_path = Path("backend/app/services/chat_service.py")
cs_text = chat_svc_path.read_text(encoding="utf-8")

cs_target = """        papers = await self.paper_service.validate_owned_papers(user, payload.paper_ids)
        paper_ids = [paper.id for paper in papers]"""

cs_replacement = """        papers = await self.paper_service.validate_owned_papers(user, payload.paper_ids)
        paper_ids = [paper.id for paper in papers]
        paper_metadata = {
            paper.id: {
                "title": paper.title,
                "authors": paper.authors if isinstance(paper.authors, list) else ([paper.authors] if paper.authors else []),
                "year": paper.publication_year,
                "venue": paper.venue,
            }
            for paper in papers
        }"""

if cs_target in cs_text:
    cs_text = cs_text.replace(cs_target, cs_replacement)

cs_call_target = """        result = await self.rag.ask_question(
            question=payload.question,
            user_id=str(user.id),  # SEC-001: Pass authenticated user ID (REQUIRED)
            paper_ids=paper_ids,
            conversation_context=conversation_context,
            progress_callback=progress_callback,
            answer_mode=payload.answer_mode,
        )"""

cs_call_replacement = """        result = await self.rag.ask_question(
            question=payload.question,
            user_id=str(user.id),  # SEC-001: Pass authenticated user ID (REQUIRED)
            paper_ids=paper_ids,
            conversation_context=conversation_context,
            progress_callback=progress_callback,
            answer_mode=payload.answer_mode,
            paper_metadata=paper_metadata,
        )"""

if cs_call_target in cs_text:
    cs_text = cs_text.replace(cs_call_target, cs_call_replacement)

chat_svc_path.write_text(cs_text, encoding="utf-8")
print("backend/app/services/chat_service.py updated.")

