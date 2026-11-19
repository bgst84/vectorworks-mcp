# Helper library executed INSIDE Vectorworks (embedded Python 3.9).
#
# The server sends this file's source as a prelude with every tool job, so
# the installed bridge never has to change when tools do. Keep it 3.9-
# compatible: no match statements, no `X | Y` type unions, stdlib only.
# `vs` is injected by the bridge.

TYPE_NAMES = {
    2: "Line", 3: "Rectangle", 4: "Oval", 5: "Polygon", 6: "Arc", 10: "Text",
    13: "Rounded Rectangle",
    11: "Group", 15: "Symbol", 16: "Symbol Definition", 21: "Polyline",
    31: "Layer", 63: "Dimension", 68: "Wall", 86: "Plug-in Object", 92: "Symbol Folder",
}
TYPE_CODES = dict((v.lower(), k) for k, v in TYPE_NAMES.items())


def _str(x):
    return "" if x is None else str(x)


def _is_nil(h):
    return h is None or str(h) == "0"


def obj_name(h):
    # GetName returns "none" for unnamed objects. An object really named
    # "none" is the one GetObject finds (which may otherwise hit class None).
    nm = _str(vs.GetName(h))
    if nm == "none" and str(vs.GetObject(nm)) != str(h):
        return ""
    return nm


def h_uuid(h):
    return vs.GetObjectUuid(h)


def handle(uuid):
    h = vs.GetObjectByUuid(uuid)
    if _is_nil(h):
        raise LookupError("no object with uuid %s" % uuid)
    return h


def pio_name(h):
    """Plug-in object name (e.g. 'Lighting Device'), or ''."""
    if vs.GetTypeN(h) != 86:
        return ""
    rec = vs.GetParametricRecord(h)
    return "" if _is_nil(rec) else _str(vs.GetName(rec))


def record_names(h):
    return [_str(vs.GetName(vs.GetRecord(h, i))) for i in range(1, vs.NumRecords(h) + 1)]


def obj_info(h):
    t = vs.GetTypeN(h)
    (x1, y1), (x2, y2) = vs.GetBBox(h)
    info = {
        "uuid": h_uuid(h),
        "type": TYPE_NAMES.get(t, "Type %d" % t),
        "type_code": t,
        "name": obj_name(h),
        "class": _str(vs.GetClass(h)),
        "layer": _str(vs.GetLName(vs.GetLayer(h))),
        "bbox": [[x1, y1], [x2, y2]],
        "records": record_names(h),
    }
    if t == 15:
        info["symbol"] = _str(vs.GetSymName(h))
    if t == 86:
        info["plugin"] = pio_name(h)
    return info


def all_objects(criteria="(ALL)"):
    found = []
    vs.ForEachObject(found.append, criteria)
    return found


def matches(h, cls=None, layer=None, type_=None, plugin=None, record=None,
            field=None, value=None, name=None):
    if cls is not None and _str(vs.GetClass(h)) != cls:
        return False
    if layer is not None and _str(vs.GetLName(vs.GetLayer(h))) != layer:
        return False
    if type_ is not None:
        want = TYPE_CODES.get(str(type_).lower(), type_)
        if vs.GetTypeN(h) != want:
            return False
    if plugin is not None and pio_name(h) != plugin:
        return False
    if name is not None and obj_name(h) != name:
        return False
    if record is not None:
        if record not in record_names(h) and pio_name(h) != record:
            return False
        if field is not None and value is not None:
            if _str(vs.GetRField(h, record, field)) != _str(value):
                return False
    return True


# ---- document -------------------------------------------------------------

def list_layers():
    out = []
    layer = vs.FLayer()
    while not _is_nil(layer):
        out.append({
            "name": _str(vs.GetLName(layer)),
            "kind": "sheet" if vs.GetObjectVariableInt(layer, 154) == 2 else "design",
            "visibility": vs.GetObjectVariableInt(layer, 153),
            "active": _str(vs.GetLName(layer)) == _str(vs.GetLName(vs.ActLayer())),
        })
        layer = vs.NextLayer(layer)
    return out


def list_classes(name_contains=None):
    names = [_str(vs.ClassList(i)) for i in range(1, vs.ClassNum() + 1)]
    if name_contains:
        needle = name_contains.lower()
        names = [n for n in names if needle in n.lower()]
    return names


# Wall style "Data" tab (Vectorworks 2027, found live by diffing styles):
# ObjectVariable selectors on the wall style resource. Booleans 1210/1211
# are assigned by the order of the dialog (Exterior, Load bearing).
WALL_STYLE_DATA = {
    "mark": (1207, "s"), "description": (1208, "s"), "function": (1209, "i"),
    "exterior": (1210, "b"), "load_bearing": (1211, "b"), "fire_rating": (1212, "s"),
    "combustible": (1213, "b"), "firewall": (1214, "b"), "acoustic_rating": (1217, "s"),
    "type": (1220, "s"), "manufacturer": (1221, "s"),
}


def _components(h):
    out = []
    ok, n = vs.GetNumberOfComponents(h)
    if not ok:
        return out
    for i in range(1, n + 1):
        cl = vs.GetComponentClass(h, i)[1]
        out.append({
            "name": _str(vs.GetComponentName(h, i)),
            "width": round(vs.GetComponentWidth(h, i)[1], 4),
            "class": _str(vs.Index2Name(cl)) if cl else "",
            "function": vs.GetComponentFunction(h, i)[1],
            "auto_join": bool(vs.GetCompAutoJoinCap(h, i)[1]),
        })
    return out


