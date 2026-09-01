# Cypher query templates for the Knowledge Graph Subsystem

CREATE_PAPER_NODE = """
MERGE (p:Paper {paper_id: $paper_id})
ON CREATE SET p.title = $title, p.topic = $topic, p.research_trends = $research_trends
ON MATCH SET p.title = $title, p.topic = $topic, p.research_trends = $research_trends
RETURN p
"""

CREATE_AUTHOR_NODE = """
MERGE (a:Author {author_id: $author_id})
ON CREATE SET a.name = $name
ON MATCH SET a.name = $name
RETURN a
"""

CREATE_CONCEPT_NODE = """
MERGE (c:Concept {concept_id: $concept_id})
ON CREATE SET c.name = $name
RETURN c
"""

ADD_CITES_RELATIONSHIP = """
MATCH (p1:Paper {paper_id: $source_id})
MATCH (p2:Paper {paper_id: $target_id})
MERGE (p1)-[r:CITES]->(p2)
RETURN r
"""

ADD_WRITTEN_BY_RELATIONSHIP = """
MATCH (p:Paper {paper_id: $paper_id})
MATCH (a:Author {author_id: $author_id})
MERGE (p)-[r:WRITTEN_BY]->(a)
RETURN r
"""

ADD_DISCUSSES_RELATIONSHIP = """
MATCH (p:Paper {paper_id: $paper_id})
MATCH (c:Concept {concept_id: $concept_id})
MERGE (p)-[r:DISCUSSES]->(c)
RETURN r
"""
