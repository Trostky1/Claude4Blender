"""Explicit background render on a copy, gated on the current storyboard revision."""
import json
import copy
from pathlib import Path
import subprocess
import threading
import uuid

import bpy
from bpy.props import IntProperty, StringProperty

from . import history, project_state

_jobs = {}


def start(width=640, height=360, samples=32):
    from .studio import validate_shots
    store = project_state.current()
    if "#" in str(store.folder):
        raise ValueError("Save the project in a path without '#'; Blender treats it as a frame placeholder")
    from .quality import scene_gate
    checks = scene_gate(bpy.context.scene)
    if any(c["status"] == "fail" for c in checks):
        raise ValueError("Scene QA failed: "+str(checks))
    validate_shots(store.data["storyboard"])
    if store.data["approved_revision"] != store.data["storyboard_revision"]:
        raise ValueError("Approve the current storyboard before rendering")
    if history.preview_entry() is not None:
        raise ValueError("Apply or end the active preview before rendering")
    if any(j["process"].poll() is None for j in _jobs.values()):
        raise ValueError("A render is already running")
    if not (16 <= width <= 8192 and 16 <= height <= 8192 and 1 <= samples <= 4096):
        raise ValueError("Render settings out of range")
    uid = uuid.uuid4().hex
    folder = store.folder/"renders"/uid
    folder.mkdir(parents=True)
    blend = folder/"scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), copy=True)
    from mathutils import Vector
    products = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    corners = [o.matrix_world@Vector(c) for o in products for c in o.bound_box]
    center = sum(corners, Vector())/max(1,len(corners))
    radius = max(((p-center).length for p in corners), default=1)
    plan = dict(shots=copy.deepcopy(store.data["storyboard"]), width=width, height=height, samples=samples,
                center=list(center), radius=radius, scene_checks=checks,
                fps=bpy.context.scene.render.fps, output=str(folder/"frames"),
                targets=[o.name for o in bpy.context.selected_objects if o.type == "MESH"])
    (folder/"plan.json").write_text(json.dumps(plan), encoding="utf-8")
    log = (folder/"render.log").open("w", encoding="utf-8")
    args = [bpy.app.binary_path, "--background", "--factory-startup", "--disable-autoexec", str(blend), "--python-exit-code", "1",
            "--python", str(Path(__file__).with_name("render_worker.py")), "--", str(folder/"plan.json")]
    import os
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    try:
        proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **flags)
    except Exception:
        log.close()
        raise
    item = dict(id=uid, status="running", output=str(folder/"frames"), shots=copy.deepcopy(plan["shots"]),
                storyboard_revision=store.data["storyboard_revision"], width=width, height=height,
                samples=samples, qa="pending", log=str(folder/"render.log"))
    store.data["render_queue"].append(item)
    store.save()
    _jobs[uid] = dict(process=proc, log=log, item=item, store=store)
    if not bpy.app.timers.is_registered(pump):
        bpy.app.timers.register(pump, first_interval=.5)
    return item


def cancel(uid):
    job = _jobs.get(uid)
    if job is None:
        raise ValueError("Render is no longer running")
    from .backends import Backend
    Backend().cancel(job["process"])
    job["item"]["cancelled"] = True


def pump():
    for uid, job in list(_jobs.items()):
        rc = job["process"].poll()
        if rc is not None:
            job["log"].close()
            complete = Path(job["item"]["output"])/"complete.json"
            job["item"]["status"] = "cancelled" if job["item"].get("cancelled") else ("rendered_needs_qa" if rc == 0 and complete.exists() else "failed")
            job["store"].save()
            del _jobs[uid]
    return .5 if _jobs else None


class C2B_OT_render_board(bpy.types.Operator):
    bl_idname = "claude2blender.render_board"
    bl_label = "Render approved storyboard"
    width: IntProperty(name="Width", default=640, min=16, max=8192)
    height: IntProperty(name="Height", default=360, min=16, max=8192)
    samples: IntProperty(name="Samples", default=32, min=1, max=4096)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            start(self.width, self.height, self.samples)
        except (ValueError, OSError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc)); return {"CANCELLED"}
        return {"FINISHED"}


class C2B_OT_cancel_render(bpy.types.Operator):
    bl_idname = "claude2blender.cancel_render"
    bl_label = "Cancel render"
    uid: StringProperty()

    def execute(self, context):
        try:
            cancel(self.uid)
        except ValueError as exc:
            self.report({"ERROR"},str(exc)); return {"CANCELLED"}
        return {"FINISHED"}


def register():
    bpy.utils.register_class(C2B_OT_render_board)
    bpy.utils.register_class(C2B_OT_cancel_render)


def unregister():
    for job in _jobs.values():
        job["process"].terminate()
        job["log"].close()
    _jobs.clear()
    if bpy.app.timers.is_registered(pump):
        bpy.app.timers.unregister(pump)
    bpy.utils.unregister_class(C2B_OT_render_board)
    bpy.utils.unregister_class(C2B_OT_cancel_render)
