import asyncio
from backend.app.database.session import get_engine
from sqlalchemy import text

async def check():
    engine = get_engine()
    async with engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'papers'
            ORDER BY ordinal_position;
        """))
        for row in res.fetchall():
            print(row)

if __name__ == '__main__':
    asyncio.run(check())

