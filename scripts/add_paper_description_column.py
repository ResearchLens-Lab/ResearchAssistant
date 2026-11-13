import asyncio
from backend.app.database.session import get_engine
from sqlalchemy import text

async def migrate_papers_description():
    engine = get_engine()
    async with engine.begin() as conn:
        print("Checking if 'description' column exists in 'papers' table...")
        res = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'papers' AND column_name = 'description';
        """))
        if res.fetchone() is None:
            print("Adding 'description' column to 'papers' table...")
            await conn.execute(text("""
                ALTER TABLE papers ADD COLUMN description TEXT;
            """))
            print("Successfully added 'description' column to 'papers' table.")
        else:
            print("'description' column already exists in 'papers' table.")

if __name__ == "__main__":
    asyncio.run(migrate_papers_description())

