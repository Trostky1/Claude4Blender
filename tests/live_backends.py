"""Opt-in subscription smoke: real CLIs stage four proposals in a disposable scene."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import claude2blender as addon
from claude2blender import claude_cli as runner, project_state

addon.register()
bpy.context.preferences.system.use_online_access=True
root=Path(__file__).parent/"out"/"live-backends"
root.mkdir(parents=True,exist_ok=True)
runner.workspace_dir=lambda:str(root.resolve())
runner.prefs=lambda:SimpleNamespace(claude_path="",codex_path="",model="",claude_model="",codex_model="",timeout_minutes=2)
project_state.reset()
state=bpy.context.window_manager.claude2blender
rows=[]
for backend in ("claude","codex"):
    state.backend=backend
    for mode,prompt in (("MATERIAL","Stage only assign_material(preset_material('plastic_white')) for the selected Cube. Explain that it is a fixture."),
                        ("ENVIRONMENT","Stage only c2b.light('Smoke Key', location=(2,-3,4), target=(0,0,0), energy=30). Explain that it is a fixture.")):
        state.mode=mode;state.prompt=prompt
        try:
            runner.start_generate(bpy.context)
            assert runner.pump_until_done(140),"Timed out"
            rows.append(dict(backend=backend,mode=mode,status=state.gen_status,detail=state.gen_detail,
                             code=state.proposal_code if state.gen_status=="COMPLETED" else "",
                             elapsed=state.gen_elapsed))
        except Exception as exc:
            rows.append(dict(backend=backend,mode=mode,error=str(exc)))
        (root/"results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
        print(json.dumps(rows[-1]),flush=True)
addon.unregister()
