"""New drawing tools: journal ops (FakeVW) and vwlib round trips (fake vs)."""

import threading

import pytest
import vwmcp_bridge
from mcp.server.mcpserver.exceptions import ToolError

from vwmcp import app
from vwmcp.client import Bridge
from vwmcp.journal import Journal
from vwmcp.tools import drawing, generic


# ---- journal-level ------------------------------------------------------------

class FakeVW:
    def __init__(self):
        self.calls, self.document = [], "Plot.vwx"

    def __call__(self, fn, **kw):
        self.calls.append((fn, kw))
        doc = {"document": self.document}
        canned = {
            "import_resource": lambda: {**doc, "name": kw.get("new_name") or kw["name"], "type_code": 16},
            "create_pio": lambda: {**doc, "uuid": "pio-1", "type": "Plug-in Object", "plugin": kw["plugin"]},
            "set_pio_parameters": lambda: {**doc, "before": {"Channel": "1"}, "record": "Lighting Device"},
            "get_record": lambda: {"Channel": "7"},
            "create_layer": lambda: {**doc, "name": kw["name"], "kind": kw["kind"], "active": False},
            "create_class": lambda: {**doc, "name": kw["name"]},
            "delete_objects": lambda: {**doc, "deleted": len(kw["uuids"])},
            "move_objects": lambda: {**doc, "moved": len(kw["uuids"])},
            "set_view": lambda: {"view": kw["view"], "fit": kw["fit"]},
            "set_objects_class": lambda: {**doc, "before": ["None"] * len(kw["uuids"])},
            "current_document": lambda: self.document,
            "revert": lambda: {**doc, "restored": 0, "deleted": 0, "moved": 0, "missing": []},
        }
        return canned[fn]()


@pytest.fixture
def fake(tmp_path, monkeypatch):
    f = FakeVW()
    for mod in (app, generic, drawing):
        monkeypatch.setattr(mod, "vw", f)
    monkeypatch.setattr(app, "get_journal", lambda: Journal(tmp_path / "j.jsonl"))
    return f


def last_revert_ops(fake):
    fn, kw = fake.calls[-1]
    assert fn == "revert"
    return kw["ops"]


def test_import_resource_reverts_by_name(fake):
    out = drawing.vw_import_resource("/lib/Truss.vwx", "Tomcat 12", new_name="Tomcat copy")
    assert out == {"name": "Tomcat copy", "type_code": 16}
    generic.vw_revert_last()
    assert last_revert_ops(fake) == [{"op": "resource", "name": "Tomcat copy"}]


def test_create_pio_reverts_created_uuid(fake):
    out = drawing.vw_create_pio("Truss", 0, 0, parameters={"Length": "10'"})
    assert out["uuid"] == "pio-1" and "document" not in out
    assert fake.calls[0][1]["parameters"] == {"Length": "10'"}
    generic.vw_revert_last()
    assert last_revert_ops(fake) == [{"op": "created", "uuid": "pio-1"}]


def test_set_pio_parameters_reports_after_and_reverts_fields(fake):
    out = drawing.vw_set_pio_parameters("ld-1", {"Channel": "7"})
    assert out == {"uuid": "ld-1", "plugin": "Lighting Device", "after": {"Channel": "7"}}
    generic.vw_revert_last()
    assert last_revert_ops(fake) == [
        {"op": "fields", "uuid": "ld-1", "record": "Lighting Device", "before": {"Channel": "1"}}
    ]


def test_layer_and_class_revert_by_name(fake):
    drawing.vw_create_layer("Truss", scale=48)
    drawing.vw_create_class("Lighting-Truss")
    generic.vw_revert_last()
    assert last_revert_ops(fake) == [{"op": "class", "name": "Lighting-Truss"}]
    generic.vw_revert_last()
    assert last_revert_ops(fake) == [{"op": "layer", "name": "Truss"}]


def test_move_reverts_with_negated_offsets(fake):
    drawing.vw_move_objects(["a", "b"], dx=1, dy=-2, dz=3)
    generic.vw_revert_last()
    assert last_revert_ops(fake) == [
        {"op": "move", "uuid": "a", "dx": 1, "dy": -2, "dz": 3},
        {"op": "move", "uuid": "b", "dx": 1, "dy": -2, "dz": 3},
    ]


def test_delete_is_a_revert_barrier_and_needs_uuids(fake):
    with pytest.raises(ToolError, match="no uuids"):
        drawing.vw_delete_objects([])
    assert drawing.vw_delete_objects(["a"]) == {"deleted": 1}
    with pytest.raises(ToolError, match="vw_delete_objects"):
        generic.vw_revert_last()


