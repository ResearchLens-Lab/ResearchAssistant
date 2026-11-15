import sqlite3

conn = sqlite3.connect(".chroma/researchlens_lexical.sqlite3")
cur = conn.cursor()
cur.execute(
    "SELECT text FROM lexical_chunks WHERE chunk_id = '5d009428-7a4c-4225-9878-ae252140b1c3_c0007_d38c39565-1e4f-4426-a313-c613485deffb_p2-3'"
)
row = cur.fetchone()
print(row[0])

