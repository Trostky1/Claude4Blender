"""Measured checks, with unmeasured aesthetic questions kept explicit."""
import math


def image_metrics(rgb, mask=None, second=None):
    import numpy as np
    rgb = np.asarray(rgb, dtype=float)
    if rgb.ndim != 3 or rgb.shape[2] < 3 or not np.isfinite(rgb).all():
        raise ValueError("Image must contain finite H x W x RGB pixels")
    rgb = rgb[:, :, :3]
    luma = rgb @ np.array([.2126, .7152, .0722])
    mask = np.ones(luma.shape, bool) if mask is None else np.asarray(mask, dtype=bool)
    if mask.shape != luma.shape or not mask.any():
        raise ValueError("Product mask is missing or empty")
    values = luma[mask]
    yy, xx = np.nonzero(mask)
    h, w = mask.shape
    result = dict(luminance_percentiles=np.percentile(values, [1, 5, 50, 95, 99]).tolist(),
                  clipped_highlights=float(np.mean(np.any(rgb[mask] >= .995, axis=-1))),
                  crushed_blacks=float(np.mean(values <= .005)),
                  fill_fraction=float(mask.mean()),
                  center=[float(xx.mean()/w), float(yy.mean()/h)],
                  margins=[float(xx.min()/w), float(yy.min()/h), float((w-1-xx.max())/w), float((h-1-yy.max())/h)],
                  background_profile=[float(luma[y][~mask[y]].mean()) if (~mask[y]).any() else None for y in np.linspace(0,h-1,8,dtype=int)],
                  noise_rms=None)
    if second is not None:
        second = np.asarray(second, dtype=float)
        if second.shape != rgb.shape or not np.isfinite(second).all():
            raise ValueError("Noise pair must match dimensions and contain finite values")
        result["noise_rms"] = float(np.sqrt(np.mean((rgb[mask]-second[mask])**2)/2))
    return result


def image_gate(metrics, highlight_limit=.02, noise_limit=.015):
    checks = []
    def add(name, status, value, reason):
        checks.append(dict(check=name, status=status, value=value, reason=reason))
    add("product_highlights", "review" if metrics["clipped_highlights"] > highlight_limit else "pass",
        metrics["clipped_highlights"], "Display-space clipping; specular pinpoints may be intentional")
    add("framing", "review" if min(metrics["margins"]) <= 0 else "pass", metrics["margins"], "Product touching border needs intent review")
    add("noise", "review" if metrics["noise_rms"] is None else ("fail" if metrics["noise_rms"] > noise_limit else "pass"),
        metrics["noise_rms"], "Requires independent same-scene noisy renders; single-frame variance is not noise")
    for name in ("edge_softness", "material_believability", "set_and_brand_fit", "animation_continuity"):
        add(name, "review", None, "Human visual review required")
    return checks


def scene_gate(scene):
    checks = []
    def add(name, ok, reason):
        checks.append(dict(check=name, status="pass" if ok else "fail", reason=reason))
    add("camera", scene.camera is not None, "An active scene camera is required")
    add("units", math.isfinite(scene.unit_settings.scale_length) and scene.unit_settings.scale_length > 0,
        "Positive finite scene scale required; verify the product's real dimensions manually")
    objects = [o for o in scene.objects if o.type == "MESH" and not o.hide_render]
    add("visible_geometry", bool(objects), "No visible mesh product/set")
    add("finite_dimensions", all(all(math.isfinite(v) and v >= 0 for v in o.dimensions) for o in objects), "Invalid dimensions")
    checks.append(dict(check="real_world_scale", status="review", reason="Compare dimensions to the actual product"))
    return checks


def lightpaint_position(point, normal, camera, distance):
    from mathutils import Vector
    p, n, c = Vector(point), Vector(normal), Vector(camera)
    if distance <= 0 or n.length < 1e-8 or (c-p).length < 1e-8:
        raise ValueError("Need a normal, distinct camera position and positive distance")
    n.normalize()
    v = (c-p).normalized()
    if n.dot(v) <= 0:
        raise ValueError("Pinned surface faces away from the camera")
    return p+(2*n.dot(v)*n-v)*distance
