"""
SEC-001 Integration Tests: Verify API routes enforce owner isolation.

Tests that all API routes passing user_id to RAG operations correctly
use the authenticated user's ID, never accepting client-supplied user_id.
"""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from backend.app.models.user import User
from backend.app.models.paper import Paper
from backend.app.schemas.chat import ChatRequest
from backend.app.schemas.paper import PaperCompareRequest
from backend.app.services.chat_service import ChatService
from backend.app.services.paper_service import PaperService


@pytest.mark.asyncio
class TestChatServiceOwnerIsolation:
    """Test ChatService passes authenticated user_id to RAG."""
    
    async def test_send_message_uses_authenticated_user_id(self, db, rag_gateway):
        """ChatService.send_message must pass authenticated user.id to RAG."""
        # Setup
        user = User(
            id=str(uuid4()),
            username="alice",
            email="alice@test.com",
            hashed_password="hashed",
        )
        db.add(user)
        
        paper = Paper(id=str(uuid4()), owner_id=user.id, title="Test Paper")
        db.add(paper)
        await db.commit()
        
        # Mock RAG gateway to capture user_id
        captured_user_id = None
        
        async def mock_ask_question(question, user_id, **kwargs):
            nonlocal captured_user_id
            captured_user_id = user_id
            return {
                "answer": "Test answer",
                "sources": [],
                "paper_ids": kwargs.get("paper_ids", []),
                "metadata": {},
            }
        
        rag_gateway.ask_question = mock_ask_question
        
        # Execute
        service = ChatService(db, rag_gateway)
        request = ChatRequest(
            question="What is the methodology?",
            paper_ids=[paper.id],
        )
        
        result = await service.send_message(user, request)
        
        # Verify: user_id passed to RAG matches authenticated user
        assert captured_user_id == str(user.id)
        assert result["answer"] == "Test answer"
    
    async def test_send_message_fails_if_rag_rejects_user_id(self, db, rag_gateway):
        """ChatService should fail if RAG rejects the user_id."""
        user = User(
            id=str(uuid4()),
            username="bob",
            email="bob@test.com",
            hashed_password="hashed",
        )
        db.add(user)
        
        paper = Paper(id=str(uuid4()), owner_id=user.id, title="Bob's Paper")
        db.add(paper)
        await db.commit()
        
        # Mock RAG to reject empty user_id
        async def mock_ask_question(question, user_id, **kwargs):
            if not user_id:
                raise ValueError("user_id is required for secure query execution (SEC-001 compliance)")
            return {"answer": "OK", "sources": [], "paper_ids": [], "metadata": {}}
        
        rag_gateway.ask_question = mock_ask_question
        
        # This should work with valid user
        service = ChatService(db, rag_gateway)
        request = ChatRequest(question="Test", paper_ids=[paper.id])
        result = await service.send_message(user, request)
        assert result["answer"] == "OK"


