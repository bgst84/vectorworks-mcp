"""PO4 door/window audit (pure Python; input from vwlib.list_openings()).

Rules (Yves, 2026-11-15): every door and window uses a plug-in style from the
project's type catalogue (styles, sizes and height references are project
specific, nothing is assumed), doors are in class DOOR_CLASS, windows in
WINDOW_CLASS (status variants -bestand / -abbruch allowed).
"""

from __future__ import annotations

from collections import Counter

DOOR_CLASS = "6 eBKP-g ausbau-tür"
WINDOW_CLASS = "6 eBKP-e fassade-fenster"
STATUS = ("-neu", "-bestand", "-abbruch")


def _class_ok(cl: str, base: str) -> bool:
    return any(cl == base + s for s in STATUS)


def audit(openings: list[dict]) -> dict:
    issues = []
    for o in openings:
        kind = "door" if "Door" in o["kind"] else "window"
        base = DOOR_CLASS if kind == "door" else WINDOW_CLASS
        problems = []
        if not _class_ok(o.get("class", ""), base):
            problems.append("class %r (expected %s-neu/-bestand/-abbruch)" % (o.get("class"), base))
        if not o.get("style"):
            problems.append("no plug-in style (type catalogue)")
        if o.get("wall_style") is None:
            problems.append("not inserted in a wall")
        if problems:
            issues.append({"uuid": o["uuid"], "kind": kind, "layer": o.get("layer"),
                           "style": o.get("style"), "problems": problems})
    by_problem = Counter(p.split(" (")[0].split(" '")[0] for i in issues for p in i["problems"])
    return {"summary": {"openings": len(openings), "with_issues": len(issues),
                        "by_problem": dict(by_problem),
                        "styles": dict(Counter(o.get("style") or "(none)" for o in openings))},
            "issues": issues}
