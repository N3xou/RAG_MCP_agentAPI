# Setup and Run Instructions - Lab 7

## Quick Reference

### Start Everything
```powershell
docker run -d -p 6379:6379 --name devops-redis redis:7-alpine
python mcp_server.py  # Terminal 1
python agent_api.py   # Terminal 2
```

### Test Everything
```powershell
curl http://localhost:8000/health
curl -X POST "http://localhost:8000/rag/ingest?directory=data/docs"
python test_mcp_tools.py
k6 run k6/load_test.js
```

### Stop Everything
```powershell
# Press Ctrl+C in both terminals
docker stop devops-redis
```
## Prerequisites

```powershell
pip install fastapi uvicorn chromadb pydantic groq python-dotenv langgraph langchain-core redis requests
```

**Additional Requirements:**
- Docker (for Redis)
- k6 (for load testing)

---

## Step 0: Start Redis

```powershell
docker run -d -p 6379:6379 --name devops-redis redis:7-alpine
```

**Verify Redis:**
```powershell
docker exec -it devops-redis redis-cli ping
# Expected: PONG
```

---

## Step 1: Configure Environment

Create `.env` file:
```env
GROQ_API_KEY=gsk_your_key_here
REDIS_URL=redis://localhost:6379
BASIC_RPM=10
PRO_RPM=60
VIP_RPM=300
```

---

## Step 2: Start MCP Server (Terminal 1)

```powershell
python mcp_server.py
```

**Expected output:**
```
✓ Database initialized
✓ Sample server data seeded
✓ MCP Server started
```

---

## Step 3: Start Agent API (Terminal 2)

```powershell
python agent_api.py
```

**Expected output:**
```
✓ Connected to Redis at redis://localhost:6379
✓ Groq LLM configured
✓ LangGraph workflow initialized
✓ MCP client connected to server
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 4: Ingest Documents

```powershell
curl -X POST "http://localhost:8000/rag/ingest?directory=data/docs"
```

**Expected output:**
```json
{
  "status": "success",
  "documents_ingested": 45,
  "message": "Ingested 45 chunks from data/docs"
}
```

---

## Step 5: Test the System

### Health Check
```powershell
curl http://localhost:8000/health
```

**Expected:** All values `true`

### Test Query (RAG)
```powershell
curl -X POST "http://localhost:8000/agent/query" `
  -H "Content-Type: application/json" `
  -H "X-Client-ID: basic-test" `
  -d '{\"message\": \"What is the deployment procedure?\"}'
```

**Expected:** HTTP 200 with citations and rate limit headers

### Test Rate Limiting
```powershell
# Send 15 requests (over 10 RPM limit)
for ($i=1; $i -le 15; $i++) {
  Write-Host "Request $i"
  curl -X POST "http://localhost:8000/agent/query" `
    -H "Content-Type: application/json" `
    -H "X-Client-ID: basic-ratelimit-test" `
    -d '{\"message\": \"Test\"}'
  Start-Sleep -Milliseconds 500
}
```

**Expected:** First ~10 get HTTP 200, rest get HTTP 429

### Test MCP Tools
```powershell
# Create ticket
curl -X POST "http://localhost:8000/agent/query" `
  -H "X-Client-ID: vip-test" `
  -H "Content-Type: application/json" `
  -d '{\"message\": \"Create a critical ticket for database outage\"}'

# Get ticket
curl -X POST "http://localhost:8000/agent/query" `
  -H "X-Client-ID: vip-test" `
  -H "Content-Type: application/json" `
  -d '{\"message\": \"Get ticket 1\"}'

# Append note
curl -X POST "http://localhost:8000/agent/query" `
  -H "X-Client-ID: vip-test" `
  -H "Content-Type: application/json" `
  -d '{\"message\": \"Append note to deploy-2024-01: Success\"}'
```

---

## Step 6: Run k6 Load Tests

### Install k6
```powershell
choco install k6
```

### Run Tests
```powershell
# Basic tier test
k6 run k6/simple_test_basic.js

# Comprehensive test
k6 run k6/load_test.js

# Mixed clients test
k6 run k6/simple_test_mixed.js
```

**Expected:** See 429 responses when limits exceeded

---

## Step 7: Run Automated Tests

### Test MCP Tools
```powershell
python test_mcp_tools.py
```

### Test RAG Accuracy
```powershell
python eval_rag.py
```

---

## Architecture

