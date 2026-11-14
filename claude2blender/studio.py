"""Notes and storyboard controller. Only explicit Blender buttons execute scene work."""
import copy
import json
from pathlib import Path
import sys
import uuid
import webbrowser

import bpy
from bpy.app.handlers import persistent
from bpy.props import FloatProperty, IntProperty, StringProperty
from bpy_extras import view3d_utils
from mathutils import Vector

from . import bridge, claude_cli, companion, project_state
from .properties import get_state

server = None
_draw_handle = None
_audit_session = uuid.uuid4().hex


@persistent
def on_load(*_args):
    claude_cli.cancel()
    project_state.reset()


@persistent
def on_save(*_args):
    try:
        project_state.migrate_saved()
    except (OSError, RuntimeError) as exc:
        get_state().status = "Sidecar: "+str(exc)


def sync_audit():
    from . import history
    try:
        store = project_state.current()
        # Do not create a sidecar merely by registering or viewing a scene.
        if not history.entries() and not store.data["conversation"] and not store.data["notes"]:
            return .5
        audit = [{k:e[k] for k in ("id", "summary", "state", "time")} for e in history.entries()]
        session_id = _audit_session
        if store.data.get("session_history") != audit:
            store.data["session_history"] = audit
            store.data["history"].append(dict(session=session_id, entries=audit, undo_scope="current Blender session"))
            store.save()
    except (OSError, RuntimeError, ValueError) as exc:
        get_state().status = "Sidecar: "+str(exc)
    return .5


def add_note(text, obj, face=-1, local=(0, 0, 0), **extra):
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError("Write a note of 1–4000 characters")
    if obj not in bpy.data.objects:
        raise ValueError("Object no longer exists")
    note = dict(id=uuid.uuid4().hex, text=text.strip(), object=obj, face=int(face),
                local_position=list(local), status="open", proposal_id=None,
                before_thumbnail=extra.pop("before_thumbnail",None), after_thumbnail=None, **extra)
    store = project_state.current()
    store.data["notes"].append(note)
    store.save()
    return note


def validate_shots(shots):
    if not isinstance(shots, list) or not 1 <= len(shots) <= 20:
        raise ValueError("Storyboard requires 1–20 shots")
    previous = 0
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError("Invalid shot")
        camera = bpy.data.objects.get(shot.get("camera", ""))
        if camera is None or camera.type != "CAMERA":
            raise ValueError("Choose an existing camera")
        start, end = shot.get("start"), shot.get("end")
        if type(start) is not int or type(end) is not int or not previous < start <= end or end > 100000:
            raise ValueError("Frame ranges must be ordered, non-overlapping positive integers")
        if shot.get("motion", "hold") not in ("hold", "push_in", "orbit"):
            raise ValueError("Unsupported motion")
        if len(str(shot.get("title", ""))) > 200:
            raise ValueError("Shot title too long")
        previous = end


def set_storyboard(shots):
    validate_shots(shots)
    store = project_state.current()
    store.data["storyboard"] = copy.deepcopy(shots)
    store.data["storyboard_revision"] += 1
    store.data["approved_revision"] = None
    store.save()