def test_set_view_is_not_journaled(fake, tmp_path):
    assert drawing.vw_set_view("iso", fit=True) == {"view": "iso", "fit": True}
    with pytest.raises(ToolError, match="nothing to revert"):
        generic.vw_revert_last()


# ---- vwlib round trips through the real bridge with a fake vs -----------------

class FakeDoc:
    """Just enough of `vs` for the new helpers. Handles are ints."""

    def __init__(self, vs):
        self.objects = {}  # handle -> dict(type, uuid, name, class, layer, x, y, z, pio, fields)
        self.layers = {"Design-1": 1}
        self.active_layer = "Design-1"
        self.classes = ["None", "Dimension", "Truss", "Lighting-Truss"]
        self.active_class = "None"
        self.resources = {"Tomcat 12": 50}  # name -> handle (symbol defs in document)
        self.library = {"/lib/Truss.vwx": ["Tomcat 12", "Tomcat 20"]}
        self.events = []
        self.next = 100
        v = vs
        v.GetFName = lambda: "Plot.vwx"
        v.GetObjectUuid = lambda h: self.objects[h]["uuid"]
        v.GetObjectByUuid = lambda u: next((h for h, o in self.objects.items() if o["uuid"] == u), 0)
        v.GetTypeN = lambda h: self.objects[h]["type"] if h in self.objects else (16 if h in self.resources.values() else 0)
        v.GetName = lambda h: h[1] if isinstance(h, tuple) else next(
            (n for n, hh in self.resources.items() if hh == h), self.objects.get(h, {}).get("name", "none"))
        v.GetObject = lambda name: self.resources.get(name, 0)
        v.GetClass = lambda h: self.objects[h]["class"]
        v.SetClass = lambda h, c: self.objects[h].__setitem__("class", c)
        v.GetLayer = lambda h: self.layers[self.objects[h]["layer"]]
        v.GetLName = lambda lh: next(n for n, hh in self.layers.items() if hh == lh)
        v.GetBBox = lambda h: ((0, 0), (1, 1))
        v.ForEachObject = lambda fn, crit: [fn(hh) for hh in list(self.objects)]
        v.NumRecords = lambda h: 0
        v.GetParametricRecord = lambda h: ("rec", self.objects[h]["pio"]) if self.objects[h]["pio"] else 0
        v.NumFields = lambda rec: len(PIO_FIELDS[rec[1]])
        v.GetFldName = lambda rec, i: PIO_FIELDS[rec[1]][i - 1]
        v.GetRField = lambda h, rec, f: self.objects[h]["fields"].get(f, "")
        v.SetRField = lambda h, rec, f, val: self.objects[h]["fields"].__setitem__(f, val)
        v.ResetObject = lambda h: self.events.append(("reset", h))
        v.DelObject = lambda h: self._delete(h)
        v.HMove = lambda h, dx, dy: self._move(h, dx, dy, 0)
        v.Move3DObj = lambda h, dx, dy, dz: self._move(h, dx, dy, dz)
        # layers / classes
        v.GetLayerByName = lambda n: self.layers.get(n, 0)
        v.ActLayer = lambda: self.layers[self.active_layer]
        v.CreateLayer = lambda n, t: self._create_layer(n, t)
        v.SetLScale = lambda lh, s: self.events.append(("scale", lh, s))
        v.SetActiveLayerN = lambda lh: setattr(self, "active_layer", v.GetLName(lh))
        v.Layer = lambda n: self.events.append(("vs.Layer!", n))
        v.ClassNum = lambda: len(self.classes)
        v.ClassList = lambda i: self.classes[i - 1]
        v.ActiveClass = lambda: self.active_class
        v.NameClass = lambda n: (self.classes.append(n) if n not in self.classes else None) or setattr(self, "active_class", n)
        v.DelClass = lambda n: self.classes.remove(n)
        # views
        v.SetViewVector = lambda loc, target, up: self.events.append(("view", loc, up))
        v.DoMenuTextByName = lambda name, chunk: self.events.append(("menu", name))
        v.ReDrawAll = lambda: None
        # libraries
        v.BuildResourceListN = lambda t, path: ((t, path), len(self.library[path]))
        v.GetNameFromResourceList = lambda lid, i: self.library[lid[1]][i - 1]
        v.ImportResourceToCurrentFile = lambda lid, i: self._import(self.library[lid[1]][i - 1])
        v.SetName = lambda h, n: self._rename(h, n)
        # PIO creation
        v.CreateCustomObjectN = lambda name, pt, rot, pref: self._create(86, pio=name, x=pt[0], y=pt[1]) if name in PIO_FIELDS else 0
        v.Symbol = lambda name, pt, rot: self._create(15, name=name, x=pt[0], y=pt[1])
        v.LNewObj = lambda: max(self.objects)

    def _create(self, t, **kw):
        h = self.next
        self.next += 1
        o = {"type": t, "uuid": "u%d" % h, "name": "none", "class": "None", "layer": self.active_layer,
             "x": 0, "y": 0, "z": 0, "pio": None, "fields": {}}
        o.update(kw)
        if o["pio"]:
            o["fields"] = {f: "" for f in PIO_FIELDS[o["pio"]]}
        self.objects[h] = o
        return h

    def _delete(self, h):
        self.events.append(("del", h))
        self.objects.pop(h, None)
        for name, hh in list(self.resources.items()):
            if hh == h:
                del self.resources[name]
        for name, lh in list(self.layers.items()):
            if lh == h:
                del self.layers[name]

    def _move(self, h, dx, dy, dz):
        o = self.objects[h]
        o["x"] += dx; o["y"] += dy; o["z"] += dz

    def _create_layer(self, n, t):
        self.layers[n] = lh = self.next
        self.next += 1
        self.active_layer = n
        return lh

    def _import(self, name):
        h = self.next
        self.next += 1
        self.resources[name] = h
        return h

    def _rename(self, h, n):
        for name, hh in list(self.resources.items()):
            if hh == h:
                del self.resources[name]
                self.resources[n] = h


