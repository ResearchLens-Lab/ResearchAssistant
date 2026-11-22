import sys, os
sys.path.insert(0, os.path.abspath("."))
import asyncio
from backend.app.database.session import get_session_factory
from backend.app.models.message import Message
from sqlalchemy import select

async def check():
    async with get_session_factory()() as db:
        res = await db.execute(select(Message).where(Message.role == 'assistant').order_by(Message.created_at.desc()).limit(3))
        msgs = res.scalars().all()
        for m in msgs:
            print('ID:', m.id)
            print('Content:', m.content[:100])
            print('Sources count:', len(m.sources) if m.sources else 0)
            if m.sources:
                print('Source 0 keys:', list(m.sources[0].keys()) if isinstance(m.sources[0], dict) else type(m.sources[0]))
                print('Source 0 citation_label:', m.sources[0].get('citation_label') if isinstance(m.sources[0], dict) else None)
            print('Meta:', m.meta)
            print('---')

if __name__ == '__main__':
    asyncio.run(check())
