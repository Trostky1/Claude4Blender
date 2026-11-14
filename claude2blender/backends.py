"""Provider adapters. No bpy, credentials, scene execution, or implicit retries."""
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .result_schema import RESULT_SCHEMA, validate_result


@dataclass
class Command:
    argv: list
    stdin: str = None


class Backend:
    id = label = ""

    def find(self, configured="", search_path=None):
        if configured:
            path = os.path.expanduser(configured)
            return path if os.path.isfile(path) else None
        found = shutil.which(self.id, path=search_path)
        if found:
            return found
        for path in self.locations():
            if os.path.isfile(path):
                return str(path)
        return None

    def locations(self):
        return []

    def environment(self, env, subscription=True):
        result = dict(env)
        if subscription:
            for key in ("ANTHROPIC_API_KEY", "CODEX_API_KEY", "OPENAI_API_KEY"):
                result.pop(key, None)
        return result

    def error_kind(self, text):
        text = text.lower()
        if any(x in text for x in ("usage limit", "rate limit", "rate_limit", "usage_limit", "quota", "limit reached", "hit your limit", "too many requests")):
            return "quota"
        if any(x in text for x in ("not logged", "not signed", "unauthorized", "authentication", "login", "log in", "api key", "credential")):
            return "auth"
        return "provider"

    def parse_result(self, value):
        if isinstance(value, str):
            value = json.loads(value)
        validate_result(value)
        return value

    def cancel(self, proc):
        if proc and proc.poll() is None:
            if os.name == "nt":
                try:
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                   capture_output=True, timeout=2,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                finally:
                    if proc.poll() is None:
                        proc.terminate()
            else:
                import signal
                os.killpg(proc.pid, signal.SIGTERM)


class ClaudeBackend(Backend):
    id, label = "claude", "Claude"
    key_overrides = ("ANTHROPIC_API_KEY",)
    login_hint = "In Terminal run `claude`, then `/login`."

    def locations(self):
        home = Path.home()
        if os.name == "nt":
            return [home/".local/bin/claude.exe", home/".claude/local/claude.exe",
                    Path(os.environ.get("APPDATA", home/"AppData/Roaming"))/"npm/claude.cmd"]
        return [home/".local/bin/claude", home/".claude/local/claude",
                Path("/opt/homebrew/bin/claude"), Path("/usr/local/bin/claude")]

    def build_command(self, launch, prompt, system, images, workspace, model="", mcp=None):
        args = [*launch, "-p", prompt, "--output-format", "stream-json", "--verbose",
                "--json-schema", json.dumps(RESULT_SCHEMA), "--append-system-prompt", system,
                "--strict-mcp-config", "--max-turns", str(max(4, len(images)+4))]
        if mcp:
            args += ["--mcp-config", mcp, "--tools", "Read",
                     "--allowedTools", "Read", "mcp__c2b__*"]
        else:
            args += ["--disallowedTools", "mcp__*", "--tools", "Read" if images else ""]
            if images:
                args += ["--allowedTools", "Read"]
        if images:
            args += ["--add-dir", *sorted({os.path.dirname(i) for i in images})]
        if model:
            args += ["--model", model]
        if os.name == "nt" and len(subprocess.list2cmdline(args)) > 30000:
            args.pop(len(launch)+1)
            return Command(args, prompt)
        return Command(args)

    def probe_command(self, launch):
        return [*launch, "auth", "status"]

    def signed_in(self, text, rc):
        try:
            start = text.index("{")
            result, _ = json.JSONDecoder().raw_decode(text[start:])
            return rc == 0 and result.get("loggedIn") is True
        except (ValueError, AttributeError):
            return False

    def stream(self, event):
        kind = event.get("type")
        if kind == "result":
            if event.get("is_error") or event.get("subtype") != "success":
                return [("error", str(event.get("result") or event.get("errors") or event))]
            return [("result", event.get("structured_output") or event.get("result")),
                    ("usage", event.get("usage", {}))]
        if kind in ("system", "assistant"):
            return [("progress", "Connected" if kind == "system" else "Working…")]
        return []


class CodexBackend(Backend):
    id, label = "codex", "Codex"
    key_overrides = ("CODEX_API_KEY", "OPENAI_API_KEY")
    login_hint = "In Terminal run `codex login`."

    def locations(self):
        home = Path.home()
        return [home/".local/bin/codex.exe", home/".local/bin/codex",
                Path(os.environ.get("APPDATA", home/"AppData/Roaming"))/"npm/codex.cmd",
                Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex")]

    def build_command(self, launch, prompt, system, images, workspace, model="", mcp=None):
        system = system.replace("with the Read tool", "in the attached images").replace("with Read", "in the attached images")
        schema = Path(workspace)/"result-schema.json"
        schema.write_text(json.dumps(RESULT_SCHEMA), encoding="utf-8")
        # Do not load user MCP servers, project instructions, hooks, or API-key overrides.
        # read-only is write protection, NOT a promise of reference-only read access.
        args = [*launch, "exec", "--ignore-user-config", "--ephemeral",
                "--sandbox", "read-only", "--skip-git-repo-check", "--json",
                "--output-schema", str(schema), "-C", str(workspace),
                "-c", "project_doc_max_bytes=0", "-c", 'web_search="disabled"']
        if mcp:
            config = json.loads(Path(mcp).read_text(encoding="utf-8"))["mcpServers"]["c2b"]
            args += ["-c", "mcp_servers.c2b.command="+json.dumps(config["command"]),
                     "-c", "mcp_servers.c2b.args="+json.dumps(config["args"])]
        if model:
            args += ["--model", model]
        for path in images:
            args += ["--image", path]
        return Command([*args, "-"], system+"\n\n"+prompt)

    def probe_command(self, launch):
        return [*launch, "login", "status"]

    def signed_in(self, text, rc):
        return rc == 0 and "logged in" in text.lower()

    def stream(self, event):
        kind = event.get("type")
        if kind in ("error", "turn.failed"):
            return [("error", str(event.get("message") or event.get("error") or event))]
        if kind == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            return [("result", event["item"].get("text", ""))]
        if kind == "turn.completed":
            return [("usage", event.get("usage", {}))]
        return [("progress", "Working…")] if kind in ("thread.started", "turn.started") else []


BACKENDS = {b.id: b for b in (ClaudeBackend(), CodexBackend())}