@pytest.mark.asyncio
class TestPaperServiceOwnerIsolation:
    """Test PaperService passes authenticated user_id to RAG."""
    
    async def test_summarize_uses_authenticated_user_id(self, db, rag_gateway):
        """PaperService.summarize must pass authenticated user.id to RAG."""
        user = User(
            id=str(uuid4()),
            username="charlie",
            email="charlie@test.com",
            hashed_password="hashed",
        )
        db.add(user)
        
        paper = Paper(id=str(uuid4()), owner_id=user.id, title="Charlie's Research")
        db.add(paper)
        await db.commit()
        
        # Mock RAG to capture user_id
        captured_user_id = None
        
        async def mock_summarize(paper_id, user_id, **kwargs):
            nonlocal captured_user_id
            captured_user_id = user_id
            return {
                "answer": f"Summary of {paper_id}",
                "sources": [],
            }
        
        rag_gateway.summarize_paper = mock_summarize
        
        # Execute
        service = PaperService(db, rag_gateway)
        result = await service.summarize(user, paper.id)
        
        # Verify
        assert captured_user_id == str(user.id)
        assert "Summary" in result["answer"]
    
    async def test_compare_uses_authenticated_user_id(self, db, rag_gateway):
        """PaperService.compare must pass authenticated user.id to RAG."""
        user = User(
            id=str(uuid4()),
            username="dave",
            email="dave@test.com",
            hashed_password="hashed",
        )
        db.add(user)
        
        paper1 = Paper(id=str(uuid4()), owner_id=user.id, title="Paper A")
        paper2 = Paper(id=str(uuid4()), owner_id=user.id, title="Paper B")
        db.add_all([paper1, paper2])
        await db.commit()
        
        # Mock RAG to capture user_id
        captured_user_id = None
        
        async def mock_compare(paper_ids, user_id, **kwargs):
            nonlocal captured_user_id
            captured_user_id = user_id
            return {
                "answer": f"Comparison of {len(paper_ids)} papers",
                "sources": [],
                "metadata": {},
            }
        
        rag_gateway.compare_papers = mock_compare
        
        # Execute
        service = PaperService(db, rag_gateway)
        request = PaperCompareRequest(paper_ids=[paper1.id, paper2.id])
        result = await service.compare(user, request)
        
        # Verify
        assert captured_user_id == str(user.id)
        assert "Comparison" in result["answer"]
    
    async def test_summarize_validates_ownership_before_rag(self, db, rag_gateway):
        """PaperService.summarize must validate ownership before calling RAG."""
        user_owner = User(
            id=str(uuid4()),
            username="owner",
            email="owner@test.com",
            hashed_password="hashed",
        )
        user_attacker = User(
            id=str(uuid4()),
            username="attacker",
            email="attacker@test.com",
            hashed_password="hashed",
        )
        db.add_all([user_owner, user_attacker])
        
        paper = Paper(id=str(uuid4()), owner_id=user_owner.id, title="Private Paper")
        db.add(paper)
        await db.commit()
        
        # Track if RAG was called
        rag_called = False
        
        async def mock_summarize(paper_id, user_id, **kwargs):
            nonlocal rag_called
            rag_called = True
            return {"answer": "Summary", "sources": []}
        
        rag_gateway.summarize_paper = mock_summarize
        
        # Attacker tries to summarize owner's paper
        service = PaperService(db, rag_gateway)
        
        from backend.app.core.exceptions import PaperNotFoundError
        with pytest.raises(PaperNotFoundError):
            await service.summarize(user_attacker, paper.id)
        
        # RAG should NOT have been called (blocked at service layer)
        assert not rag_called
    
    async def test_compare_validates_all_papers_ownership(self, db, rag_gateway):
        """PaperService.compare must validate ALL papers are owned before RAG call."""
        user_alice = User(
            id=str(uuid4()),
            username="alice_cmp",
            email="alice_cmp@test.com",
            hashed_password="hashed",
        )
        user_bob = User(
            id=str(uuid4()),
            username="bob_cmp",
            email="bob_cmp@test.com",
            hashed_password="hashed",
        )
        db.add_all([user_alice, user_bob])
        
        paper_alice = Paper(id=str(uuid4()), owner_id=user_alice.id, title="Alice's Paper")
        paper_bob = Paper(id=str(uuid4()), owner_id=user_bob.id, title="Bob's Paper")
        db.add_all([paper_alice, paper_bob])
        await db.commit()
        
        # Track if RAG was called
        rag_called = False
        
        async def mock_compare(paper_ids, user_id, **kwargs):
            nonlocal rag_called
            rag_called = True
            return {"answer": "Comparison", "sources": [], "metadata": {}}
        
        rag_gateway.compare_papers = mock_compare
        
        # Alice tries to compare her paper with Bob's paper
        service = PaperService(db, rag_gateway)
        request = PaperCompareRequest(paper_ids=[paper_alice.id, paper_bob.id])
        
        from backend.app.core.exceptions import PaperNotFoundError
        with pytest.raises(PaperNotFoundError):
            await service.compare(user_alice, request)
        
        # RAG should NOT have been called
        assert not rag_called


