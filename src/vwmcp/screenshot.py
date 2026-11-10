"""Capture the Vectorworks document window as a PNG (macOS).

Vectorworks can't save its viewport to a file from a script, so this runs
outside it: list the app's windows with CGWindowListCopyWindowInfo (JXA),
pick the document window, and `screencapture -l <window id>`. That works
even when the window is covered by other apps. Needs Screen Recording
permission for the app that runs the server (usually Claude).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# kCGWindowListOptionAll = 0, kCGNullWindowID = 0
LIST_WINDOWS_JXA = """
ObjC.import('CoreGraphics');
ObjC.import('Cocoa');
var raw = $.CGWindowListCopyWindowInfo(0, 0);
var info = ObjC.deepUnwrap(ObjC.castRefToObject(raw));
var out = [];
for (var i = 0; i < info.length; i++) {
  var w = info[i];
  var owner = w.kCGWindowOwnerName || '';
  if (owner.indexOf('Vectorworks') >= 0 && w.kCGWindowLayer === 0) {
    out.push({id: w.kCGWindowNumber, title: w.kCGWindowName || '',
              bounds: w.kCGWindowBounds || {}, onscreen: !!w.kCGWindowIsOnscreen});
  }
}
JSON.stringify(out);
"""


class ScreenshotError(RuntimeError):
    pass


def _area(w: dict) -> float:
    b = w.get("bounds") or {}
    return float(b.get("Width", 0)) * float(b.get("Height", 0))


def pick_window(windows: list[dict], document: str | None) -> dict:
    """The window showing `document`, else the largest on-screen window."""
    if not windows:
        raise ScreenshotError("No Vectorworks window found. Is Vectorworks open with a document?")
    if document:
        stem = document.rsplit(".", 1)[0]
        titled = [w for w in windows if w.get("title") and (
            w["title"] == document or w["title"].startswith(stem))]
        if titled:
            return max(titled, key=_area)
    candidates = [w for w in windows if w.get("onscreen")] or windows
    best = max(candidates, key=_area)
    if _area(best) < 200 * 200:
        raise ScreenshotError("Only small Vectorworks windows found (palettes); no document window.")
    return best


def list_windows() -> list[dict]:
    res = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", LIST_WINDOWS_JXA],
        capture_output=True, text=True, timeout=15,
    )
    if res.returncode != 0:
        raise ScreenshotError(f"Listing windows failed: {res.stderr.strip()}")
    return json.loads(res.stdout or "[]")


def capture(document: str | None = None, max_size: int = 1600) -> tuple[bytes, dict]:
    """PNG bytes of the document window, downscaled so the long side is at
    most max_size px (0 = full resolution), plus info about the window."""
    if sys.platform != "darwin":
        raise ScreenshotError("vw_screenshot is only available on macOS.")
    window = pick_window(list_windows(), document)
    with tempfile.TemporaryDirectory(prefix="vwmcp-shot-") as tmp:
        out = Path(tmp) / "window.png"
        res = subprocess.run(
            ["screencapture", "-x", "-o", f"-l{window['id']}", "-t", "png", str(out)],
            capture_output=True, text=True, timeout=30,
        )
        if res.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            raise ScreenshotError(
                "screencapture failed. Allow Screen Recording for Claude in System "
                "Settings > Privacy & Security > Screen Recording, then restart Claude. "
                f"({res.stderr.strip()})"
            )
        if max_size:
            subprocess.run(["sips", "-Z", str(max_size), str(out)], capture_output=True, timeout=30)
        data = out.read_bytes()
    return data, {"window_id": window["id"], "title": window.get("title", ""),
                  "bounds": window.get("bounds", {})}
