"""
Integration tests for chat routes with SEC-001 owner isolation.

Tests the full stack from HTTP route → Service → RAG Gateway to ensure
authenticated user_id flows correctly through all layers.
"""

import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
class TestChatRouteIntegration:
    """Integration tests for /api/v1/chat endpoint with owner isolation."""
    
    async def test_chat_route_sends_authenticated_user_to_rag(self, client: AsyncClient, auth_headers):
        """
        POST /api/v1/chat must send authenticated user's ID to RAG, not accept from client.
        """
        # Create paper using authenticated user
        from backend.tests.conftest import create_paper
        paper = await create_paper(client, auth_headers, title="Integration Test Paper")
        
        # Make authenticated chat request
        response = await client.post(
            "/api/v1/chat",
            json={
                "question": "What is the main finding?",
                "paper_ids": [paper["id"]],
            },
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify response structure
        assert "conversation_id" in data
        assert "answer" in data
        assert paper["id"] in data["paper_ids"]
    
    async def test_chat_route_rejects_unauthenticated_requests(self, client: AsyncClient):
        """
        POST /api/v1/chat must reject requests without authentication.
        """
        response = await client.post(
            "/api/v1/chat",
            json={
                "question": "Test question",
                "paper_ids": [],
            },
            # No auth headers
        )
        
        # Should return 401 Unauthorized or 403 Forbidden
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
    
    async def test_chat_route_prevents_cross_user_paper_access(self, client: AsyncClient, auth_headers, second_user_headers):
        """
        User cannot query papers they don't own, even if they know the paper_id.
        """
        from backend.tests.conftest import create_paper
        
        # First user creates a paper
        paper_user1 = await create_paper(client, auth_headers, title="User 1 Paper")
        
        # Second user tries to query first user's paper
        response = await client.post(
            "/api/v1/chat",
            json={
                "question": "What is the methodology?",
                "paper_ids": [paper_user1["id"]],  # First user's paper
            },
            headers=second_user_headers,  # Second user's credentials
        )
        
        # Should be rejected (404 or 403)
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.asyncio
class TestPaperRouteIntegration:
    """Integration tests for paper summary/compare routes with owner isolation."""
    
    async def test_summarize_route_uses_authenticated_user(self, client: AsyncClient, auth_headers):
        """
        POST /api/v1/papers/{paper_id}/summary must use authenticated user.
        """
        from backend.tests.conftest import create_paper
        
        paper = await create_paper(client, auth_headers, title="Summary Test Paper")
        
        response = await client.post(
            f"/api/v1/papers/{paper['id']}/summary",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "answer" in data
        assert data["paper_id"] == paper["id"]
    
    async def test_compare_route_uses_authenticated_user(self, client: AsyncClient, auth_headers):
        """
        POST /api/v1/papers/compare must use authenticated user.
        """
        from backend.tests.conftest import create_paper
        
        paper1 = await create_paper(client, auth_headers, title="Paper 1")
        paper2 = await create_paper(client, auth_headers, title="Paper 2")
        
        response = await client.post(
            "/api/v1/papers/compare",
            json={
                "paper_ids": [paper1["id"], paper2["id"]],
            },
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "answer" in data
        assert set(data["paper_ids"]) == {paper1["id"], paper2["id"]}
    
    async def test_summarize_rejects_other_users_paper(self, client: AsyncClient, auth_headers, second_user_headers):
        """
        User cannot summarize papers they don't own.
        """
        from backend.tests.conftest import create_paper
        
        # First user creates a paper
        paper = await create_paper(client, auth_headers, title="Private Paper")
        
        # Second user tries to summarize first user's paper
        response = await client.post(
            f"/api/v1/papers/{paper['id']}/summary",
            headers=second_user_headers,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    async def test_compare_rejects_if_any_paper_not_owned(self, client: AsyncClient, auth_headers, second_user_headers):
        """
        Compare must reject if ANY paper in the list is not owned by user.
        """
        from backend.tests.conftest import create_paper
        
        # First user creates a paper
        paper1 = await create_paper(client, auth_headers, title="User 1 Paper")
        
        # Second user creates a paper
        paper2 = await create_paper(client, second_user_headers, title="User 2 Paper")
        
        # Second user tries to compare their paper with first user's paper
        response = await client.post(
            "/api/v1/papers/compare",
            json={
                "paper_ids": [paper2["id"], paper1["id"]],  # Mix of owned and not owned
            },
            headers=second_user_headers,
        )
        
        # Should be rejected
        assert response.status_code == status.HTTP_404_NOT_FOUND


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
