"""Owner-approved storyboard demo; original procedural product, no external assets."""
from pathlib import Path
import json
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import claude2blender as addon
from claude2blender import claude_cli,project_state,studio,render_queue,bridge,history

bpy.ops.wm.read_factory_settings(use_empty=True)
addon.register()
root=Path(__file__).parent/"out"/"studio-demo"
root.mkdir(parents=True,exist_ok=True)
claude_cli.workspace_dir=lambda:str(root.resolve())
scene=bpy.context.scene
scene.unit_settings.system="METRIC"
scene.render.fps=24
def material(name,color,roughness,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True
    bsdf=m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Roughness'].default_value=roughness
    bsdf.inputs['Metallic'].default_value=metal
    return m
bodymat=material('Housing · graphite',(.055,.068,.08),.25,.12)
rubber=material('Grip · elastomer',(.015,.019,.023),.57)
accent=material('Control · warm aluminum',(.5,.24,.075),.25,.65)
floor=material('Floor · warm grey',(.22,.205,.19),.67)
def box(name,loc,scale,bevel,mat):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.name=name;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    mod=o.modifiers.new('Manufactured edge radius','BEVEL');mod.width=bevel;mod.segments=6
    o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    o.data.materials.append(mat)
    return o
body=box('Demo handheld housing',(0,0,.028),(.145,.082,.042),.015,bodymat)
grip=box('Demo lower grip',(0,0,.012),(.14,.077,.018),.007,rubber)
button=box('Demo control',(0,-.013,.052),(.035,.019,.006),.006,accent)
ground=box('Studio floor',(0,0,-.009),(3,3,.02),.001,floor)
bpy.ops.object.camera_add(location=(.24,-.3,.22))
cam=bpy.context.object;cam.name='Demo hero camera';cam.data.lens=58
cam.rotation_euler=(Vector((0,0,.028))-cam.location).to_track_quat('-Z','Y').to_euler()
scene.camera=cam
bpy.ops.object.light_add(type='AREA',location=(-.19,-.14,.3))
key=bpy.context.object;key.name='Broad studio key';key.data.energy=18;key.data.shape='DISK';key.data.size=.27
key.rotation_euler=(Vector((0,0,.025))-key.location).to_track_quat('-Z','Y').to_euler()
world=bpy.data.worlds.new('Quiet studio');scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(.25,.25,.25,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25
for o in bpy.context.selected_objects:o.select_set(False)
for o in (body,grip,button):o.select_set(True)
bpy.context.view_layer.objects.active=body
bpy.ops.wm.save_as_mainfile(filepath=str((root/'Handheld studio demo.blend').resolve()))
project_state.reset()
studio.add_note('Soften the housing sheen without changing its graphite color',body.name)
state=bpy.context.window_manager.claude2blender;state.mode='MATERIAL'
bridge.send_request(bpy.context,copy_to_clipboard=False)
bridge._api.stage_proposal("bpy.data.materials['Housing · graphite'].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.34",'Demo note: soften housing sheen',request_id=state.request_id)
# Known, inspected fixture proposal; automation checks the owner's Preview / Apply path.
bpy.ops.claude2blender.preview_proposal()
assert history.preview_entry() is not None,state.status
bpy.ops.claude2blender.apply_proposal()
assert state.last_apply_ok,state.status
studio.set_storyboard([dict(id='hero',title='Handheld hero · slow orbit',camera=cam.name,start=1,end=48,motion='orbit')])
bpy.ops.claude2blender.approve_storyboard()
store=project_state.current()
store.data['storyboard_approval_note']='Owner explicitly approved this 48-frame, 15-degree, 640x360 demo storyboard in chat on 2026-11-14.'
store.save()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
job=render_queue.start(640,360,64)
(root/'job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
deadline=time.time()+900
while render_queue._jobs and time.time()<deadline:
    render_queue.pump();time.sleep(.25)
assert job['status']=='rendered_needs_qa',job
(root/'job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
print('DEMO_OUTPUT',job['output'],flush=True)
addon.unregister()
