import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

# Ensure Python can locate our services directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.neo4j_service import Neo4jService

app = FastAPI(
    title="ResearchLens Knowledge Graph API",
    description="Exposes Neo4j citation and research trend data to the team frontend.",
    version="1.0.0"
)

# Enable CORS so Himanshu's frontend can make requests to your API cleanly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to our active Neo4j database service
db = Neo4jService()
db.connect()

@app.get("/api/v1/graph/health")
def health_check():
    """Simple endpoint to verify if the Knowledge Graph API layer is alive."""
    return {"status": "healthy", "module": "knowledge-graph"}

@app.get("/api/v1/graph/network/{paper_id}")
def get_citation_network(paper_id: str):
    """
    Fetches a specific paper's citation network (cites, written_by, discusses).
    Matches Section 17 & Section 41 Data Flow contracts.
    """
    query = """
    MATCH (p:Paper {paper_id: $paper_id})
    OPTIONAL MATCH (p)-[c:CITES]->(cited:Paper)
    OPTIONAL MATCH (p)-[w:WRITTEN_BY]->(a:Author)
    OPTIONAL MATCH (p)-[d:DISCUSSES]->(concept:Concept)
    RETURN p as target_paper, 
           collect(distinct cited) as citations, 
           collect(distinct a) as authors, 
           collect(distinct concept) as concepts
    """
    
    if not db.driver:
        raise HTTPException(status_code=500, detail="Database driver connection is offline.")
        
    try:
        with db.driver.session() as session:
            records = session.run(query, paper_id=paper_id).data()
            if not records:
                raise HTTPException(status_code=404, detail=f"Paper with ID '{paper_id}' not found.")
            return {"paper_id": paper_id, "network_data": records[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph query failed: {str(e)}")

@app.on_event("shutdown")
def shutdown_event():
    """Safely closes connection pools when the API server terminates."""
    db.close()
