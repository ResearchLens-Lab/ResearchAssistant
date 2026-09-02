import os
import sys

# Ensure Python can find our queries and services directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.neo4j_service import Neo4jService
from queries import cypher_queries

class GraphIngestProcessor:
    def __init__(self, db_service: Neo4jService):
        self.db = db_service

    def ingest_paper_metadata(self, metadata: dict):
        """
        Ingests a paper, its authors, concepts, and hooks them together.
        Matches the Section 20 Team Data Contract.
        """
        paper_id = metadata.get("paper_id")
        title = metadata.get("title")
        topic = metadata.get("topic", "General")
        trends = metadata.get("research_trends", [])
        
        if not paper_id or not title:
            print("❌ Ingestion skipped: Missing core paper_id or title.")
            return False

        # 1. Create the primary Paper Node
        print(f"📦 Ingesting Paper Node: {title}")
        self.db.execute_write(cypher_queries.CREATE_PAPER_NODE, {
            "paper_id": paper_id,
            "title": title,
            "topic": topic,
            "research_trends": trends
        })

        # 2. Process and connect Authors
        authors = metadata.get("authors", [])
        for author in authors:
            author_id = author.get("author_id")
            author_name = author.get("name")
            if author_id and author_name:
                self.db.execute_write(cypher_queries.CREATE_AUTHOR_NODE, {
                    "author_id": author_id,
                    "name": author_name
                })
                self.db.execute_write(cypher_queries.ADD_WRITTEN_BY_RELATIONSHIP, {
                    "paper_id": paper_id,
                    "author_id": author_id
                })

        # 3. Process and connect Concepts/Topics
        concepts = metadata.get("concepts", [])
        for concept in concepts:
            concept_id = concept.lower().replace(" ", "_")
            self.db.execute_write(cypher_queries.CREATE_CONCEPT_NODE, {
                "concept_id": concept_id,
                "name": concept
            })
            self.db.execute_write(cypher_queries.ADD_DISCUSSES_RELATIONSHIP, {
                "paper_id": paper_id,
                "concept_id": concept_id
            })

        # 4. Process Citation Network relationships
        citations = metadata.get("citations", [])
        for cited_paper_id in citations:
            # Create a shell node for the cited paper if it doesn't exist yet
            self.db.execute_write(cypher_queries.CREATE_PAPER_NODE, {
                "paper_id": cited_paper_id,
                "title": f"Cited Reference [{cited_paper_id}]",
                "topic": None,
                "research_trends": []
            })
            self.db.execute_write(cypher_queries.ADD_CITES_RELATIONSHIP, {
                "source_id": paper_id,
                "target_id": cited_paper_id
            })

        print(f"✅ Finished structural graph ingestion for paper: {paper_id}\n")
        return True

# Quick isolated module test
if __name__ == "__main__":
    db_connection = Neo4jService()
    db_connection.connect()
    
    processor = GraphIngestProcessor(db_connection)
    
    # Mock composite data structure coming from Abhay's pipeline
    mock_payload = {
        "paper_id": "paper_rag_2026",
        "title": "Advanced Evaluation Techniques for Vector-based Graph RAG",
        "topic": "Knowledge Representation",
        "research_trends": ["GraphRAG", "Evaluation Models"],
        "authors": [
            {"author_id": "auth_gorav_01", "name": "Gorav Gumber"},
            {"author_id": "auth_harendra_04", "name": "Harendra Godara"}
        ],
        "concepts": ["GraphRAG", "Evaluation", "Vector Database"],
        "citations": ["paper_cse_001", "paper_baseline_999"]
    }
    
    processor.ingest_paper_metadata(mock_payload)
    db_connection.close()
