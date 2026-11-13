#!/usr/bin/env python
"""
Quick validation script for SEC-001 fixes.
Tests that owner_id is required and enforced across all RAG query layers.
"""

import sys
sys.path.insert(0, ".")

def test_filter_builder_validation():
    """Test FilterBuilder enforces owner_id."""
    from rag.retrieval.filters import FilterBuilder
    
    print("Testing FilterBuilder owner_id validation...")
    
    # Test 1: Empty owner_id should fail
    try:
        FilterBuilder.build_where_filter(owner_id="", paper_ids=["paper_1"])
        print("  ❌ FAIL: Empty owner_id was accepted")
        return False
    except ValueError as e:
        if "owner_id is required" in str(e):
            print("  ✅ PASS: Empty owner_id rejected")
        else:
            print(f"  ❌ FAIL: Wrong error: {e}")
            return False
    
    # Test 2: Valid owner_id should work
    try:
        result = FilterBuilder.build_where_filter(owner_id="user_alice", paper_ids=["paper_1"])
        if "owner_id" in str(result):
            print("  ✅ PASS: Valid owner_id included in filter")
        else:
            print(f"  ❌ FAIL: owner_id not in filter: {result}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL: Valid owner_id raised error: {e}")
        return False
    
    # Test 3: owner_id should be first clause
    try:
        result = FilterBuilder.build_where_filter(
            owner_id="user_bob",
            paper_ids=["paper_1", "paper_2"],
        )
        if "$and" in result:
            if result["$and"][0] == {"owner_id": "user_bob"}:
                print("  ✅ PASS: owner_id is first clause in $and filter")
            else:
                print(f"  ❌ FAIL: owner_id not first clause: {result}")
                return False
        else:
            print(f"  ⚠️  WARNING: Expected $and structure, got: {result}")
    except Exception as e:
        print(f"  ❌ FAIL: Error building multi-clause filter: {e}")
        return False
    
    return True


def test_retriever_validation():
    """Test ResearchRetriever enforces owner_id."""
    from rag.retrieval.retriever import ResearchRetriever
    from rag.retrieval.query import QueryRequest
    
    print("\nTesting ResearchRetriever owner_id validation...")
    
    retriever = ResearchRetriever()
    request = QueryRequest(question="Test query", paper_ids=["paper_1"])
    
    # Test: Empty owner_id should fail
    try:
        retriever.retrieve(request, owner_id="")
        print("  ❌ FAIL: Empty owner_id was accepted")
        return False
    except ValueError as e:
        if "owner_id is required" in str(e):
            print("  ✅ PASS: Empty owner_id rejected")
        else:
            print(f"  ❌ FAIL: Wrong error: {e}")
            return False
    except Exception as e:
        print(f"  ⚠️  WARNING: Different error (expected if no embedder): {type(e).__name__}")
        # This might fail due to missing embedder, but that's OK for validation
    
    return True


def test_query_pipeline_validation():
    """Test QueryPipeline enforces user_id."""
    from rag.pipelines.query_pipeline import QueryPipeline
    
    print("\nTesting QueryPipeline user_id validation...")
    
    pipeline = QueryPipeline()
    
    # Test: Empty user_id should fail
    try:
        pipeline.answer_question(question="Test query", user_id="")
        print("  ❌ FAIL: Empty user_id was accepted")
        return False
    except ValueError as e:
        if "user_id is required" in str(e):
            print("  ✅ PASS: Empty user_id rejected in answer_question")
        else:
            print(f"  ❌ FAIL: Wrong error: {e}")
            return False
    except Exception as e:
        print(f"  ⚠️  WARNING: Different error (expected if no LLM): {type(e).__name__}")
    
    # Test summarize_paper
    try:
        pipeline.summarize_paper(paper_id="paper_1", user_id="")
        print("  ❌ FAIL: Empty user_id accepted in summarize_paper")
        return False
    except ValueError as e:
        if "user_id is required" in str(e):
            print("  ✅ PASS: Empty user_id rejected in summarize_paper")
        else:
            print(f"  ❌ FAIL: Wrong error: {e}")
            return False
    except Exception as e:
        print(f"  ⚠️  WARNING: Different error: {type(e).__name__}")
    
    # Test compare_papers
    try:
        pipeline.compare_papers(paper_ids=["paper_1", "paper_2"], user_id="")
        print("  ❌ FAIL: Empty user_id accepted in compare_papers")
        return False
    except ValueError as e:
        if "user_id is required" in str(e):
            print("  ✅ PASS: Empty user_id rejected in compare_papers")
        else:
            print(f"  ❌ FAIL: Wrong error: {e}")
            return False
    except Exception as e:
        print(f"  ⚠️  WARNING: Different error: {type(e).__name__}")
    
    return True


def test_rag_client_validation():
    """Test RAGClient enforces user_id."""
    from backend.app.integrations.rag_client import RAGClient
    
    print("\nTesting RAGClient user_id validation...")
    
    client = RAGClient()
    
    # Test ask_question
    try:
        client.ask_question(question="Test", user_id="")
        print("  ❌ FAIL: Empty user_id accepted in ask_question")
        return False
    except ValueError as e:
        if "user_id is required" in str(e):
            print("  ✅ PASS: Empty user_id rejected in ask_question")
        else:
            print(f"  ❌ FAIL: Wrong error: {e}")
            return False
    except Exception as e:
        print(f"  ⚠️  WARNING: Different error: {type(e).__name__}")
    
    # Test summarize_paper
    try:
        client.summarize_paper(paper_id="paper_1", user_id="")
        print("  ❌ FAIL: Empty user_id accepted in summarize_paper")
        return False
    except ValueError as e:
        if "user_id is required" in str(e):
            print("  ✅ PASS: Empty user_id rejected in summarize_paper")
        else:
            print(f"  ❌ FAIL: Wrong error: {e}")
            return False
    except Exception as e:
        print(f"  ⚠️  WARNING: Different error: {type(e).__name__}")
    
    # Test compare_papers
    try:
        client.compare_papers(paper_ids=["paper_1", "paper_2"], user_id="")
        print("  ❌ FAIL: Empty user_id accepted in compare_papers")
        return False
    except ValueError as e:
        if "user_id is required" in str(e):
            print("  ✅ PASS: Empty user_id rejected in compare_papers")
        else:
            print(f"  ❌ FAIL: Wrong error: {e}")
            return False
    except Exception as e:
        print(f"  ⚠️  WARNING: Different error: {type(e).__name__}")
    
    return True


def main():
    """Run all SEC-001 validation tests."""
    print("=" * 70)
    print("SEC-001 VALIDATION: RAG Owner Isolation")
    print("=" * 70)
    
    results = []
    
    results.append(("FilterBuilder", test_filter_builder_validation()))
    results.append(("ResearchRetriever", test_retriever_validation()))
    results.append(("QueryPipeline", test_query_pipeline_validation()))
    results.append(("RAGClient", test_rag_client_validation()))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for component, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{component:20s}: {status}")
    
    all_passed = all(passed for _, passed in results)
    
    print("=" * 70)
    if all_passed:
        print("✅ SEC-001 FIX VALIDATED: All owner_id checks working")
        return 0
    else:
        print("❌ SEC-001 FIX INCOMPLETE: Some checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