def dispatch(method, params):
    if not isinstance(params, dict):
        raise ValueError("Expected object parameters")
    state, store = get_state(), project_state.current()
    if method == "get_state":
        from . import models
        p = claude_cli.prefs()
        models.migrate(p)
        return dict(store=copy.deepcopy(store.data), scene=bridge.scene_overview(),
                    status=state.gen_detail, backend=state.backend, filepath=bpy.data.filepath,
                    busy=claude_cli.busy(),
                    references=[dict(file=bpy.path.basename(r.filepath), role=r.role.lower(), note=r.note,
                                     exists=Path(bpy.path.abspath(r.filepath)).is_file()) for r in state.references],
                    model=dict(choice=models.choice(p, state.backend), label=models.label(p, state.backend),
                               custom=getattr(p, state.backend+"_model", "") if p else "",
                               options=[[i[0], i[1]] for i in models.items(state.backend)],
                               editable=p is not None))
    if method == "add_reference_image":
        # An image pasted on the companion page becomes a reference file beside the project.
        from . import clipboard
        from .operators import MODE_TO_ROLE, _add_reference
        role = str(params.get("role") or MODE_TO_ROLE[state.mode]).upper()
        if role not in ("MATERIAL", "ENVIRONMENT", "COMPOSITION", "PRODUCT"):
            raise ValueError("Unknown reference role")
        note = params.get("note", "")
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError("Note is too long")
        if len(state.references) >= 24:
            raise ValueError("Remove a reference first (24 at most)")
        path = clipboard.save_upload(clipboard.folder_for(store.folder), params.get("image"), params.get("name"))
        _add_reference(state, path, role)
        state.references[state.active_reference].note = note.strip()
        bridge._redraw()
        return dict(file=Path(path).name, role=role.lower(), count=len(state.references))
    if method == "set_model":
        # A setting, not a scene change: which backend and model the next message uses.
        from . import models
        p = claude_cli.prefs()
        backend, choice, custom = params.get("backend", state.backend), params.get("choice"), params.get("custom", "")
        if claude_cli.busy():
            raise ValueError("Wait for the current message")
        if backend not in ("claude", "codex"):
            raise ValueError("Unknown backend")
        if choice is None:   # switching backend only: keep that backend's saved model
            choice = models.choice(p, backend)
        if choice not in models.choices(backend):
            raise ValueError("Unknown model")
        if not isinstance(custom, str) or len(custom) > 200 or any(ord(c) < 32 for c in custom):
            raise ValueError("Invalid model name")
        if p is None:
            raise ValueError("Add-on preferences are unavailable")
        state.backend = backend
        setattr(p, backend+"_model_choice", choice)
        if choice == models.CUSTOM and "custom" in params and params.get("choice") is not None:
            setattr(p, backend+"_model", custom.strip())
        return dict(backend=backend, choice=choice, label=models.label(p, backend))
    if method == "get_context":
        return bridge._api.live_context()
    if method == "list_notes":
        return copy.deepcopy(store.data["notes"])
    if method == "get_storyboard":
        return dict(shots=copy.deepcopy(store.data["storyboard"]), revision=store.data["storyboard_revision"],
                    approved_revision=store.data["approved_revision"])
    if method == "get_queue":
        return copy.deepcopy(store.data["render_queue"])
    if method in ("render_image", "add_render_note", "analyze_render", "finish_preview", "finish_stage", "finish_lights", "review_render", "approve_render", "pack_render"):
        from . import render_analysis
        from . import delivery
        job = next(j for j in store.data["render_queue"] if j["id"] == params.get("job"))
        folder = delivery.artifact_folder(store, job)
        shot = params.get("shot", 1)
        if type(shot) is not int or not 1 <= shot <= 20:
            raise ValueError("Invalid shot number")
        if method == "add_render_note":
            obj = render_analysis.pick_object(folder, shot, params.get("u", -1), params.get("v", -1))
            return add_note(params.get("text"), obj, render_job=job["id"], render_shot=shot,
                            render_pixel=[params["u"], params["v"]], before_thumbnail=dict(job=job["id"],shot=shot))
        if method == "analyze_render":
            return delivery.measure(store, job)
        if method == "approve_render":
            delivery.approve(store, job, params.get("note"))
            return job["qa"]
        if method == "pack_render":
            return delivery.pack(store, job)
        if method == "review_render":
            if job.get("review_passes", 0) >= 3:
                raise ValueError("Three critique passes reached for this capture; apply a reviewed proposal and rerender")
            if claude_cli.busy():
                raise ValueError("Wait for the active generation")
            frame = next(iter(sorted(folder.glob(f"shot-{shot:02d}-*.png"))), None)
            if frame is None:
                raise ValueError("Render is not ready")
            report = render_analysis.analyze(folder, shot)
            state.prompt = "Review the captured render against supplied references and these measured checks: "+json.dumps(report)+". Propose one correction for review; do not execute it."
            claude_cli.start_generate(bpy.context, review_images=[str(frame)])
            job["review_passes"] = job.get("review_passes", 0)+1
            store.save()
            return "Critique requested; any correction waits for Preview / Apply in Blender"
        if method == "finish_lights":
            return json.loads((folder/"lights.json").read_text())
        if method.startswith("finish_"):
            import math
            factors = params.get("factors", {})
            exposure = float(params.get("exposure",0))
            lights = json.loads((folder/"lights.json").read_text())
            if not isinstance(factors, dict) or set(factors)-set(lights) or not -5 <= exposure <= 5:
                raise ValueError("Invalid finishing settings")
            if any(not math.isfinite(float(x)) or not 0 <= float(x) <= 8 for x in factors.values()):
                raise ValueError("Invalid light multipliers")
            if method == "finish_stage":
                from .knowledge import finish_code
                if any(bpy.data.objects.get(v["object"]) is None or bpy.data.objects[v["object"]].type != "LIGHT" or abs(bpy.data.objects[v["object"]].data.energy-v["energy"]) > .0001 for v in lights.values()):
                    raise ValueError("Light energies changed since capture; rerender before Finish")
                state.mode = "ENVIRONMENT"
                bridge.send_request(bpy.context, copy_to_clipboard=False)
                code = finish_code({v["object"]:v["energy"]*float(factors.get(k,1)) for k,v in lights.items()}, exposure)
                return bridge._api.stage_proposal(code, "Finish light balance and exposure", request_id=state.request_id)
            import numpy as np
            import OpenImageIO as oiio
            # Explicitly labeled sRGB approximation; the production render retains its view transform.
            rgb = render_analysis.relight(folder/f"shot-{shot:02d}-passes.exr", factors, exposure)
            rgb = np.clip(np.where(rgb <= .0031308, rgb*12.92, 1.055*np.maximum(rgb,0)**(1/2.4)-.055),0,1)
            image = folder/"finish-preview.png"
            output = oiio.ImageOutput.create(str(image))
            output.open(str(image), oiio.ImageSpec(rgb.shape[1],rgb.shape[0],3,oiio.UINT8))
            output.write_image((rgb*255).astype(np.uint8)); output.close()
        else:
            image = next(iter(sorted(folder.glob(f"shot-{shot:02d}-*.png"))),None)
        if image is None or image.stat().st_size > 8_000_000:
            raise ValueError("Preview missing or too large")
        import base64
        return dict(png=base64.b64encode(image.read_bytes()).decode())
    if method == "proposal_status":
        return bridge._api.proposal_status()
    if method == "stage_proposal":
        if params.get("request_id") != state.request_id:
            raise ValueError("Request is stale; read current context")
        if claude_cli.busy():
            raise ValueError("Wait for the active generation to finish")
        if state.request_id == 0:
            bridge.send_request(bpy.context, copy_to_clipboard=False)
        code, summary = params.get("code"), params.get("summary")
        if not isinstance(code, str) or len(code) > 150000 or not isinstance(summary, str):
            raise ValueError("Invalid proposal")
        return bridge._api.stage_proposal(code, summary, request_id=state.request_id)
    if method == "add_note":
        # Companion may create notes, but the MCP shim exposes no mutation except staging.
        return add_note(params.get("text"), params.get("object"))
    if method == "note_status":
        status = params.get("status")
        if status not in ("open", "in_progress", "done", "wontfix"):
            raise ValueError("Unknown note status")
        note = next(n for n in store.data["notes"] if n["id"] == params.get("id"))
        note["status"] = status
        store.save()
        return note
    if method in ("work_note", "note_after"):
        note = next(n for n in store.data["notes"] if n["id"] == params.get("id"))
        if method == "work_note":
            if claude_cli.busy():
                raise ValueError("Wait for the active generation")
            state.prompt = "Address this part note with a proposal for review: "+json.dumps(note)
            claude_cli.start_generate(bpy.context,note_id=note["id"])
            return "Note sent to agent; correction will be staged for review"
        job = next(j for j in store.data["render_queue"] if j["id"] == params.get("job"))
        from .delivery import artifact_folder
        shot = params.get("shot")
        if type(shot) is not int or not 1 <= shot <= len(job.get("shots",[])):
            raise ValueError("Invalid captured shot")
        folder = artifact_folder(store,job)
        if not (folder/"complete.json").exists():
            raise ValueError("Capture is not complete")
        note["after_thumbnail"] = dict(job=job["id"],shot=shot)
        store.save()
        return note
    if method == "set_storyboard":
        set_storyboard(params.get("shots"))
        return dispatch("get_storyboard", {})
    if method == "chat":
        text = params.get("text")
        if not isinstance(text, str) or not 0 < len(text) <= 16000:
            raise ValueError("Message requires 1–16000 characters")
        if claude_cli.busy():
            raise ValueError("Wait for the current message")
        state.prompt = text
        claude_cli.start_generate(bpy.context)
        return "Message sent; proposals require review in Blender"
    raise ValueError("Method is not exposed")