def wall_styles(name_contains=None):
    """Wall styles in the document: name, total width, components (name,
    width, class, function) and the Data tab fields."""
    lid, n = vs.BuildResourceList(127, 0, "")
    out = []
    for i in range(1, n + 1):
        name = _str(vs.GetNameFromResourceList(lid, i))
        if name_contains and name_contains.lower() not in name.lower():
            continue
        h = vs.GetObject(name)
        if _is_nil(h):
            continue  # listed from a library folder, not in this document
        data = {}
        for key, (sel, kind) in WALL_STYLE_DATA.items():
            if kind == "s":
                data[key] = _str(vs.GetObjectVariableString(h, sel))
            elif kind == "b":
                data[key] = bool(vs.GetObjectVariableBoolean(h, sel))
            else:
                data[key] = vs.GetObjectVariableInt(h, sel)
        comps = _components(h)
        out.append({"name": name, "width": round(sum(c["width"] for c in comps), 4),
                    "components": comps, "data": data})
    return out


def document_info():
    units = vs.GetUnits()
    return {
        "name": _str(vs.GetFName()),
        "path": _str(vs.GetFPathName()),
        "units": {"display_name": units[4].strip() or units[4], "area_name": units[5].strip()},
        "active_layer": _str(vs.GetLName(vs.ActLayer())),
        "active_class": _str(vs.ActiveClass()),
        "layer_count": vs.NumLayers(),
        "class_count": vs.ClassNum(),
        "selection_count": vs.NumSelectedObjects(),
    }


def get_selection(limit=500):
    out = []
    h = vs.FSActLayer()
    while not _is_nil(h) and len(out) < limit:
        out.append(obj_info(h))
        h = vs.NextSObj(h)
    return out


def find_objects(cls=None, layer=None, type_=None, plugin=None, record=None,
                 field=None, value=None, name=None, limit=500):
    out = []
    for h in all_objects():
        if matches(h, cls, layer, type_, plugin, record, field, value, name):
            out.append(obj_info(h))
            if len(out) >= limit:
                break
    return out


# ---- records ----------------------------------------------------------------

def _record_handle(h, record):
    if pio_name(h) == record:
        return vs.GetParametricRecord(h)
    for i in range(1, vs.NumRecords(h) + 1):
        rec = vs.GetRecord(h, i)
        if _str(vs.GetName(rec)) == record:
            return rec
    raise LookupError("object has no record %r (has %r)" % (record, record_names(h)))


def get_record(uuid, record):
    h = handle(uuid)
    rec = _record_handle(h, record)
    fields = {}
    for i in range(1, vs.NumFields(rec) + 1):
        fname = _str(vs.GetFldName(rec, i))
        fields[fname] = _str(vs.GetRField(h, record, fname))
    return fields


def set_record(uuid, record, values):
    h = handle(uuid)
    rec = _record_handle(h, record)
    known = set(_str(vs.GetFldName(rec, i)) for i in range(1, vs.NumFields(rec) + 1))
    unknown = [k for k in values if k not in known]
    if unknown:
        raise KeyError("unknown field(s) %r on record %r" % (unknown, record))
    before = dict((k, _str(vs.GetRField(h, record, k))) for k in values)
    _write_fields(h, record, values)
    return {"document": current_document(), "before": before}


def _write_fields(h, record, values):
    if record == LD:
        values = _address_fields(h, values)
    for k, v in values.items():
        vs.SetRField(h, record, k, _str(v))
    if vs.GetTypeN(h) == 86:
        vs.ResetObject(h)


def current_document():
    return _str(vs.GetFName())


def revert(ops):
    """Undo journaled tool calls: restore field values, delete created objects."""
    restored, deleted, missing = 0, 0, []
    for op in ops:
        # Extensions handle their own op types: a function revert_<op> sent
        # along as prelude returns "restored", "deleted" or "missing".
        handler = globals().get("revert_" + op["op"])
        if handler is not None:
            outcome = handler(op)
            if outcome == "restored":
                restored += 1
            elif outcome == "deleted":
                deleted += 1
            else:
                missing.append(op.get("name") or op.get("uuid") or op["op"])
            continue
        if op["op"] == "layer_created":
            lay = vs.GetLayerByName(op["name"])
            if not _is_nil(lay):
                vs.DelObject(lay)
            if _is_nil(lay) or not _is_nil(vs.GetLayerByName(op["name"])):
                missing.append(op["name"])
            else:
                deleted += 1
            continue
        h = vs.GetObjectByUuid(op["uuid"])
        if _is_nil(h):
            missing.append(op["uuid"])
            continue
        if op["op"] == "vertices":
            b = op["before"]
            _apply_vertices(h, b["points"], b.get("vertex_types"), b.get("arc_radii"))
            restored += 1
        elif op["op"] == "fields":
            _write_fields(h, op["record"], op["before"])
            restored += 1
        elif op["op"] == "created":
            vs.DelObject(h)
            deleted += 1
    return {"document": current_document(), "restored": restored, "deleted": deleted,
            "missing": missing}


# ---- symbols ------------------------------------------------------------------

def list_symbols(name_contains=None, folder=None, limit=1000):
    out = []

    def walk(h, path):
        while not _is_nil(h) and len(out) < limit:
            t = vs.GetTypeN(h)
            nm = _str(vs.GetName(h))
            if t == 92:
                walk(vs.FInFolder(h), path + [nm])
            elif t == 16:
                fpath = "/".join(path)
                if (not name_contains or name_contains.lower() in nm.lower()) and \
                        (not folder or folder.lower() in fpath.lower()):
                    out.append({"name": nm, "folder": fpath})
            h = vs.NextSymDef(h)

    walk(vs.FSymDef(), [])
    return out


