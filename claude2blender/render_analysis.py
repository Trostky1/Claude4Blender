"""Read only our explicitly selected render artifacts, with exact index-pass picking."""
import json
from pathlib import Path


def channels(path):
    import numpy as np
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(str(path))
    if inp is None:
        raise ValueError("Could not open render passes")
    result = {}
    try:
        sub = 0
        while inp.seek_subimage(sub, 0):
            spec = inp.spec()
            pixels = np.asarray(inp.read_image(sub, 0, 0, spec.nchannels, oiio.FLOAT)).reshape(spec.height, spec.width, spec.nchannels)
            result.update({name: pixels[:,:,i] for i,name in enumerate(spec.channelnames)})
            sub += 1
    finally:
        inp.close()
    return result


def pick_object(folder, shot, u, v):
    if type(shot) is not int or not 1 <= shot <= 20 or not 0 <= u < 1 or not 0 <= v < 1:
        raise ValueError("Pixel outside the rendered image")
    data = channels(Path(folder)/f"shot-{shot:02d}-passes.exr")
    index = next((value for name,value in data.items() if "IndexOB" in name or "Object Index" in name), None)
    if index is None:
        raise ValueError("Object-index pass unavailable")
    h,w = index.shape
    value = int(round(float(index[int(v*h), int(u*w)])))
    names = json.loads((Path(folder)/"objects.json").read_text())
    if value == 0 or str(value) not in names:
        raise ValueError("Background pixel; choose the product")
    return names[str(value)]


def relight(path, multipliers, exposure=0):
    """Linear light-group sum, for an approximate Finish preview before rerender."""
    import numpy as np
    data = channels(path)
    bases = [n[:-2] for n in data if ".Combined_" in n and n.endswith(".R")]
    if not bases:
        raise ValueError("No light groups in capture")
    result = None
    for base in bases:
        name = base.split(".Combined_",1)[1]
        factor = float(multipliers.get(name, 1))
        if not 0 <= factor <= 8:
            raise ValueError("Light multiplier must be between 0 and 8")
        rgb = np.stack([data[base+"."+c] for c in "RGB"],axis=-1)*factor
        result = rgb if result is None else result+rgb
    return result*(2**exposure)


def analyze(folder, shot):
    import numpy as np
    import OpenImageIO as oiio
    from .quality import image_metrics, image_gate
    folder = Path(folder)
    png = next(iter(sorted(folder.glob(f"shot-{shot:02d}-*.png"))), None)
    if png is None:
        raise ValueError("Rendered frame missing")
    inp = oiio.ImageInput.open(str(png))
    spec = inp.spec()
    pixels = np.asarray(inp.read_image(0,0,0,spec.nchannels,oiio.FLOAT)).reshape(spec.height,spec.width,spec.nchannels)[:,:,:3]
    inp.close()
    data = channels(folder/f"shot-{shot:02d}-passes.exr")
    indices = next((v for k,v in data.items() if "IndexOB" in k or "Object Index" in k), None)
    if indices is None:
        raise ValueError("Object mask missing")
    targets = json.loads((folder/"targets.json").read_text())
    names = json.loads((folder/"objects.json").read_text())
    ids = [int(k) for k,v in names.items() if v in targets]
    if not ids:
        raise ValueError("No selected product in capture; select the product before rendering")
    metrics = image_metrics(pixels, np.isin(np.rint(indices).astype(int),ids))
    return dict(scope=targets, metrics=metrics, checks=image_gate(metrics))