PIO_FIELDS = {"Truss": ["Length", "Truss Type"], "Lighting Device": ["Channel", "Purpose"]}


class Runner:
    def __init__(self, root, vs):
        self.root, self.vs = root, vs

    def __call__(self):
        threading.Thread(target=vwmcp_bridge.run_pending, args=(self.root,), kwargs={"vs_module": self.vs}).start()


@pytest.fixture
def doc(fake_vs, root, tmp_path, monkeypatch):
    d = FakeDoc(fake_vs)
    b = Bridge(root=root, trigger=Runner(root, fake_vs), poll_interval=0.01, timeout=2)
    monkeypatch.setattr(app, "get_bridge", lambda: b)
    monkeypatch.setattr(app, "get_journal", lambda: Journal(tmp_path / "journal.jsonl"))
    return d


def test_create_layer_restores_active_layer_without_vs_layer(doc):
    out = drawing.vw_create_layer("Truss", scale=48)
    assert out == {"name": "Truss", "kind": "design", "active": False}
    assert "Truss" in doc.layers and doc.active_layer == "Design-1"
    assert ("scale", doc.layers["Truss"], 48.0) in doc.events
    assert not any(e[0] == "vs.Layer!" for e in doc.events)
    with pytest.raises(ToolError, match="already exists"):
        drawing.vw_create_layer("Truss")
    lh = doc.layers["Truss"]
    assert generic.vw_revert_last()["deleted"] == 1
    assert ("del", lh) in doc.events and "Truss" not in doc.layers


def test_create_class_keeps_active_class_and_reverts(doc):
    drawing.vw_create_class("MCP-Test")
    assert "MCP-Test" in doc.classes and doc.active_class == "None"
    generic.vw_revert_last()
    assert "MCP-Test" not in doc.classes


def test_create_pio_sets_parameters_and_reverts(doc, tmp_path):
    out = drawing.vw_create_pio("Truss", 1, 2, parameters={"Length": "10"}, class_name="Lighting-Truss")
    h = doc.objects and max(doc.objects)
    assert out["plugin"] == "Truss" and out["class"] == "Lighting-Truss"
    assert doc.objects[h]["class"] == "Lighting-Truss"  # applied by the second job
    assert doc.objects[h]["fields"]["Length"] == "10" and ("reset", h) in doc.events
    assert drawing.vw_get_pio_parameters(out["uuid"]) == {"plugin": "Truss", "fields": {"Length": "10", "Truss Type": ""}}
    generic.vw_revert_last()
    assert h not in doc.objects


def test_create_pio_with_bad_parameter_places_nothing(doc):
    with pytest.raises(ToolError, match="unknown field"):
        drawing.vw_create_pio("Truss", 0, 0, parameters={"Lenght": "10"})
    assert doc.objects == {}


def test_create_pio_unknown_plugin(doc):
    with pytest.raises(ToolError, match="not available"):
        drawing.vw_create_pio("Flying Pig", 0, 0)


