"""Shared strict wire format, independent of Blender and providers."""
import math

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "One short line naming the change, e.g. 'Brushed aluminium on Body'"},
        "code": {"type": "string", "description": "Blender Python to stage for review, or empty if you need more information"},
        "message": {"type": "string", "description": "Technical explanation for the Details section: what you saw, which nodes, assumptions"},
        "material": {
            "type": "object",
            "description": "Summary of the main material you produced. Use empty strings / -1 for non-material changes.",
            "properties": {
                "name": {"type": "string"},
                "base_color_hex": {"type": "string", "description": "sRGB hex of the perceived base colour, e.g. #1A1A1C"},
                "roughness": {"type": "number", "description": "0-1, or -1 if not applicable"},
                "metallic": {"type": "number", "description": "0-1, or -1 if not applicable"},
                "surface": {"type": "string", "description": "Very short: grain/bump/texture, e.g. 'fine bead-blast grain, 0.2 mm'"},
                "match": {"type": "string", "enum": ["close", "approximate", "needs_texture_maps", "n/a"]},
                "limitations": {"type": "string", "description": "One short sentence on what a procedural match cannot reproduce, or empty"},
            },
            "required": ["name", "base_color_hex", "roughness", "metallic", "surface", "match", "limitations"],
            "additionalProperties": False,
        },
        "scene": {
            "type": "object",
            "description": ("Environment/Composition summary, one short phrase per field naming what you set; "
                            "empty string for anything you didn't change (and all empty in Material mode)."),
            "properties": {
                "lighting": {"type": "string", "description": "e.g. 'Large soft key upper left, 3:1 fill, cool rim'"},
                "world": {"type": "string", "description": "e.g. 'Dark grey gradient, 0.3 strength'"},
                "backdrop": {"type": "string", "description": "e.g. 'Light grey sweep, matte'"},
                "camera": {"type": "string", "description": "e.g. '85 mm, 25° above, 3/4 left'"},
                "objects": {"type": "string", "description": "e.g. 'Exploded along Z, 40 mm gaps'"},
                "render": {"type": "string", "description": "e.g. 'AgX, Medium High Contrast, -0.3 EV'"},
                "match": {"type": "string", "enum": ["close", "approximate", "needs_hdri_or_textures", "n/a"]},
                "limitations": {"type": "string", "description": "One short sentence on what can't be matched exactly, or empty"},
            },
            "required": ["lighting", "world", "backdrop", "camera", "objects", "render", "match", "limitations"],
            "additionalProperties": False,
        },
    },
    "required": ["summary", "code", "message", "material", "scene"],
    "additionalProperties": False,
}

def validate_result(value, schema=RESULT_SCHEMA, path="result"):
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(schema["properties"]):
            raise ValueError(f"{path}: expected exactly {list(schema['properties'])}")
        for key, child in schema["properties"].items():
            validate_result(value[key], child, path+"."+key)
    elif kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path}: expected text")
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
            raise ValueError(f"{path}: expected finite number")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: unknown value")
    return value
