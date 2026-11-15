"""PO4 wall style audit (pure Python; input from vwlib.wall_styles()).

Checks every wall style against PO4 rules (docs/po4-3d.md):
- Data tab: mark (Bezeichnung) and fire rating set; exterior / load bearing /
  firewall flags agree with what the name says;
- components: every layer has a class, preferably a material class
  ("3 material-...") or a facade class ("6 eBKP-e fassade-..."); class
  matches the material named in the component; component function set;
- components are butt-joined ("Schichten gestossen verbinden"), except
  applied layers (Putz, Anstrich, ...);
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

APPLIED_KEYWORDS = ("putz", "anstrich", "farbe", "spachtel", "abrieb", "beschichtung", "lasur")

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
        if "auto_join" in c:
            applied = any(k in cname for k in APPLIED_KEYWORDS)
            if applied and c["auto_join"]:
                issues.append(_issue("warning", "Applied layer is butt-joined (Schichten gestossen verbinden).", label))
            elif not applied and not c["auto_join"]:
                issues.append(_issue("warning", "Not butt-joined (Schichten gestossen verbinden is off).", label))
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


# ---- plan fixes (vw_wall_style_apply) -------------------------------------------

INSULATION_KEYWORDS = ("dämm", "xps", "eps", "mineralwolle", "steinwolle", "glaswolle", "foamglas", "pir")
AIR_KEYWORDS = ("hinterlüft", "luftschicht", "luftraum")
FUNC_LOAD_BEARING, FUNC_INSULATION, FUNC_FINISH_IN, FUNC_FINISH_OUT, FUNC_AIR = 1, 2, 3, 4, 5
FUNC_NAMES = {1: "tragend", 2: "Dämmung", 3: "Innenbekleidung", 4: "Aussenbekleidung", 5: "Luftschicht"}


def _infer_function(i, n, comp, style_exterior, style_load_bearing, core):
    name = (comp.get("name") or "").lower()
    if any(k in name for k in AIR_KEYWORDS):
        return FUNC_AIR
    if any(k in name for k in INSULATION_KEYWORDS):
        return FUNC_INSULATION
    if style_load_bearing and core and i == core:
        return FUNC_LOAD_BEARING
    if n > 1 and i == 1:
        return FUNC_FINISH_OUT if style_exterior else FUNC_FINISH_IN
    if n > 1 and i == n:
        return FUNC_FINISH_IN
    return None


def plan_style(style: dict) -> dict:
    """Changes that make a style agree with its name and the PO4 rules.
    Never overwrites a set component function or the fire rating."""
    name, data = style["name"], style.get("data", {})
    change = {"style": name, "data": {}, "components": [], "notes": []}
    if NAME_PATTERN.match(name):
        code = name.split()[0]
        if data.get("mark") != code:
            change["data"]["mark"] = code
            change["notes"].append("Bezeichnung %r -> %r" % (data.get("mark", ""), code))
    said = _name_says(name)
    for key, label in (("exterior", "Aussen"), ("load_bearing", "Tragend"), ("firewall", "Brandmauer")):
        if key in said and bool(data.get(key)) != said[key]:
            change["data"][key] = said[key]
            change["notes"].append("%s %s" % (label, "an" if said[key] else "aus"))
    exterior = change["data"].get("exterior", data.get("exterior"))
    load_bearing = change["data"].get("load_bearing", data.get("load_bearing"))
    comps = style.get("components", [])
    for i, c in enumerate(comps, 1):
        fix = {}
        if not c.get("function"):
            fn = _infer_function(i, len(comps), c, exterior, load_bearing, style.get("core"))
            if fn:
                fix["function"] = fn
        if "auto_join" in c:
            want = not any(k in (c.get("name") or "").lower() for k in APPLIED_KEYWORDS)
            if bool(c["auto_join"]) != want:
                fix["auto_join"] = want
        if fix:
            fix["index"] = i
            change["components"].append(fix)
            bits = []
            if "function" in fix:
                bits.append("Funktion %s" % FUNC_NAMES[fix["function"]])
            if "auto_join" in fix:
                bits.append("gestossen %s" % ("an" if fix["auto_join"] else "aus"))
            change["notes"].append("Schicht %d %s: %s" % (i, c.get("name") or "", ", ".join(bits)))
    if not data.get("fire_rating"):
        change["notes"].append("Feuerwiderstand fehlt (bitte selbst eintragen)")
    return change


def plan(styles: list[dict], only: list[str] | None = None) -> list[dict]:
    out = []
    for st in styles:
        if st["name"].startswith(SKIP_STYLES) or (only and st["name"] not in only):
            continue
        ch = plan_style(st)
        if ch["data"] or ch["components"]:
            out.append(ch)
    return out
