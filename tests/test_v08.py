"""0.7.4 to 0.8.x: version display, sending references with notes, model choice, pasted images, combined modes."""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import claude2blender as addon  # noqa: E402

addon.register()
from claude2blender import bridge, claude_cli, ui, version  # noqa: E402

ok = 0


def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1
    print("  ok:", msg)


class _L:
    """Records label texts and operator ids; accepts every layout call."""
    texts, ops = [], []

    def __getattr__(self, name):
        def call(*a, **k):
            if name == "label":
                _L.texts.append(k.get("text", ""))
            if name == "operator":
                _L.ops.append((a[0], k.get("text", "")))
            return _L()
        return call


class _P:
    def __init__(self):
        self.layout = _L()


def draw(cls, method="draw"):
    _L.texts, _L.ops = [], []
    getattr(cls, method)(_P(), bpy.context)
    return list(_L.texts), list(_L.ops)


C = bpy.context
state = C.window_manager.claude2blender
tmp = tempfile.mkdtemp(prefix="c2b_v08_")

# ---------------------------------------------------------------- which version is running

manifest = os.path.join(os.path.dirname(HERE), "claude2blender", "blender_manifest.toml")
with open(manifest, encoding="utf-8") as fh:
    on_disk = next(l.split('"')[1] for l in fh if l.startswith("version"))
check(version.LOADED == on_disk and not version.restart_needed(), f"running version is the manifest version ({on_disk})")
check(addon.bl_info["version"] == tuple(int(p) for p in on_disk.split(".")), "bl_info and the manifest agree")
texts, _ops = draw(ui.C2B_PT_main, "draw_header_preset")
check(texts == ["v" + on_disk], "the panel header shows the running version")
texts, _ops = draw(ui.C2B_PT_main)
check(not any("still running" in t for t in texts), "no restart notice when the versions match")
version._cache = (float("inf"), "99.0.0")   # as if a newer zip was installed over the running code
check(version.restart_needed(), "a different version on disk is detected")
texts, _ops = draw(ui.C2B_PT_main)
check(any("99.0.0" in t for t in texts) and any("reopen Blender" in t for t in texts),
      "the panel says to restart Blender to finish updating")
version._cache = (0.0, version.LOADED)
check(not version.restart_needed(), "and the notice clears")

# ---------------------------------------------------------------- reference image + note travel together

img = bpy.data.images.new("ref", 8, 8)
img.filepath_raw = os.path.join(tmp, "ref.png")
img.file_format = "PNG"
img.save()
ref = state.references.add()
ref.filepath = img.filepath_raw
ref.role = "ENVIRONMENT"
ref.note = "Match the soft key light only"
gone = state.references.add()
gone.filepath = os.path.join(tmp, "missing.png")
state.prompt = "Light it like the photo"
state.mode = "ENVIRONMENT"
request = bridge.build_request(C)
sent = [r for r in request["references"] if r["exists"]]
check(len(sent) == 1 and sent[0]["note"] == "Match the soft key light only" and sent[0]["role"] == "environment",
      "the request carries the image with its note and role")
images, _conv = claude_cli.plan_images(request)
prompt = claude_cli.build_prompt(request, images, False)
check(img.filepath_raw in prompt and "Note: Match the soft key light only" in prompt,
      "the prompt sent to the agent names the image and its note on one line")
texts, ops = draw(ui.C2B_PT_references)
check(any(t.startswith("1 image, 1 note will be sent") for t in texts), "References says what will be sent")
check(any("1 file not found" in t for t in texts), "and which files are left out")
check(("claude2blender.generate", "Send to Claude") in ops, "References has its own Send button")
check(any("Enter saves a note" in t for t in texts), "and says what Enter does")
state.references.clear()

# ---------------------------------------------------------------- model choice from the companion page

import types  # noqa: E402
from claude2blender import studio  # noqa: E402