def insert_symbol(name, x, y, z=None, layer=None, cls=None, rotation=0.0):
    if _is_nil(vs.GetObject(name)):
        raise LookupError("no symbol definition named %r" % name)
    if layer:
        if _is_nil(vs.GetLayerByName(layer)):
            raise LookupError("no layer named %r" % layer)
        vs.Layer(layer)
    vs.Symbol(name, (x, y), rotation)
    h = vs.LNewObj()
    if cls:
        vs.SetClass(h, cls)
    if z is not None:
        vs.Move3DObj(h, 0, 0, z - vs.GetSymLoc3D(h)[2])
    info = obj_info(h)
    info["document"] = current_document()
    return info


# ---- Spotlight ------------------------------------------------------------------

LD = "Lighting Device"
LD_FIELDS = [
    "Unit Number", "Channel", "Dimmer", "Universe", "DMX Address", "UniverseAddress",
    "Absolute Address", "Num Channels", "Purpose", "Position", "Inst Type", "Wattage",
    "Color", "Template", "Template2", "Focus", "Circuit Number", "Circuit Name",
    "Mark", "Symbol Name", "Fixture Mode", "GDTF Fixture Name", "Device Type",
    "User Field 1", "User Field 2", "User Field 3", "User Field 4", "User Field 5",
    "User Field 6",
]
# Plug-in name -> parameter holding the position's name.
POSITION_PLUGINS = {
    "Light Position Obj": "Position Name",
    "Lighting Pipe": "Name",
    "Lighting Pipe Ladder": "Name",
    "Hanging Position": "Position Name",
    "Truss": "Name",
}


def _natural(s):
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def lighting_devices():
    return all_objects("(PON='%s')" % LD)


def ld_row(h, fields):
    row = {"uuid": h_uuid(h), "layer": _str(vs.GetLName(vs.GetLayer(h))),
           "class": _str(vs.GetClass(h))}
    for f in fields:
        row[f] = _str(vs.GetRField(h, LD, f))
    return row


def ld_field_names():
    devs = lighting_devices()
    if not devs:
        return []
    rec = vs.GetParametricRecord(devs[0])
    return [_str(vs.GetFldName(rec, i)) for i in range(1, vs.NumFields(rec) + 1)]


def list_lighting_devices(fields=None, position=None, layer=None, limit=5000):
    fields = fields or LD_FIELDS
    keyed = []
    for h in lighting_devices():
        pos = _str(vs.GetRField(h, LD, "Position"))
        if position is not None and pos != position:
            continue
        if layer is not None and _str(vs.GetLName(vs.GetLayer(h))) != layer:
            continue
        unit = _str(vs.GetRField(h, LD, "Unit Number"))
        keyed.append(((_natural(pos), _natural(unit)), ld_row(h, fields)))
    keyed.sort(key=lambda kr: kr[0])
    return [row for _, row in keyed[:limit]]


def _resolve_devices(selectors):
    """Map each selector to exactly one device handle, or raise before any edit."""
    by_uuid, by_pos_unit, by_unit, by_chan = {}, {}, {}, {}
    for h in lighting_devices():
        u = h_uuid(h)
        pos = _str(vs.GetRField(h, LD, "Position"))
        unit = _str(vs.GetRField(h, LD, "Unit Number"))
        by_uuid[u] = h
        by_pos_unit.setdefault((pos, unit), []).append(h)
        by_unit.setdefault(unit, []).append(h)
        by_chan.setdefault(_str(vs.GetRField(h, LD, "Channel")), []).append(h)
    out, errors = [], []
    for i, sel in enumerate(selectors):
        if sel.get("uuid"):
            hs = [by_uuid[sel["uuid"]]] if sel["uuid"] in by_uuid else []
            label = "uuid %s" % sel["uuid"]
        elif sel.get("unit_number") is not None and sel.get("position") is not None:
            hs = by_pos_unit.get((sel["position"], str(sel["unit_number"])), [])
            label = "%s unit %s" % (sel["position"], sel["unit_number"])
        elif sel.get("unit_number") is not None:
            hs = by_unit.get(str(sel["unit_number"]), [])
            label = "unit %s (add position: unit numbers repeat per position)" % sel["unit_number"]
        elif sel.get("channel") is not None:
            hs = by_chan.get(str(sel["channel"]), [])
            label = "channel %s" % sel["channel"]
        else:
            errors.append("update %d: needs uuid, unit_number(+position) or channel" % i)
            continue
        if len(hs) != 1:
            errors.append("update %d: %s matches %d devices" % (i, label, len(hs)))
        else:
            out.append(hs[0])
    if errors:
        raise LookupError("; ".join(errors))
    return out


def _address_fields(h, fields):
    """Spotlight rebuilds Universe/DMX Address from UniverseAddress on reset, so
    route split-address edits through UniverseAddress."""
    fields = dict(fields)
    if ("Universe" in fields or "DMX Address" in fields) and "UniverseAddress" not in fields:
        uni = _str(fields.pop("Universe", vs.GetRField(h, LD, "Universe")))
        addr = _str(fields.pop("DMX Address", vs.GetRField(h, LD, "DMX Address")))
        fields["UniverseAddress"] = "%s/%s" % (uni, addr)
    return fields


