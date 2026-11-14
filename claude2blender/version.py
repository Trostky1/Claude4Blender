"""Which version is running, and whether a newer one is waiting on disk.

Blender keeps an add-on's Python loaded until it is disabled or Blender restarts, so after an update the
panel can still be running old code. LOADED is read once, when this module is imported; installed() reads
the manifest on disk again, so the two differ exactly when a restart is needed.
"""

import os
import re
import time

_MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_manifest.toml")
_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _read():
    try:
        with open(_MANIFEST, encoding="utf-8") as fh:
            found = _VERSION.search(fh.read())
        return found.group(1) if found else ""
    except OSError:
        return ""


LOADED = _read() or "unknown"

_cache = (0.0, LOADED)


def installed():
    """The version in the manifest on disk right now (re-read at most every 3 seconds)."""
    global _cache
    now = time.time()
    if now - _cache[0] > 3.0:
        _cache = (now, _read() or LOADED)
    return _cache[1]


def restart_needed():
    return installed() != LOADED
