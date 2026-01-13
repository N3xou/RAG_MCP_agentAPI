"""
LangGraph-based orchestrator for DevOps Helper Agent
Uses graph workflow for intent routing and tool orchestration
"""
from typing import Dict, Any, List, TypedDict
from langgraph.graph import StateGraph, END
from groq import Groq
from dotenv import load_dotenv
import os
import re

from rag_system import RAGSystem
from mcp_client import MCPClient

load_dotenv()


# Define the state for our graph
class AgentState(TypedDict):
    """State that flows through the graph"""
    message: str
    intent: str
    citations: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    answer: str
    context: str
    top_k: int


class DevOpsOrchestrator:
    """
    LangGraph orchestrator for DevOps operations
    Implements a graph-based workflow with explicit state transitions
    """

    def __init__(self):
        self.rag_system = RAGSystem()
        self.mcp_client = MCPClient()

        # Initialize Groq LLM client
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("⚠ Warning: GROQ_API_KEY not set. Using fallback mode.")
            self.llm_configured = False
            self.client = None
        else:
            self.client = Groq(api_key=api_key)
            self.llm_configured = True
            print("✓ Groq LLM configured")

        # Build the LangGraph workflow
        self.workflow = self._build_graph()
        print("✓ LangGraph workflow initialized")

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph workflow with nodes and edges

        Workflow:
        START → classify_intent → [retrieve_knowledge | execute_tools | both] 
              → generate_answer → END
        """
        workflow = StateGraph(AgentState)

        # Add nodes (each node is a function that processes state)
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("retrieve_knowledge", self._retrieve_knowledge_node)
        workflow.add_node("execute_tools", self._execute_tools_node)
        workflow.add_node("generate_answer", self._generate_answer_node)

        # Set entry point
        workflow.set_entry_point("classify_intent")

        # Add conditional edges based on intent classification
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_based_on_intent,
            {
                "knowledge": "retrieve_knowledge",
                "action": "execute_tools",
                "both": "retrieve_knowledge"  # For 'both', do knowledge first
            }
        )

        # Connect nodes to final answer generation
        workflow.add_edge("retrieve_knowledge", "generate_answer")
        workflow.add_edge("execute_tools", "generate_answer")

        # End after generating answer
        workflow.add_edge("generate_answer", END)

        return workflow.compile()

    def _classify_intent_node(self, state: AgentState) -> AgentState:
        """
        Node: Classify user intent
        Determines if query needs knowledge retrieval, tool execution, or both
        """
        message = state["message"].lower()

        # DevOps action keywords
        action_keywords = [
            'create', 'open', 'file', 'ticket', 'incident',
            'lookup', 'find', 'search', 'get', 'show', 'list'
        ]

        # Knowledge keywords
        knowledge_keywords = [
            'how', 'what', 'why', 'explain', 'describe',
            'procedure', 'policy', 'documentation', 'guide', 'process'
        ]

        has_action = any(kw in message for kw in action_keywords)
        has_knowledge = any(kw in message for kw in knowledge_keywords)

        if has_action and has_knowledge:
            intent = 'both'
        elif has_action:
            intent = 'action'
        else:
            intent = 'knowledge'

        state["intent"] = intent
        print(f"→ Intent classified: {intent}")
        return state

    def _route_based_on_intent(self, state: AgentState) -> str:
        """
        Conditional edge: Route to appropriate node based on intent
        This is the decision point in the graph
        """
        return state["intent"]

    def _retrieve_knowledge_node(self, state: AgentState) -> AgentState:
        """
        Node: Retrieve relevant documentation from RAG system
        """
        print(f"→ Retrieving knowledge (top_k={state['top_k']})")

        citations = self.rag_system.retrieve(state["message"], state["top_k"])
        state["citations"] = citations

        # Build context from retrieved documents
        if citations:
            context = "\n\n".join([c.get('full_text', c['snippet']) for c in citations])
            state["context"] = context
            print(f"✓ Retrieved {len(citations)} documents")
        else:
            state["context"] = ""
            print("⚠ No relevant documents found")

        # If intent is 'both', continue to execute tools
        if state["intent"] == "both":
            state = self._execute_tools_node(state)

        return state

    def _execute_tools_node(self, state: AgentState) -> AgentState:
        """
        Node: Execute MCP tools based on message content
        """
        print("→ Executing tools")

        message = state["message"].lower()
        tool_calls = []

        # -------------------------------
        # Tool 1: create_ticket
        # -------------------------------
        if self._should_create_ticket(message):
            summary = self._extract_incident_title(state["message"])
            details = self._extract_incident_details(state["message"])
            priority = self._extract_severity(state["message"])

            result = self.mcp_client.call_tool('create_ticket', {
                'summary': summary,
                'details': details,
                'priority': priority
            })
            tool_calls.append({
                'tool': 'create_ticket',
                'input': {
                    'summary': summary,
                    'details': details,
                    'priority': priority
                },
                'output': result
            })
            print(f"✓ Created ticket: ID={result.get('ticket_id')}")

        # -------------------------------
        # Tool 2: get_ticket
        # -------------------------------
        # Example: if message contains "show ticket 42"
        ticket_id_match = re.search(r'ticket\s+(\d+)', message)
        if ticket_id_match:
            ticket_id = int(ticket_id_match.group(1))
            result = self.mcp_client.call_tool('get_ticket', {'ticket_id': ticket_id})

            tool_calls.append({
                'tool': 'get_ticket',
                'input': {'ticket_id': ticket_id},
                'output': result
            })
            print(f"✓ Retrieved ticket: ID={ticket_id}")

        # -------------------------------
        # Tool 3: append_note
        # -------------------------------
        # Example: "Add note 'Investigated issue' to ticket 42"
        note_match = re.search(r'add note ["\'](.+?)["\'] to (ticket|deploy|server)-([\w\-]+)', message)

        if note_match:
            note_text = note_match.group(1)
            entity_type = note_match.group(2)
            entity_id = f"{entity_type}-{note_match.group(3)}"

            result = self.mcp_client.call_tool('append_note', {
                'entity_id': entity_id,
                'note': note_text
            })

            tool_calls.append({
                'tool': 'append_note',
                'input': {
                    'entity_id': entity_id,
                    'note': note_text
                },
                'output': result
            })
            print(f"✓ Appended note to {entity_id}: ID={result.get('note_id')}")

        state["tool_calls"] = tool_calls
        return state

    def _generate_answer_node(self, state: AgentState) -> AgentState:
        """
        Node: Generate final answer using LLM or fallback
        Combines context from RAG and tool results
        """
        print("→ Generating answer")

        if self.llm_configured and state.get("context"):
            # Use Groq LLM to generate answer
            answer = self._call_llm(state["message"], state.get("context", ""))
        else:
            # Fallback: template-based answer
            answer = self._generate_template_answer(state)

        # Append tool results if any
        if state.get("tool_calls"):
            tool_summary = self._format_tool_results(state["tool_calls"])
            answer += "\n\n" + tool_summary

        state["answer"] = answer
        print("✓ Answer generated")
        return state

    def _call_llm(self, question: str, context: str) -> str:
        """Call Groq LLM to generate answer from context"""
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a DevOps assistant. Answer questions based on the provided documentation. Be concise and technical."
                    },
                    {
                        "role": "user",
                        "content": f"Documentation:\n{context}\n\nQuestion: {question}\n\nProvide a clear, technical answer based on the documentation:"
                    }
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠ LLM call failed: {e}")
            return f"Based on the documentation:\n\n{context[:400]}..."

    def _generate_template_answer(self, state: AgentState) -> str:
        """Generate template-based answer when LLM is not available"""
        if state.get("context"):
            return f"Based on the DevOps documentation:\n\n{state['context'][:400]}..."
        return "I can help you with DevOps documentation and operations. What would you like to know?"

    def _format_tool_results(self, tool_calls: List[Dict]) -> str:
        """Format tool execution results for display"""
        if not tool_calls:
            return ""

        results = []

        for call in tool_calls:
            if call['tool'] == 'create_incident':
                output = call['output']
                results.append(
                    f"✓ Incident Created:\n"
                    f"  ID: {output.get('incident_id')}\n"
                    f"  Title: {output.get('title')}\n"
                    f"  Severity: {output.get('severity')}\n"
                    f"  Status: {output.get('status')}\n"
                    f"  Created: {output.get('created_at')}"
                )

            elif call['tool'] == 'lookup_server':
                output = call['output']
                if output.get('found') and 'server' in output:
                    srv = output['server']
                    results.append(
                        f"✓ Server Configuration:\n"
                        f"  Hostname: {srv['hostname']}\n"
                        f"  IP Address: {srv['ip_address']}\n"
                        f"  Environment: {srv['environment']}\n"
                        f"  Status: {srv['status']}\n"
                        f"  Resources: {srv['cpu_cores']} cores, {srv['memory_gb']}GB RAM\n"
                        f"  OS: {srv['os']}"
                    )
                elif output.get('servers'):
                    env = call['input'].get('environment', 'unknown')
                    results.append(
                        f"✓ Found {output['count']} server(s) in '{env}' environment:\n" +
                        "\n".join([f"  - {s['hostname']} ({s['ip_address']})" for s in output['servers'][:5]])
                    )
                else:
                    results.append("✗ Server not found")

        return "\n\n".join(results)

    # Tool routing helpers
    def _should_create_ticket(self, message: str) -> bool:
        """Check if message should trigger incident creation"""
        return any(kw in message for kw in ['create', 'open', 'file']) and \
            any(kw in message for kw in ['incident', 'ticket'])

    def _should_lookup_server(self, message: str) -> bool:
        """Check if message should trigger server lookup"""
        return any(kw in message for kw in ['lookup', 'find', 'show', 'get', 'list']) and \
            any(kw in message for kw in ['server', 'host', 'machine'])

    # Extraction helpers
    def _extract_incident_title(self, message: str) -> str:
        """Extract summary/title from user message"""
        match = re.search(r'["\']([^"\']+)["\']', message)
        if match:
            return match.group(1)
        match = re.search(r'(?:for|about)\s+(.+?)(?:\.|$)', message, re.I)
        if match:
            return match.group(1).strip()
        return message[:50]

    def _extract_incident_details(self, message: str) -> str:
        """Optional: extract longer details from message"""
        # You can use everything after the title or after keywords like "details:"
        match = re.search(r'details?:\s*(.+)', message, re.I)
        return match.group(1).strip() if match else ""

    def _extract_severity(self, message: str) -> str:
        """Extract severity level from message"""
        message_lower = message.lower()
        if 'critical' in message_lower:
            return 'critical'
        elif 'high' in message_lower:
            return 'high'
        elif 'low' in message_lower:
            return 'low'
        return 'medium'


    async def process_query(self, message: str, top_k: int = 4,
                            session_id: str = None) -> Dict[str, Any]:
        """
        Process query using LangGraph workflow

        Args:
            message: User query
            top_k: Number of documents to retrieve
            session_id: Optional session identifier

        Returns:
            Dict with answer, citations, tool_calls, and metadata
        """
        # Initialize state
        initial_state = {
            "message": message,
            "intent": "",
            "citations": [],
            "tool_calls": [],
            "answer": "",
            "context": "",
            "top_k": top_k
        }

        # Run the LangGraph workflow
        print(f"\n{'=' * 60}")
        print(f"Processing Query: {message}")
        print(f"{'=' * 60}")

        final_state = self.workflow.invoke(initial_state)

        print(f"{'=' * 60}\n")

        # Return formatted response
        return {
            "answer": final_state["answer"],
            "citations": final_state["citations"],
            "tool_calls": final_state["tool_calls"],
            "meta": {
                "orchestrator": "langgraph",
                "model": "llama-3.1-8b-instant",
                "vector_db": "chromadb",
                "intent": final_state["intent"],
                "workflow": "graph-based"
            }
        }