def set_lighting_device_fields(updates):
    """updates: [{selector keys..., "fields": {name: value}}]. All-or-nothing:
    every selector and field name is validated before anything changes.
    Values are re-read by the server afterwards (resets apply at script end)."""
    handles = _resolve_devices(updates)
    known = set(ld_field_names())
    bad = sorted(set(k for u in updates for k in u["fields"]) - known)
    if bad:
        raise KeyError("unknown Lighting Device field(s): %r" % bad)
    done = []
    for h, u in zip(handles, updates):
        before = dict((k, _str(vs.GetRField(h, LD, k))) for k in u["fields"])
        _write_fields(h, LD, u["fields"])
        done.append({"uuid": h_uuid(h), "before": before})
    return {"document": current_document(), "devices": done}


def read_devices(uuids, fields):
    return [ld_row(handle(u), fields) for u in uuids]


def list_positions(include_devices=True):
    devices = {}
    for h in lighting_devices():
        devices.setdefault(_str(vs.GetRField(h, LD, "Position")), []).append(
            ld_row(h, ["Unit Number", "Channel", "Inst Type", "Purpose"]))
    positions, named = [], set()
    for h in all_objects("(T=86)"):
        plug = pio_name(h)
        if plug not in POSITION_PLUGINS:
            continue
        nm = _str(vs.GetRField(h, plug, POSITION_PLUGINS[plug]))
        named.add(nm)
        devs = sorted(devices.get(nm, []), key=lambda r: _natural(r["Unit Number"]))
        p = {"name": nm, "uuid": h_uuid(h), "kind": plug,
             "layer": _str(vs.GetLName(vs.GetLayer(h))), "device_count": len(devs) if nm else 0}
        if include_devices and nm:
            p["devices"] = devs
        positions.append(p)
    positions.sort(key=lambda p: _natural(p["name"]))
    orphans = dict((k, len(v)) for k, v in devices.items() if k and k not in named)
    return {"positions": positions,
            "unassigned_device_count": len(devices.get("", [])),
            "device_positions_without_object": orphans}


# ---- tracked raw Python (vw_exec_python) ---------------------------------------

def _jsonable(value):
    import json
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


def _uuid_parents():
    """uuid -> parent uuid for every object ForEachObject reaches."""
    out = {}

    def add(h):
        u = vs.GetObjectUuid(h)
        if u:
            p = vs.GetParent(h)
            out[u] = "" if _is_nil(p) else _str(vs.GetObjectUuid(p))

    vs.ForEachObject(add, "(ALL)")
    return out


def exec_tracked(code, track=True, libs=None):
    """Run user code like the bridge does (last expression or `result` is the
    value) and report which objects it created, so they can be reverted.
    Errors are returned, not raised, so a script that fails halfway still
    reports what it already drew."""
    import ast
    import traceback
    before = _uuid_parents() if track else None
    scope = {"vs": vs, "__name__": "__vwmcp_user__"}
    value, error, tb = None, None, None
    try:
        for lib_name, lib_source in (libs or {}).items():
            import types
            mod = types.ModuleType(lib_name)
            mod.vs = vs
            exec(compile(lib_source, "<%s>" % lib_name, "exec"), mod.__dict__)
            scope[lib_name] = mod
        tree = ast.parse(code, "<vw_exec_python>", "exec")
        last = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last = ast.Expression(tree.body.pop().value)
        exec(compile(tree, "<vw_exec_python>", "exec"), scope)
        if last is not None:
            value = eval(compile(last, "<vw_exec_python>", "eval"), scope)
        if "result" in scope:
            value = scope["result"]
    except BaseException as e:  # noqa: BLE001 - report, never crash Vectorworks
        error = "%s: %s" % (type(e).__name__, e)
        tb = traceback.format_exc()
    out = {"value": _jsonable(value), "error": error, "traceback": tb,
           "document": current_document()}
    lib_warnings = []
    for lib_name in (libs or {}):
        mod = scope.get(lib_name)
        lib_warnings.extend(getattr(mod, "WARNINGS", None) or [])
    if lib_warnings:
        out["warnings"] = lib_warnings
    if track:
        after = _uuid_parents()
        new = set(after) - set(before)
        # Keep only top-level new objects: deleting a new group removes its contents.
        out["created"] = sorted(u for u in new if after[u] not in new)
        out["deleted_existing"] = len(set(before) - set(after))
    return out


# ---- geometry export (read-back) -----------------------------------------------

def _pt(p, nd):
    return [round(p[0], nd) + 0.0, round(p[1], nd) + 0.0]   # + 0.0: no "-0.0"


# 2D affine maps are tuples (a, b, c, d, tx, ty):
#   x' = a*x + c*y + tx,   y' = b*x + d*y + ty
# They carry symbol contents from definition coordinates to layer coordinates.

def _xf_symbol(insert, rotation, mirrored=False, scale=(1.0, 1.0)):
    """Map of one symbol instance: scale, mirror (y -> -y in the definition,
    as Vectorworks stores a flipped symbol), rotate counterclockwise by
    `rotation` degrees, move to the insertion point."""
    import math
    r = math.radians(rotation)
    co, si = math.cos(r), math.sin(r)
    sx = scale[0]
    sy = -scale[1] if mirrored else scale[1]
    return (co * sx, si * sx, -si * sy, co * sy, insert[0], insert[1])


def _xf_mul(m, n):
    """The map that applies n first, then m."""
    return (m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
            m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
            m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5])


