"""Review and delivery of captured frames. Never executes a scene proposal."""
import hashlib
import json
from pathlib import Path
import shutil
import time


def artifact_folder(store, job):
    root = (store.folder/"renders").resolve()
    folder = Path(job["output"]).resolve()
    if not folder.is_relative_to(root) or folder.name != "frames":
        raise ValueError("Render artifact is outside this project's capture folder")
    return folder


def measure(store, job):
    from .render_analysis import analyze
    folder = artifact_folder(store, job)
    if not (folder/"complete.json").is_file():
        raise ValueError("Render has not completed")
    plan = json.loads((folder.parent/"plan.json").read_text(encoding="utf-8"))
    result = [analyze(folder, i+1) for i in range(len(plan["shots"]))]
    unchanged = result == job.get("qa_report")
    job["qa_report"] = result
    if not unchanged or job.get("qa") != "approved_with_visual_review":
        job["qa"] = "needs_review"
        job["status"] = "rendered_needs_qa"
    store.save()
    return result


def approve(store, job, note):
    if not isinstance(note, str) or not 10 <= len(note.strip()) <= 4000:
        raise ValueError("Record the visual review, including noise, scale, materials and motion (10–4000 characters)")
    reports = measure(store, job)
    if any(c["status"] == "fail" for r in reports for c in r["checks"]):
        raise ValueError("A measured QA failure must be resolved before delivery")
    job.update(qa="approved_with_visual_review", review_note=note.strip(), reviewed_at=time.time(),
               status="complete")
    store.save()


def pack(store, job):
    """Lossless PNG sequence, JPEG stills, contact sheet and explicit review manifest."""
    import numpy as np
    import OpenImageIO as oiio
    if job.get("qa") != "approved_with_visual_review" or job.get("status") != "complete":
        raise ValueError("Measure and approve the render QA before creating a Pack")
    folder = artifact_folder(store, job)
    plan = json.loads((folder.parent/"plan.json").read_text(encoding="utf-8"))
    frames = sorted(folder.glob("shot-*.png"))
    expected = sum(s["end"]-s["start"]+1 for s in plan["shots"])
    if len(frames) != expected:
        raise ValueError("Frame sequence is incomplete")
    destination = folder.parent/("pack-"+str(time.time_ns()))
    (destination/"frames").mkdir(parents=True)
    (destination/"stills").mkdir()
    if (folder/"preview.mp4").exists():
        shutil.copy2(folder/"preview.mp4",destination/"preview.mp4")
    manifest = dict(format_version=1, fps=plan["fps"], shots=plan["shots"],
                    width=plan["width"], height=plan["height"],
                    qa=job["qa_report"], visual_review=job["review_note"], frames=[])
    thumbs=[]
    for file in frames:
        shutil.copy2(file, destination/"frames"/file.name)
        manifest["frames"].append(dict(file="frames/"+file.name,
            sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
    for number, shot in enumerate(plan["shots"],1):
        file = folder/f"shot-{number:02d}-{shot['start']:06d}.png"
        source=oiio.ImageBuf(str(file))
        if not source.write(str(destination/"stills"/f"shot-{number:02d}.jpg")):
            raise ValueError(source.geterror())
        thumb=oiio.ImageBufAlgo.resize(source, roi=oiio.ROI(0,240,0,135,0,1,0,3))
        thumbs.append(np.asarray(thumb.get_pixels(oiio.FLOAT))[:,:,:3])
    cols=min(4,len(thumbs)); rows=(len(thumbs)+cols-1)//cols
    sheet=np.zeros((rows*135,cols*240,3),dtype=np.float32)
    for i,thumb in enumerate(thumbs):
        sheet[(i//cols)*135:(i//cols+1)*135,(i%cols)*240:(i%cols+1)*240]=thumb
    output=oiio.ImageOutput.create(str(destination/"contact-sheet.png"))
    output.open(str(destination/"contact-sheet.png"),oiio.ImageSpec(sheet.shape[1],sheet.shape[0],3,oiio.UINT8))
    output.write_image((np.clip(sheet,0,1)*255).astype(np.uint8)); output.close()
    (destination/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    (destination/"README.txt").write_text(
        "PNG frames retain the rendered view transform. JPEGs are first-frame previews.\n"
        "Contact-sheet thumbnails fit 16:9 and are for navigation, not composition review.\n"
        "preview.mp4 is included when encoded by Blender. No textures, HDRIs or source blend is bundled. Frame order and FPS are in manifest.json.\n",
        encoding="utf-8")
    job["pack"] = str(destination)
    store.save()
    return str(destination)
