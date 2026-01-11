import subprocess
import json
from typing import Dict, Any


class MCPClient:
    def __init__(self, server_path: str = "python mcp_server.py"):
        self.server_path = server_path
        self.process = None
        self._connect()

    def _connect(self):
        """Start MCP server process"""
        try:
            self.process = subprocess.Popen(
                self.server_path.split(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except Exception as e:
            print(f"Failed to start MCP server: {e}")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call MCP tool"""
        if not self.process:
            return {"error": "MCP server not connected"}

        request = {
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }

        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()

            response = self.process.stdout.readline()
            result = json.loads(response)

            if 'content' in result:
                return json.loads(result['content'][0]['text'])
            return result
        except Exception as e:
            return {"error": str(e)}

    def list_tools(self) -> Dict[str, Any]:
        """List available tools"""
        request = {"method": "tools/list", "params": {}}

        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()

            response = self.process.stdout.readline()
            return json.loads(response)
        except Exception as e:
            return {"error": str(e)}

    def is_connected(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def disconnect(self):
        """Close MCP server connection"""
        if self.process:
            self.process.terminate()
            self.process = None