def start_server():
    global server
    if server is None:
        server = companion.Server(dispatch, Path(claude_cli.workspace_dir())/"runtime")
        bpy.app.timers.register(server.pump, first_interval=.1)
    return server


def mcp_config():
    if server is None:
        return None
    path = server.runtime/"mcp.json"
    path.write_text(json.dumps({"mcpServers": {"c2b": {"command": sys.executable,
        "args": [str(Path(__file__).with_name("mcp_shim.py")), str(server.connection_file)]}}}), encoding="utf-8")
    return str(path)


class C2B_OT_companion(bpy.types.Operator):
    bl_idname = "claude2blender.companion"
    bl_label = "Open companion"

    def execute(self, context):
        webbrowser.open(start_server().url)
        return {"FINISHED"}


class C2B_OT_pair(bpy.types.Operator):
    bl_idname = "claude2blender.copy_pairing_key"
    bl_label = "Copy pairing key"

    def execute(self, context):
        context.window_manager.clipboard = start_server().token
        self.report({"INFO"}, "Paste the pairing key in the companion")
        return {"FINISHED"}


class C2B_OT_note(bpy.types.Operator):
    bl_idname = "claude2blender.add_note"
    bl_label = "Note on selected part"
    text: StringProperty(name="Note")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=440)

    def execute(self, context):
        add_note(self.text, context.active_object.name)
        return {"FINISHED"}


