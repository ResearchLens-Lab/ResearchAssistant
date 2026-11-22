import sqlite3

conn = sqlite3.connect(".chroma/researchlens_lexical.sqlite3")
cur = conn.cursor()
cur.execute(
    "SELECT chunk_id, section, page_start, text FROM lexical_chunks WHERE paper_id = ? AND text LIKE ? LIMIT 5",
    ("5d009428-7a4c-4225-9878-ae252140b1c3", "%METHODOLOGY%")
)
rows = cur.fetchall()
print(f"Found {len(rows)} chunks matching METHODOLOGY:")
for r in rows:
    print(f"Chunk: {r[0]} | Sec: {r[1]} | Page: {r[2]}")
    print(r[3][:250])
    print("---")
