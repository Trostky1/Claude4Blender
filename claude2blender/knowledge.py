"""Original, sourced recipes. Functions produce reviewable code, never execute it."""
import math
import random

ENTRIES = {
    "material": "Use named CMF presets, real-unit grain and separate base/coat roughness. Bump changes shading, not silhouette. Inspect edge softness; do not alter CAD without permission.",
    "environment": "Shape glossy reflections with area-light size and placement before adding lights. A watt ratio is not the measured key:fill luminance ratio. Keep set, floor and lighting independently editable.",
    "composition": "Frame the selected product, then reserve intentional negative space. Camera/sensor/target distance jointly control perspective. Do not invent assembly clearances.",
}
SOURCES = {
    "material": "https://docs.blender.org/manual/en/5.0/render/shader_nodes/shader/principled.html",
    "environment": "https://broncolor.swiss/news/the-ultimate-product-photography-lighting-setup",
    "composition": "https://docs.blender.org/manual/en/5.0/render/cameras.html",
}


def recipe_code(seed=0, key_azimuth=None, elevation=None, source_size=None,
                fill_ratio=None, rim_ratio=None, floor_color="#252628", lens=85,
                camera_height=.6, include_camera=False):
    rng = random.Random(seed)
    az = key_azimuth if key_azimuth is not None else rng.uniform(-60, -20)
    elev = elevation if elevation is not None else rng.uniform(25, 65)
    size = source_size if source_size is not None else rng.uniform(.7, 2.5)
    fill = fill_ratio if fill_ratio is not None else rng.uniform(.08, .3)
    rim = rim_ratio if rim_ratio is not None else rng.uniform(.2, .6)
    if not (-90 <= az <= 90 and 10 <= elev <= 85 and .1 <= size <= 5 and 0 <= fill <= 1 and 0 <= rim <= 2 and 25 <= lens <= 200):
        raise ValueError("Recipe parameter outside supported range")
    code = f'''# Studio generator, seed {seed}; named, adjustable components.
import math
from mathutils import Vector
b = c2b.bounds(c2b.targets())
c, r = b['center'], max(b['radius'], .001)
cam = bpy.context.scene.camera
front = (cam.matrix_world.translation-c) if cam else Vector((0,-1,0))
front.z = 0
front.normalize()
right = front.cross(Vector((0,0,1))).normalized()
a, e = math.radians({az!r}), math.radians({elev!r})
direction = front*math.cos(a)*math.cos(e)+right*math.sin(a)*math.cos(e)+Vector((0,0,math.sin(e)))
watts = 30*(r/.15)**2
c2b.light('C2B Recipe Key', location=c+direction*r*4, target=c, energy=watts, size=r*{size!r}, shape='RECTANGLE', size_y=r*{size*1.5!r})
c2b.light('C2B Recipe Fill', location=c+(front+right)*r*3, target=c, energy=watts*{fill!r}, size=r*2)
c2b.light('C2B Recipe Rim', location=c+(-front+Vector((0,0,1)))*r*3, target=c, energy=watts*{rim!r}, size=r)
c2b.studio_world(top='#111216', strength=.12)
c2b.backdrop('C2B Recipe Floor', kind='floor', width=r*20, depth=r*20, location=(c.x,c.y,b['min'].z), color={floor_color!r}, roughness=.28)
'''
    if include_camera:
        code += f"c2b.camera('C2B Recipe Camera', location=c+front*r*6+Vector((0,0,r*{camera_height!r})), target=c, lens={lens!r}, make_active=True)\n"
    return code


def finish_code(light_factors, exposure):
    if not -5 <= exposure <= 5 or any(not math.isfinite(float(v)) or not 0 <= float(v) <= 1e9 for v in light_factors.values()):
        raise ValueError("Finish controls outside supported range")
    # Caller snapshots base energies, so repeated previews don't compound multipliers.
    lines = ["# Finishing proposal; Preview / Apply / Undo remain available."]
    for name, energy in light_factors.items():
        lines.append(f"c2b.light({name!r}, energy={float(energy)!r})")
    lines.append(f"c2b.exposure({float(exposure)!r})")
    return "\n".join(lines)
