from pydantic import BaseModel, Field
from typing import List, Optional

# --- NODE SCHEMAS ---

class PaperNode(BaseModel):
    """Represents a Paper Node in Neo4j"""
    paper_id: str = Field(..., description="The unique ID shared across all team databases")
    title: str
    topic: Optional[str] = None
    research_trends: Optional[List[str]] = []

class AuthorNode(BaseModel):
    """Represents an Author Node in Neo4j"""
    author_id: str = Field(..., description="The unique ID shared across all team databases")
    name: str

class ConceptNode(BaseModel):
    """Represents a Concept/Topic Node in Neo4j (e.g., 'RAG', 'LLM')"""
    concept_id: str
    name: str

# --- RELATIONSHIP SCHEMAS ---

class CitesRelationship(BaseModel):
    """PaperA -CITES-> PaperB"""
    source_paper_id: str
    target_paper_id: str

class WrittenByRelationship(BaseModel):
    """Paper -WRITTEN_BY-> Author"""
    paper_id: str
    author_id: str

class DiscussesRelationship(BaseModel):
    """Paper -DISCUSSES-> Concept"""
    paper_id: str
    concept_id: str
