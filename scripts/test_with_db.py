import sys, os
sys.path.insert(0, os.path.abspath("."))
import asyncio
from backend.app.database.session import get_session_factory
from backend.app.services.chat_service import ChatService
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.chat import ChatRequest

async def run():
    async with get_session_factory()() as db:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id("4526f09d-ae50-47d8-8a73-ffe73e3dc0dd")
        if not user:
            print("User not found!")
            return
        
        chat_service = ChatService(db, RAGGateway())
        payload = ChatRequest(
            question="What is cybersecurity?",
            paper_ids=["5d009428-7a4c-4225-9878-ae252140b1c3"],
            answer_mode="EVIDENCE_FIRST"
        )
        res = await chat_service.send_message(user, payload)
        print("Status: Success!")
        print("Answer:\n", res["answer"][:400])
        print("Sources count:", len(res["sources"]))
        if res["sources"]:
            print("Source 0 citation_label:", res["sources"][0].get("citation_label"))
            print("Source 0 author_metadata:", res["sources"][0].get("author_metadata"))
            print("Source 0 paper_title:", res["sources"][0].get("paper_title"))

if __name__ == '__main__':
    asyncio.run(run())

