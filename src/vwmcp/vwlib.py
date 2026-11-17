# Helper library executed INSIDE Vectorworks (embedded Python 3.9).
#
# The server sends this file's source as a prelude with every tool job, so
# the installed bridge never has to change when tools do. Keep it 3.9-
# compatible: no match statements, no `X | Y` type unions, stdlib only.
# `vs` is injected by the bridge.

TYPE_NAMES = {
    2: "Line", 3: "Rectangle", 4: "Oval", 5: "Polygon", 6: "Arc", 10: "Text",
    11: "Group", 15: "Symbol", 16: "Symbol Definition", 21: "Polyline",
    31: "Layer", 86: "Plug-in Object", 92: "Symbol Folder",
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
    """Undo journaled tool calls: restore fields, delete created objects,
    move objects back, remove created layers/classes/resources."""
    restored, deleted, moved, missing = 0, 0, 0, []
    for op in ops:
        kind = op["op"]
        if kind == "layer":
            h = vs.GetLayerByName(op["name"])
        elif kind == "class":
            h = op["name"] if op["name"] in list_classes() else None
        elif kind == "resource":
            h = vs.GetObject(op["name"])
        else:
            h = vs.GetObjectByUuid(op["uuid"])
        if _is_nil(h):
            missing.append(op.get("uuid") or op.get("name"))
            continue
        if kind == "fields":
            _write_fields(h, op["record"], op["before"])
            restored += 1
        elif kind == "created" or kind == "layer" or kind == "resource":
            vs.DelObject(h)
            deleted += 1
        elif kind == "class":
            vs.DelClass(op["name"])
            deleted += 1
        elif kind == "move":
            _move(h, -op["dx"], -op["dy"], -op.get("dz", 0.0))
            moved += 1
    return {"document": current_document(), "restored": restored, "deleted": deleted,
            "moved": moved, "missing": missing}


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
        _activate_layer(layer)
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
    "TrussItem": "PositionName",  # VW 2026 truss objects (internal name)
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


# ---- layers, classes, views, move, delete -------------------------------------
# Calls marked (vwx) follow vicquick/vwx-mcp (MIT). Live-tested here on
# Vectorworks 2026 (31.7) 2026-11-17; see docs/vs-notes.md "Drawing tools".

def _activate_layer(name):
    """Make a layer active. VW 2026 (31.7) has no SetActiveLayerN, so this is
    vs.Layer(name), which vwx-mcp found hazardous from palette/timer contexts;
    from our menu command it worked live (2026-11-17)."""
    h = vs.GetLayerByName(name)
    if _is_nil(h):
        raise LookupError("no layer named %r" % name)
    fn = getattr(vs, "SetActiveLayerN", None)
    if fn is not None:
        fn(h)
    else:
        vs.Layer(name)


def create_layer(name, kind="design", scale=None, activate=False):
    if not _is_nil(vs.GetLayerByName(name)):
        raise ValueError("layer %r already exists" % name)
    prev = _str(vs.GetLName(vs.ActLayer()))
    h = vs.CreateLayer(name, 2 if kind == "sheet" else 1)  # (vwx) 1 design, 2 sheet
    if _is_nil(h):
        raise RuntimeError("CreateLayer did not create %r" % name)
    if scale is not None and kind != "sheet":
        vs.SetLScale(h, float(scale))
    if not activate and prev:
        _activate_layer(prev)  # CreateLayer leaves the new layer active
    return {"document": current_document(), "name": name, "kind": kind,
            "active": activate or not prev}


def create_class(name):
    if name in list_classes():
        raise ValueError("class %r already exists" % name)
    prev = _str(vs.ActiveClass())
    vs.NameClass(name)  # (vwx) creates the class, and makes it active
    if prev:
        vs.NameClass(prev)
    return {"document": current_document(), "name": name}


def _handles(uuids):
    """All handles, or a LookupError naming every missing uuid (nothing touched)."""
    hs, missing = [], []
    for u in uuids:
        h = vs.GetObjectByUuid(u)
        (missing if _is_nil(h) else hs).append(u if _is_nil(h) else h)
    if missing:
        raise LookupError("no object with uuid(s) %s" % ", ".join(missing))
    return hs


def delete_objects(uuids):
    hs = _handles(uuids)
    for h in hs:
        vs.DelObject(h)
    return {"document": current_document(), "deleted": len(hs)}


def move_objects(uuids, dx=0.0, dy=0.0, dz=0.0):
    hs = _handles(uuids)
    for h in hs:
        _move(h, dx, dy, dz)
    return {"document": current_document(), "moved": len(hs)}


def _move(h, dx, dy, dz):
    if dz:
        vs.Move3DObj(h, dx, dy, dz)
    else:
        vs.HMove(h, dx, dy)


# (camera direction, up vector); the target is the origin. (vwx)
VIEWS = {
    "top": ((0, 0, 1), (0, 1, 0)), "bottom": ((0, 0, -1), (0, -1, 0)),
    "front": ((0, -1, 0), (0, 0, 1)), "back": ((0, 1, 0), (0, 0, 1)),
    "right": ((1, 0, 0), (0, 0, 1)), "left": ((-1, 0, 0), (0, 0, 1)),
    "iso": ((1, -1, 1), (0, 0, 1)), "iso_right": ((1, -1, 1), (0, 0, 1)),
    "iso_left": ((-1, -1, 1), (0, 0, 1)),
}


def set_view(view=None, fit=False):
    if view == "top_plan":
        vs.DoMenuTextByName("Standard Views", 1)  # live-tested (vs-notes)
    elif view:
        if view not in VIEWS:
            raise ValueError("unknown view %r (use top_plan, %s)" % (view, ", ".join(VIEWS)))
        loc, up = VIEWS[view]
        vs.SetViewVector(loc, (0, 0, 0), up)
    if fit:
        vs.DoMenuTextByName("Fit To Objects", 0)  # (vwx) VW 2026 has no ZoomToSel
    vs.ReDrawAll()
    return {"view": view, "fit": fit}


# ---- libraries and resources ------------------------------------------------------
# Type codes for BuildResourceList: 16 symbol definition (also plug-in styles,
# which are symbol definitions wrapping one plug-in object), 47 record format.

def _resource_names(list_id, count):
    return [_str(vs.GetNameFromResourceList(list_id, i)) for i in range(1, count + 1)]


def library_resources(path, type_code=16, name_contains=None, limit=500):
    import os
    if not os.path.isfile(path):
        raise LookupError("no file at %s" % path)
    list_id, n = vs.BuildResourceListN(type_code, path)  # (vwx)
    names = _resource_names(list_id, n)
    if name_contains:
        needle = name_contains.lower()
        names = [nm for nm in names if needle in nm.lower()]
    return {"path": path, "type_code": type_code, "count": len(names), "names": names[:limit]}


def import_resource(path, name, type_code=16, new_name=None):
    """Import one resource from a library file via Vectorworks' own importer
    (plug-in style data travels with it). (vwx)"""
    import os
    if not os.path.isfile(path):
        raise LookupError("no file at %s" % path)
    final = new_name or name
    if not _is_nil(vs.GetObject(final)):
        raise ValueError("a resource named %r is already in the document" % final)
    list_id, n = vs.BuildResourceListN(type_code, path)
    names = _resource_names(list_id, n)
    if name not in names:
        raise LookupError("%r is not in %s (has %d resources of type %d)"
                          % (name, path, n, type_code))
    existing = vs.GetObject(name)
    tmp = None
    if not _is_nil(existing):  # importing a copy under new_name: park the local one
        tmp = name + "__vwmcp_tmp"
        vs.SetName(existing, tmp)
    try:
        fn = getattr(vs, "ImportResourceToCurrentFile", None)  # (listID, index) in VW 2026
        if fn is not None:
            h = fn(list_id, names.index(name) + 1)
        else:
            h = vs.ImportResToCurFileN(list_id, names.index(name) + 1, lambda *a: 0)
        if _is_nil(h):
            raise RuntimeError("resource import returned nothing for %r" % name)
        if new_name:
            vs.SetName(h, new_name)
    finally:
        if tmp is not None:
            vs.SetName(existing, name)
    return {"document": current_document(), "name": _str(vs.GetName(h)),
            "type_code": vs.GetTypeN(h)}


# ---- plug-in objects --------------------------------------------------------------

def create_pio(plugin, x, y, rotation=0.0, parameters=None, layer=None, cls=None):
    """Place a plug-in object by its internal name ('Lighting Device',
    'TrussItem', 'Light Position Obj', ...) and set parameters by field name."""
    if layer:
        _activate_layer(layer)
    fn = getattr(vs, "CreateCustomObjectN", None)
    if fn is not None:
        h = fn(plugin, (x, y), rotation, False)  # False: no preferences dialog
    else:
        h = vs.CreateCustomObject(plugin, (x, y), rotation)
    if _is_nil(h):
        raise LookupError("plug-in %r is not available in this document" % plugin)
    try:
        if cls:
            vs.SetClass(h, cls)
        if parameters:
            set_record(h_uuid(h), pio_name(h) or plugin, parameters)
    except Exception:
        vs.DelObject(h)
        raise
    info = obj_info(h)
    info["document"] = current_document()
    return info


def pio_parameters(uuid):
    h = handle(uuid)
    rec = pio_name(h)
    if not rec:
        raise TypeError("object %s is not a plug-in object" % uuid)
    return {"plugin": rec, "fields": get_record(uuid, rec)}


def set_pio_parameters(uuid, values):
    rec = pio_name(handle(uuid))
    if not rec:
        raise TypeError("object %s is not a plug-in object" % uuid)
    out = set_record(uuid, rec, values)
    out["record"] = rec
    return out