def _xf_pt(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def _xf_det(m):
    return m[0] * m[3] - m[2] * m[1]


def _xf_angle(m, deg):
    """Direction angle (degrees, -180..180) of a direction after the map."""
    import math
    r = math.radians(deg)
    dx, dy = math.cos(r), math.sin(r)
    return math.degrees(math.atan2(m[1] * dx + m[3] * dy, m[0] * dx + m[2] * dy))


def _xf_decompose(m):
    """(insert, rotation, mirrored, (sx, sy)) so that _xf_symbol gives m back
    (exact for maps built from symbol placements with uniform scale)."""
    import math
    mirrored = _xf_det(m) < 0
    sx, sy = math.hypot(m[0], m[1]), math.hypot(m[2], m[3])
    return (m[4], m[5]), math.degrees(math.atan2(m[1], m[0])), mirrored, (sx, sy)


def _rect_points(center, width, height, angle):
    """Corners of a rectangle turned by `angle` degrees around its center,
    counterclockwise starting at the corner that is bottom left when unturned."""
    m = _xf_symbol(center, angle)
    w, h = width / 2.0, height / 2.0
    return [_xf_pt(m, p) for p in ((-w, -h), (w, -h), (w, h), (-w, h))]


def _wall_outline(p1, p2, width, offset=0.0):
    """Plan outline of a straight wall from its definition line: start left,
    end left, end right, start right. offset moves the body to the left of
    the line (0 = centered)."""
    import math
    length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if not length:
        return [tuple(p1), tuple(p2)]
    nx, ny = -(p2[1] - p1[1]) / length, (p2[0] - p1[0]) / length
    a, b = offset + width / 2.0, offset - width / 2.0
    return [(p1[0] + nx * a, p1[1] + ny * a), (p2[0] + nx * a, p2[1] + ny * a),
            (p2[0] + nx * b, p2[1] + ny * b), (p1[0] + nx * b, p1[1] + ny * b)]


def _extent_pts(e):
    """Points whose bounding box is the exact extent of one entry (the box
    is only axis-true in the coordinates the entry is given in)."""
    import math
    if "radius" in e and "center" in e:
        (cx, cy), r = e["center"], e["radius"]
        start, sweep = e.get("start_angle", 0.0), e.get("sweep", 360.0)
        lo, hi = min(start, start + sweep), max(start, start + sweep)
        angles = [lo, hi] + [q for q in range(int(math.floor(lo / 90.0)) * 90, int(hi) + 1, 90) if lo <= q <= hi]
        return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in angles]
    if "radii" in e:
        (cx, cy), (rx, ry) = e["center"], e["radii"]
        co, si = math.cos(math.radians(e.get("rotation", 0.0))), math.sin(math.radians(e.get("rotation", 0.0)))
        ex, ey = math.hypot(rx * co, ry * si), math.hypot(rx * si, ry * co)
        return [(cx - ex, cy - ey), (cx + ex, cy + ey)]
    if e.get("points"):
        return list(e["points"])
    for key in ("bbox", "bbox_view"):
        if key in e:
            return list(e[key])
    for key in ("origin", "center"):
        if key in e:
            return [e[key]]
    return []


def _bbox_of(pts, nd):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [[round(min(xs), nd), round(min(ys), nd)], [round(max(xs), nd), round(max(ys), nd)]]


def _place(e, m, nd):
    """Copy of a raw entry with rounded coordinates; with a map m the entry
    is carried from definition to layer coordinates first. Lengths of arcs
    and ovals use the mean scale of m (exact for uniform symbol scaling)."""
    import math
    out = dict(e)
    s = 1.0 if m is None else math.sqrt(abs(_xf_det(m)))
    flip = m is not None and _xf_det(m) < 0

    def pt(p):
        return _pt(p if m is None else _xf_pt(m, p), nd)

    def ang(a, full=False):
        if m is not None:
            a = _xf_angle(m, a)
            if full:
                a = a % 360.0
        return round(a, 6)

    for key in ("center", "origin"):
        if key in e:
            out[key] = pt(e[key])
    for key in ("points", "line"):
        if key in e:
            out[key] = [pt(p) for p in e[key]]
    if "radius" in e:
        out["radius"] = round(e["radius"] * s, nd)
    if "start_angle" in e:
        out["start_angle"] = ang(e["start_angle"], True)
        out["sweep"] = round(-e["sweep"] if flip else e["sweep"], 6)
    if "radii" in e:
        out["radii"] = [round(r * s, nd) for r in e["radii"]]
        out["rotation"] = ang(e.get("rotation", 0.0))
    if "arc_radii" in e:
        out["arc_radii"] = [round(r * s, nd) for r in e["arc_radii"]]
    if "angle" in e:
        out["angle"] = ang(e["angle"])
        if flip:
            out["mirrored"] = not e.get("mirrored", False)
    if "width" in e:
        out["width"] = round(e["width"] * s, nd)
    if "bbox_view" in e:
        if m is None:
            out["bbox_view"] = [_pt(p, nd) for p in e["bbox_view"]]
        else:
            # GetBBox is not exact under rotation: report the box of the turned box.
            del out["bbox_view"]
            (x1, y1), (x2, y2) = e["bbox_view"]
            out["bbox"] = _bbox_of([_xf_pt(m, p) for p in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))], nd)
    return out


def _symbol_params(h):
    """Placement of a symbol instance in its container."""
    g = {"symbol": _str(vs.GetSymName(h)), "insert": tuple(vs.GetSymLoc(h)),
         "rotation": vs.GetSymRot(h), "mirrored": bool(vs.IsObjectFlipped(h))}
    if vs.GetObjectVariableInt(h, 101) > 1:  # 1 none, 2 symmetric, 3 asymmetric
        sx = vs.GetObjectVariableReal(h, 102)
        g["scale"] = (sx, sx if vs.GetObjectVariableInt(h, 101) == 2 else vs.GetObjectVariableReal(h, 103))
    return g


