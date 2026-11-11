# PO4 class standard helpers, executed INSIDE Vectorworks after vwlib.py
# (registered as prelude "po4" in tools/po4.py). Python 3.9-compatible.
# Format matches PO4's klassen_standard.json: line weight in mm, colors 0-255,
# line/fill as "none" | "solid" | "res:<resource name>". Live findings (VW 2027):
# GetClOpacityN returns (pen, fill) despite its docstring; line types are
# negative resource indices (-Name2Index(name)); hatches via GetClVectorFill.

MIL_MM = 0.0254


def _rgb8(c):
    return [int(v) // 257 for v in c]


def _rgb16(c):
    return tuple(int(v) * 257 for v in c)


def _class_in_use(name):
    used = []
    vs.ForEachObject(used.append, "(C='%s')" % name.replace("'", "''"))
    return bool(used)


def class_names():
    return [_str(vs.ClassList(i)) for i in range(1, vs.ClassNum() + 1)]


def _class_raw(name):
    pen_op, fill_op = vs.GetClOpacityN(name)
    vf = vs.GetClVectorFill(name)
    return {"lw": vs.GetClLW(name), "ls": vs.GetClLSN(name), "fpat": vs.GetClFPat(name),
            "hatch": vf[1] if vf[0] else "",
            "pen_fore": list(vs.GetClPenFore(name)), "pen_back": list(vs.GetClPenBack(name)),
            "fill_fore": list(vs.GetClFillFore(name)), "fill_back": list(vs.GetClFillBack(name)),
            "pen_op": pen_op, "fill_op": fill_op, "use": bool(vs.GetClUseGraphic(name))}


def _line_name(ls):
    if ls == 0:
        return "none"
    if ls < 0:
        return "res:" + _str(vs.Index2Name(-ls))
    return "solid" if ls == 2 else "pattern:%d" % ls


def _fill_name(raw):
    if raw["hatch"]:
        return "res:" + raw["hatch"]
    fp = raw["fpat"]
    if fp == 0:
        return "none"
    if fp == 1:
        return "solid"
    if fp < 0:
        return "res:" + _str(vs.Index2Name(-fp))
    return "pattern:%d" % fp


def class_attrs(name):
    raw = _class_raw(name)
    return {"name": name, "automatisch_zuweisen": raw["use"],
            "strichstaerke_mm": round(raw["lw"] * MIL_MM, 3), "linie": _line_name(raw["ls"]),
            "fuellung": _fill_name(raw),
            "stift_vorne": _rgb8(raw["pen_fore"]), "stift_hinten": _rgb8(raw["pen_back"]),
            "fuellung_vorne": _rgb8(raw["fill_fore"]), "fuellung_hinten": _rgb8(raw["fill_back"]),
            "deckkraft_fuellung": raw["fill_op"], "deckkraft_stift": raw["pen_op"]}


def read_classes(names=None):
    """Attributes of the given classes (default: all) in standard format."""
    existing = class_names()
    want = existing if names is None else [n for n in names if n in set(existing)]
    return {"document": current_document(), "classes": [class_attrs(n) for n in want],
            "all_names": existing}


def _set_class_std(name, std):
    """Apply standard-format attributes; returns a list of problems."""
    problems = []
    if "strichstaerke_mm" in std:
        vs.SetClLW(name, int(round(std["strichstaerke_mm"] / MIL_MM)))
    if "linie" in std:
        v = std["linie"]
        if v == "none":
            vs.SetClLSN(name, 0)
        elif v == "solid":
            vs.SetClLSN(name, 2)
        elif v.startswith("res:"):
            idx = vs.Name2Index(v[4:])
            if idx > 0:
                vs.SetClLSN(name, -idx)
            else:
                problems.append("line type %r not in document" % v[4:])
    if "fuellung" in std:
        v = std["fuellung"]
        if v == "none":
            vs.SetClFPat(name, 0)
        elif v == "solid":
            vs.SetClFPat(name, 1)
        elif v.startswith("res:"):
            if not vs.SetClVectorFill(name, v[4:]):
                idx = vs.Name2Index(v[4:])
                if idx > 0:
                    vs.SetClFPat(name, -idx)
                else:
                    problems.append("fill %r not in document" % v[4:])
    for key, fn in (("stift_vorne", vs.SetClPenFore), ("stift_hinten", vs.SetClPenBack),
                    ("fuellung_vorne", vs.SetClFillFore), ("fuellung_hinten", vs.SetClFillBack)):
        if key in std:
            fn(name, _rgb16(std[key]))
    if "deckkraft_fuellung" in std or "deckkraft_stift" in std:
        pen_op, fill_op = vs.GetClOpacityN(name)
        vs.SetOpacityN(vs.GetObject(name), std.get("deckkraft_stift", pen_op),
                       std.get("deckkraft_fuellung", fill_op))
    if "automatisch_zuweisen" in std:
        vs.SetClUseGraphic(name, bool(std["automatisch_zuweisen"]))
    return problems


def _set_class_raw(name, raw):
    vs.SetClLW(name, raw["lw"])
    vs.SetClLSN(name, raw["ls"])
    if raw["hatch"]:
        vs.SetClVectorFill(name, raw["hatch"])
    else:
        vs.SetClFPat(name, raw["fpat"])
    vs.SetClPenFore(name, tuple(raw["pen_fore"]))
    vs.SetClPenBack(name, tuple(raw["pen_back"]))
    vs.SetClFillFore(name, tuple(raw["fill_fore"]))
    vs.SetClFillBack(name, tuple(raw["fill_back"]))
    vs.SetOpacityN(vs.GetObject(name), raw["pen_op"], raw["fill_op"])
    vs.SetClUseGraphic(name, raw["use"])


def apply_classes(renames, creates, updates):
    """renames: [[old, new]], creates: [std], updates: [std (only differing keys + name)].
    Returns undo ops (in undo order) and problems per class."""
    undo, problems, done = [], {}, {"renamed": 0, "created": 0, "updated": 0}
    existing = set(class_names())
    for old, new in renames:
        if old in existing and new not in existing:
            vs.RenameClass(old, new)
            existing.discard(old)
            existing.add(new)
            undo.append({"op": "class_renamed", "old": old, "new": new})
            done["renamed"] += 1
    active = _str(vs.ActiveClass())
    for std in creates:
        name = std["name"]
        if name in existing:
            continue
        vs.NameClass(name)
        existing.add(name)
        p = _set_class_std(name, std)
        if p:
            problems[name] = p
        undo.append({"op": "class_created", "name": name})
        done["created"] += 1
    if active:
        vs.NameClass(active)
    for std in updates:
        name = std["name"]
        if name not in existing:
            continue
        undo.append({"op": "class_attrs", "name": name, "raw": _class_raw(name)})
        p = _set_class_std(name, std)
        if p:
            problems[name] = p
        done["updated"] += 1
    undo.reverse()
    return {"document": current_document(), "undo": undo, "problems": problems, **done}


def revert_class_attrs(op):
    if op["name"] not in class_names():
        return "missing"
    _set_class_raw(op["name"], op["raw"])
    return "restored"


def revert_class_renamed(op):
    names = class_names()
    if op["new"] not in names or op["old"] in names:
        return "missing"
    vs.RenameClass(op["new"], op["old"])
    return "restored"


def revert_class_created(op):
    if op["name"] not in class_names() or _class_in_use(op["name"]):
        return "missing"
    vs.DelClass(op["name"])
    return "deleted"
