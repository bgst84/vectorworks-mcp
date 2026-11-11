"""PO4 wall style audit (pure Python; input from vwlib.wall_styles()).

Checks every wall style against PO4 rules (docs/po4-3d.md):
- Data tab: mark (Bezeichnung) and fire rating set; exterior / load bearing /
  firewall flags agree with what the name says;
- components: every layer has a class, preferably a material class
  ("3 material-...") or a facade class ("6 eBKP-e fassade-..."); class
  matches the material named in the component; component function set;
- name: follows the catalogue pattern "W<n>[.<m>] ..." (info only).

Severity: "error" (must fix), "warning" (probably wrong), "info".
"""

from __future__ import annotations

import re

MATERIAL_PREFIXES = ("3 material-", "6 eBKP-e fassade-")

# component name keyword -> class keywords that are acceptable
MATERIAL_HINTS = {
    "hinterlüftung": ("hinterlüftung",),   # 3 material-hinterlüftung
    "beton": ("beton",),
    "kalksandstein": ("backstein",),
    "mauerwerk": ("backstein",),
    "backstein": ("backstein",),
    "gkp": ("gkp",),
    "gips": ("gkp",),
    "fermacell": ("gkp", "holzwerkstoff"),
    "xps": ("dämmung",),
    "mineralwolle": ("dämmung",),
    "dämmung": ("dämmung",),
    "foamglas": ("dämmung",),
    "bsp": ("holzwerkstoff", "massivholz"),
    "osb": ("holzwerkstoff",),
    "putz": ("verputz",),
    "blech": ("blech",),
    "keramik": ("keramik", "platten"),
    "eternit": ("fassade",),
    "fassade": ("fassade",),
}

NAME_PATTERN = re.compile(r"^W\d+(\.\d+)?\s")
SKIP_STYLES = ("<",)  # e.g. "<Raumabgrenzung>"


def _issue(sev, msg, component=None):
    d = {"severity": sev, "message": msg}
    if component is not None:
        d["component"] = component
    return d


def _name_says(name):
    n = name.lower()
    out = {}
    if "aussenwand" in n or "außenwand" in n or n.startswith("aussen"):
        out["exterior"] = True
    elif "innenwand" in n:
        out["exterior"] = False
    if "nicht tragend" in n:
        out["load_bearing"] = False
    elif "tragend" in n:          # "aussteifend" alone is NOT load-bearing
        out["load_bearing"] = True
    if "brandmauer" in n:
        out["firewall"] = True
    return out


def audit_style(style: dict) -> list[dict]:
    name = style["name"]
    data = style.get("data", {})
    issues = []

    # name
    if not NAME_PATTERN.match(name):
        issues.append(_issue("info", "Name does not follow the catalogue pattern 'W<n>.<m> ...'."))
    else:
        code = name.split()[0]
        if not data.get("mark"):
            issues.append(_issue("warning", "Data: Bezeichnung empty (expected %r)." % code))
        elif data["mark"] != code:
            issues.append(_issue("warning", "Data: Bezeichnung %r differs from the name code %r."
                                 % (data["mark"], code)))

    # data tab
    if not data.get("fire_rating"):
        issues.append(_issue("warning", "Data: Feuerwiderstand empty."))
    for key, label in (("exterior", "Aussen"), ("load_bearing", "Tragend"), ("firewall", "Brandmauer")):
        said = _name_says(name).get(key)
        if said is not None and bool(data.get(key)) != said:
            issues.append(_issue("warning", "Data: %s is %s, but the name says %s."
                                 % (label, "on" if data.get(key) else "off", "on" if said else "off")))

    # components
    comps = style.get("components", [])
    for i, c in enumerate(comps, 1):
        label = "%d %s" % (i, c.get("name") or "(unnamed)")
        cl = c.get("class", "")
        if not cl:
            issues.append(_issue("error", "No class.", label))
            continue
        if not cl.startswith(MATERIAL_PREFIXES):
            issues.append(_issue("warning", "Class %r is not a material or facade class." % cl, label))
        cname = (c.get("name") or "").lower()
        for kw, ok in MATERIAL_HINTS.items():
            if kw in cname:
                if not any(o in cl.lower() for o in ok):
                    issues.append(_issue("warning", "Named %r but class %r." % (c.get("name"), cl), label))
                break
        if not c.get("function"):
            issues.append(_issue("info", "Component function not set.", label))
    if not comps:
        issues.append(_issue("error", "Style has no components."))
    return issues


def audit(styles: list[dict], only: list[str] | None = None, skip_info: bool = False) -> dict:
    """Audit report: {styles: {name: [issues]}, summary: {...}}. Styles
    without issues are listed in `clean`."""
    report, clean = {}, []
    counts = {"error": 0, "warning": 0, "info": 0}
    for st in styles:
        name = st["name"]
        if name.startswith(SKIP_STYLES) or (only and name not in only):
            continue
        issues = audit_style(st)
        if skip_info:
            issues = [i for i in issues if i["severity"] != "info"]
        for i in issues:
            counts[i["severity"]] += 1
        if issues:
            report[name] = issues
        else:
            clean.append(name)
    return {"summary": {"styles": len(report) + len(clean), "with_issues": len(report), **counts},
            "styles": report, "clean": clean}
