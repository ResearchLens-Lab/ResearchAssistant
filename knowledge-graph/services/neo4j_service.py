import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Import the Cypher templates we just created
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from queries import cypher_queries

load_dotenv()

class Neo4jService:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.driver = None

    def connect(self):
        """Establishes connection to the Neo4j instance."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            self.driver.verify_connectivity()
            print("🚀 Successfully connected to Neo4j Graph Database!")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")

    def execute_write(self, query_template, parameters):
        """Executes a database write transaction using a Cypher template."""
        if not self.driver:
            print("❌ No active database driver connection.")
            return None
        
        try:
            with self.driver.session() as session:
                result = session.execute_write(lambda tx: tx.run(query_template, **parameters).data())
                return result
        except Exception as e:
            print(f"❌ Transaction execution failed: {e}")
            return None

    def close(self):
        """Closes the driver connection safely."""
        if self.driver:
            self.driver.close()

# Let's run a test transaction inserting mock data matching Abhay's contract!
if __name__ == "__main__":
    service = Neo4jService()
    service.connect()
    
    # Define sample data conforming to Section 19 Contract (Common IDs)
    sample_paper = {
        "paper_id": "paper_cse_001",
        "title": "An Introduction to RAG Architectures",
        "topic": "Artificial Intelligence",
        "research_trends": ["RAG", "LLM Integration"]
    }
    
    print("\n📦 Attempting to insert test paper node...")
    insertion_result = service.execute_write(cypher_queries.CREATE_PAPER_NODE, sample_paper)
    
    if insertion_result:
        print("✅ Graph Node Created successfully inside Neo4j Workspace!")
    
    service.close()
