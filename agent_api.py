# agent_api.py
"""
DevOps Helper Agent API with Rate Limiting
Integrates rate limiter middleware for per-client RPM limits
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from orchestrator import DevOpsOrchestrator
from rate_limiter import rate_limiter

app = FastAPI(
    title="DevOps Helper Agent API (with Rate Limiting)",
    description="Agent AI API with per-client rate limiting using Redis",
    version="2.0.0"
)

orchestrator = DevOpsOrchestrator()


# Pydantic models
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


# Middleware for rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware applied to all requests
    Checks X-Client-ID header and enforces per-client RPM limits
    """
    # Skip rate limiting for health and docs endpoints
    if request.url.path in ["/health", "/docs", "/openapi.json", "/", "/rate-limit/stats"]:
        response = await call_next(request)
        return response

    # Check rate limit
    rate_limit_response = await rate_limiter.check_request(request)

    if rate_limit_response:
        # Rate limited - return 429 response
        return rate_limit_response

    # Allowed - proceed with request
    response = await call_next(request)

    # Add rate limit headers to successful responses
    if hasattr(request.state, "rate_limit_info"):
        info = request.state.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(info.get("limit_rpm", 0))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset_timestamp", 0))

    return response


# API Endpoints
@app.post("/agent/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """
    Main agent endpoint - routes to RAG and/or MCP tools
    Protected by rate limiter
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
async def ingest_documents(directory: str = "data/docs"):
    """
    Ingest DevOps documentation into Vector DB
    Protected by rate limiter
    """
    try:
        result = orchestrator.rag_system.ingest_directory(directory)
        return {
            "status": "success",
            "documents_ingested": result,
            "message": f"Ingested {result} chunks from {directory}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def list_tools():
    """
    List available MCP tools
    Protected by rate limiter
    """
    return orchestrator.mcp_client.list_tools()


@app.get("/health")
async def health_check():
    """
    Check system health (NOT rate limited)
    """
    # Check Redis connection
    redis_ready = rate_limiter.redis_client is not None
    if redis_ready:
        try:
            rate_limiter.redis_client.ping()
        except:
            redis_ready = False

    return {
        "status": "healthy",
        "llm_configured": orchestrator.llm_configured,
        "vector_db_ready": orchestrator.rag_system.is_ready(),
        "mcp_server_ready": orchestrator.mcp_client.is_connected(),
        "redis_ready": redis_ready,
        "orchestrator": "langgraph",
        "rate_limiting": "enabled" if redis_ready else "disabled"
    }


@app.get("/rate-limit/stats/{client_id}")
async def get_rate_limit_stats(client_id: str):
    """
    Get current rate limit statistics for a client
    NOT rate limited (for debugging)
    """
    stats = rate_limiter.get_stats(client_id)
    return stats


@app.get("/rate-limit/config")
async def get_rate_limit_config():
    """
    Get rate limit tier configuration
    NOT rate limited
    """
    return {
        "tiers": rate_limiter.TIER_LIMITS,
        "tier_patterns": {
            "basic": "basic-*",
            "pro": "pro-*",
            "vip": "vip-*"
        },
        "algorithm": "leaky_bucket",
        "note": "Limits are in requests per minute (RPM)"
    }


@app.get("/")
async def root():
    """
    Root endpoint with API information
    NOT rate limited
    """
    return {
        "service": "DevOps Helper Agent with Rate Limiting",
        "version": "2.0.0",
        "rate_limiting": {
            "enabled": True,
            "algorithm": "leaky_bucket",
            "header_required": "X-Client-ID"
        },
        "endpoints": {
            "protected": [
                "POST /agent/query - Main query endpoint",
                "POST /rag/ingest - Ingest documents",
                "GET /tools - List available tools"
            ],
            "unprotected": [
                "GET /health - Health check",
                "GET /rate-limit/stats/{client_id} - View rate limit stats",
                "GET /rate-limit/config - View tier configuration"
            ]
        },
        "tiers": rate_limiter.TIER_LIMITS
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)