class C2B_OT_pin(bpy.types.Operator):
    bl_idname = "claude2blender.pin_note"
    bl_label = "Pin note on surface"
    text: StringProperty(name="Note")

    def invoke(self, context, event):
        if context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=440)

    def execute(self, context):
        if not self.text.strip():
            return {"CANCELLED"}
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("Click the product surface to pin; Esc to cancel")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"}:
            context.area.header_text_set(None)
            return {"CANCELLED"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            region = next(r for r in context.area.regions if r.type == "WINDOW")
            xy = (event.mouse_x-region.x, event.mouse_y-region.y)
            if not (0 <= xy[0] < region.width and 0 <= xy[1] < region.height):
                return {"RUNNING_MODAL"}
            rv3d = context.space_data.region_3d
            origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
            direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
            hit, pos, normal, face, obj, matrix = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)
            if hit:
                add_note(self.text, obj.original.name, face, matrix.inverted()@pos,
                         local_normal=list(matrix.to_3x3().transposed()@normal))
                context.area.header_text_set(None)
                context.area.tag_redraw()
                return {"FINISHED"}
        return {"PASS_THROUGH"}


def draw_pins():
    if bpy.app.background:
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    points = []
    for note in project_state.current().data["notes"]:
        obj = bpy.data.objects.get(note["object"])
        if obj and note["status"] in ("open", "in_progress"):
            points.append(obj.matrix_world@Vector(note["local_position"]))
    if points:
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "POINTS", {"pos": points})
        gpu.state.point_size_set(9)
        shader.bind()
        shader.uniform_float("color", (1, .55, .12, 1))
        batch.draw(shader)
        gpu.state.point_size_set(1)


class C2B_OT_shot(bpy.types.Operator):
    bl_idname = "claude2blender.add_shot"
    bl_label = "Add shot from active camera"
    title: StringProperty(name="Shot", default="Hero")
    start: IntProperty(name="First frame", default=1, min=1)
    end: IntProperty(name="Last frame", default=48, min=1)

    def invoke(self, context, event):
        shots = project_state.current().data["storyboard"]
        self.start = shots[-1]["end"]+1 if shots else 1
        self.end = self.start+47
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if context.scene.camera is None:
            self.report({"ERROR"}, "Choose a scene camera first")
            return {"CANCELLED"}
        shots = copy.deepcopy(project_state.current().data["storyboard"])
        shots.append(dict(id=uuid.uuid4().hex, title=self.title, camera=context.scene.camera.name,
                          start=self.start, end=self.end, motion="push_in", transition="cut"))
        try:
            set_storyboard(shots)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc)); return {"CANCELLED"}
        return {"FINISHED"}


class C2B_OT_approve(bpy.types.Operator):
    bl_idname = "claude2blender.approve_storyboard"
    bl_label = "Approve storyboard"

    def execute(self, context):
        store = project_state.current()
        try:
            validate_shots(store.data["storyboard"])
        except ValueError as exc:
            self.report({"ERROR"}, str(exc)); return {"CANCELLED"}
        store.data["approved_revision"] = store.data["storyboard_revision"]
        store.save()
        return {"FINISHED"}


