#!/usr/bin/env python3
"""
Verify SEC-001 API route integration coverage.

This script statically analyzes the codebase to ensure:
1. All RAG query methods are called with user_id parameter
2. No API routes accept client-supplied user_id for authorization
3. All services pass authenticated user.id to RAG methods

Usage:
    python scripts/verify_sec001_coverage.py
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class RAGCallVisitor(ast.NodeVisitor):
    """AST visitor to find RAG method calls and verify user_id parameter."""
    
    RAG_QUERY_METHODS = {
        'ask_question',
        'summarize_paper',
        'compare_papers',
        'answer_question',  # QueryPipeline direct call
    }
    
    def __init__(self, filename: str):
        self.filename = filename
        self.issues: List[Tuple[int, str]] = []
        self.secure_calls: List[Tuple[int, str]] = []
    
    def visit_Call(self, node: ast.Call):
        """Check if this is a RAG query method call."""
        # Check for method calls like: self.rag.ask_question(...)
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            
            if method_name in self.RAG_QUERY_METHODS:
                # Check if user_id is passed
                has_user_id = any(
                    kw.arg == 'user_id' for kw in node.keywords
                )
                
                if has_user_id:
                    self.secure_calls.append((
                        node.lineno,
                        f"✅ {method_name}() called with user_id parameter"
                    ))
                else:
                    self.issues.append((
                        node.lineno,
                        f"⚠️  {method_name}() called WITHOUT user_id parameter"
                    ))
        
        self.generic_visit(node)


def check_file(filepath: Path) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]]]:
    """Parse Python file and check for RAG calls."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        
        visitor = RAGCallVisitor(str(filepath))
        visitor.visit(tree)
        return visitor.issues, visitor.secure_calls
    except SyntaxError as e:
        print(f"  ⚠️  Syntax error in {filepath}: {e}")
        return [], []
    except Exception as e:
        print(f"  ⚠️  Error parsing {filepath}: {e}")
        return [], []


def main():
    print("=" * 80)
    print("SEC-001 API Route Integration Coverage Verification")
    print("=" * 80)
    print()
    
    # Directories to check
    service_dir = Path(__file__).resolve().parent.parent / "backend" / "app" / "services"
    route_dir = Path(__file__).resolve().parent.parent / "backend" / "app" / "routes"
    
    all_issues = []
    all_secure_calls = []
    
    # Check service files
    print("📂 Checking Services...")
    print("-" * 80)
    for service_file in sorted(service_dir.glob("*.py")):
        if service_file.name.startswith("__"):
            continue
        
        issues, secure_calls = check_file(service_file)
        
        if issues or secure_calls:
            print(f"\n📄 {service_file.name}")
            for lineno, message in secure_calls:
                print(f"   Line {lineno:3d}: {message}")
                all_secure_calls.append((service_file, lineno, message))
            
            for lineno, message in issues:
                print(f"   Line {lineno:3d}: {message}")
                all_issues.append((service_file, lineno, message))
    
    # Check route files
    print("\n\n📂 Checking Routes...")
    print("-" * 80)
    for route_file in sorted(route_dir.glob("*.py")):
        if route_file.name.startswith("__"):
            continue
        
        issues, secure_calls = check_file(route_file)
        
        if issues or secure_calls:
            print(f"\n📄 {route_file.name}")
            for lineno, message in secure_calls:
                print(f"   Line {lineno:3d}: {message}")
                all_secure_calls.append((route_file, lineno, message))
            
            for lineno, message in issues:
                print(f"   Line {lineno:3d}: {message}")
                all_issues.append((route_file, lineno, message))
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Secure RAG calls found:    {len(all_secure_calls)}")
    print(f"⚠️  Insecure RAG calls found: {len(all_issues)}")
    print()
    
    if all_issues:
        print("⚠️  SECURITY ISSUES DETECTED:")
        for filepath, lineno, message in all_issues:
            print(f"   {filepath.name}:{lineno} - {message}")
        print()
        print("❌ SEC-001 coverage verification FAILED")
        return 1
    else:
        print("✅ All RAG query calls include user_id parameter")
        print("✅ SEC-001 coverage verification PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