info = studio.dispatch("get_state", {})["model"]
check(info["choice"] == "default" and info["editable"] is False and ["claude-fable-5-2", "Fable 5.2"] in info["options"],
      "the companion page gets the model list; read-only when Preferences are unavailable")
prefs = types.SimpleNamespace(claude_model_choice="default", codex_model_choice="default", claude_model="",
                              codex_model="gpt-test", model="", model_migrated=True)
real_prefs, claude_cli.prefs = claude_cli.prefs, lambda: prefs
out = studio.dispatch("set_model", {"backend": "claude", "choice": "claude-sonnet-5-5"})
check(prefs.claude_model_choice == "claude-sonnet-5-5" and out["label"] == "Sonnet 5.5", "set_model picks a preset")
prefs.codex_model_choice = "custom"
out = studio.dispatch("set_model", {"backend": "codex"})
check(state.backend == "codex" and out == {"backend": "codex", "choice": "custom", "label": "gpt-test"},
      "switching backend keeps that backend's saved model")
info = studio.dispatch("get_state", {})["model"]
check(info["choice"] == "custom" and info["custom"] == "gpt-test" and info["editable"], "get_state reports the active choice")
studio.dispatch("set_model", {"backend": "claude", "choice": "custom", "custom": " opus "})
check(prefs.claude_model == "opus" and state.backend == "claude", "a custom name is stored trimmed")
for bad in ({"backend": "other"}, {"backend": "claude", "choice": "gpt"}, {"backend": "claude", "choice": "custom", "custom": "x" * 201},
            {"backend": "claude", "choice": "custom", "custom": "a\nb"}):
    try:
        studio.dispatch("set_model", bad)
        refused = False
    except ValueError:
        refused = True
    check(refused, f"set_model refuses {sorted(bad.items())[-1][0]}={str(sorted(bad.items())[-1][1])[:12]!r}")
check(prefs.claude_model == "opus", "refused requests change nothing")
from claude2blender import mcp_shim  # noqa: E402
check("set_model" not in (*mcp_shim.READ_TOOLS, "stage_proposal"), "the MCP shim cannot change the model")
claude_cli.prefs = real_prefs
state.backend = "claude"

# ---------------------------------------------------------------- pasted reference images

import base64  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402
from claude2blender import clipboard, companion, project_state  # noqa: E402

with open(img.filepath_raw, "rb") as fh:
    png = fh.read()
b64 = base64.b64encode(png).decode()
state.mode = "MATERIAL"
out = studio.dispatch("add_reference_image", {"image": b64, "name": "../../evil name!.png", "note": " matte finish "})
saved = bpy.path.abspath(state.references[-1].filepath)
folder = os.path.join(str(project_state.current().folder), "references")
check(out["role"] == "material" and out["count"] == 1 and os.path.dirname(saved) == folder
      and open(saved, "rb").read() == png, "an image pasted on the companion page is saved in the project's references folder")
check(os.path.basename(saved).startswith("evilname-") and saved.endswith(".png"), "the file name is generated, never a path from the page")
check(state.references[-1].note == "matte finish" and state.references[-1].role == "MATERIAL", "it becomes a normal reference with its note")
out = studio.dispatch("add_reference_image", {"image": b64, "role": "environment"})
check(out["role"] == "environment" and out["count"] == 2 and out["file"] != os.path.basename(saved), "a second paste gets its own file and role")
request = bridge.build_request(C)
check([r["exists"] for r in request["references"]] == [True, True], "pasted images are sent like any other reference")
check(len(studio.dispatch("get_state", {})["references"]) == 2, "the companion page lists them")
for bad, why in (({"image": "not base64!"}, "bad base64"), ({"image": base64.b64encode(b"GIF89a....").decode()}, "not PNG/JPEG"),
                 ({"image": b64, "role": "other"}, "unknown role"), ({"image": b64, "note": "x" * 2001}, "long note"), ({}, "no image")):
    try:
        studio.dispatch("add_reference_image", bad)
        refused = False
    except ValueError:
        refused = True
    check(refused and len(state.references) == 2, f"paste refused: {why}")
jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 64).decode()
check(clipboard.save_upload(folder, jpeg).endswith(".jpg"), "JPEG data is saved as .jpg")
check("add_reference_image" not in (*mcp_shim.READ_TOOLS, "stage_proposal"), "the MCP shim cannot add references")

if os.environ.get("C2B_SKIP_TRANSPORT") != "1":
    seen = []
    server = companion.Server(lambda method, params: seen.append((method, len(json.dumps(params)))) or "ok",
                              os.path.join(tmp, "runtime"))

    def post(path, payload, token=None):
        req = urllib.request.Request(server.url + path, json.dumps(payload).encode(),
                                     headers={"Authorization": "Bearer " + (token or server.token), "Content-Type": "application/json"})
        import threading
        result = {}

        def go():
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=20) as resp:
                    result["status"], result["body"] = resp.status, json.load(resp)
            except urllib.error.HTTPError as exc:
                result["status"], result["body"] = exc.code, json.load(exc)
            except (urllib.error.URLError, ConnectionError):
                # The server answers 400 from the headers alone and closes; a client still sending sees a reset.
                result["status"], result["body"] = 400, {"error": "connection closed"}
        thread = threading.Thread(target=go)
        thread.start()
        while thread.is_alive():
            server.pump()
            thread.join(0.02)
        return result["status"], result["body"]

    big = {"method": "add_reference_image", "params": {"image": "A" * 600_000}}
    check(post("/upload", big) == (200, {"result": "ok"}) and seen[-1][0] == "add_reference_image", "/upload accepts a large pasted image")
    check(post("/rpc", big)[0] == 400, "/rpc still refuses bodies over 256 kB")
    check(post("/upload", {"method": "chat", "params": {"text": "hi"}})[0] == 400 and len(seen) == 1, "/upload accepts nothing but pasted references")
    small = {"method": "add_reference_image", "params": {"image": "AAAA"}}
    check(post("/upload", small, token="wrong")[0] == 403 and len(seen) == 1, "/upload needs the pairing key")
    check(post("/upload", {"method": "add_reference_image", "params": {"image": "A" * 12_100_000}})[0] == 400, "/upload has its own size limit")
    server.close()

# The real clipboard (opt-in: it replaces what is on the clipboard for a moment). Windows only here.
if os.environ.get("C2B_CLIPBOARD") == "1" and os.name == "nt":
    ps = ["powershell.exe", "-NoProfile", "-STA", "-Command"]
    subprocess.run(ps + ["Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                         "$b = New-Object System.Drawing.Bitmap 40,24; "
                         "$g = [System.Drawing.Graphics]::FromImage($b); $g.Clear([System.Drawing.Color]::FromArgb(255,200,40,10)); "
                         "[System.Windows.Forms.Clipboard]::SetImage($b)"], check=True, timeout=30)
    n = len(state.references)
    state.mode = "ENVIRONMENT"
    check(bpy.ops.claude2blender.paste_reference() == {"FINISHED"} and len(state.references) == n + 1, "Paste Image reads a bitmap from the Windows clipboard")
    pasted = bpy.path.abspath(state.references[-1].filepath)
    loaded = bpy.data.images.load(pasted)
    check(tuple(loaded.size) == (40, 24) and abs(loaded.pixels[0] - 200 / 255) < 0.02 and os.path.dirname(pasted) == folder
          and state.references[-1].role == "ENVIRONMENT", "the pasted file is the clipboard image, saved beside the project, with the mode's role")
    subprocess.run(ps + ["Set-Clipboard -Value 'plain text, no image'"], check=True, timeout=30)
    try:
        result = bpy.ops.claude2blender.paste_reference()
    except RuntimeError:
        result = {"CANCELLED"}
    check(result == {"CANCELLED"} and len(state.references) == n + 1 and "No image on the clipboard" in state.status,
          "with no image on the clipboard it says so and adds nothing")
    subprocess.run(ps + ["Add-Type -AssemblyName System.Windows.Forms; $c = New-Object System.Collections.Specialized.StringCollection; "
                         f"[void]$c.Add('{img.filepath_raw}'); [System.Windows.Forms.Clipboard]::SetFileDropList($c)"], check=True, timeout=30)
    check(bpy.ops.claude2blender.paste_reference() == {"FINISHED"} and bpy.path.abspath(state.references[-1].filepath) == img.filepath_raw,
          "an image file copied in Explorer is added by its own path")