def _geom(h, t):
    """Exact geometry (not rounded) for the common 2D types. vs.GetBBox
    depends on the plan rotation of the view, so it is only a last resort."""
    import math
    g = {}
    if t == 2:
        g["points"] = [vs.GetSegPt1(h), vs.GetSegPt2(h)]
    elif t in (5, 21):
        n = vs.GetVertNum(h)
        if t == 5:
            g["points"] = [vs.GetPolyPt(h, i) for i in range(1, n + 1)]
        else:
            pts, kinds, radii = [], [], []
            for i in range(1, n + 1):
                p, kind, radius = vs.GetPolylineVertex(h, i)
                pts.append(p)
                kinds.append(kind)
                radii.append(radius)
            g["points"] = pts
            if any(kinds):
                g["vertex_types"] = kinds  # 0 corner, 1 bezier, 2 cubic, 3 arc, 4 radius
                g["arc_radii"] = radii
        try:
            g["closed"] = bool(vs.IsPolyClosed(h))
        except Exception:  # noqa: BLE001 - optional
            pass
    elif t == 6:
        c = vs.HCenter(h)
        p1, p2 = vs.GetSegPt1(h), vs.GetSegPt2(h)
        start, sweep = vs.GetArc(h)
        g.update({"center": c, "radius": math.hypot(p1[0] - c[0], p1[1] - c[1]),
                  "start_angle": start, "sweep": sweep, "points": [p1, p2]})
    elif t == 10:
        origin, angle, mirrored = vs.GetTextOrientation(h)
        size = vs.GetTextSize(h, 0)
        g.update({"text": _str(vs.GetText(h)), "origin": origin, "angle": angle,
                  "size_raw": size, "size_pt": round(size, 4), "just": vs.GetTextJust(h),
                  "vertical_align": vs.GetTextVerticalAlign(h),
                  "font": _str(vs.GetFontName(vs.GetTextFont(h, 0)))})
        if mirrored:
            g["mirrored"] = True
    elif t == 63:
        g.update({"text": _str(vs.GetDimText(h)), "center": vs.HCenter(h)})
    elif t == 15:
        g.update(_symbol_params(h))
    elif t == 68:
        p1, p2 = vs.GetSegPt1(h), vs.GetSegPt2(h)
        ok, width = vs.GetWallThickness(h)
        g.update({"points": _wall_outline(p1, p2, width), "closed": True, "line": [p1, p2],
                  "width": width, "wall_style": _str(vs.GetWallStyle(h))})
    else:
        (x1, y1), (x2, y2) = vs.GetBBox(h)
        c = vs.HCenter(h)
        g.update({"center": c, "bbox_view": [(min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2))]})
        if t in (3, 13):
            g.update({"points": _rect_points(c, vs.HWidth(h), vs.HHeight(h), vs.HAngle(h)), "closed": True})
        elif t == 4:
            g.update({"radii": (vs.HWidth(h) / 2.0, vs.HHeight(h) / 2.0), "rotation": vs.HAngle(h)})
    return g


def _hex(color):
    return "#%02x%02x%02x" % tuple(int(v) >> 8 for v in color[:3])


def _attrs(h):
    """Fill and pen as the object is drawn, and whether they follow its class.
    fill pattern: 0 none, 1 solid background color, 2 solid foreground color,
    other values are patterns / hatches ("hatch" is the name of a hatch
    fill). pen weight in mils (4 = 0.1 mm), pen style 0 = no line,
    2 = solid, negative = a dash style. opacity in percent."""
    a = {
        "fill": {
            "pattern": vs.GetFPat(h), "back": _hex(vs.GetFillBack(h)), "fore": _hex(vs.GetFillFore(h)),
            "by_class": {"pattern": bool(vs.IsFPatByClass(h)), "color": bool(vs.IsFillColorByClass(h))},
        },
        "pen": {
            "color": _hex(vs.GetPenFore(h)), "weight": vs.GetLW(h), "style": vs.GetLSN(h),
            "by_class": {"color": bool(vs.IsPenColorByClass(h)), "weight": bool(vs.IsLWByClass(h)),
                         "style": bool(vs.IsLSByClass(h))},
        },
        "opacity": vs.GetOpacity(h),
    }
    has_hatch, hatch = vs.GetVectorFill(h)
    if has_hatch:
        a["fill"]["hatch"] = _str(hatch)
    return a


def _raw_entry(h, t, attributes):
    e = {"uuid": h_uuid(h), "type": TYPE_NAMES.get(t, "Type %d" % t), "type_code": t,
         "class": _str(vs.GetClass(h))}
    if t == 86:
        e["plugin"] = pio_name(h)
    e.update(_geom(h, t))
    if attributes:
        e["attrs"] = _attrs(h)
    return e


def _read_definition(name, attributes, cache):
    """Raw entries of a symbol definition in definition coordinates, in
    drawing order, groups flattened. Read once per export."""
    if name not in cache:
        entries = cache[name] = []
        d = vs.GetObject(name)

        def walk(h, group):
            while not _is_nil(h):
                t = vs.GetTypeN(h)
                if t == 11:
                    walk(vs.FInGroup(h), h_uuid(h))
                else:
                    e = _raw_entry(h, t, attributes)
                    if group:
                        e["group"] = group
                    entries.append(e)
                h = vs.NextObj(h)

        if not _is_nil(d) and vs.GetTypeN(d) == 16:
            walk(vs.FInSymDef(d), None)
    return cache[name]


