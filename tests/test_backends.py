"""Both providers through the real worker, stage/apply/undo, quota, strict parsing."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import claude2blender as addon
from claude2blender import claude_cli as runner, project_state, history
from claude2blender.backends import BACKENDS
from claude2blender.result_schema import RESULT_SCHEMA

addon.register()
bpy.context.preferences.system.use_online_access = True
root = Path(tempfile.mkdtemp())
runner.workspace_dir = lambda: str(root)
project_state.reset()
state = bpy.context.window_manager.claude2blender
fake = root/"fake.py"
fake.write_text(r'''
import json, os, pathlib, sys, time
a=sys.argv[1:]
provider="codex" if a[0] in ("exec","login") else "claude"
mode=pathlib.Path(os.environ["C2B_FAKE_MODE"]).read_text()
if a[0]=="--version": print("test 1.0"); sys.exit()
if a[0]=="login": print("Logged in using ChatGPT"); sys.exit()
if a[0]=="auth": print(json.dumps({"loggedIn":True})); sys.exit()
prompt=sys.stdin.read() if provider=="codex" else a[a.index("-p")+1]
with open(os.environ["C2B_FAKE_LOG"],"a") as f:
 f.write(json.dumps({"provider":provider,"prompt":prompt,"args":a,
 "keys":[k for k in ("CODEX_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY") if k in os.environ]})+"\n")
def emit(x): print(json.dumps(x),flush=True)
if mode=="slow": time.sleep(30)
if mode=="quota":
 emit({"type":"error","message":"usage_limit_reached"} if provider=="codex" else {"type":"result","is_error":True,"result":"usage limit reached"});sys.exit(1)
if mode=="transport": sys.exit(2)
out=json.loads(pathlib.Path(os.environ["C2B_FAKE_RESULT"]).read_text())
if mode=="malformed": del out["scene"]["match"]
if provider=="codex":
 emit({"type":"item.completed","item":{"type":"agent_message","text":json.dumps(out)}})
 emit({"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":5}})
else: emit({"type":"result","subtype":"success","structured_output":out})
''', encoding="utf-8")
prefs = SimpleNamespace(claude_path=str(fake), codex_path=str(fake), model="",
                        claude_model="", codex_model="", timeout_minutes=1)
runner.prefs = lambda: prefs
os.environ.update(C2B_FAKE_MODE=str(root/"mode"), C2B_FAKE_LOG=str(root/"log"),
                  C2B_FAKE_RESULT=str(root/"result"), CODEX_API_KEY="test", OPENAI_API_KEY="test",
                  ANTHROPIC_API_KEY="test")
count = 0
def check(ok, msg):
    global count
    assert ok, msg
    count += 1
    print("PASS", msg)
def defaults(schema):
    if schema["type"]=="object": return {k:defaults(v) for k,v in schema["properties"].items()}
    if schema["type"]=="number": return -1
    return "n/a" if "enum" in schema else ""
def run(mode="ok", code="", prompt="Test"):
    result=defaults(RESULT_SCHEMA)
    result.update(summary="Test proposal", message="Test reply", code=code)
    (root/"result").write_text(json.dumps(result))
    (root/"mode").write_text(mode)
    state.prompt=prompt
    runner.start_generate(bpy.context)
    assert runner.pump_until_done(15)

bpy.ops.mesh.primitive_cube_add()
cube=bpy.context.object
(root/"mode").write_text("ok")
for provider in BACKENDS:
    state.backend=provider
    runner.start_check(bpy.context); runner.pump_until_done(10)
    check(state.cli_ok, provider+" signed in")
    state.mode="MATERIAL"
    run(code="assign_material(preset_material('plastic_white'))", prompt="Satin housing")
    check(state.proposal_pending and state.gen_status=="COMPLETED", provider+" stages Material")
    before=len(cube.data.materials)
    bpy.ops.claude2blender.apply_proposal()
    check(state.last_apply_ok, provider+" guarded Material Apply")
    bpy.ops.claude2blender.history_undo()
    check(len(cube.data.materials)==before, provider+" Material undo")
    state.mode="ENVIRONMENT"
    run(code="c2b.light('Backend Key', location=(2,-3,4), target=(0,0,0), energy=50)")
    check(state.gen_status=="COMPLETED", provider+" stages Environment")
    bpy.ops.claude2blender.apply_proposal()
    check(state.last_apply_ok and bpy.data.objects.get("Backend Key") is not None, provider+" Environment Apply")
    bpy.ops.claude2blender.history_undo()
    check(history.entries()[-1]["state"]=="UNDONE", provider+" Environment undo")
    run("malformed")
    check(state.gen_error_kind=="malformed", provider+" rejects missing nested field")
    run("transport")
    check(state.gen_status=="FAILED" and state.gen_error_kind!="quota", provider+" transport is not quota")

state.backend="codex"
run("quota",prompt="Make the existing key softer")
check(state.gen_error_kind=="quota", "quota is explicit")
(root/"mode").write_text("ok")
bpy.ops.claude2blender.switch_backend(); runner.pump_until_done(15)
check(state.backend=="claude" and state.gen_status=="COMPLETED", "quota switch completes on other backend")
calls=[json.loads(x) for x in (root/"log").read_text().splitlines()]
check("Satin housing" in calls[-1]["prompt"] and "Make the existing key softer" in calls[-1]["prompt"], "conversation transfers")
check(all("--resume" not in x["args"] for x in calls), "neither provider relies on resume")
check(all("CODEX_API_KEY" not in x["keys"] and "OPENAI_API_KEY" not in x["keys"] for x in calls if x["provider"]=="codex"), "Codex keys hidden")
state.backend="codex"
(root/"mode").write_text("slow")
runner.start_generate(bpy.context); time.sleep(.3); runner.cancel(); runner.pump_until_done(10)
check(state.gen_detail=="Cancelled" and not runner.busy(), "Codex cancellation")
bpy.context.preferences.system.use_online_access=False
try: runner.start_generate(bpy.context)
except RuntimeError as exc: check("Online Access" in str(exc), "offline guard")
else: raise AssertionError("offline call allowed")
addon.unregister()
print(f"All {count} backend checks passed on Blender {bpy.app.version_string}")
