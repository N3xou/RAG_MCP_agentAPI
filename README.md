# Setup and Run Instructions

## Prerequisites
```bash
pip install fastapi uvicorn chromadb pydantic
```



## Step 1: Start MCP Server (Terminal 1)
```bash
python mcp_server.py
```
## Step 2: Start Agent API (Terminal 2)
```bash
python agent_api.py
```
## Step 3: Ingest Documents
```bash
curl -X POST "http://localhost:8000/rag/ingest?file_path=data/docs"
```
## Architecture

```
Client → Agent API → Orchestrator
                    ↓
            ┌───────┴────────┐
            ↓                ↓
        RAG System      MCP Tools
            ↓                ↓
       Vector DB      SQLite/JSON
```

## Tech Stack
- **API**: Python FastAPI
- **Vector DB**: ChromaDB (embedded)
- **LLM**: OpenAI (or compatible endpoint)
- **MCP Server**: Python (stdio transport)
- **Orchestrator**: Custom router with intent classification
  
## Project Structure
```
lab6-agentic-api/
├── agent_api.py          # Main FastAPI server
├── orchestrator.py       # Intent routing & orchestration
├── rag_system.py         # RAG with ChromaDB
├── mcp_server.py         # MCP server with tools
├── mcp_client.py         # MCP client (in orchestrator.py)
├── requirements.txt
├── data/
│   └── docs/            # Sample documents
│       ├── late_policy.md
│       ├── grading.md
│       └── ... (10+ docs)
└── tests/
    └── test_queries.json

```