def _symbol_map(e, m):
    """Layer-coordinate map of the symbol entry e that lies in a container with map m."""
    own = _xf_symbol(e["insert"], e["rotation"], e["mirrored"], e.get("scale", (1.0, 1.0)))
    return own if m is None else _xf_mul(m, own)


def _origin_shift():
    """Coordinates read inside a symbol definition come back shifted by the
    user origin of the document (true = read + origin); this map undoes it."""
    ox, oy = vs.GetOrigin()
    return (1.0, 0.0, 0.0, 1.0, ox, oy)


def _definition_pts(name, world, attributes, cache, shift, level=0):
    """Layer-coordinate points spanning everything a symbol instance draws.
    world: map of the instance; shift: see _origin_shift."""
    pts = []
    inner = _xf_mul(world, shift)
    for c in _read_definition(name, attributes, cache):
        if c["type_code"] == 15:
            if level < 8:
                pts.extend(_definition_pts(c["symbol"], _symbol_map(c, inner), attributes, cache, shift, level + 1))
        else:
            pts.extend(_extent_pts(_place(c, inner, 12)))
    return pts


def export_geometry(layer=None, classes=None, limit=20000, digits=4, attributes=True,
                    symbols="instances", symbol_depth=3):
    """All objects of one layer (default: active) with exact 2D geometry,
    descending into groups. Plug-in objects (chain dimensions, doors...)
    are reported as one entry with their center. attributes: add fill and
    pen of every object ("attrs"). symbols="expand": after every symbol
    instance, also the objects of its definition in layer coordinates
    ("parent", "depth"), nested symbols up to symbol_depth levels.
    "stack" is the drawing order (0 = backmost)."""
    if symbols not in ("instances", "expand"):
        raise ValueError("symbols must be 'instances' or 'expand', not %r" % (symbols,))
    lay = vs.ActLayer() if not layer else vs.GetLayerByName(layer)
    if _is_nil(lay):
        raise LookupError("no layer named %r" % layer)
    want = set(classes) if classes else None
    out, truncated, stack, defs = [], [False], [0], {}
    shift = _origin_shift()

    def emit(e, m, parent, depth):
        if len(out) >= limit:
            truncated[0] = True
            return
        placed = _place(e, m, digits)
        placed["stack"] = stack[0]
        stack[0] += 1
        if parent:
            placed["parent"] = parent
            placed["depth"] = depth
        if e["type_code"] != 15:
            out.append(placed)
            return
        world = _symbol_map(e, m)
        insert, rotation, mirrored, scale = _xf_decompose(world)
        placed.update({"insert": _pt(insert, digits), "rotation": round(rotation, 6), "mirrored": mirrored})
        if "scale" in e or abs(scale[0] - 1) > 1e-9 or abs(scale[1] - 1) > 1e-9:
            placed["scale"] = [round(scale[0], 6), round(scale[1], 6)]
        pts = _definition_pts(e["symbol"], world, attributes, defs, shift)
        if pts:
            box = placed["bbox"] = _bbox_of(pts, digits)
            placed["center"] = _pt(((box[0][0] + box[1][0]) / 2.0, (box[0][1] + box[1][1]) / 2.0), digits)
        out.append(placed)
        if symbols == "expand" and depth < symbol_depth:
            children = _read_definition(e["symbol"], attributes, defs)
            placed["children"] = len(children)
            inner = _xf_mul(world, shift)
            for c in children:
                emit(c, inner, placed["uuid"], depth + 1)

    def walk(h, group):
        while not _is_nil(h):
            if truncated[0]:
                return
            t = vs.GetTypeN(h)
            if t == 11:
                walk(vs.FInGroup(h), h_uuid(h))
            elif want is None or _str(vs.GetClass(h)) in want:
                e = _raw_entry(h, t, attributes)
                if group:
                    e["group"] = group
                emit(e, None, None, 0)
            else:
                stack[0] += 1
            h = vs.NextObj(h)

    walk(vs.FInLayer(lay), None)
    return {"document": current_document(), "layer": _str(vs.GetLName(lay)),
            "scale": vs.GetLScale(lay), "units_per_inch": vs.GetUnits()[3],
            "objects": out, "truncated": truncated[0]}


# ---- layers ---------------------------------------------------------------------

VISIBILITY = {"visible": 0, "hidden": -1, "gray": 2}


def _layer_names():
    out = []
    layer = vs.FLayer()
    while not _is_nil(layer):
        out.append(_str(vs.GetLName(layer)))
        layer = vs.NextLayer(layer)
    return out


def _pair_uuids(a, b, out):
    """uuid of an object -> uuid of its duplicate, walking groups in parallel."""
    out[h_uuid(a)] = h_uuid(b)
    if vs.GetTypeN(a) == 11 and vs.GetTypeN(b) == 11:
        x, y = vs.FInGroup(a), vs.FInGroup(b)
        while not _is_nil(x) and not _is_nil(y):
            _pair_uuids(x, y, out)
            x, y = vs.NextObj(x), vs.NextObj(y)


