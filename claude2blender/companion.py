"""Loopback HTTP transport. Requests are queued; only the main thread touches bpy."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import threading
import uuid

MAX_BODY = 256_000


class Server:
    def __init__(self, dispatch, runtime):
        self.dispatch = dispatch
        self.pending = queue.Queue(maxsize=32)
        self.token = secrets.token_urlsafe(32)
        self.runtime = Path(runtime)/uuid.uuid4().hex
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Never log auth headers or request bodies.

            def reply(self, status, data, mime="application/json"):
                content = data if isinstance(data, bytes) else json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; frame-ancestors 'none'; connect-src 'self'")
                self.end_headers()
                self.wfile.write(content)

            def host_ok(self):
                return self.headers.get("Host") == f"127.0.0.1:{owner.port}"

            def do_GET(self):
                if not self.host_ok():
                    return self.reply(403, {"error": "Invalid host"})
                if self.path != "/":
                    return self.reply(404, {"error": "Unknown resource"})
                self.reply(200, Path(__file__).with_name("companion.html").read_bytes(), "text/html; charset=utf-8")

            def do_POST(self):
                if not self.host_ok() or self.headers.get("Origin", owner.url) != owner.url:
                    return self.reply(403, {"error": "Origin rejected"})
                if self.path != "/rpc" or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer "+owner.token):
                    return self.reply(403, {"error": "Pair with the key from Blender"})
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= MAX_BODY:
                        raise ValueError("Request must be between 1 and 256000 bytes")
                    self.connection.settimeout(5)
                    request = json.loads(self.rfile.read(size))
                    if not isinstance(request, dict):
                        raise ValueError("Expected an object")
                    response, expired = queue.Queue(maxsize=1), threading.Event()
                    owner.pending.put_nowait((request, response, expired))
                    try:
                        status, value = response.get(timeout=15)
                    except queue.Empty:
                        expired.set()
                        return self.reply(503, {"error": "Blender is busy; retry when it is responsive"})
                    self.reply(status, value)
                except (ValueError, queue.Full, OSError) as exc:
                    self.reply(400, {"error": str(exc)})

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.http.daemon_threads = True
        self.port = self.http.server_port
        self.url = f"http://127.0.0.1:{self.port}"
        self.runtime.mkdir(parents=True, exist_ok=True)
        os.chmod(self.runtime, 0o700)
        if os.name == "nt":
            import subprocess
            options = dict(capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            owner_name = subprocess.run(["whoami"], check=True, **options).stdout.strip()
            subprocess.run(["icacls", str(self.runtime), "/inheritance:r", "/grant:r", owner_name+":(OI)(CI)F"], check=True, **options)
        self.connection_file = self.runtime/"connection.json"
        fd = os.open(self.connection_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(dict(url=self.url, token=self.token), f)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def pump(self):
        for _ in range(8):
            try:
                request, response, expired = self.pending.get_nowait()
            except queue.Empty:
                break
            if expired.is_set():
                continue
            try:
                value = self.dispatch(request.get("method", ""), request.get("params", {}))
                response.put_nowait((200, {"result": value}))
            except Exception as exc:
                response.put_nowait((400, {"error": str(exc)}))
        return .1

    def close(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)
        try:
            self.connection_file.unlink()
        except FileNotFoundError:
            pass
