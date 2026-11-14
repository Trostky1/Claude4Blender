"""Meaningful geometry, photometric, persistence and recipe safety checks."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import numpy as np
from mathutils import Vector
import claude2blender as addon
from claude2blender import bridge, history, knowledge, project_state, quality, studio

addon.register()
state=bpy.context.window_manager.claude2blender
checks=0
def check(v,msg):
    global checks
    assert v,msg
    checks+=1;print("PASS",msg)

p=quality.lightpaint_position((0,0,0),(0,0,1),(1,0,1),2)
incoming=p.normalized();view=Vector((1,0,1)).normalized()
check((incoming+view).normalized().dot(Vector((0,0,1)))>.999999,"highlight obeys mirror geometry")
try: quality.lightpaint_position((0,0,0),(0,0,1),(0,0,-1),2)
except ValueError: check(True,"backfacing highlight rejected")
else:raise AssertionError("backface")
image=np.full((20,30,3),.5);mask=np.zeros((20,30),bool);mask[5:15,10:20]=True
m=quality.image_metrics(image,mask,image)
check(m["noise_rms"]==0 and abs(m["fill_fraction"]-1/6)<1e-9,"known noise and fill measurements")
image[6:8,12:14]=1
m=quality.image_metrics(image,mask)
check(abs(m["clipped_highlights"]-.04)<1e-9,"known clipped product area")
check(any(c["check"]=="noise" and c["status"]=="review" for c in quality.image_gate(m)),"unmeasured noise never passes")
check(knowledge.recipe_code(2)==knowledge.recipe_code(2) and knowledge.recipe_code(2)!=knowledge.recipe_code(3),"repeatable seed with variation")
state.mode="ENVIRONMENT"
bridge.send_request(bpy.context,copy_to_clipboard=False)
before=bpy.data.objects['Cube'].matrix_world.copy()
bridge._api.stage_proposal(knowledge.recipe_code(2),"Varied studio")
check(bpy.data.objects.get('C2B Recipe Key') is None,"recipe only stages")
bpy.ops.claude2blender.apply_proposal()
check(state.last_apply_ok,"recipe passes existing guards")
key=bpy.data.objects['C2B Recipe Key']
energy=key.data.energy
bridge.send_request(bpy.context,copy_to_clipboard=False)
bridge._api.stage_proposal(knowledge.finish_code({key.name:energy*.5},-.3),"Finish")
bpy.ops.claude2blender.apply_proposal()
check(state.last_apply_ok and abs(key.data.energy-energy*.5)<1e-5,"Finish changes named light")
history.undo_last()
check(abs(key.data.energy-energy)<1e-5 and bpy.data.objects['Cube'].matrix_world==before,"Finish exact undo preserves product")
folder=Path(tempfile.mkdtemp())
a=project_state.Store(folder);a.save();b=project_state.Store(folder);a.turn('user','a')
try:b.turn('user','b')
except RuntimeError:check(True,"concurrent sidecar writer rejected")
else:raise AssertionError("lost update")
(folder/'state.json').write_text('{bad')
c=project_state.Store(folder)
try:c.save()
except RuntimeError:check(True,"corrupt sidecar preserved")
else:raise AssertionError("corruption overwritten")
addon.unregister()
print(f"All {checks} quality checks passed on Blender {bpy.app.version_string}")