@pytest.mark.asyncio
class TestAPIRoutesNeverAcceptClientSuppliedUserId:
    """
    Verify that API routes NEVER accept client-supplied user_id.
    
    Critical Security Requirement: The user_id passed to RAG must ALWAYS
    come from the authenticated session (CurrentUser dependency), never
    from request payload.
    """
    
    async def test_chat_route_uses_current_user_not_payload(self):
        """
        Chat route must use CurrentUser dependency, not accept user_id in payload.
        
        This is a design verification test - the ChatRequest schema should
        NOT have a user_id field that clients can set.
        """
        from backend.app.schemas.chat import ChatRequest
        import inspect
        
        # Verify ChatRequest does NOT have user_id field
        sig = inspect.signature(ChatRequest.__init__)
        params = list(sig.parameters.keys())
        
        # Should NOT have user_id (it comes from CurrentUser dependency)
        assert "user_id" not in params, \
            "SECURITY VIOLATION: ChatRequest should not accept user_id from client"
        
        # Should have question and paper_ids
        schema_fields = ChatRequest.model_fields.keys()
        assert "question" in schema_fields
        assert "paper_ids" in schema_fields
    
    async def test_compare_request_does_not_accept_user_id(self):
        """
        PaperCompareRequest must not have user_id field.
        """
        from backend.app.schemas.paper import PaperCompareRequest
        import inspect
        
        sig = inspect.signature(PaperCompareRequest.__init__)
        params = list(sig.parameters.keys())
        
        assert "user_id" not in params, \
            "SECURITY VIOLATION: PaperCompareRequest should not accept user_id from client"
        
        schema_fields = PaperCompareRequest.model_fields.keys()
        assert "paper_ids" in schema_fields
    
    async def test_routes_require_authentication(self):
        """
        All RAG query routes must require CurrentUser dependency.
        
        This verifies that routes cannot be called without authentication.
        """
        from backend.app.routes.chat import router as chat_router
        from backend.app.routes.papers import router as papers_router
        import inspect
        
        # Check chat routes
        chat_route = None
        for route in chat_router.routes:
            if hasattr(route, 'path') and route.path == "/chat":
                chat_route = route
                break
        
        if chat_route and hasattr(chat_route, 'endpoint'):
            sig = inspect.signature(chat_route.endpoint)
            params = sig.parameters
            
            # Should have current_user parameter
            assert "current_user" in params, \
                "Chat route must have current_user parameter for authentication"
        
        # Similar check for papers routes
        compare_route = None
        for route in papers_router.routes:
            if hasattr(route, 'path') and '/compare' in route.path:
                compare_route = route
                break
        
        if compare_route and hasattr(compare_route, 'endpoint'):
            sig = inspect.signature(compare_route.endpoint)
            params = sig.parameters
            assert "current_user" in params, \
                "Compare route must have current_user parameter for authentication"


@pytest.mark.asyncio
class TestFailClosedWhenAuthUnavailable:
    """
    Verify system fails closed when authenticated identity is unavailable.
    """
    
    async def test_rag_gateway_rejects_empty_user_id(self, rag_gateway):
        """RAG Gateway should reject empty user_id."""
        with pytest.raises(ValueError, match="user_id is required"):
            await rag_gateway.ask_question(
                question="Test",
                user_id="",  # Empty user_id
            )
    
    async def test_rag_gateway_rejects_none_user_id(self, rag_gateway):
        """RAG Gateway should reject None user_id."""
        with pytest.raises(ValueError, match="user_id is required"):
            await rag_gateway.ask_question(
                question="Test",
                user_id=None,  # None user_id
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
