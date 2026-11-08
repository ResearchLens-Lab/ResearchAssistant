"""
Pytest configuration and shared test fixtures for ResearchLens RAG.
"""

import pytest
import os
import shutil
import tempfile
from pathlib import Path

# Automated tests use deterministic providers and never access cloud APIs.
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["EMBEDDING_MODEL"] = "mock-dense-384"
os.environ["EMBEDDING_DIMENSION"] = "384"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["APP_ENV"] = "testing"

from rag.ingestion.document_normalizer import Page, Section, DocumentMetadata, NormalizedDocument, DocumentNormalizer
from rag.chunking.chunker import DocumentChunker
from rag.embeddings.embedder import DeterministicMockEmbedder
from rag.vectorstore.chroma_client import ChromaClientFactory
from rag.vectorstore.collection_manager import CollectionManager
from rag.vectorstore.vector_repository import VectorRepository
from rag.retrieval.retriever import ResearchRetriever
from rag.context.context_builder import ContextBuilder
from rag.generation.llm_client import MockGroundedLLMClient
from rag.generation.generator import GroundedGenerator
from rag.pipelines.ingest_pipeline import IngestionPipeline
from rag.pipelines.query_pipeline import QueryPipeline


SAMPLE_PAPER_TEXT = """
Attention Is All You Need

Abstract
The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer, a model architecture eschewing recurrence and relying entirely on an attention mechanism to draw global dependencies between input and output.

1. Introduction
Recurrent neural networks, long short-term memory and gated recurrent neural networks in particular, have been firmly established as state of the art approaches in sequence modeling. Recurrent models typically factor computation along the symbol positions of the input and output sequences. This inherently sequential nature precludes parallelization within training examples. The Transformer allows for significantly more parallelization and can reach a new state of the art in translation quality.

2. Related Work
The goal of reducing sequential computation also forms the foundation of the Extended Neural GPU, ByteNet and ConvS2S, all of which use convolutional neural networks as basic building blocks. In these models, the number of operations required to relate signals from two arbitrary input or output positions grows in the distance between positions. In the Transformer this is reduced to a constant number of operations.

3. Methodology
An attention function can be described as mapping a query and a set of key-value pairs to an output. The output is computed as a weighted sum of the values, where the weight assigned to each value is computed by a compatibility function of the query with the corresponding key. We compute the Scaled Dot-Product Attention: Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V. Multi-Head Attention allows the model to jointly attend to information from different representation subspaces at different positions.

4. Experiments
We trained on the standard WMT 2014 English-to-German dataset consisting of about 4.5 million sentence pairs. Sentences were encoded using byte-pair encoding, which has a shared source-target vocabulary of about 37000 tokens. On the WMT 2014 English-to-German translation task, the big transformer model achieves a BLEU score of 28.4, outperforming the best previously reported models.

5. Results
The Transformer achieves 28.4 BLEU on the English-to-German translation task and 41.8 BLEU on the English-to-French translation task. Training took 3.5 days on 8 P100 GPUs, a small fraction of the training costs of competing models from the literature.

6. Discussion
In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used in encoder-decoder architectures with multi-headed self-attention. However, standard self-attention exhibits quadratic complexity O(n^2) with respect to sequence length, which presents memory constraints for very long sequences.

7. Conclusion
We are excited about the future of attention-based models and plan to apply them to other tasks. We plan to extend the Transformer to problems involving input and output modalities other than text and to investigate local, restricted attention mechanisms to efficiently handle large inputs such as images, audio and video.
"""


SAMPLE_PAPER_2_TEXT = """
Graph Neural Networks for Research Paper Representation

Abstract
Understanding scientific papers requires modeling complex relations between entities, concepts, and citations. We propose GraphLens, a graph neural network framework for structural research paper modeling.

1. Introduction
Traditional vector space models represent documents in isolation. However, scientific literature forms an interconnected web of citations and co-authorship graphs. GraphLens integrates textual semantics with explicit graph relational topology.

2. Methodology
We construct a heterogeneous graph where nodes represent papers, authors, and concepts. Node representations are updated via relational graph convolution layers with multi-hop message passing. Edge weights are dynamically computed via structural attention.

3. Experiments
We evaluate on the Cora and PubMed citation network benchmarks. GraphLens achieves 89.2% classification accuracy, surpassing standard Graph Convolutional Networks (GCN) and Graph Attention Networks (GAT).

4. Conclusion
GraphLens provides a powerful foundation for citation network analysis and scientific intelligence exploration.
"""


@pytest.fixture
def temp_chroma_dir():
    temp_dir = tempfile.mkdtemp(prefix="test_chroma_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_llm_state_path(tmp_path, monkeypatch):
    from rag.config.settings import settings
    monkeypatch.setattr(settings, "embedding_cache_path", str(tmp_path / "llm-state.sqlite3"))


@pytest.fixture
def mock_embedder():
    return DeterministicMockEmbedder(dimension=384)


@pytest.fixture
def test_chroma_client(temp_chroma_dir):
    ChromaClientFactory.reset_client()
    return ChromaClientFactory.get_client(persist_dir=temp_chroma_dir, force_new=True)


@pytest.fixture
def vector_repo(test_chroma_client):
    col_mgr = CollectionManager(client=test_chroma_client)
    return VectorRepository(collection_manager=col_mgr)


@pytest.fixture
def sample_document():
    normalizer = DocumentNormalizer()
    pages = [
        Page(page_number=1, text="Attention Is All You Need\n\nAbstract\nThe Transformer replaces recurrence with attention.\n\n1. Introduction\nRecurrence is sequential."),
        Page(page_number=2, text="2. Methodology\nScaled Dot-Product Attention: Attention(Q,K,V)=softmax(QK^T/sqrt(d_k))V.\n\n3. Experiments\nEvaluated on WMT 2014 English-to-German."),
        Page(page_number=3, text="4. Results\nAchieved 28.4 BLEU score.\n\n5. Conclusion\nTransformers provide state of the art results."),
    ]
    meta = DocumentMetadata(
        paper_id="paper_attention_2017",
        document_id="doc_attention_001",
        title="Attention Is All You Need",
        authors=["Vaswani et al."],
        year=2017,
    )
    return normalizer.normalize(pages=pages, metadata=meta)


@pytest.fixture
def full_rag_pipeline(vector_repo, mock_embedder):
    chunker = DocumentChunker()
    ingest = IngestionPipeline(
        chunker=chunker,
        embedder=mock_embedder,
        vector_repo=vector_repo,
    )

    retriever = ResearchRetriever(
        embedder=mock_embedder,
        vector_repo=vector_repo,
    )
    context_builder = ContextBuilder()
    generator = GroundedGenerator(llm_client=MockGroundedLLMClient())

    query_p = QueryPipeline(
        retriever=retriever,
        context_builder=context_builder,
        generator=generator,
    )

    return ingest, query_p
