"""Loopback/MCP boundary, persistent notes and storyboard gates, background copy."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import claude2blender as addon
from claude2blender import claude_cli, companion, project_state, studio, render_queue
from claude2blender import mcp_shim

addon.register()
root = Path(tempfile.mkdtemp(dir=Path(__file__).parent/"out"))
claude_cli.workspace_dir = lambda: str(root)
project_state.reset()
store = project_state.current()
state = bpy.context.window_manager.claude2blender
checks=0
def check(value, msg):
    global checks
    assert value, msg
    checks+=1; print("PASS",msg,flush=True)

cube = bpy.data.objects.get("Cube")
note=studio.add_note("Reduce the sheen on the grip",cube.name,0,(1,0,0))
check(project_state.Store(store.folder).data["notes"][0]["text"]==note["text"],"notes survive reload")
check(set(t["name"] for t in mcp_shim.TOOLS)==set(mcp_shim.READ_TOOLS)|{"stage_proposal"},"MCP only reads and stages")
for method in ("apply","execute_code","delete","start_render","approve_storyboard"):
    try: studio.dispatch(method,{})
    except ValueError: check(True,method+" rejected")
    else: raise AssertionError(method)
shots=[dict(id="one",title="Review test",camera="Camera",start=1,end=2,motion="push_in")]
studio.set_storyboard(shots)
try: render_queue.start(32,32,1)
except ValueError as exc: check("Approve" in str(exc),"animation blocked until approval")
else: raise AssertionError("unapproved render")
bpy.ops.claude2blender.approve_storyboard()
studio.set_storyboard(shots)
check(store.data["approved_revision"] is None,"editing storyboard invalidates approval")
srv=None
if os.environ.get('C2B_SKIP_TRANSPORT') != '1':
    srv=studio.start_server()
    results=[]
    def request(method, params={}, token=None, origin=None):
        headers={"Authorization":"Bearer "+(srv.token if token is None else token),"Content-Type":"application/json"}
        if origin: headers["Origin"]=origin
        req=urllib.request.Request(srv.url+"/rpc", json.dumps(dict(method=method,params=params)).encode(),headers)
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=5) as r:
                results.append((r.status,json.load(r)))
        except urllib.error.HTTPError as exc: results.append((exc.code,json.load(exc)))
    def queued(method,params={},**extra):
        results.clear(); t=threading.Thread(target=request,args=(method,params),kwargs=extra);t.start()
        until=time.time()+6
        while t.is_alive() and time.time()<until:
            srv.pump();time.sleep(.02)
        t.join(timeout=1);assert results
        return results[-1]
    check(queued("get_state",token="wrong")[0]==403,"token rejected")
    check(queued("get_state",origin="https://evil.example")[0]==403,"cross-origin request rejected")
    check(queued("get_state")[0]==200,"paired companion reads state")
    check(queued("stage_proposal",dict(code="raise RuntimeError('must not run')",summary="Inspect",request_id=state.request_id))[0]==200,"HTTP stages without executing")
    check(state.proposal_pending,"proposal waits in Blender")
    check(queued("stage_proposal",dict(code="pass",summary="Stale",request_id=-1))[0]==400,"stale staging rejected")
    check(queued("add_note",dict(text="<script>alert(1)</script>",object="Cube"))[0]==200,"note text stored as data")
    
# This is an automated two-frame fixture, not approval of an owner's production storyboard.
bpy.ops.claude2blender.approve_storyboard()
original_path=bpy.data.filepath
matrix=bpy.context.scene.camera.matrix_world.copy()
item=render_queue.start(32,32,1)
check(bpy.data.filepath==original_path and bpy.context.scene.camera.matrix_world==matrix,"render uses a copy")
deadline=time.time()+90
while render_queue._jobs and time.time()<deadline:
    render_queue.pump();time.sleep(.1)
check(item["status"]=="rendered_needs_qa", "background two-frame render completes and requires QA")
check((Path(item["output"])/"preview.mp4").stat().st_size>0,"background frames encode to MP4")
check(len(list(Path(item["output"]).glob('*.png')))==2,"expected frames written")
print("FIXTURE_OUTPUT",item["output"],flush=True)
from claude2blender import render_analysis, delivery
import numpy as np
folder=Path(item["output"])
channels=render_analysis.channels(folder/"shot-01-passes.exr")
mask=next(v for k,v in channels.items() if "IndexOB" in k or "Object Index" in k)
names=json.loads((folder/"objects.json").read_text(encoding="utf-8"))
cube_id=int(next(k for k,v in names.items() if v=="Cube"))
yy,xx=np.nonzero(np.rint(mask)==cube_id)
u,v=(float(xx[len(xx)//2])+.5)/mask.shape[1],(float(yy[len(yy)//2])+.5)/mask.shape[0]
check(render_analysis.pick_object(folder,1,u,v)=="Cube","render pixel maps to exact object index")
render_note=studio.dispatch("add_render_note",dict(job=item["id"],u=u,v=v,text="Correct this rendered edge"))
check(render_note["object"]=="Cube" and render_note["render_job"]==item["id"],"render note retains capture identity")
check(len(studio.dispatch("finish_preview",dict(job=item["id"],factors={},exposure=0))["png"])>0,"captured light groups produce Finish preview")
check(studio.dispatch("analyze_render",dict(job=item["id"]))[0]["scope"]==["Cube"],"QA uses selected product mask")
try: delivery.pack(store,item)
except ValueError: check(True,"Pack blocked until QA review")
else: raise AssertionError("unreviewed Pack")
delivery.approve(store,item,"Automated fixture review only; not owner approval or production quality certification.")
delivery.measure(store,item)
check(item["qa"]=="approved_with_visual_review","repeating unchanged QA preserves explicit approval")
packed=Path(delivery.pack(store,item))
check((packed/"contact-sheet.png").is_file() and len(list((packed/"frames").glob('*.png')))==2,"Pack contains reviewed frames and contact sheet")
check(len(json.loads((packed/"manifest.json").read_text())["frames"])==2,"Pack manifest inventories frame hashes")
try: delivery.artifact_folder(store,dict(output=str(root)))
except ValueError: check(True,"artifact paths cannot escape project capture folder")
else: raise AssertionError("unsafe artifact path")
studio.dispatch("note_after",dict(id=render_note["id"],job=item["id"],shot=1))
check(render_note["before_thumbnail"]==render_note["after_thumbnail"],"render note retains before/after capture links")
original_generate=claude_cli.start_generate
requests=[]
claude_cli.start_generate=lambda context,**kw: requests.append(kw)
studio.dispatch("work_note",dict(id=render_note["id"]))
check(requests.pop()["note_id"]==render_note["id"],"agent request carries note identity")
for _ in range(3): studio.dispatch("review_render",dict(job=item["id"]))
try: studio.dispatch("review_render",dict(job=item["id"]))
except ValueError: check(len(requests)==3 and requests[0]["review_images"],"critique includes captured image and caps at three passes")
else: raise AssertionError("uncapped critique")
claude_cli.start_generate=original_generate
addon.unregister()
if srv: check(not srv.connection_file.exists(),"local token removed on shutdown")
print(f"All {checks} studio checks passed on Blender {bpy.app.version_string}")
