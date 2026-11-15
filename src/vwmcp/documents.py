"""List the open Vectorworks documents and bring one to the front (macOS).

The vs.* API has no call to list open documents or to activate one, and
switching documents while a script runs is not safe. Vectorworks lists every
open document in its Window menu, with a check mark at the active one, so
this module reads and clicks that menu from outside through System Events
(macOS Accessibility). Needs Accessibility permission for the app that runs
the server (usually Claude); macOS asks on first use.

The Window menu also holds commands (palettes, tabs, ...). The documents are
the group between two separators that holds the check-marked active
document.
"""

from __future__ import annotations

import subprocess
import sys

BUNDLE_ID = "net.nemetschek.vectorworks"
WINDOW_MENU_TITLES = ("Window", "Fenster", "Fenêtre", "Finestra", "Ventana", "Venster")
SEPARATOR = "---"

_PROLOGUE = f'''
on windowMenu(p)
  tell application "System Events"
    repeat with mbi in menu bar items of menu bar 1 of p
      if {{{", ".join('"%s"' % t for t in WINDOW_MENU_TITLES)}}} contains (name of mbi as text) then return menu 1 of mbi
    end repeat
  end tell
  error "No Window menu found in Vectorworks."
end windowMenu

on vwProcess()
  tell application "System Events"
    set ps to (every application process whose bundle identifier is "{BUNDLE_ID}")
    if ps is {{}} then error "Vectorworks is not running."
    return item 1 of ps
  end tell
end vwProcess
'''

LIST_SCRIPT = _PROLOGUE + '''
on run argv
  set p to my vwProcess()
  tell application "System Events"
    set m to my windowMenu(p)
    set out to ""
    repeat with mi in menu items of m
      set n to name of mi
      if n is missing value then
        set out to out & "---" & linefeed
      else
        set mk to ""
        try
          set mk to value of attribute "AXMenuItemMarkChar" of mi
        end try
        if mk is missing value then set mk to ""
        set en to "1"
        try
          if not (enabled of mi) then set en to "0"
        end try
        set sm to "0"
        try
          if exists menu 1 of mi then set sm to "1"
        end try
        set out to out & n & tab & mk & tab & en & tab & sm & linefeed
      end if
    end repeat
  end tell
  return out
end run
'''

CLICK_SCRIPT = _PROLOGUE + '''
on run argv
  set target to item 1 of argv
  set p to my vwProcess()
  tell application "System Events"
    set m to my windowMenu(p)
    click (first menu item of m whose name is target)
  end tell
  return "ok"
end run
'''


class DocumentsError(RuntimeError):
    pass


def parse_menu(text: str) -> list[dict]:
    """Window menu dump -> [{"name", "marked", "enabled", "submenu"} | {"separator": True}]."""
    items = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.strip() == SEPARATOR:
            items.append({"separator": True})
            continue
        parts = line.split("\t")
        name = parts[0]
        mark = parts[1] if len(parts) > 1 else ""
        enabled = (parts[2] if len(parts) > 2 else "1") != "0"
        submenu = (parts[3] if len(parts) > 3 else "0") == "1"
        items.append({"name": name, "marked": bool(mark.strip()), "enabled": enabled, "submenu": submenu})
    return items


def documents_from_menu(items: list[dict]) -> dict:
    """The document group: the separator-delimited group with a check mark
    whose items are not all commands. Returns {"documents": [...], "active": name}."""
    groups, cur = [], []
    for it in items:
        if it.get("separator"):
            if cur:
                groups.append(cur)
            cur = []
        else:
            cur.append(it)
    if cur:
        groups.append(cur)
    marked = [g for g in groups if any(i["marked"] for i in g)]
    if not marked:
        raise DocumentsError("No active document marked in the Window menu (is a document open?).")
    # Several groups can carry check marks (e.g. "Show Document Tabs"); the
    # document group is the last one: Vectorworks lists documents at the end.
    group = marked[-1]
    active = next(i["name"] for i in group if i["marked"])
    return {"documents": [i["name"] for i in group if not i.get("submenu")], "active": active}


def _osascript(script: str, *args: str) -> str:
    if sys.platform != "darwin":
        raise DocumentsError("Switching documents is only available on macOS.")
    res = subprocess.run(["osascript", "-", *args], input=script, capture_output=True, text=True, timeout=20)
    if res.returncode != 0:
        err = res.stderr.strip()
        if "-1719" in err or "-25211" in err or "assistive" in err.lower() or "not allowed" in err.lower():
            err += ("\nGive Claude Accessibility permission: System Settings > Privacy & Security > "
                    "Accessibility, then try again.")
        raise DocumentsError(err or "osascript failed")
    return res.stdout


def list_documents() -> dict:
    return documents_from_menu(parse_menu(_osascript(LIST_SCRIPT)))


def switch_document(name: str) -> dict:
    """Bring the open document `name` to the front; verified by re-reading
    the check mark. A name without extension matches "<name>.vwx"."""
    before = list_documents()
    docs = before["documents"]
    target = name if name in docs else next((d for d in docs if d.rsplit(".", 1)[0] == name), None)
    if target is None:
        raise DocumentsError(f"{name!r} is not open. Open documents: {', '.join(docs)}")
    if before["active"] == target:
        return {"active": target, "switched": False, "documents": docs}
    _osascript(CLICK_SCRIPT, target)
    after = list_documents()
    if after["active"] != target:
        raise DocumentsError(f"Clicked {target!r} in the Window menu, but {after['active']!r} is still "
                             "active. Is a dialog open in Vectorworks?")
    return {"active": target, "switched": True, "previous": before["active"], "documents": after["documents"]}