class C2B_OT_recipe(bpy.types.Operator):
    bl_idname = "claude2blender.recipe"
    bl_label = "Stage varied studio recipe"
    seed: IntProperty(name="Variation seed", default=1, min=0)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .knowledge import recipe_code
        state = get_state(context)
        state.mode = "ENVIRONMENT"
        bridge.send_request(context, copy_to_clipboard=False)
        bridge._api.stage_proposal(recipe_code(self.seed), f"Studio recipe, seed {self.seed}", request_id=state.request_id)
        return {"FINISHED"}


class C2B_OT_lightpaint(bpy.types.Operator):
    bl_idname = "claude2blender.lightpaint"
    bl_label = "Stage highlight at latest pin"
    distance: FloatProperty(name="Light distance", default=1, min=.001, subtype="DISTANCE")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .quality import lightpaint_position
        try:
            note = next(n for n in reversed(project_state.current().data["notes"]) if "local_normal" in n)
            obj = bpy.data.objects[note["object"]]
            point = obj.matrix_world@Vector(note["local_position"])
            normal = obj.matrix_world.to_3x3().inverted().transposed()@Vector(note["local_normal"])
            camera = context.scene.camera
            if camera is None:
                raise ValueError("Choose a scene camera first")
            position = lightpaint_position(point, normal, camera.matrix_world.translation, self.distance)
        except (StopIteration, KeyError, ValueError) as exc:
            self.report({"ERROR"}, str(exc) or "Pin a visible surface first"); return {"CANCELLED"}
        state = get_state(context)
        state.mode = "ENVIRONMENT"
        bridge.send_request(context, copy_to_clipboard=False)
        code = f"c2b.light('C2B Highlight', location={tuple(position)!r}, target={tuple(point)!r}, energy=30, size=.2)"
        bridge._api.stage_proposal(code, "Place highlight at pinned surface", request_id=state.request_id)
        return {"FINISHED"}


class C2B_PT_studio(bpy.types.Panel):
    bl_idname = "C2B_PT_studio"
    bl_label = "Studio board"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Claude"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("claude2blender.companion")
        row.operator("claude2blender.copy_pairing_key", text="Pair")
        row = layout.row(align=True)
        row.operator("claude2blender.add_note")
        row.operator("claude2blender.pin_note", text="Pin")
        layout.operator("claude2blender.lightpaint")
        layout.operator("claude2blender.recipe")
        store = project_state.current()
        for note in store.data["notes"][-8:]:
            layout.label(text=f"{note['object']}: {note['text'][:65]}")
        layout.separator()
        for i, shot in enumerate(store.data["storyboard"]):
            layout.label(text=f"{i+1}. {shot['title']} · {shot['start']}–{shot['end']}")
        layout.operator("claude2blender.add_shot")
        layout.operator("claude2blender.approve_storyboard")
        approved = store.data["approved_revision"] == store.data["storyboard_revision"]
        layout.label(text="Storyboard approved" if approved else "Storyboard needs approval")
        layout.operator("claude2blender.render_board")
        for job in store.data["render_queue"][-3:]:
            row = layout.row(align=True)
            row.label(text=job["status"])
            if job["status"] == "running":
                row.operator("claude2blender.cancel_render",text="Cancel").uid=job["id"]


_classes = (C2B_OT_companion, C2B_OT_pair, C2B_OT_note, C2B_OT_pin,
            C2B_OT_shot, C2B_OT_approve, C2B_OT_recipe, C2B_OT_lightpaint, C2B_PT_studio)


def register():
    global _draw_handle
    for cls in _classes:
        bpy.utils.register_class(cls)
    if not bpy.app.background:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_pins, (), "WINDOW", "POST_VIEW")
    bpy.app.handlers.load_post.append(on_load)
    bpy.app.handlers.save_post.append(on_save)
    bpy.app.timers.register(sync_audit, first_interval=.5, persistent=True)


def unregister():
    global server, _draw_handle
    if bpy.app.timers.is_registered(sync_audit):
        bpy.app.timers.unregister(sync_audit)
    for handlers, fn in ((bpy.app.handlers.load_post,on_load),(bpy.app.handlers.save_post,on_save)):
        if fn in handlers:
            handlers.remove(fn)
    if server:
        if bpy.app.timers.is_registered(server.pump):
            bpy.app.timers.unregister(server.pump)
        server.close()
        server = None
    if _draw_handle:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        _draw_handle = None
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
