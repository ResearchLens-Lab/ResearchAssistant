"""
SEC-001 Test: Verify RAG query layer enforces owner_id isolation.

This test validates that the FilterBuilder, Retriever, and Query Pipeline
all correctly enforce owner-based access control.
"""

import pytest
from rag.retrieval.filters import FilterBuilder
from rag.retrieval.query import QueryFilters


class TestOwnerIdFiltering:
    """Test owner_id enforcement at the filter level."""
    
    def test_filter_builder_requires_owner_id(self):
        """FilterBuilder must reject queries without owner_id."""
        with pytest.raises(ValueError, match="owner_id is required"):
            FilterBuilder.build_where_filter(
                owner_id="",  # Empty owner_id should fail
                paper_ids=["paper_123"],
            )
        
        with pytest.raises(ValueError, match="owner_id is required"):
            FilterBuilder.build_where_filter(
                owner_id=None,  # None should fail
                paper_ids=["paper_123"],
            )
    
    def test_filter_builder_includes_owner_id_in_filter(self):
        """FilterBuilder must always include owner_id in the where clause."""
        result = FilterBuilder.build_where_filter(
            owner_id="user_alice",
            paper_ids=["paper_123"],
        )
        
        # Result should be an $and clause with owner_id first
        assert "$and" in result or "owner_id" in result
        
        # If it's an $and clause, owner_id should be the first condition
        if "$and" in result:
            clauses = result["$and"]
            assert len(clauses) >= 1
            assert clauses[0] == {"owner_id": "user_alice"}
        else:
            # Single clause case (only owner_id filter)
            assert result == {"owner_id": "user_alice"}
    
    def test_filter_builder_with_multiple_filters(self):
        """Owner_id must be included even with complex filters."""
        filters = QueryFilters(
            paper_ids=["paper_1", "paper_2"],
            document_ids=["doc_1"],
            sections=["Methodology"],
        )
        
        result = FilterBuilder.build_where_filter(
            owner_id="user_bob",
            paper_ids=["paper_3"],
            filters=filters,
        )
        
        # Must have $and structure
        assert "$and" in result
        clauses = result["$and"]
        
        # First clause must be owner_id
        assert clauses[0] == {"owner_id": "user_bob"}
        
        # Other filters should be present
        assert any("paper_id" in str(clause) for clause in clauses)
        assert any("document_id" in str(clause) for clause in clauses)
        assert any("section" in str(clause) for clause in clauses)
    
    def test_filter_builder_strips_whitespace_from_owner_id(self):
        """Owner_id should be sanitized (whitespace stripped)."""
        result = FilterBuilder.build_where_filter(
            owner_id="  user_charlie  ",
            paper_ids=None,
        )
        
        # Should normalize to trimmed owner_id
        if "$and" in result:
            assert result["$and"][0] == {"owner_id": "user_charlie"}
        else:
            assert result == {"owner_id": "user_charlie"}
    
    def test_filter_builder_only_owner_id(self):
        """Filter with only owner_id should work."""
        result = FilterBuilder.build_where_filter(
            owner_id="user_dave",
        )
        
        # Should return single owner_id clause
        assert result == {"owner_id": "user_dave"}


class TestRetrieverOwnerValidation:
    """Test that ResearchRetriever enforces owner_id."""
    
    def test_retriever_requires_owner_id(self):
        """Retriever.retrieve must require owner_id parameter."""
        from rag.retrieval.retriever import ResearchRetriever
        from rag.retrieval.query import QueryRequest
        
        retriever = ResearchRetriever()
        request = QueryRequest(
            question="What is the methodology?",
            paper_ids=["paper_123"],
        )
        
        # Should raise ValueError when owner_id not provided
        with pytest.raises(ValueError, match="owner_id is required"):
            retriever.retrieve(request, owner_id="")
        
        with pytest.raises(ValueError, match="owner_id is required"):
            retriever.retrieve(request, owner_id=None)