```
Client (k6/curl) → Rate Limiter (Redis) → LangGraph Orchestrator
                                                ↓
                                    ┌───────────┴────────────┐
                                    ↓                        ↓
                                RAG System              MCP Tools
                                    ↓                        ↓
                                ChromaDB                SQLite DB
```

### Request Flow with Rate Limiting

```
1. Client → API: Request with X-Client-ID header
2. Rate Limiter → Redis: Check bucket state (Leaky Bucket)
3. If allowed → Orchestrator: Process request
4. Orchestrator → RAG/MCP: Based on intent
5. Response → Client: With rate limit headers
```

---

## Tech Stack

### Core Components
- **API**: Python FastAPI with rate limiting middleware
- **Rate Limiter**: Redis + Leaky Bucket algorithm
- **Vector DB**: ChromaDB (embedded)
- **LLM**: Groq (free tier)
- **MCP Server**: Python (stdio transport)
- **Orchestrator**: LangGraph (graph-based workflow)

### Testing
- **Load Testing**: Grafana k6
- **Unit Tests**: Python unittest
- **Integration Tests**: Custom test suites

---

## Project Structure

```
lab7-devops-agent/
├── agent_api.py              # FastAPI server with rate limiting
├── rate_limiter.py           # Redis + Leaky Bucket implementation
├── devops_orchestrator.py    # LangGraph orchestrator
├── rag_system.py             # RAG with ChromaDB
├── mcp_server.py             # MCP server (3 tools)
├── mcp_client.py             # MCP client
├── test_mcp_tools.py         # Automated tool tests
├── eval_rag.py               # RAG evaluation script
├── docker-compose.yml        # Redis + API services
├── Dockerfile                # API container image
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
├── k6/
│   ├── load_test.js         # Comprehensive k6 test
│   ├── simple_test_basic.js # Basic tier test
│   ├── simple_test_pro.js   # Pro tier test
│   └── simple_test_mixed.js # Mixed clients test
├── data/
│   └── docs/                # DevOps documentation (10+ files)
│       ├── deployment_procedure.md
│       ├── incident_management.md
│       ├── server_maintenance.md
│       ├── monitoring.md
│       ├── backup_policy.md
│       └── ... (5+ more)
└── tests/
    ├── test_queries.json    # RAG test queries
    └── eval_results.json    # Evaluation results
```

---

## Rate Limit Tiers

| Tier | Client ID Pattern | RPM Limit | Use Case |
|------|------------------|-----------|----------|
| **Basic** | `basic-*` | 10 | Free tier, testing |
| **Pro** | `pro-*` | 60 | Paid subscriptions |
| **VIP** | `vip-*` | 300 | Enterprise, load testing |

**Example Client IDs:**
- `basic-user-123`
- `pro-company-456`
- `vip-enterprise-789`

---

## MCP Tools (3 Tools)

1. **create_ticket** - Create incident/issue tickets
   - Input: summary, details, priority
   - Output: ticket_id, status

2. **get_ticket** - Retrieve ticket details by ID
   - Input: ticket_id
   - Output: ticket details or not found

3. **append_note** - Add notes to entities
   - Input: entity_id, note
   - Output: note_id, confirmation

---

## Docker Compose Alternative

Instead of manual steps, use Docker Compose:

```powershell
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f agent-api

# Ingest documents
curl -X POST "http://localhost:8000/rag/ingest?directory=data/docs"

# Stop services
docker-compose down
```

---

## Troubleshooting

### Redis not connecting
```powershell
docker ps | findstr redis
docker start devops-redis
```

### Rate limiting not working
```powershell
curl http://localhost:8000/health
# Check "redis_ready": true
```

### MCP server not responding
```powershell
# Restart MCP server (Terminal 1)
# Press Ctrl+C, then:
python mcp_server.py
```

### Reset all rate limits
```powershell
docker exec -it devops-redis redis-cli FLUSHALL
```

### Port 8000 already in use
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

## Success Checklist

- ✅ Redis running: `docker ps | findstr redis`
- ✅ Health check: All `true` in `/health`
- ✅ Documents ingested: 40+ chunks
- ✅ RAG working: Queries return citations
- ✅ MCP tools working: All 3 tools tested
- ✅ Rate limiting: Basic tier gets 429 after 10 requests
- ✅ k6 tests: Load tests show expected rate limiting
- ✅ Different tiers: Pro/VIP have higher limits

---