def test_create_pio_unknown_class_leaves_object_but_errors(doc):
    with pytest.raises(ToolError, match="no class named"):
        drawing.vw_create_pio("Truss", 0, 0, class_name="Nope")
    assert len(doc.objects) == 1  # created in job 1; revertable
    generic.vw_revert_last()
    assert doc.objects == {}


def test_set_pio_parameters_then_revert(doc):
    uuid = drawing.vw_create_pio("Lighting Device", 0, 0)["uuid"]
    out = drawing.vw_set_pio_parameters(uuid, {"Channel": "7"})
    assert out["after"]["Channel"] == "7"
    generic.vw_revert_last()
    h = max(doc.objects)
    assert doc.objects[h]["fields"]["Channel"] == ""


def test_move_and_revert(doc):
    a = drawing.vw_create_pio("Truss", 0, 0)["uuid"]
    b = drawing.vw_create_pio("Truss", 5, 5)["uuid"]
    assert drawing.vw_move_objects([a, b], dx=1, dy=2) == {"moved": 2}
    assert [ (o["x"], o["y"]) for o in doc.objects.values()] == [(1, 2), (6, 7)]
    drawing.vw_move_objects([a], dz=3)
    assert doc.objects[max(doc.objects) - 1]["z"] == 3
    generic.vw_revert_last()
    generic.vw_revert_last()
    assert [(o["x"], o["y"], o["z"]) for o in doc.objects.values()] == [(0, 0, 0), (5, 5, 0)]
    with pytest.raises(ToolError, match="no object with uuid"):
        drawing.vw_move_objects([a, "nope"], dx=1)
    assert doc.objects[max(doc.objects) - 1]["x"] == 0


def test_delete_is_all_or_nothing(doc):
    a = drawing.vw_create_pio("Truss", 0, 0)["uuid"]
    with pytest.raises(ToolError, match="nope"):
        drawing.vw_delete_objects([a, "nope"])
    assert len(doc.objects) == 1
    assert drawing.vw_delete_objects([a]) == {"deleted": 1}
    assert doc.objects == {}


def test_set_view_variants(doc):
    drawing.vw_set_view("iso", fit=True)
    assert ("view", [1, -1, 1], [0, 0, 1]) in [tuple(e[:1]) + tuple(list(x) for x in e[1:]) for e in doc.events]
    assert ("menu", "Fit To Objects") in doc.events
    drawing.vw_set_view("top_plan")
    assert ("menu", "Standard Views") in doc.events
    with pytest.raises(ToolError, match="unknown view"):
        drawing.vw_set_view("sideways")


def test_library_resources_and_import(doc, monkeypatch):
    import os
    monkeypatch.setattr(os.path, "isfile", lambda p: p in doc.library)
    out = drawing.vw_list_library_resources("/lib/Truss.vwx", name_contains="20")
    assert out == {"path": "/lib/Truss.vwx", "type_code": 16, "count": 1, "names": ["Tomcat 20"]}
    with pytest.raises(ToolError, match="no file"):
        drawing.vw_list_library_resources("/nope.vwx")
    imp = drawing.vw_import_resource("/lib/Truss.vwx", "Tomcat 20")
    assert imp == {"name": "Tomcat 20", "type_code": 16} and "Tomcat 20" in doc.resources
    with pytest.raises(ToolError, match="already in the document"):
        drawing.vw_import_resource("/lib/Truss.vwx", "Tomcat 12")
    copy = drawing.vw_import_resource("/lib/Truss.vwx", "Tomcat 12", new_name="Tomcat 12 (lib)")
    assert copy["name"] == "Tomcat 12 (lib)" and doc.resources["Tomcat 12"] == 50
    with pytest.raises(ToolError, match="is not in"):
        drawing.vw_import_resource("/lib/Truss.vwx", "Nope")
    generic.vw_revert_last()
    assert "Tomcat 12 (lib)" not in doc.resources and doc.resources["Tomcat 12"] == 50


# ---- truss runs ----------------------------------------------------------------

