"""Reference images from the clipboard or from the companion page, saved as files beside the project.

Blender's Python has no call that returns a clipboard image as a file, so the operating system's own tools
read it: PowerShell on Windows, osascript on macOS, wl-paste or xclip on Linux. Nothing is installed and
nothing leaves the computer. Only the Windows path has been run for real; see the README.
"""

import base64
import os
import subprocess
import sys
import time

MAX_IMAGE_BYTES = 8_000_000
_PNG, _JPEG = b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff"

# Saves a clipboard bitmap as PNG, or lists copied image files (for example from Explorer).
_WINDOWS = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$image = [System.Windows.Forms.Clipboard]::GetImage()
if ($image) {
    $image.Save($args[0], [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output 'C2B_IMAGE'
} elseif ([System.Windows.Forms.Clipboard]::ContainsFileDropList()) {
    foreach ($f in [System.Windows.Forms.Clipboard]::GetFileDropList()) { Write-Output ('C2B_FILE ' + $f) }
} else {
    Write-Output 'C2B_NONE'
}
"""

_MAC = """
try
    set png to the clipboard as «class PNGf»
on error
    return "C2B_NONE"
end try
set f to open for access POSIX file (item 1 of argv) with write permission
set eof f to 0
write png to f
close access f
return "C2B_IMAGE"
"""


def folder_for(store_folder):
    path = os.path.join(str(store_folder), "references")
    os.makedirs(path, exist_ok=True)
    return path


def new_name(folder, stem="pasted", ext=".png"):
    base = f"{stem}-{time.strftime('%Y%m%d-%H%M%S')}"
    path, n = os.path.join(folder, base + ext), 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, f"{base}-{n}{ext}")
    return path


def _run(argv, timeout=15, stdin=None):
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    return subprocess.run(argv, capture_output=True, timeout=timeout, input=stdin, **flags)


def read_clipboard(folder, image_extensions=(".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
    """Returns (paths, message). paths: image files now usable as references (a new PNG in `folder`, or
    image files that were copied in a file manager). message says why when there are none."""
    target = new_name(folder)
    try:
        if os.name == "nt":
            out = _run(["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass",
                        "-Command", "& {" + _WINDOWS + "} '" + target.replace("'", "''") + "'"])
            lines = out.stdout.decode("utf-8", "replace").splitlines()
            if any(l.strip() == "C2B_IMAGE" for l in lines):
                return _checked([target])
            files = [l[9:].strip() for l in lines if l.startswith("C2B_FILE ")]
            files = [f for f in files if f.lower().endswith(image_extensions) and os.path.isfile(f)]
            if files:
                return files, ""
            if any(l.strip() == "C2B_NONE" for l in lines):
                return [], "No image on the clipboard. Copy an image or a screenshot first"
            return [], "Could not read the clipboard: " + (out.stderr.decode("utf-8", "replace").strip()[:200] or "no answer")
        if sys.platform == "darwin":
            out = _run(["osascript", "-", target], stdin=_MAC.encode("utf-8"))
            if b"C2B_IMAGE" in out.stdout:
                return _checked([target])
            return [], "No image on the clipboard. Copy an image or a screenshot first"
        for argv in (["wl-paste", "--type", "image/png"], ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"]):
            try:
                out = _run(argv)
            except FileNotFoundError:
                continue
            if out.returncode == 0 and out.stdout.startswith(_PNG):
                with open(target, "wb") as fh:
                    fh.write(out.stdout)
                return _checked([target])
        return [], "No image on the clipboard (needs wl-paste or xclip on Linux)"
    except subprocess.TimeoutExpired:
        return [], "Reading the clipboard took too long"
    except OSError as exc:
        return [], f"Could not read the clipboard: {exc}"


def _checked(paths):
    good = []
    for path in paths:
        try:
            with open(path, "rb") as fh:
                head = fh.read(8)
            if head.startswith(_PNG) and 0 < os.path.getsize(path):
                good.append(path)
            else:
                os.remove(path)
        except OSError:
            pass
    return (good, "") if good else ([], "The clipboard image could not be saved")


def save_upload(folder, data_b64, name=""):
    """An image pasted on the companion page (base64 PNG or JPEG). Returns the saved path."""
    if not isinstance(data_b64, str) or len(data_b64) > MAX_IMAGE_BYTES * 4 // 3 + 8:
        raise ValueError("Image is missing or larger than 8 MB")
    try:
        raw = base64.b64decode(data_b64, validate=True)
    except Exception:
        raise ValueError("Image data is not valid base64") from None
    if raw.startswith(_PNG):
        ext = ".png"
    elif raw.startswith(_JPEG):
        ext = ".jpg"
    else:
        raise ValueError("Only PNG and JPEG images can be pasted")
    stem = "".join(c for c in os.path.splitext(os.path.basename(str(name or "")))[0] if c.isalnum() or c in "-_")[:40]
    path = new_name(folder, stem or "pasted", ext)
    with open(path, "wb") as fh:
        fh.write(raw)
    return path