state.references.clear()
state.mode = "MATERIAL"

# ---------------------------------------------------------------- several modes in one request

from claude2blender import guard, history, properties  # noqa: E402

api = bpy.app.driver_namespace["claude2blender"]
bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0, 0, 0.1))
body = C.active_object
body.name = "Body"
bpy.ops.mesh.primitive_plane_add(size=2)
table = C.active_object
table.name = "Table"
bpy.ops.object.select_all(action="DESELECT")
body.select_set(True)
C.view_layer.objects.active = body

check(set(state.modes) == {"MATERIAL"} and properties.active_modes(state) == ["MATERIAL"], "one mode by default, as before")
state.mode = "ENVIRONMENT"
check(set(state.modes) == {"ENVIRONMENT"}, "setting mode (older code, presets) still means exactly that mode")
state.modes = {"COMPOSITION", "MATERIAL"}
check(state.mode == "MATERIAL" and properties.active_modes(state) == ["MATERIAL", "COMPOSITION"], "modes combine; mode follows as the first one on")
state.modes = set()
check(set(state.modes) == {"MATERIAL"}, "at least one mode always stays on")
state.modes = {"ENVIRONMENT", "COMPOSITION"}
properties.ensure_mode(state, "ENVIRONMENT")
check(set(state.modes) == {"ENVIRONMENT", "COMPOSITION"}, "Use Style / Measure keep a combination that already has Environment")

# How permissions combine: each mode adds its own toggles, nothing else.
state.perm_env.lighting, state.perm_env.camera, state.perm_comp.camera, state.perm_comp.lighting = True, False, True, False
state.perm_env.full_assembly, state.perm_comp.full_assembly = False, True
check(properties.permissions_for(state, "MATERIAL") is None, "Material alone has no scene permissions (no guard), as before")
env, comp = properties.permissions_for(state, "ENVIRONMENT"), properties.permissions_for(state, "COMPOSITION")
both = properties.permissions_for(state, ["ENVIRONMENT", "COMPOSITION"])
check(all(both[k] == (env[k] or comp[k]) for k in guard.CATEGORIES) and both["full_assembly"] and not both["materials"],
      "Environment + Composition allows what either allows")
check(env["lighting"] and not env["camera"] and not env["materials"], "a single mode's permissions are unchanged")
mixed = properties.permissions_for(state, ["MATERIAL", "ENVIRONMENT"])
check(mixed["materials"] and all(mixed[k] == env[k] for k in guard.CATEGORIES), "Material + Environment adds only 'materials' to Environment's toggles")

state.modes = {"MATERIAL", "ENVIRONMENT"}
state.prompt = "Brushed steel body under a soft key light"
request, _text = bridge.send_request(C, copy_to_clipboard=False)
check(request["mode"] == "material" and request["modes"] == ["material", "environment"], "the request lists every mode that is on")
check(request["mode_label"] == "Material Match + Environment Match" and "combines these modes" in request["mode_guidance"],
      "label and guidance name the combination")
check(request["permissions"]["materials"] and "layout" in request["scene"]
      and any("Materials" in a for a in request["permissions"]["allowed"]), "it carries scene permissions, layout and the materials permission")
system = claude_cli.system_prompt(request["modes"])
check("Material mode:" in system and "Environment mode:" in system and "Scene helpers" in system
      and "Combined request" in system and "Composition mode:" not in system, "the agent gets both modes' rules and the combined rule")