def _move_layer_next_to(layer, name, source):
    """Step `layer` through the stack until it sits right after `source` in
    list order. HMoveBackward / HMoveForward on a layer handle move it one
    or more places; the direction is taken from what the first step did."""
    def gap():
        names = _layer_names()
        return names.index(name) - names.index(source)

    start = gap()
    if start == 1:
        return
    vs.HMoveBackward(layer, False)
    backward_lowers = gap() < start
    for _ in range(4 * len(_layer_names())):
        g = gap()
        if g == 1:
            return
        lower = g > 1
        if lower == backward_lowers:
            vs.HMoveBackward(layer, False)
        else:
            vs.HMoveForward(layer, False)
        if gap() == g:
            return  # stuck (e.g. sheet layers in between): leave it there


def duplicate_layer(source, name, visibility=None, uuid_map=False):
    """Copy a design layer with all its objects: same scale, placed right
    after the source in the layer list. visibility: "visible", "hidden",
    "gray" or None (same as the source has now). The active layer stays
    active. uuid_map: also return {source object uuid: copy uuid}."""
    src = vs.GetLayerByName(source)
    if _is_nil(src):
        raise LookupError("no layer named %r" % source)
    if vs.GetObjectVariableInt(src, 154) == 2:
        raise ValueError("%r is a sheet layer; only design layers can be duplicated" % source)
    if not _is_nil(vs.GetLayerByName(name)):
        raise ValueError("a layer named %r already exists" % name)
    if visibility is not None and visibility not in VISIBILITY:
        raise ValueError("visibility must be one of %r or None" % sorted(VISIBILITY))
    active = _str(vs.GetLName(vs.ActLayer()))
    originals = []
    h = vs.FInLayer(src)
    while not _is_nil(h):
        originals.append(h)
        h = vs.NextObj(h)
    new = vs.CreateLayer(name, 1)
    vs.SetLScale(new, vs.GetLScale(src))
    mapping, copied = {}, 0
    for h in originals:
        d = vs.CreateDuplicateObject(h, new)
        if _is_nil(d):
            continue
        copied += 1
        if uuid_map:
            _pair_uuids(h, d, mapping)
    vis = vs.GetObjectVariableInt(src, 153) if visibility is None else VISIBILITY[visibility]
    vs.SetObjectVariableInt(new, 153, vis)
    _move_layer_next_to(new, name, source)
    vs.Layer(active)
    names = _layer_names()
    out = {"document": current_document(), "layer": name, "source": source,
           "objects": copied, "source_objects": len(originals), "scale": vs.GetLScale(new),
           "visibility": vis, "after_source": names.index(name) - names.index(source) == 1}
    if uuid_map:
        out["uuid_map"] = mapping
    return out


# ---- polygon / polyline vertices ------------------------------------------------

def _vertices(h):
    t = vs.GetTypeN(h)
    n = vs.GetVertNum(h)
    if t == 5:
        return {"points": [list(vs.GetPolyPt(h, i)) for i in range(1, n + 1)]}
    pts, kinds, radii = [], [], []
    for i in range(1, n + 1):
        p, kind, radius = vs.GetPolylineVertex(h, i)
        pts.append(list(p))
        kinds.append(kind)
        radii.append(radius)
    return {"points": pts, "vertex_types": kinds, "arc_radii": radii}


def _apply_vertices(h, points, vertex_types=None, arc_radii=None):
    """Make the vertex list of a polygon (type 5) or polyline (type 21) equal
    to `points`. SetPolyPt silently does nothing on polylines, so those go
    through SetPolylineVertex."""
    n = vs.GetVertNum(h)
    while n > len(points):
        vs.DelVertex(h, n)
        n -= 1
    while n < len(points):
        vs.InsertVertex(h, points[0][0], points[0][1], n, 0, 0)
        n += 1
    polyline = vs.GetTypeN(h) == 21
    for i, p in enumerate(points):
        if polyline:
            kind = vertex_types[i] if vertex_types else 0
            radius = arc_radii[i] if arc_radii else 0
            vs.SetPolylineVertex(h, i + 1, (p[0], p[1]), kind, radius, True)
        else:
            vs.SetPolyPt(h, i + 1, p[0], p[1])
    vs.ResetBBox(h)


def _shoelace(points):
    n = len(points)
    return abs(sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
                   for i in range(n))) / 2.0


def set_vertices(uuid, points, vertex_types=None, arc_radii=None):
    """Replace all vertices of a polygon or polyline. Re-reads them afterwards
    and reports whether every point arrived ("applied")."""
    h = handle(uuid)
    t = vs.GetTypeN(h)
    if t not in (5, 21):
        raise TypeError("%s is a %s; only polygons and polylines have editable vertices"
                        % (uuid, TYPE_NAMES.get(t, "Type %d" % t)))
    if len(points) < 2:
        raise ValueError("need at least 2 points")
    for name, extra in (("vertex_types", vertex_types), ("arc_radii", arc_radii)):
        if extra is not None and len(extra) != len(points):
            raise ValueError("%s must have one entry per point" % name)
    if t == 5 and vertex_types and any(vertex_types):
        raise ValueError("curved vertices need a polyline; this object is a polygon")
    before = _vertices(h)
    _apply_vertices(h, points, vertex_types, arc_radii)
    after = _vertices(h)["points"]
    applied = len(after) == len(points) and all(
        abs(a[0] - p[0]) < 1e-6 and abs(a[1] - p[1]) < 1e-6 for a, p in zip(after, points))
    return {"document": current_document(), "uuid": uuid,
            "type": TYPE_NAMES.get(vs.GetTypeN(h), "Type %d" % vs.GetTypeN(h)),
            "before": before, "points": after, "applied": applied,
            "area_before": _shoelace(before["points"]), "area": _shoelace(after),
            "closed": bool(vs.IsPolyClosed(h))}
