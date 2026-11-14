"""Versioned sidecar data. Loading never executes proposals or restores scene data."""
import copy
import json
import os
from pathlib import Path
import time
import uuid
from contextlib import contextmanager


@contextmanager
def exclusive(folder):
    """Cross-process save lock; a second Blender cannot silently replace state."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder/"state.lock").open("a+b") as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"0"); lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def empty_state():
    return dict(schema_version=1, project_id=uuid.uuid4().hex, revision=0,
                conversation=[], notes=[], storyboard=[], proposals=[], history=[],
                render_queue=[], approved_revision=None, storyboard_revision=0)


class Store:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.data = empty_state()
        self.load_error = ""
        path = self.folder/"state.json"
        if path.exists():
            try:
                if path.stat().st_size > 16_000_000:
                    raise ValueError("Sidecar exceeds 16 MB")
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Sidecar must be an object")
                if data.get("schema_version") != 1:
                    raise ValueError("Unsupported sidecar version")
                for key in ("conversation", "notes", "storyboard", "proposals", "history", "render_queue"):
                    if not isinstance(data.get(key), list):
                        raise ValueError("Invalid sidecar field: "+key)
                    if any(not isinstance(item, dict) for item in data[key]):
                        raise ValueError("Invalid sidecar record: "+key)
                for key in ("revision", "storyboard_revision"):
                    if type(data.get(key)) is not int or data[key] < 0:
                        raise ValueError("Invalid revision")
                for note in data["notes"]:
                    if not all(isinstance(note.get(k), str) for k in ("id", "text", "object", "status")) or len(note.get("local_position", [])) != 3:
                        raise ValueError("Invalid note")
                for turn in data["conversation"]:
                    if not all(isinstance(turn.get(k), str) for k in ("role", "text", "backend")):
                        raise ValueError("Invalid conversation")
                self.data.update(data)
            except (ValueError, OSError, TypeError, KeyError) as exc:
                self.load_error = str(exc)
        self.saved_revision = self.data["revision"]

    def save(self):
        if self.load_error:
            raise RuntimeError("Sidecar is read-only after load error: "+self.load_error)
        with exclusive(self.folder):
            self._save_locked()

    def _save_locked(self):
        target = self.folder/"state.json"
        if target.exists():
            disk = json.loads(target.read_text(encoding="utf-8"))
            if disk["revision"] != self.saved_revision:
                raise RuntimeError("Sidecar changed in another Blender instance; reopen before editing")
        self.data["revision"] = self.saved_revision+1
        temporary = self.folder/("state-"+uuid.uuid4().hex+".tmp")
        text = json.dumps(self.data, indent=2, allow_nan=False)
        with temporary.open("w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if target.exists():
            backup = self.folder/"state.previous.json"
            backup.write_bytes(target.read_bytes())
        os.replace(temporary, target)
        self.saved_revision = self.data["revision"]

    def turn(self, role, text, backend="", **extra):
        record = dict(id=uuid.uuid4().hex, time=time.time(), role=role,
                      text=text, backend=backend, **extra)
        self.data["conversation"].append(record)
        self.save()
        return record

    def context(self, max_chars=48000):
        selected, count = [], 0
        for turn in reversed(self.data["conversation"]):
            size = len(json.dumps(turn))
            if count+size > max_chars:
                break
            selected.append(copy.deepcopy(turn))
            count += size
        return list(reversed(selected))


_store = None
_key = None
_unsaved_id = uuid.uuid4().hex


def current():
    import bpy
    from .claude_cli import workspace_dir
    global _store, _key
    key = bpy.data.filepath
    if _store is None or key != _key:
        folder = Path(key).with_suffix(".c2b") if key else Path(workspace_dir())/"unsaved"/_unsaved_id
        _store, _key = Store(folder), key
    return _store


def reset():
    global _store, _key
    _store = _key = None


def migrate_saved():
    """Save As carries metadata; opening another file is handled separately."""
    import bpy
    global _store, _key
    key = bpy.data.filepath
    if _store is not None and key and key != _key:
        target = Store(Path(key).with_suffix(".c2b"))
        if (target.folder/"state.json").exists():
            raise RuntimeError("Destination already has a sidecar; preserved both copies")
        target.data = copy.deepcopy(_store.data)
        target.data["revision"] = 0
        target.saved_revision = 0
        target.save()
        _store, _key = target, key