class TestQueryPipelineOwnerValidation:
    """Test that QueryPipeline enforces owner_id."""
    
    def test_answer_question_requires_user_id(self):
        """QueryPipeline.answer_question must require user_id."""
        from rag.pipelines.query_pipeline import QueryPipeline
        
        pipeline = QueryPipeline()
        
        # Should raise ValueError when user_id not provided
        with pytest.raises(ValueError, match="user_id is required"):
            pipeline.answer_question(
                question="What is the finding?",
                user_id="",  # Empty user_id
            )
        
        with pytest.raises(ValueError, match="user_id is required"):
            pipeline.answer_question(
                question="What is the finding?",
                user_id=None,  # None user_id
            )
    
    def test_summarize_paper_requires_user_id(self):
        """QueryPipeline.summarize_paper must require user_id."""
        from rag.pipelines.query_pipeline import QueryPipeline
        
        pipeline = QueryPipeline()
        
        with pytest.raises(ValueError, match="user_id is required"):
            pipeline.summarize_paper(
                paper_id="paper_123",
                user_id="",
            )
    
    def test_compare_papers_requires_user_id(self):
        """QueryPipeline.compare_papers must require user_id."""
        from rag.pipelines.query_pipeline import QueryPipeline
        
        pipeline = QueryPipeline()
        
        with pytest.raises(ValueError, match="user_id is required"):
            pipeline.compare_papers(
                paper_ids=["paper_1", "paper_2"],
                user_id="",
            )


class TestRAGClientOwnerValidation:
    """Test that RAGClient enforces user_id."""
    
    def test_ask_question_requires_user_id(self):
        """RAGClient.ask_question must require user_id."""
        from backend.app.integrations.rag_client import RAGClient
        
        client = RAGClient()
        
        with pytest.raises(ValueError, match="user_id is required"):
            client.ask_question(
                question="What is the result?",
                user_id="",
            )
    
    def test_summarize_paper_requires_user_id(self):
        """RAGClient.summarize_paper must require user_id."""
        from backend.app.integrations.rag_client import RAGClient
        
        client = RAGClient()
        
        with pytest.raises(ValueError, match="user_id is required"):
            client.summarize_paper(
                paper_id="paper_123",
                user_id="",
            )
    
    def test_compare_papers_requires_user_id(self):
        """RAGClient.compare_papers must require user_id."""
        from backend.app.integrations.rag_client import RAGClient
        
        client = RAGClient()
        
        with pytest.raises(ValueError, match="user_id is required"):
            client.compare_papers(
                paper_ids=["paper_1", "paper_2"],
                user_id="",
            )


@pytest.mark.asyncio
class TestRAGGatewayOwnerValidation:
    """Test that RAGGateway enforces user_id."""
    
    async def test_ask_question_requires_user_id(self):
        """RAGGateway.ask_question must require user_id."""
        from backend.app.integrations.rag_gateway import RAGGateway
        
        gateway = RAGGateway()
        
        with pytest.raises(ValueError, match="user_id is required"):
            await gateway.ask_question(
                question="What is the finding?",
                user_id="",
            )
    
    async def test_summarize_paper_requires_user_id(self):
        """RAGGateway.summarize_paper must require user_id."""
        from backend.app.integrations.rag_gateway import RAGGateway
        
        gateway = RAGGateway()
        
        with pytest.raises(ValueError, match="user_id is required"):
            await gateway.summarize_paper(
                paper_id="paper_123",
                user_id="",
            )
    
    async def test_compare_papers_requires_user_id(self):
        """RAGGateway.compare_papers must require user_id."""
        from backend.app.integrations.rag_gateway import RAGGateway
        
        gateway = RAGGateway()
        
        with pytest.raises(ValueError, match="user_id is required"):
            await gateway.compare_papers(
                paper_ids=["paper_1", "paper_2"],
                user_id="",
            )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "--tb=short"])
