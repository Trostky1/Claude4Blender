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

print(f"\nAll {ok} v0.8 checks passed on Blender {bpy.app.version_string}")
addon.unregister()
