"""Encode already rendered frames in a disposable Blender scene."""
from pathlib import Path
import bpy


def encode(frames, output, width, height, fps):
    original=bpy.context.window.scene
    scene=bpy.data.scenes.new("C2B sequence encoding")
    bpy.context.window.scene=scene
    try:
        scene.render.resolution_x=width;scene.render.resolution_y=height
        scene.render.resolution_percentage=100;scene.render.fps=fps
        scene.frame_start=1;scene.frame_end=len(frames)
        scene.view_settings.view_transform="Standard"
        scene.view_settings.look="None"
        scene.render.use_sequencer=True
        strip=scene.sequence_editor_create().strips.new_image("Rendered frames",str(frames[0]),channel=1,frame_start=1)
        for path in frames[1:]:strip.elements.append(Path(path).name)
        strip.frame_final_duration=len(frames)
        settings=scene.render.image_settings
        if hasattr(settings,"media_type"):settings.media_type="VIDEO"
        settings.file_format="FFMPEG"
        scene.render.ffmpeg.format="MPEG4"
        scene.render.ffmpeg.codec="H264"
        scene.render.ffmpeg.constant_rate_factor="HIGH"
        scene.render.filepath=str(output)
        bpy.ops.render.render(animation=True)
    finally:
        bpy.context.window.scene=original
        bpy.data.scenes.remove(scene)


if __name__=="__main__":
    import json,sys
    plan=json.loads(Path(sys.argv[sys.argv.index("--")+1]).read_text(encoding="utf-8"))
    folder=Path(plan["output"])
    encode(sorted(folder.glob("shot-*.png")),folder/"preview.mp4",plan["width"],plan["height"],plan["fps"])
