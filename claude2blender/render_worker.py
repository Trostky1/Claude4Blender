"""Internal background renderer; reads only a validated job plan created by Blender."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


def render(plan):
    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_percentage = 100
    scene.render.resolution_x, scene.render.resolution_y = plan["width"], plan["height"]
    scene.render.fps = plan["fps"]
    scene.render.engine = "CYCLES"
    scene.cycles.samples = plan["samples"]
    scene.cycles.use_denoising = True
    scene.cycles.device = "CPU"
    out = Path(plan["output"])
    out.mkdir(parents=True, exist_ok=True)
    view = bpy.context.view_layer
    view.use_pass_object_index = True
    object_names = {}
    light_manifest = {}
    for index, obj in enumerate(scene.objects, 1):
        obj.pass_index = index
        object_names[str(index)] = obj.name
        if obj.type == "LIGHT":
            group = "C2B_"+str(index)
            view.lightgroups.add(name=group)
            obj.lightgroup = group
            light_manifest[group] = dict(object=obj.name, energy=obj.data.energy)
    if scene.world:
        view.lightgroups.add(name="C2B_world")
        scene.world.lightgroup = "C2B_world"
    (out/"objects.json").write_text(json.dumps(object_names))
    (out/"lights.json").write_text(json.dumps(light_manifest))
    (out/"targets.json").write_text(json.dumps(plan.get("targets", [])))
    for number, shot in enumerate(plan["shots"], 1):
        camera = bpy.data.objects[shot["camera"]]
        scene.camera = camera
        base = camera.matrix_world.copy()
        # Animation lives only in this temporary copy. Never keyframe the open project.
        for frame in range(shot["start"], shot["end"]+1):
            scene.frame_set(frame)
            t = (frame-shot["start"])/max(1, shot["end"]-shot["start"])
            ease = 1-(1-t)**3
            camera.matrix_world = base.copy()
            if shot.get("motion") == "push_in":
                camera.matrix_world.translation += base.to_quaternion()@Vector((0, 0, -.12*plan.get("radius",1)*ease))
            elif shot.get("motion") == "orbit":
                center = Vector(plan.get("center",(0,0,0)))
                camera.matrix_world = Matrix.Translation(center)@Matrix.Rotation(math.radians(15)*ease, 4, "Z")@Matrix.Translation(-center)@base
            scene.render.filepath = str(out/f"shot-{number:02d}-{frame:06d}.png")
            bpy.ops.render.render(write_still=True)
            if frame == shot["start"]:
                settings = scene.render.image_settings
                if hasattr(settings, "media_type"):
                    settings.media_type = "MULTI_LAYER_IMAGE"
                formats = [i.identifier for i in settings.bl_rna.properties["file_format"].enum_items]
                settings.file_format = "OPEN_EXR_MULTILAYER" if "OPEN_EXR_MULTILAYER" in formats else "OPEN_EXR"
                settings.color_depth = "32"
                bpy.data.images["Render Result"].save_render(str(out/f"shot-{number:02d}-passes.exr"), scene=scene)
                if hasattr(settings, "media_type"):
                    settings.media_type = "IMAGE"
                settings.file_format = "PNG"
                settings.color_depth = "8"
            print("C2B_FRAME", number, frame, flush=True)
        camera.matrix_world = base
    # The video encoder sees rendered PNGs, never touches the open owner scene.
    sys.path.insert(0,str(Path(__file__).parent))
    from encode_sequence import encode
    encode(sorted(out.glob("shot-*.png")),out/"preview.mp4",plan["width"],plan["height"],plan["fps"])
    (out/"complete.json").write_text(json.dumps(dict(frames=sum(s["end"]-s["start"]+1 for s in plan["shots"]))))


if __name__ == "__main__":
    render(json.loads(Path(sys.argv[sys.argv.index("--")+1]).read_text(encoding="utf-8")))