def add_truss_symbol(doc, vs, name="Global Truss F34-300 Straight", length=3000):
    h = doc._import(name)
    doc.symdef_records = getattr(doc, "symdef_records", {})
    doc.symdef_records[h] = {"BrxTrussItemRecord": {
        "Name": "F34-300", "Type": "F34", "ItemType": "Line", "Length": str(length),
        "Height": "290", "Width": "290", "Section": "F34", "Connection": "F34", "Weight": "19.05"}}
    old_rec, old_rf = vs.GetName, vs.GetRField
    vs.NumRecords = lambda hh: len(doc.symdef_records.get(hh, {}))
    vs.GetRecord = lambda hh, i: ("symrec", hh, list(doc.symdef_records[hh])[i - 1])
    vs.GetName = lambda hh: hh[2] if isinstance(hh, tuple) and hh[0] == "symrec" else old_rec(hh)
    vs.GetRField = lambda hh, rec, f: (doc.symdef_records[hh][rec].get(f, "") if hh in doc.symdef_records
                                       else old_rf(hh, rec, f))
    vs.GetUnits = lambda: (25, 3, 2, 1.0, '"', " sq ft")  # feet-inches doc: internal inch
    doc.moves3d = []
    vs.Move3DObj = lambda hh, dx, dy, dz: doc.moves3d.append((hh, dz)) or doc._move(hh, dx, dy, dz)
    PIO_FIELDS["TrussItem"] = ["Symbol", "Name", "Type", "ItemType", "CrossSection", "ConnectionIdent",
                               "Length", "Height", "Width", "TrussSystem", "TrussLine",
                               "TrussSystemLineIdent", "C_START_UUID", "PositionName",
                               "Weight", "Distributed weight"]
    return h


def test_truss_run_places_pieces_on_length_centres_linked(doc, fake_vs):
    add_truss_symbol(doc, fake_vs)
    out = drawing.vw_insert_truss_run("Global Truss F34-300 Straight", 100, 50, 3, rotation=90,
                                      z=120, position_name="US TRUSS", class_name="Truss")
    assert out["system"] == "T0" and out["piece_length"] == pytest.approx(118.11, 0.01)
    assert out["total_length"] == pytest.approx(3 * 118.11, 0.01) and len(out["pieces"]) == 3
    pcs = [o for o in doc.objects.values() if o["pio"] == "TrussItem"]
    assert [round(p["y"], 2) for p in pcs] == [109.06, 227.17, 345.28]
    assert all(p["x"] == pytest.approx(100) for p in pcs)
    assert all(p["z"] == 120 for p in pcs) and len(doc.moves3d) == 3
    f = [p["fields"] for p in pcs]
    assert f[0]["C_START_UUID"] == "" and f[1]["C_START_UUID"] == pcs[0]["uuid"] and f[2]["C_START_UUID"] == pcs[1]["uuid"]
    assert f[0]["Length"] == "3000mm" and f[0]["Height"] == "290mm" and f[0]["Type"] == "F34"
    assert f[0]["TrussSystemLineIdent"] == "T0-1" and f[0]["PositionName"] == "US TRUSS"
    assert all(p["class"] == "Truss" for p in pcs)
    assert f[0]["Weight"] == "19050" and f[0]["Distributed weight"] == "6.35"
    generic.vw_revert_last()
    assert not [o for o in doc.objects.values() if o["pio"] == "TrussItem"]


def test_truss_run_picks_next_free_system(doc, fake_vs):
    add_truss_symbol(doc, fake_vs)
    drawing.vw_insert_truss_run("Global Truss F34-300 Straight", 0, 0, 1)
    assert drawing.vw_insert_truss_run("Global Truss F34-300 Straight", 0, 500, 1)["system"] == "T1"


def test_truss_run_imports_when_given_library_path(doc, fake_vs, monkeypatch):
    import os
    monkeypatch.setattr(os.path, "isfile", lambda p: p in doc.library)
    doc.library["/lib/Truss.vwx"] = ["Global Truss F34-300 Straight"]
    real_import = doc._import

    def importing(name):
        doc._import = real_import
        h = add_truss_symbol(doc, fake_vs, name)  # library symbol carries the record
        doc._import = importing
        return h

    doc._import = importing
    out = drawing.vw_insert_truss_run("Global Truss F34-300 Straight", 0, 0, 2, library_path="/lib/Truss.vwx")
    assert out["imported"] == "Global Truss F34-300 Straight"
    generic.vw_revert_last()
    assert "Global Truss F34-300 Straight" not in doc.resources


def test_truss_run_rejects_non_truss_symbol_and_bad_count(doc, fake_vs):
    with pytest.raises(ToolError, match="import_resource"):
        drawing.vw_insert_truss_run("Nope", 0, 0, 2)
    with pytest.raises(ToolError, match="no BrxTrussItemRecord"):
        drawing.vw_insert_truss_run("Tomcat 12", 0, 0, 2)
    with pytest.raises(ToolError, match="count"):
        drawing.vw_insert_truss_run("Tomcat 12", 0, 0, 0)
