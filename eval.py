# eval_rag.py
"""
RAG Evaluation Script for DevOps Helper Agent
Tests retrieval accuracy with 10 test queries
"""
import json
import requests
from typing import List, Dict, Any

# Test queries with expected source documents
TEST_QUERIES = [
    {
        "query": "What is the production deployment procedure?",
        "expected_source": "Deployment_guidelines.md",
        "category": "deployment"
    },
    {
        "query": "What are the incident severity levels?",
        "expected_source": "Incident_response.md",
        "category": "incident"
    },
    {
        "query": "What are the key monitoring metrics we should track?",
        "expected_source": "Monitoring_alerting.md",
        "category": "monitoring"
    },
    {
        "query": "What is our backup retention policy?",
        "expected_source": "Backup_recovery.md",
        "category": "backup"
    },
    {
        "query": "What is the rollback procedure if deployment fails?",
        "expected_source": "Deployment_guidelines.md",
        "category": "deployment"
    },
    {
        "query": "What is the response time for critical incidents?",
        "expected_source": "Incident_response.md",
        "category": "incident"
    },

    {
        "query": "What CPU usage threshold triggers an alert?",
        "expected_source": "Monitoring_alerting.md",
        "category": "monitoring"
    },
    {
        "query": "How frequently are database backups performed?",
        "expected_source": "Backup_recovery.md",
        "category": "backup"
    }
]


def evaluate_rag(api_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """
    Evaluate RAG system retrieval accuracy

    Args:
        api_url: Base URL of the agent API

    Returns:
        Dict with evaluation results and metrics
    """
    results = []
    correct_retrievals = 0
    total_queries = len(TEST_QUERIES)

    print("=" * 70)
    print("RAG EVALUATION - DevOps Helper Agent")
    print("=" * 70)
    print(f"Testing {total_queries} queries...\n")

    for idx, test_case in enumerate(TEST_QUERIES, 1):
        query = test_case["query"]
        expected = test_case["expected_source"]
        category = test_case["category"]

        print(f"[{idx}/{total_queries}] Testing: {query}")

        try:
            # Call the agent API
            response = requests.post(
                f"{api_url}/agent/query",
                json={"message": query, "top_k": 4},
                headers={"X-Client-ID": "VIP-test"},
                timeout=10
            )

            if response.status_code != 200:
                print(f"  ✗ API Error: {response.status_code}")
                results.append({
                    "query": query,
                    "expected": expected,
                    "retrieved": [],
                    "correct": False,
                    "category": category,
                    "error": f"HTTP {response.status_code}"
                })
                continue

            data = response.json()
            citations = data.get("citations", [])

            # Check if expected source is in citations
            retrieved_sources = [c.get("source", "") for c in citations]
            is_correct = expected in retrieved_sources

            if is_correct:
                correct_retrievals += 1
                print(f"  ✓ CORRECT - Found '{expected}' in top-{len(citations)} results")
            else:
                print(f"  ✗ INCORRECT - Expected '{expected}', got: {retrieved_sources}")

            results.append({
                "query": query,
                "expected": expected,
                "retrieved": retrieved_sources,
                "correct": is_correct,
                "category": category,
                "num_citations": len(citations)
            })

        except requests.exceptions.ConnectionError:
            print(f"  ✗ Connection Error - Is the API running at {api_url}?")
            results.append({
                "query": query,
                "expected": expected,
                "retrieved": [],
                "correct": False,
                "category": category,
                "error": "Connection refused"
            })
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            results.append({
                "query": query,
                "expected": expected,
                "retrieved": [],
                "correct": False,
                "category": category,
                "error": str(e)
            })

        print()

    # Calculate metrics
    accuracy = (correct_retrievals / total_queries) * 100 if total_queries > 0 else 0

    # Category breakdown
    category_stats = {}
    for result in results:
        cat = result["category"]
        if cat not in category_stats:
            category_stats[cat] = {"correct": 0, "total": 0}
        category_stats[cat]["total"] += 1
        if result["correct"]:
            category_stats[cat]["correct"] += 1

    # Print summary
    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)
    print(f"Total Queries: {total_queries}")
    print(f"Correct Retrievals: {correct_retrievals}")
    print(f"Incorrect Retrievals: {total_queries - correct_retrievals}")
    print(f"\n{'=' * 70}")
    print(f"ACCURACY: {accuracy:.1f}% ({correct_retrievals}/{total_queries})")
    print(f"{'=' * 70}\n")

    # Category breakdown
    print("Category Breakdown:")
    print("-" * 70)
    for category, stats in sorted(category_stats.items()):
        cat_accuracy = (stats["correct"] / stats["total"]) * 100
        print(f"  {category.capitalize():15} {stats['correct']}/{stats['total']} ({cat_accuracy:.1f}%)")
    print()

    # Failed queries
    failed_queries = [r for r in results if not r["correct"]]
    if failed_queries:
        print("Failed Queries:")
        print("-" * 70)
        for fail in failed_queries:
            print(f"  • {fail['query']}")
            print(f"    Expected: {fail['expected']}")
            print(f"    Retrieved: {fail['retrieved']}")
            if "error" in fail:
                print(f"    Error: {fail['error']}")
            print()

    # Save detailed results
    output_file = "eval_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "summary": {
                "total_queries": total_queries,
                "correct": correct_retrievals,
                "incorrect": total_queries - correct_retrievals,
                "accuracy": accuracy
            },
            "category_stats": category_stats,
            "detailed_results": results
        }, f, indent=2)

    print(f"Detailed results saved to: {output_file}")

    return {
        "accuracy": accuracy,
        "correct": correct_retrievals,
        "total": total_queries,
        "results": results
    }


def save_test_queries_json():
    """Save test queries to JSON file for reference"""
    with open("tests/test_queries.json", 'w') as f:
        json.dump(TEST_QUERIES, f, indent=2)
    print("Test queries saved to tests/test_queries.json")


if __name__ == "__main__":
    import sys

    # Check if API URL is provided
    api_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    print(f"Using API at: {api_url}\n")

    # Run evaluation
    evaluate_rag(api_url)