check(claude_cli.system_prompt("material") == claude_cli.SYSTEM_PROMPT and "Combined request" not in claude_cli.system_prompt("environment"),
      "single-mode prompts are unchanged")
state.mode = "ENVIRONMENT"
texts, _ops = draw(ui.C2B_PT_main)
check("Mode" in texts and "Shift+click another mode to combine them" in texts, "one mode: the panel says how to combine")
state.modes = {"MATERIAL", "ENVIRONMENT", "COMPOSITION"}
texts, ops = draw(ui.C2B_PT_main)
check("Modes (combined in one request)" in texts and any(t.startswith("Environment may change") for t in texts)
      and any(t.startswith("Composition may change") for t in texts) and ("claude2blender.stage_preset", "Use Preset") in ops,
      "three modes: presets, styles and each scene mode's toggles are all shown")

# One change, one Apply, one Undo for a combined request; the guard follows the combined set.
COMBO = ("mat = bpy.data.materials.get('Combo Steel') or bpy.data.materials.new('Combo Steel')\n"
         "mat.use_nodes = True\nassign_material(mat)\n"
         "c2b.light('C2B Combo Key', location=(1, -1, 2), target=(0, 0, 0), energy=40)\n")


def stage(modes, code, summary):
    state.modes = set(modes)
    bridge.send_request(C, copy_to_clipboard=False)
    api.stage_proposal(code, summary)


state.perm_env.lighting = True
stage({"ENVIRONMENT"}, COMBO, "combo in Environment only")
bpy.ops.claude2blender.apply_proposal()
check(state.status.startswith("Blocked by Allowed Changes") and "turn on Material as well" in state.status
      and "C2B Combo Key" not in bpy.data.objects and not body.material_slots, "Environment alone still blocks material changes, and says how to allow them")
state.proposal_pending = False
n = len(history.entries())
stage({"MATERIAL", "ENVIRONMENT"}, COMBO, "Steel body and key light")
bpy.ops.claude2blender.preview_proposal()
check(history.preview_entry() is not None and body.material_slots[0].material.name == "Combo Steel"
      and "C2B Combo Key" in C.scene.objects, "Material + Environment: one preview shows the material and the light")
bpy.ops.claude2blender.apply_proposal()
check(len(history.entries()) == n + 1 and history.entries()[-1]["request"]["modes"] == ["material", "environment"],
      "it is one History entry")
bpy.ops.claude2blender.history_undo()
check((not body.material_slots or body.material_slots[0].material is None) and "C2B Combo Key" not in C.scene.objects,
      "one Undo takes back the material and the light together")
bpy.ops.claude2blender.history_redo()
check(body.material_slots[0].material.name == "Combo Steel" and "C2B Combo Key" in C.scene.objects, "one Redo brings both back")
stage({"MATERIAL", "ENVIRONMENT"}, "bpy.data.objects['Table'].location.x += 1.0", "moves the table")
bpy.ops.claude2blender.apply_proposal()
check(state.status.startswith("Blocked by Allowed Changes") and abs(table.location.x) < 1e-6,
      "combining with Material does not loosen the scene guard")
state.proposal_pending = False
state.preserve_geometry = True
stage({"MATERIAL", "ENVIRONMENT"}, "bpy.data.objects['Body'].scale.x = 3.0", "scales the body")
bpy.ops.claude2blender.apply_proposal()
check(not state.last_apply_ok and "Preserve Geometry" in state.status, "Preserve Geometry still guards a combined request")
state.proposal_pending = False
old_request = {"mode": "environment", "selection": {"objects": [], "faces": []}}
check(guard.applies(old_request) and not guard.applies({"mode": "material"}) and guard.request_modes(old_request) == ["environment"],
      "requests saved before 0.8.2 (mode only) are still understood")
state.mode = "MATERIAL"

print(f"\nAll {ok} v0.8 checks passed on Blender {bpy.app.version_string}")
addon.unregister()
