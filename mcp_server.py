"""
MCP Server with study assistant tools
Run as: python mcp_server.py
"""
import json
import sys
from typing import Any, Dict
import sqlite3
from datetime import datetime


class MCPServer:
    def __init__(self):
        self.conn = sqlite3.connect('study_assistant.db', check_same_thread=False)
        self._init_db()

    def _init_db(self):
        """Initialize database tables"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'open',
                created_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course TEXT NOT NULL,
                title TEXT NOT NULL,
                due_date TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        self.conn.commit()

    def create_task(self, title: str, description: str = "",
                    priority: str = "medium") -> Dict[str, Any]:
        """Create a study task"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (title, description, priority, created_at)
            VALUES (?, ?, ?, ?)
        ''', (title, description, priority, datetime.now().isoformat()))
        self.conn.commit()

        return {
            "task_id": cursor.lastrowid,
            "title": title,
            "priority": priority,
            "status": "created"
        }

    def lookup_assignment(self, course: str) -> Dict[str, Any]:
        """Look up assignments for a course"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, due_date, status FROM assignments 
            WHERE course = ? AND status = 'pending'
        ''', (course,))

        rows = cursor.fetchall()
        assignments = []
        for row in rows:
            assignments.append({
                "id": row[0],
                "title": row[1],
                "due_date": row[2],
                "status": row[3]
            })

        return {"course": course, "assignments": assignments}

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol request"""
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "create_task",
                        "description": "Create a study task or reminder",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "priority": {"type": "string", "enum": ["low", "medium", "high"]}
                            },
                            "required": ["title"]
                        }
                    },
                    {
                        "name": "lookup_assignment",
                        "description": "Look up pending assignments for a course",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "course": {"type": "string"}
                            },
                            "required": ["course"]
                        }
                    }
                ]
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            if tool_name == "create_task":
                result = self.create_task(**tool_args)
            elif tool_name == "lookup_assignment":
                result = self.lookup_assignment(**tool_args)
            else:
                return {"error": f"Unknown tool: {tool_name}"}

            return {"content": [{"type": "text", "text": json.dumps(result)}]}

        return {"error": "Unknown method"}

    def run(self):
        """Run MCP server (stdio transport)"""
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}), flush=True)


if __name__ == "__main__":
    server = MCPServer()
    server.run()