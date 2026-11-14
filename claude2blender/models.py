"""Which model each backend runs. The list lives in models.json so it can change without a code release.

A choice is "default" (let the CLI decide), a model id from models.json, or "custom" (the free-text name in
Preferences). No bpy here, so it can be tested and used from the companion page.
"""

import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json")
DEFAULT, CUSTOM = "default", "custom"

try:
    with open(_PATH, encoding="utf-8") as _fh:
        CATALOG = json.load(_fh)
except (OSError, ValueError):
    CATALOG = {}


def presets(backend):
    """[(id, label, note)] from models.json for one backend."""
    out = []
    for entry in CATALOG.get(backend, []):
        if isinstance(entry, dict) and entry.get("id") and entry["id"] not in (DEFAULT, CUSTOM):
            out.append((str(entry["id"]), str(entry.get("label") or entry["id"]), str(entry.get("note") or "")))
    return out


def items(backend):
    """EnumProperty items: CLI default, the presets, then Custom."""
    out = [(DEFAULT, "CLI default", "Let the CLI choose (its own default model)")]
    out += [(mid, label, note or mid) for mid, label, note in presets(backend)]
    out.append((CUSTOM, "Custom…", "Any other model name, typed below"))
    return out


def choices(backend):
    return [i[0] for i in items(backend)]


def _get(prefs, name, default=""):
    return getattr(prefs, name, default) if prefs is not None else default


def choice(prefs, backend):
    value = _get(prefs, backend + "_model_choice", DEFAULT) or DEFAULT
    return value if value in choices(backend) else DEFAULT


def migrate(prefs):
    """Before 0.8 the model was only a text field: a name typed there becomes the Custom choice, once."""
    if prefs is None or _get(prefs, "model_migrated", True):
        return
    for backend in CATALOG or ("claude", "codex"):
        text = (_get(prefs, backend + "_model") or (_get(prefs, "model") if backend == "claude" else "")).strip()
        if text and _get(prefs, backend + "_model_choice", DEFAULT) == DEFAULT:
            known = [mid for mid, _l, _n in presets(backend)]
            setattr(prefs, backend + "_model_choice", text if text in known else CUSTOM)
            if text not in known:
                setattr(prefs, backend + "_model", text)
    prefs.model_migrated = True


def resolve(prefs, backend):
    """The value for the CLI's --model flag ('' means: don't pass the flag)."""
    picked = choice(prefs, backend)
    if picked == DEFAULT:
        return ""
    if picked == CUSTOM:
        return _get(prefs, backend + "_model").strip()
    return picked


def label(prefs, backend):
    """Short name for the panel and for each chat turn."""
    picked = choice(prefs, backend)
    if picked == DEFAULT:
        return "CLI default"
    if picked == CUSTOM:
        return _get(prefs, backend + "_model").strip() or "Custom (no name typed)"
    return next((lab for mid, lab, _n in presets(backend) if mid == picked), picked)


def problem(prefs, backend):
    """Why this choice can't be sent, or ''."""
    if choice(prefs, backend) == CUSTOM and not _get(prefs, backend + "_model").strip():
        return "Type a model name next to Custom, or pick another model"
    return ""


REJECT_HINTS = ("not found", "not_found", "invalid model", "unknown model", "does not exist", "not available",
                "not supported", "no access", "do not have access", "don't have access", "issue with the selected model",
                "may not exist", "model_not_found")


def rejected(text, model):
    """True when a backend error reads like 'that model name was not accepted'."""
    low = (text or "").lower()
    return bool(model) and "model" in low and any(h in low for h in REJECT_HINTS)
