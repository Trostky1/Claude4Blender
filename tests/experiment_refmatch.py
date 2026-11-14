"""Controlled A/B/C/D evaluation; real backend failures are recorded, never substituted.

blender --background --factory-startup --python tests/experiment_refmatch.py -- prepare
blender --background --factory-startup --python tests/experiment_refmatch.py -- evaluate
All outputs under ignored tests/out/vision-experiment. No image generator or user blend.
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bpy
import numpy as np
import OpenImageIO as oiio
from mathutils import Vector
import claude2blender as addon
from claude2blender import claude_cli, refmatch, scene_tools
from claude2blender.backends import BACKENDS

OUT=ROOT/'tests/out/vision-experiment'
OUT.mkdir(parents=True,exist_ok=True)

def write_png(path,linear):
    rgb=np.clip(np.where(linear<=.0031308,linear*12.92,1.055*np.maximum(linear,0)**(1/2.4)-.055),0,1)
    image=oiio.ImageOutput.create(str(path));image.open(str(path),oiio.ImageSpec(rgb.shape[1],rgb.shape[0],3,oiio.UINT8))
    image.write_image((rgb*255).astype(np.uint8));image.close()

def prepare():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=.1,location=(0,0,.05));body=bpy.context.object;body.name='Product'
    bevel=body.modifiers.new('Manufactured edge','BEVEL');bevel.width=.003;bevel.segments=3
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.035,location=(.07,0,.035));knob=bpy.context.object;knob.name='Knob'
    bpy.ops.object.shade_smooth()
    for obj in (body,knob):
        mat=bpy.data.materials.new(obj.name+' neutral');mat.diffuse_color=(.5,.5,.5,1);mat.use_nodes=True
        mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.5,.5,.5,1)
        mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.28
        obj.data.materials.append(mat)
    bpy.ops.mesh.primitive_plane_add(size=3);floor=bpy.context.object;floor.name='Floor'
    floor.hide_render=True  # Plain environment background: segmentation is not the confound in this fixture.
    mat=bpy.data.materials.new('Floor neutral');mat.diffuse_color=(.15,.15,.15,1);floor.data.materials.append(mat)
    cam=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));bpy.context.scene.collection.objects.link(cam)
    cam.location=(.3,-.5,.22);cam.data.lens=60;bpy.context.scene.camera=cam
    bpy.context.view_layer.update();scene_tools.look_at(cam,(.02,0,.04))
    bpy.context.scene.render.resolution_x=240;bpy.context.scene.render.resolution_y=160
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'fixture.blend'))
    variants=[]
    for suffix,scale in [('basis',1.0),('narrow',.55),('broad',1.6)]:
        args,flags=refmatch.basis_command(str(OUT/'fixture.blend'),str(OUT/(suffix+'.exr')),['Product','Knob'],samples=256,width=240,source_scale=scale)
        with (OUT/(suffix+'.log')).open('w') as log:
            run=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=180,**flags)
        if run.returncode:raise RuntimeError('Basis render failed; inspect '+suffix+'.log')
        variants.append(refmatch.read_basis(str(OUT/(suffix+'.exr'))))
    meta=json.loads((OUT/'basis.exr.json').read_text())
    cases=[]
    for i in range(12):
        groups,mask,_=variants[i%3]
        key=f'L{[0,3,7,9,13,15,17,20,22,24,5,11][i]:02d}'
        color=np.array([(1,.72,.4),(.5,.75,1),(1,1,1)][i%3])
        weights={key:color.tolist()}
        if i%2:weights[f'L{(int(key[1:])+11)%25:02d}']=[.15,.2,.3]
        if i%3==2:weights[f'L{(int(key[1:])+5)%25:02d}']=[.12,.12,.12]
        world=[.04,.1,.18][i%3]
        image=sum(groups[k]*np.array(v) for k,v in weights.items())+groups['world']*world
        scale=.22/max(float(image[mask].mean()),1e-6)
        weights={k:(np.array(v)*scale).tolist() for k,v in weights.items()};world*=scale
        path=OUT/f'reference-{i:02d}.png';write_png(path,image*scale)
        cases.append(dict(id=i,path=str(path),key=key,weights=weights,world=world,source_scale=[1,.55,1.6][i%3]))
    (OUT/'cases.json').write_text(json.dumps(cases,indent=2))
    print('PREPARED 12 references, known directions/colors/counts/background contributions and three source sizes',flush=True)

def predict(result,groups,meta):
    image=np.zeros_like(groups['world'])
    for light in result['lights']:
        image+=groups[light['name']]*(light['energy']/meta['energy'])*np.array(light['color'])
    image+=groups['world']*result['world']['strength']*np.array(result['world']['color'])
    return image

def direction(light):
    e,a=map(math.radians,(light['elevation'],light['azimuth']))
    return np.array([math.cos(e)*math.cos(a),math.cos(e)*math.sin(a),math.sin(e)])

def score(case,result,groups,meta):
    ref=refmatch.read_image(case['path']);image=predict(result,groups,meta)
    truth=next(x for x in meta['lights'] if x['name']==case['key'])
    top=max(result['lights'],key=lambda x:x['energy']) if result['lights'] else None
    return dict(rmse=float(np.sqrt(np.mean((ref-image)**2))),
                angle_degrees=float(np.degrees(np.arccos(np.clip(direction(truth)@direction(top),-1,1)))) if top else 180,
                residuals=result.get('residuals',{}))

def ask(backend,prompt,images,tag):
    prompt += '\nReference image paths, in order (view every image):\n'+'\n'.join(images)
    cli=backend.find()
    if not cli:raise RuntimeError('CLI not found')
    folder=OUT/backend.id;folder.mkdir(exist_ok=True)
    system='You are evaluating product-lighting references. Do not execute code or use a shell. Return empty code and put the requested JSON object in message. All other schema summaries use empty strings, -1 and n/a.'
    command=backend.build_command(claude_cli.launch_command(cli),prompt,system,images,str(folder))
    env=backend.environment(os.environ)
    begin=time.monotonic()
    run=subprocess.run(command.argv,input=command.stdin,cwd=folder,env=env,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=100)
    (folder/(tag+'.jsonl')).write_text(run.stdout,encoding='utf-8')
    (folder/(tag+'.stderr')).write_text(run.stderr[-4000:],encoding='utf-8')
    output=None;error=''
    for line in run.stdout.splitlines():
        try:events=backend.stream(json.loads(line))
        except ValueError:continue
        for kind,value in events:
            if kind=='error':error=str(value)
            if kind=='result':output=value
    if run.returncode or error or output is None:raise RuntimeError(error or run.stderr[-1000:] or 'No result')
    value=backend.parse_result(output)
    return json.loads(value['message']),round(time.monotonic()-begin,2)

def evaluate():
    addon.register()
    cases=json.loads((OUT/'cases.json').read_text());groups,mask,albedo=refmatch.read_basis(str(OUT/'basis.exr'))
    meta=json.loads((OUT/'basis.exr.json').read_text());rows=[]
    catalogue=[{k:x[k] for k in ('name','azimuth','elevation')} for x in meta['lights']]
    for case in cases:
        measured=refmatch.solve(str(OUT/'basis.exr'),case['path'])
        rows.append(dict(case=case['id'],backend='measured',arm='A',**score(case,measured,groups,meta)))
    for backend in BACKENDS.values():
        failures=0
        for case in cases:
            try:
                request='Choose which basis lights explain the attached image. Return JSON in message with keys lights (1-8 names), bbox (normalized [left,top,right,bottom] or null), weights (object mapping each chosen light name to three nonnegative RGB weights), world (three nonnegative RGB weights). The weights multiply unit basis-light images; estimate rather than using hidden data. Catalogue: '+json.dumps(catalogue)
                prior,elapsed=ask(backend,request,[case['path']],f"{case['id']:02d}-prior")
                enabled=prior['lights'];bbox=prior.get('bbox')
                if bbox is not None and (len(bbox)!=4 or not 0<=bbox[0]<bbox[2]<=1 or not 0<=bbox[1]<bbox[3]<=1):raise ValueError('Invalid bbox')
                fitted=refmatch.solve(str(OUT/'basis.exr'),case['path'],bbox=bbox,enabled_lights=enabled)
                rows.append(dict(case=case['id'],backend=backend.id,arm='B',latency=elapsed,**score(case,fitted,groups,meta)))
                alone=[]
                for name,weight in prior['weights'].items():
                    if name not in groups or len(weight)!=3 or any(not math.isfinite(x) or x<0 for x in weight):raise ValueError('Invalid weights')
                    info=next(x for x in meta['lights'] if x['name']==name);peak=max(weight)
                    if peak:alone.append(dict(info,energy=peak*meta['energy'],color=(np.array(weight)/peak).tolist()))
                world=np.array(prior['world'],dtype=float)
                if world.shape!=(3,) or not np.isfinite(world).all() or (world<0).any():raise ValueError('Invalid world')
                peak=max(float(world.max()),1e-8)
                d=dict(lights=alone,world=dict(strength=peak,color=(world/peak).tolist()))
                rows.append(dict(case=case['id'],backend=backend.id,arm='D',**score(case,d,groups,meta)))
                a=refmatch.solve(str(OUT/'basis.exr'),case['path'])
                preview=OUT/f"{backend.id}-{case['id']:02d}-A.png";write_png(preview,predict(a,groups,meta))
                correction,t=ask(backend,'First image is reference, second is measured fit. Suggest one corrected light-selection/mask prior as JSON with lights and bbox. Catalogue: '+json.dumps(catalogue),[case['path'],str(preview)],f"{case['id']:02d}-correction")
                c=refmatch.solve(str(OUT/'basis.exr'),case['path'],bbox=correction.get('bbox'),enabled_lights=correction['lights'])
                rows.append(dict(case=case['id'],backend=backend.id,arm='C',latency=t,**score(case,c,groups,meta)))
                print('SCORED',backend.id,case['id'],flush=True)
            except Exception as exc:
                failures+=1;rows.append(dict(case=case['id'],backend=backend.id,error=str(exc)))
                print('FAILED',backend.id,case['id'],str(exc)[:200],flush=True)
            (OUT/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
            if failures>=2:
                print('STOPPED backend after two failures:',backend.id,flush=True);break
    addon.unregister()

if __name__=='__main__':
    mode=sys.argv[sys.argv.index('--')+1]
    prepare() if mode=='prepare' else evaluate()
