"""Dependency-free stdio MCP shim. Run with a Python 3 interpreter, not Blender."""
import json
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlsplit

READ_TOOLS = ("get_context", "list_notes", "get_storyboard", "get_queue", "proposal_status")
TOOLS = [{"name": name, "description": "Read Claude2Blender "+name,
          "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
          "annotations": {"readOnlyHint": True}} for name in READ_TOOLS]
TOOLS.append({"name": "stage_proposal", "description": "Stage code for human review in Blender. Never executes or applies it.",
              "inputSchema": {"type": "object", "properties": {
                  "code": {"type": "string"}, "summary": {"type": "string"},
                  "request_id": {"type": "integer"}},
                  "required": ["code", "summary", "request_id"], "additionalProperties": False},
              "annotations": {"readOnlyHint": False, "destructiveHint": False}})


def call(connection, name, params):
    url = urlsplit(connection["url"])
    if url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port or url.username or url.password or url.path or url.query or url.fragment:
        raise ValueError("Only a bare loopback server URL is allowed")
    if name not in (*READ_TOOLS, "stage_proposal"):
        raise ValueError("Tool is not exposed")
    request = urllib.request.Request(connection["url"]+"/rpc",
        json.dumps(dict(method=name, params=params)).encode(),
        headers={"Authorization": "Bearer "+connection["token"], "Content-Type": "application/json"})
    # Local requests must not inherit an external HTTP proxy.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=20) as response:
        result = json.load(response)
    if "error" in result:
        raise ValueError(result["error"])
    return result["result"]


def main(path):
    connection = json.loads(Path(path).read_text(encoding="utf-8"))
    if not connection["url"].startswith("http://127.0.0.1:"):
        raise ValueError("Only loopback connections are allowed")
    for line in sys.stdin:
        if len(line) > 300000:
            continue
        request = {}
        try:
            request = json.loads(line)
            if "id" not in request:
                continue
            method = request.get("method")
            if method == "initialize":
                result = dict(protocolVersion="2024-11-05", capabilities={"tools": {}},
                              serverInfo={"name": "c2b", "version": "0.7.0"})
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = request["params"]
                value = call(connection, params["name"], params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(value)}]}
            else:
                raise ValueError("Unsupported method")
            reply = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except Exception as exc:
            reply = {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32602, "message": str(exc)}}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
