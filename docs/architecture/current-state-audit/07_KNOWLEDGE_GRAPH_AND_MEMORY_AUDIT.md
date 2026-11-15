# Knowledge Graph and Associative Memory Architecture Audit

**Document Version**: 1.0  
**Last Updated**: November 8, 2026

---

## Executive Finding

**CRITICAL**: Knowledge graph implementation is **PLACEHOLDER ONLY**. Directories exist but contain no working code. Associative memory, temporal tracking, and episodic research history are **NOT IMPLEMENTED**.

---

## Table of Contents

1. [Current Implementation Status](#current-implementation-status)
2. [What Exists Today](#what-exists-today)
3. [What Is Missing](#what-is-missing)
4. [Associative Memory Requirements](#associative-memory-requirements)
5. [Proposed Temporal Knowledge Graph Architecture](#proposed-temporal-knowledge-graph-architecture)
6. [Memory Types for Research Intelligence](#memory-types-for-research-intelligence)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Current Implementation Status

### Directory Structure

```
knowledge-graph/
├── graph-api/          # EMPTY/PLACEHOLDER
├── ingestion/          # EMPTY/PLACEHOLDER
├── models/             # EMPTY/PLACEHOLDER
├── queries/            # EMPTY/PLACEHOLDER
└── services/           # EMPTY/PLACEHOLDER
```

**Evidence**: `list_directory knowledge-graph/` shows directories but no Python files found

**Status**: ❌ **NO IMPLEMENTATION**

### What the Frontend Expects

**Route**: `/graph` exists in `frontend/src/app/(workbench)/graph/`

**Expected Features** (based on typical research map UIs):
- Visual graph of papers, entities, relationships
- Interactive node exploration
- Temporal view of knowledge evolution
- Related concept discovery

**Current Backend Support**: ❌ **NONE**

**Evidence**: No `/api/v1/graph` or `/api/v1/research/map` endpoints detected

---

## What Exists Today

### 1. Conversation History (Limited Episodic Memory)

**Implementation**: `backend/app/models/conversation.py`, `backend/app/models/message.py`

**Stored Data**:
- Conversation sessions (title, paper_ids, user_id, created_at)
- Messages (role, content, sources, created_at)

**Capabilities**:
- ✅ View previous conversations
- ✅ Continue existing conversations
- ✅ See past questions and answers

**Limitations**:
- ❌ No concept extraction from conversations
- ❌ No relationship discovery
- ❌ No cross-conversation memory
- ❌ No "recall similar previous research"

**Evidence**: Database models exist, no semantic reuse of past queries

### 2. RAG Retrieval Context (Stateless)

**Current Behavior**: Each query retrieves from indexed documents independently

**No Memory**:
- ❌ Previous answers not reused as evidence
- ❌ Previously identified entities not tracked
- ❌ Related queries not linked
- ❌ Contradiction detection across sessions

**Evidence**: `rag/pipelines/query_pipeline.py` - each query is independent

### 3. Paper Metadata (Basic Relationships)

**Stored**: `papers` table has title, authors, DOI, venue

**Relationships**:
- ✅ User owns papers (FK: owner_id)
- ✅ Papers have documents (FK: paper_id)
- ❌ No paper-to-paper relationships (citations, similarities)
- ❌ No author-to-author relationships
- ❌ No venue/conference networks
- ❌ No topic/domain clustering

**Evidence**: `backend/app/models/paper.py` - isolated records

---

## What Is Missing

### 1. Entity Extraction & Recognition

**Not Implemented**:
- ❌ Method/algorithm extraction (e.g., "Transformer", "BERT", "CNN")
- ❌ Dataset extraction (e.g., "ImageNet", "COCO", "WMT 2014")
- ❌ Metric extraction (e.g., "BLEU score", "F1", "Accuracy")
- ❌ Claim extraction (e.g., "Attention is more efficient than RNNs")
- ❌ Author/institution recognition
- ❌ Research domain classification

**Evidence**: No NER model, no entity extraction pipeline detected

### 2. Relationship Modeling

**Not Implemented**:
- ❌ CITES (Paper A cites Paper B)
- ❌ USES_METHOD (Paper uses Transformer architecture)
- ❌ EVALUATED_ON (Method evaluated on ImageNet)
- ❌ IMPROVES_UPON (Our method improves BERT)
- ❌ CONTRADICTS (Finding X contradicts previous claim Y)
- ❌ EXTENDS (Paper extends prior work Z)
- ❌ SUPPORTS (Evidence E supports Claim C)

**Evidence**: No relationship extraction code

### 3. Graph Storage & Query

**No Graph Database**:
- ❌ No Neo4j integration
- ❌ No NetworkX graph structures
- ❌ No RDF triple store
- ❌ No custom graph implementation

**No Graph Queries**:
- ❌ Find related papers (2-hop neighbor search)
- ❌ Trace citation chains
- ❌ Discover similar methods
- ❌ Find supporting/contradicting evidence
- ❌ Temporal knowledge evolution

**Evidence**: No graph database config, no query implementations

### 4. Temporal Knowledge Tracking

**Not Tracked**:
- ❌ When entity first mentioned
- ❌ When relationship discovered
- ❌ When claim verified/refuted
- ❌ Knowledge updates over time
- ❌ Research session timestamps per entity

**Evidence**: No temporal attributes on extracted knowledge

### 5. Associative Memory

**Not Implemented**:
- ❌ "Recall when I researched similar topic"
- ❌ "Connect to previous findings on X"
- ❌ "Show evolution of concept Y across my papers"
- ❌ "Detect contradictions with past research"
- ❌ "Surface related knowledge from 6 months ago"

**Evidence**: Queries are stateless, no memory reuse

---

## Associative Memory Requirements

### Human Research Memory Model

**How Researchers Actually Work**:

1. **Episodic Memory**: "I read this paper last month that discussed X"
2. **Semantic Memory**: "I know that CNNs are used for image classification"
3. **Source Memory**: "That claim came from the Transformer paper, page 4"
4. **Temporal Memory**: "I discovered this relationship after reading 3 related papers"
5. **Associative Memory**: "This new paper reminds me of Y, which relates to Z"
6. **Contradiction Memory**: "This contradicts what Paper A said about X"
7. **Gap Memory**: "I still don't have evidence for claim C"

### Current ResearchLens Memory Model

**Reality**: Nearly stateless

1. **Episodic Memory**: ⚠️ Partial (conversation history, but no semantic reuse)
2. **Semantic Memory**: ❌ None (no persistent concept extraction)
3. **Source Memory**: ✅ Exists (RAG citations track provenance)
4. **Temporal Memory**: ❌ None (no timestamps on knowledge)
5. **Associative Memory**: ❌ None (no connections between concepts)
6. **Contradiction Memory**: ❌ None (no conflict detection)
7. **Gap Memory**: ❌ None (no knowledge incompleteness tracking)

**Evidence**: Architecture inspection shows stateless query processing

---

## Proposed Temporal Knowledge Graph Architecture

### Graph Schema v1 (Minimum Viable)

#### Node Types

1. **Paper**
   - Properties: paper_id, title, authors, year, doi, added_date
   - Source: PostgreSQL papers table

2. **Concept**
   - Properties: concept_id, name, type (method/dataset/metric/domain), first_seen, last_updated
   - Source: Extracted from papers via NER

3. **Claim**
   - Properties: claim_id, text, confidence, source_paper_id, page, first_seen
   - Source: Extracted via claim detection model

4. **Research Session**
   - Properties: session_id, user_id, created_at, topic_summary
   - Source: Conversation sessions

#### Relationship Types

1. **MENTIONS**
   - (Paper)-[:MENTIONS {page: int, section: str, timestamp: datetime}]->(Concept)
   - Tracks which papers mention which concepts

2. **USES**
   - (Paper)-[:USES {context: str, timestamp: datetime}]->(Concept)
   - Specifically for methods/datasets used in research

3. **SUPPORTS**
   - (Paper)-[:SUPPORTS {evidence_text: str, confidence: float, discovered: datetime}]->(Claim)
   - Evidence backing a claim

4. **CONTRADICTS**
   - (Paper)-[:CONTRADICTS {explanation: str, discovered: datetime}]->(Claim)
   - Evidence refuting a claim

5. **RELATED_TO**
   - (Concept)-[:RELATED_TO {strength: float, co_occurrences: int, last_seen: datetime}]->(Concept)
   - Semantic similarity between concepts

6. **EXPLORED_IN**
   - (Research Session)-[:EXPLORED_IN {timestamp: datetime}]->(Concept)
   - User research history

7. **CITES** (future)
   - (Paper)-[:CITES {context: str}]->(Paper)
   - Citation relationships (requires reference extraction)

### Temporal Attributes (Critical)

**Every Relationship Must Include**:
```python
{
    "created_at": "2026-11-08T15:30:00Z",  # When first discovered
    "last_confirmed": "2026-11-10T09:15:00Z",  # Most recent verification
    "confidence": 0.85,  # Extraction confidence
    "source_paper_id": "paper_abc",
    "source_page": 4,
    "extraction_method": "NER_model_v1",  # Provenance
    "user_id": "user_xyz"  # Who discovered it
}
```

**Why Temporal**:
- Track knowledge evolution
- Show "I learned X after reading Y"
- Detect when relationships emerged
- Enable time-based queries

### Example Graph Structure

```
(Paper: Transformer)
  -[:MENTIONS {page: 1, timestamp: "2026-11-08"}]-> (Concept: Attention Mechanism)
  -[:USES {context: "encoder-decoder", timestamp: "2026-11-08"}]-> (Concept: Multi-Head Attention)
  -[:SUPPORTS {confidence: 0.9, discovered: "2026-11-08"}]-> (Claim: "Attention outperforms RNNs")
  
(Concept: Attention Mechanism)
  -[:RELATED_TO {strength: 0.7, last_seen: "2026-11-09"}]-> (Concept: Self-Attention)
  -[:RELATED_TO {strength: 0.5, last_seen: "2026-11-09"}]-> (Concept: CNN)
  
(Research Session: "Understanding Transformers")
  -[:EXPLORED_IN {timestamp: "2026-11-08T14:00:00"}]-> (Concept: Attention Mechanism)
  -[:EXPLORED_IN {timestamp: "2026-11-08T14:15:00"}]-> (Concept: BERT)
```

### Graph Queries (Desired)

**Q1: Find related concepts**
```cypher
MATCH (c1:Concept {name: "Transformer"})-[:RELATED_TO]-(c2:Concept)
RETURN c2
ORDER BY relationship.strength DESC
LIMIT 10
```

**Q2: Trace knowledge discovery timeline**
```cypher
MATCH (session:ResearchSession)-[:EXPLORED_IN]->(concept:Concept)
WHERE session.user_id = "user_xyz"
RETURN concept, session.created_at
ORDER BY session.created_at
```

**Q3: Find supporting evidence for claim**
```cypher
MATCH (paper:Paper)-[r:SUPPORTS]->(claim:Claim)
WHERE claim.text CONTAINS "attention is efficient"
RETURN paper, r.evidence_text, r.confidence
```

**Q4: Detect contradictions**
```cypher
MATCH (p1:Paper)-[:SUPPORTS]->(claim:Claim)<-[:CONTRADICTS]-(p2:Paper)
RETURN p1, p2, claim
```

**Q5: Show concept evolution**
```cypher
MATCH (paper:Paper)-[r:MENTIONS]->(concept:Concept {name: "BERT"})
RETURN paper, r.timestamp
ORDER BY r.timestamp
```

---

## Memory Types for Research Intelligence

### 1. Episodic Memory (Research Sessions)

**Definition**: Remember specific research events

**Implementation**:
- Store research sessions as graph nodes
- Link sessions to concepts explored
- Link sessions to papers read
- Link sessions to questions asked

**Use Cases**:
- "Show me what I learned about X last month"
- "When did I first encounter concept Y?"
- "Revisit my previous research on topic Z"

**Storage**: Graph nodes + PostgreSQL conversations

### 2. Semantic Memory (Concepts & Facts)

**Definition**: General knowledge about research domain

**Implementation**:
- Extract concepts from all papers
- Build concept-to-concept relationships
- Track methods, datasets, metrics independently
- Maintain concept definitions/descriptions

**Use Cases**:
- "What is BERT?" (aggregate from all papers mentioning it)
- "List all image classification methods I've indexed"
- "Show me all datasets used for object detection"

**Storage**: Graph nodes (Concept, Method, Dataset, Metric)

### 3. Source Memory (Evidence Provenance)

**Definition**: Where knowledge came from

**Implementation**: ✅ **Already exists in RAG**
- Chunk IDs track source document + page
- Citations map claims to evidence

**Use Cases**:
- "Which paper claimed X?"
- "Show me the original text supporting Y"

**Storage**: RAG chunk metadata, citation mappings

### 4. Temporal Memory (Knowledge Timeline)

**Definition**: When knowledge was discovered/updated

**Implementation**:
- Timestamp all graph relationships
- Track first_seen, last_confirmed dates
- Record research session chronology

**Use Cases**:
- "How has my understanding of X evolved?"
- "Show knowledge added after date Y"
- "What did I learn this week?"

**Storage**: Temporal attributes on graph edges

### 5. Associative Memory (Connections)

**Definition**: Links between related concepts

**Implementation**:
- Co-occurrence analysis (concepts in same papers)
- Explicit RELATED_TO edges
- Similarity-based clustering

**Use Cases**:
- "This new paper about X reminds me of Y"
- "Find papers related to my current research"
- "Connect concept A to previously studied B"

**Storage**: RELATED_TO edges with strength scores

### 6. Contradiction Memory (Conflicts)

**Definition**: Track disagreements in research

**Implementation**:
- Extract claims from papers
- Detect contradicting claims via semantic similarity
- Store CONTRADICTS relationships

**Use Cases**:
- "Paper A says X, but Paper B says not-X"
- "Show me conflicting findings on topic Y"
- "Which paper refutes claim Z?"

**Storage**: Claim nodes + CONTRADICTS edges

### 7. Gap Memory (Unknowns)

**Definition**: Track what is NOT known

**Implementation**:
- Identify questions without satisfactory answers
- Track claims without sufficient evidence
- Store "need more research" flags

**Use Cases**:
- "What questions remain unanswered?"
- "Which claims lack strong evidence?"
- "Suggest papers to fill knowledge gaps"

**Storage**: Gap nodes or flags on Claim nodes

---

## Implementation Roadmap

### Phase 1: Basic Graph Foundation (Month 1-2)

**Goal**: Store papers and simple relationships

**Tasks**:
1. Choose graph database (Neo4j recommended)
2. Define schema v1 (Paper, Concept, MENTIONS)
3. Set up Neo4j Docker container
4. Implement graph client in `knowledge-graph/services/`
5. Create API endpoints: `POST /api/v1/graph/papers`

**Deliverable**: Papers stored as graph nodes

### Phase 2: Entity Extraction Pipeline (Month 2-3)

**Goal**: Extract concepts from papers

**Tasks**:
1. Train/integrate NER model (or use spaCy with custom patterns)
2. Implement extraction in `knowledge-graph/ingestion/`
3. Extract methods, datasets, metrics from chunks
4. Create MENTIONS relationships with page tracking
5. Deduplicate and canonicalize entities

**Deliverable**: Concepts auto-extracted and linked to papers

### Phase 3: Temporal Tracking (Month 3-4)

**Goal**: Add timestamps to all knowledge

**Tasks**:
1. Add created_at, last_confirmed to all edges
2. Store extraction provenance (which model, when)
3. Implement research session tracking
4. Link conversations to explored concepts

**Deliverable**: Timeline view of knowledge discovery

### Phase 4: Associative Memory (Month 4-5)

**Goal**: Enable "recall related research"

**Tasks**:
1. Compute concept co-occurrence scores
2. Create RELATED_TO edges
3. Implement graph traversal queries
4. Build "suggest related papers" feature
5. Surface previous research in new queries

**Deliverable**: Query answering uses past knowledge

### Phase 5: Contradiction Detection (Month 5-6)

**Goal**: Identify conflicting findings

**Tasks**:
1. Implement claim extraction
2. Detect semantic similarity between claims
3. Identify contradicting claims (negation, opposite metrics)
4. Create CONTRADICTS relationships
5. Surface contradictions in UI

**Deliverable**: "Paper A contradicts Paper B" alerts

### Phase 6: Visual Research Map (Month 6-7)

**Goal**: Interactive frontend graph

**Tasks**:
1. Implement graph query endpoints
2. Serialize graph to frontend-friendly JSON
3. Integrate graph visualization library (vis.js, Cytoscape.js)
4. Build interactive node exploration
5. Add temporal filtering (show graph at time T)

**Deliverable**: Working `/graph` page with visual network

### Phase 7: Advanced Memory Features (Month 7+)

**Goal**: Full associative memory

**Tasks**:
1. Implement gap detection (unanswered questions)
2. Build knowledge evolution viewer
3. Add "similar to past research" recommendations
4. Implement cross-session concept reuse
5. Train custom relation extraction model

**Deliverable**: Fully associative research assistant

---

## Technical Considerations

### Graph Database Selection

**Option 1: Neo4j** (Recommended)
- ✅ Mature, full-featured graph database
- ✅ Cypher query language (expressive)
- ✅ Good Python driver (neo4j-driver)
- ✅ Free community edition
- ❌ Separate service to run

**Option 2: NetworkX** (Python library)
- ✅ Pure Python, no separate service
- ✅ Simple for small graphs
- ❌ No persistent storage (requires serialization)
- ❌ Not scalable to millions of nodes

**Option 3: SQLite with Graph Extension**
- ✅ No new dependencies
- ✅ Can reuse existing SQLite knowledge
- ❌ Graph queries less expressive
- ❌ Not ideal for complex traversals

**Recommendation**: **Neo4j** for production, **NetworkX** for prototyping

### Entity Extraction Strategy

**Option 1: Rule-Based (Immediate)**
- Use domain lexicons (CS/ML terms)
- Regex patterns for datasets ("WMT 2014", "ImageNet")
- Quick to implement, limited recall

**Option 2: Pretrained NER (Short-Term)**
- Use spaCy's scientific NER models
- Or SciSpaCy for biomedical (adapt for CS)
- Moderate quality, no training needed

**Option 3: Custom Trained NER (Long-Term)**
- Annotate 5,000+ paper excerpts
- Train BERT-NER on academic corpus
- Best quality, requires labeling effort

**Recommendation**: Start with **Option 1 + 2**, migrate to **Option 3**

### Performance & Scalability

**Graph Size Projections**:
- 1,000 papers → ~10,000 concepts → ~50,000 edges
- 10,000 papers → ~100,000 concepts → ~500,000 edges

**Query Performance**:
- Neo4j handles millions of nodes efficiently
- 2-hop traversals: <100ms
- Complex multi-hop: 100ms-1s

**Maintenance**:
- Periodically merge duplicate concepts
- Update relationship strengths based on new papers
- Archive stale knowledge (optional)

---

## Summary

### Current State

❌ **No knowledge graph** implementation  
❌ **No entity extraction** pipeline  
❌ **No associative memory** features  
⚠️ **Partial episodic memory** (conversation history only)  
✅ **Strong source memory** (RAG citations)

### Required for Associative Memory

1. **Graph Database**: Neo4j or equivalent
2. **Entity Extraction**: NER model for concepts
3. **Relationship Extraction**: Detect MENTIONS, USES, SUPPORTS
4. **Temporal Tracking**: Timestamps on all knowledge
5. **Cross-Session Reuse**: Query past knowledge in new contexts
6. **Contradiction Detection**: Identify conflicting claims

### Implementation Effort

- **Phase 1-2 (Basic Graph)**: 2-3 months, 1 developer
- **Phase 3-4 (Temporal + Associative)**: 2-3 months, 1 developer
- **Phase 5-6 (Contradictions + Visual)**: 2-3 months, 1 developer
- **Total**: 6-9 months for full associative memory system

### Key Architectural Decision

**Choice**: Neo4j vs SQLite/PostgreSQL for graph

**Recommendation**: Use **Neo4j** for true graph capabilities, but start with **PostgreSQL + simple tables** to validate schema before committing to graph database infrastructure.

---

**Next Document**: [12_GAP_ANALYSIS_AND_TECHNICAL_DEBT.md](./12_GAP_ANALYSIS_AND_TECHNICAL_DEBT.md)
