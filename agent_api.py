from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
from orchestrator import DevOpsOrchestrator
from dotenv import load_dotenv
load_dotenv()
app = FastAPI(title="Study Assistant Agent API")
orchestrator = DevOpsOrchestrator()

class QueryRequest(BaseModel):
    message: str
    top_k: int = 4
    session_id: Optional[str] = None

class Citation(BaseModel):
    source: str
    chunk_id: str
    snippet: str

class ToolCall(BaseModel):
    tool: str
    input: Dict[str, Any]
    output: Dict[str, Any]

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    tool_calls: List[ToolCall]
    meta: Dict[str, str]

@app.post("/agent/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """
    Main agent endpoint - routes to RAG and/or MCP tools
    """
    try:
        result = await orchestrator.process_query(
            message=request.message,
            top_k=request.top_k,
            session_id=request.session_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rag/ingest")
async def ingest_documents(file_path: str):
    """
    Ingest documents into Vector DB
    """
    try:
        result = orchestrator.rag_system.ingest_directory(file_path)
        if result == 0:
            return {
                "status": "success",
                "warning": "No documents ingested",
                "path": file_path
            }
        return {"status": "success", "documents_ingested": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tools")
async def list_tools():
    """
    List available MCP tools
    """
    return orchestrator.mcp_client.list_tools()

@app.get("/health")
async def health_check():
    """
    Check system health
    """
    return {
        "status": "healthy",
        "llm_configured": orchestrator.llm_configured,
        "vector_db_ready": orchestrator.rag_system.is_ready(),
        "mcp_server_ready": orchestrator.mcp_client.is_connected()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)