import requests
import json

BASE_URL = "http://localhost:8000"

def test_rag_query():
    """Test 1: Knowledge Query (RAG only)"""
    url = f"{BASE_URL}/agent/query"
    payload = {
        "message": "What is the late submission policy?",
        "top_k": 3
    }
    response = requests.post(url, json=payload)
    print("Test 1 - RAG Query Response:")
    print(json.dumps(response.json(), indent=2))
    print("-" * 50)

def test_mcp_action():
    """Test 2: Action Query (MCP tool only)"""
    url = f"{BASE_URL}/agent/query"
    payload = {
        "message": "Create a task to review chapter 5",
        "top_k": 3
    }
    response = requests.post(url, json=payload)
    print("Test 2 - MCP Action Response:")
    print(json.dumps(response.json(), indent=2))
    print("-" * 50)

def test_combined_query():
    """Test 3: Combined Query (RAG + MCP)"""
    url = f"{BASE_URL}/agent/query"
    payload = {
        "message": "What is the grading policy? Also create a task to study for the midterm.",
        "top_k": 3
    }
    response = requests.post(url, json=payload)
    print("Test 3 - Combined Query Response:")
    print(json.dumps(response.json(), indent=2))
    print("-" * 50)

def test_health():
    """Test 4: Check Health"""
    url = f"{BASE_URL}/health"
    response = requests.get(url)
    print("Test 4 - Health Check Response:")
    print(json.dumps(response.json(), indent=2))
    print("-" * 50)

def test_tools():
    """Test 5: List Available Tools"""
    url = f"{BASE_URL}/tools"
    response = requests.get(url)
    print("Test 5 - Tools Response:")
    print(json.dumps(response.json(), indent=2))
    print("-" * 50)

def test_rag_ingest():
    """Extra Test: Ingest Documents"""
    url = f"{BASE_URL}/rag/ingest"
    params = {"file_path": "data/docs"}
    response = requests.post(url, params=params)
    print("Extra Test - RAG Ingest Response:")
    print(json.dumps(response.json(), indent=2))
    print("-" * 50)

if __name__ == "__main__":
    test_rag_ingest()
    test_health()
    test_rag_query()
    test_mcp_action()
    test_combined_query()
    test_tools()
