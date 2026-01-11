"""
MCP Server for DevOps Helper
Provides tools for incident management, server lookups, and deployment notes

Run as: python mcp_server.py
"""
import json
import sys
import sqlite3
from datetime import datetime
from typing import Any, Dict, List


class DevOpsMCPServer:
    def __init__(self):
        self.conn = sqlite3.connect('devops.db', check_same_thread=False)
        self._init_db()
        self._seed_data()

    def _init_db(self):
        """Initialize database tables"""
        cursor = self.conn.cursor()

        # Incidents/Tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                details TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'open',
                created_at TEXT,
                assigned_to TEXT
            )
        ''')

        # Server configurations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname TEXT NOT NULL UNIQUE,
                ip_address TEXT,
                environment TEXT,
                status TEXT DEFAULT 'active',
                cpu_cores INTEGER,
                memory_gb INTEGER,
                os TEXT
            )
        ''')

        # Deployment notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deployment_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT,
                created_by TEXT DEFAULT 'system'
            )
        ''')

        self.conn.commit()
        print("✓ Database initialized", file=sys.stderr)

    def _seed_data(self):
        """Seed sample server data"""
        cursor = self.conn.cursor()

        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM servers")
        if cursor.fetchone()[0] > 0:
            return

        sample_servers = [
            ('web-prod-01', '10.0.1.10', 'production', 'active', 8, 32, 'Ubuntu 22.04'),
            ('web-prod-02', '10.0.1.11', 'production', 'active', 8, 32, 'Ubuntu 22.04'),
            ('web-prod-03', '10.0.1.12', 'production', 'active', 8, 32, 'Ubuntu 22.04'),
            ('db-prod-01', '10.0.2.10', 'production', 'active', 16, 64, 'Ubuntu 22.04'),
            ('db-prod-02', '10.0.2.11', 'production', 'active', 16, 64, 'Ubuntu 22.04'),
            ('app-staging-01', '10.0.3.10', 'staging', 'active', 4, 16, 'Ubuntu 22.04'),
            ('app-staging-02', '10.0.3.11', 'staging', 'active', 4, 16, 'Ubuntu 22.04'),
            ('app-dev-01', '10.0.4.10', 'development', 'active', 2, 8, 'Ubuntu 22.04'),
        ]

        cursor.executemany('''
            INSERT INTO servers (hostname, ip_address, environment, status, cpu_cores, memory_gb, os)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_servers)

        self.conn.commit()
        print("✓ Sample server data seeded", file=sys.stderr)

    # Tool 1: create_ticket
    def create_ticket(self, summary: str, details: str = "",
                     priority: str = "medium") -> Dict[str, Any]:
        """
        Create a new incident/issue ticket

        Args:
            summary: Brief description of the incident
            details: Detailed information (optional)
            priority: Ticket priority (low, medium, high, critical)

        Returns:
            Dict with ticket_id and ticket details
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tickets (summary, details, priority, created_at)
            VALUES (?, ?, ?, ?)
        ''', (summary, details, priority, datetime.now().isoformat()))
        self.conn.commit()

        ticket_id = cursor.lastrowid

        return {
            "ticket_id": ticket_id,
            "summary": summary,
            "priority": priority,
            "status": "open",
            "created_at": datetime.now().isoformat()
        }

    # Tool 2: get_ticket
    def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """
        Retrieve ticket details by ID

        Args:
            ticket_id: Ticket ID to retrieve

        Returns:
            Dict with ticket information or error
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, summary, details, priority, status, created_at, assigned_to
            FROM tickets WHERE id = ?
        ''', (ticket_id,))

        row = cursor.fetchone()

        if row:
            return {
                "found": True,
                "ticket": {
                    "id": row[0],
                    "summary": row[1],
                    "details": row[2],
                    "priority": row[3],
                    "status": row[4],
                    "created_at": row[5],
                    "assigned_to": row[6]
                }
            }

        return {
            "found": False,
            "error": f"Ticket {ticket_id} not found"
        }

    # Tool 3: append_note
    def append_note(self, entity_id: str, note: str) -> Dict[str, Any]:
        """
        Append a note to a deployment, server, or incident

        Args:
            entity_id: Identifier for the entity (e.g., "deploy-2024-01", "web-prod-01", "ticket-123")
            note: Note text to append

        Returns:
            Dict with confirmation
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO deployment_notes (entity_id, note, created_at)
            VALUES (?, ?, ?)
        ''', (entity_id, note, datetime.now().isoformat()))
        self.conn.commit()

        note_id = cursor.lastrowid

        return {
            "ok": True,
            "note_id": note_id,
            "entity_id": entity_id,
            "note": note,
            "created_at": datetime.now().isoformat()
        }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol request"""
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "create_ticket",
                        "description": "Create a new incident or issue ticket for DevOps problems",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Brief summary of the incident"
                                },
                                "details": {
                                    "type": "string",
                                    "description": "Detailed description of the issue"
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high", "critical"],
                                    "description": "Ticket priority level"
                                }
                            },
                            "required": ["summary"]
                        }
                    },
                    {
                        "name": "get_ticket",
                        "description": "Retrieve details of an existing ticket by ID",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ticket_id": {
                                    "type": "integer",
                                    "description": "The ticket ID to retrieve"
                                }
                            },
                            "required": ["ticket_id"]
                        }
                    },
                    {
                        "name": "append_note",
                        "description": "Append a note to a deployment, server, or incident entity",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "entity_id": {
                                    "type": "string",
                                    "description": "Entity identifier (e.g., 'deploy-2024-01', 'web-prod-01', 'ticket-123')"
                                },
                                "note": {
                                    "type": "string",
                                    "description": "Note text to append"
                                }
                            },
                            "required": ["entity_id", "note"]
                        }
                    }
                ]
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            try:
                if tool_name == "create_ticket":
                    result = self.create_ticket(**tool_args)
                elif tool_name == "get_ticket":
                    result = self.get_ticket(**tool_args)
                elif tool_name == "append_note":
                    result = self.append_note(**tool_args)
                else:
                    return {"error": f"Unknown tool: {tool_name}"}

                return {"content": [{"type": "text", "text": json.dumps(result)}]}
            except Exception as e:
                return {"error": str(e)}

        return {"error": "Unknown method"}

    def run(self):
        """Run MCP server (stdio transport)"""
        print("✓ MCP Server started", file=sys.stderr)

        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}), flush=True)


if __name__ == "__main__":
    server = DevOpsMCPServer()
    server.run()