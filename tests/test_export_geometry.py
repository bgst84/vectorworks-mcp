"""Geometry export: symbol transforms, expansion, walls and stacking order.

The helper library runs inside Vectorworks; here it is executed against a
small object-tree stand-in for `vs`. That checks our own logic (transforms,
walking, ordering), not how Vectorworks behaves (see docs/vs-notes.md).
"""

import math
import threading
import types

import pytest
import vwmcp_bridge

from vwmcp import calls
from vwmcp.client import Bridge

BLACK = (0, 0, 0)
WHITE = (65535, 65535, 65535)


class Obj:
    def __init__(self, type_, uuid, cls="None", **data):
        self.type, self.uuid, self.cls, self.data = type_, uuid, cls, data
        self.next = None
        self.first = None

    def __str__(self):
        return "<%s>" % self.uuid


def chain(objs):
    for a, b in zip(objs, objs[1:]):
        a.next = b
    return objs[0] if objs else None


def line(uuid, p1, p2, cls="None"):
    return Obj(2, uuid, cls, p1=p1, p2=p2)


def poly(uuid, pts, closed=True):
    return Obj(5, uuid, pts=pts, closed=closed)


def group(uuid, children):
    g = Obj(11, uuid)
    g.first = chain(children)
    return g


def symbol(uuid, name, loc, rot=0.0, flipped=False, cls="None", scale=None):
    return Obj(15, uuid, cls, name=name, loc=loc, rot=rot, flipped=flipped, scale=scale)


class FakeVS(types.ModuleType):
    """The subset of `vs` the geometry export reads."""

    def __init__(self, objects, definitions=None):
        super().__init__("vs")
        self.layer = Obj(31, "layer")
        self.layer.first = chain(objects)
        self.defs = {}
        for name, children in (definitions or {}).items():
            d = Obj(16, "def-" + name)
            d.first = chain(children)
            self.defs[name] = d
        self.definition_reads = []

    # document and layer
    def GetFName(self): return "Test.vwx"
    def ActLayer(self): return self.layer
    def GetLayerByName(self, name): return self.layer if name == "plan" else None
    def GetLName(self, h): return "plan"
    def GetLScale(self, h): return 50.0
    def GetUnits(self): return (1, 1, 1, 25.4, "mm", "sq mm")
    def FInLayer(self, h): return h.first

    # traversal
    def NextObj(self, h): return h.next
    def FInGroup(self, h): return h.first
    def GetTypeN(self, h): return h.type
    def GetClass(self, h): return h.cls
    def GetObjectUuid(self, h): return h.uuid
    def GetObject(self, name): return self.defs.get(name)

    def FInSymDef(self, h):
        self.definition_reads.append(h.uuid)
        return h.first

    # geometry
    def GetSegPt1(self, h): return h.data["p1"]
    def GetSegPt2(self, h): return h.data["p2"]
    def GetVertNum(self, h): return len(h.data["pts"])
    def GetPolyPt(self, h, i): return h.data["pts"][i - 1]
    def IsPolyClosed(self, h): return h.data["closed"]
    def HCenter(self, h): return h.data["center"]
    def GetArc(self, h): return h.data["start"], h.data["sweep"]
    def HWidth(self, h): return h.data["w"]
    def HHeight(self, h): return h.data["h"]
    def HAngle(self, h): return h.data.get("angle", 0.0)

    def GetBBox(self, h):
        (cx, cy), w, ht = h.data["center"], h.data["w"], h.data["h"]
        return (cx - w / 2, cy + ht / 2), (cx + w / 2, cy - ht / 2)

    # symbols
    def GetSymName(self, h): return h.data["name"]
    def GetSymLoc(self, h): return h.data["loc"]
    def GetSymRot(self, h): return h.data["rot"]
    def IsObjectFlipped(self, h): return h.data["flipped"]
    def GetObjectVariableInt(self, h, i): return 2 if h.data["scale"] else 1
    def GetObjectVariableReal(self, h, i): return h.data["scale"]

    # walls
    def GetWallThickness(self, h): return True, h.data["width"]
    def GetWallStyle(self, h): return h.data.get("style", "")

    # text
    def GetTextOrientation(self, h): return h.data["origin"], h.data.get("angle", 0.0), False
    def GetText(self, h): return h.data["text"]
    def GetTextSize(self, h, pos): return h.data["size"]
    def GetTextJust(self, h): return 1
    def GetTextVerticalAlign(self, h): return 1
    def GetTextFont(self, h, pos): return 7
    def GetFontName(self, i): return "Helvetica"

    # attributes
    def GetFPat(self, h): return h.data.get("fpat", 0)
    def GetFillBack(self, h): return WHITE
    def GetFillFore(self, h): return BLACK
    def IsFPatByClass(self, h): return False
    def IsFillColorByClass(self, h): return False
    def GetPenFore(self, h): return BLACK
    def GetLW(self, h): return 4
    def GetLSN(self, h): return 2
    def IsPenColorByClass(self, h): return False
    def IsLWByClass(self, h): return False
    def IsLSByClass(self, h): return False
    def GetOpacity(self, h): return h.data.get("opacity", 100)
    def GetVectorFill(self, h): return ("hatch" in h.data), h.data.get("hatch", "")


def load(vs):
    mod = types.ModuleType("vwlib_under_test")
    mod.vs = vs
    exec(compile(calls.VWLIB_SOURCE, "vwlib.py", "exec"), mod.__dict__)
    return mod


def export(objects, definitions=None, **kw):
    return load(FakeVS(objects, definitions)).export_geometry(**kw)


@pytest.fixture(scope="module")
def lib():
    return load(FakeVS([]))


# ---- transforms (pure) -----------------------------------------------------------

@pytest.mark.parametrize("rotation, expected", [
    (0, (12, 21)), (90, (9, 22)), (180, (8, 19)), (-90, (11, 18)),
])
def test_symbol_map_rotates_then_moves(lib, rotation, expected):
    m = lib._xf_symbol((10, 20), rotation)
    assert lib._xf_pt(m, (2, 1)) == pytest.approx(expected)


def test_symbol_map_mirrors_x_before_rotating(lib):
    assert lib._xf_pt(lib._xf_symbol((10, 20), 0, True), (2, 1)) == pytest.approx((8, 21))
    assert lib._xf_pt(lib._xf_symbol((10, 20), 90, True), (2, 1)) == pytest.approx((9, 18))


def test_symbol_map_scales_first(lib):
    assert lib._xf_pt(lib._xf_symbol((1, 1), 90, False, (2, 3)), (1, 1)) == pytest.approx((-2, 3))


def test_composed_map_is_outer_after_inner(lib):
    outer, inner = lib._xf_symbol((10, 0), 90), lib._xf_symbol((1, 0), 90)
    m = lib._xf_mul(outer, inner)
    assert lib._xf_pt(m, (1, 0)) == pytest.approx(lib._xf_pt(outer, lib._xf_pt(inner, (1, 0))))
    assert lib._xf_pt(m, (1, 0)) == pytest.approx((9, 1))


@pytest.mark.parametrize("rotation", [0, 90, 180, -90, 37.5])
@pytest.mark.parametrize("mirrored", [False, True])
def test_decompose_gives_the_placement_back(lib, rotation, mirrored):
    insert, rot, mir, scale = lib._xf_decompose(lib._xf_symbol((3, -4), rotation, mirrored, (2, 2)))
    assert insert == pytest.approx((3, -4)) and mir is mirrored and scale == pytest.approx((2, 2))
    assert math.cos(math.radians(rot - rotation)) == pytest.approx(1)


def test_wall_outline_is_centered_on_its_line(lib):
    assert lib._wall_outline((0, 0), (4, 0), 0.2) == pytest.approx([(0, 0.1), (4, 0.1), (4, -0.1), (0, -0.1)])
    assert lib._wall_outline((0, 0), (0, 2), 1.0)[0] == pytest.approx((-0.5, 0))


def test_rect_points_turn_around_the_center(lib):
    assert lib._rect_points((5, 5), 4, 2, 90) == pytest.approx([(6, 3), (6, 7), (4, 7), (4, 3)])


def test_place_carries_an_arc_through_a_mirror(lib):
    arc = {"type_code": 6, "center": (1, 0), "radius": 1.0, "start_angle": 0.0, "sweep": 90.0,
           "points": [(2, 0), (1, 1)]}
    out = lib._place(arc, lib._xf_symbol((0, 0), 0, True), 4)
    assert out["center"] == [-1, 0] and out["radius"] == 1
    assert out["start_angle"] == 180 and out["sweep"] == -90
    assert out["points"] == [[-2, 0], [-1, 1]]
    # the transformed arc still runs from its start point to its end point
    end = math.radians(out["start_angle"] + out["sweep"])
    assert [out["center"][0] + math.cos(end), out["center"][1] + math.sin(end)] == pytest.approx([-1, 1])


def test_place_rotates_arc_and_text_angles(lib):
    m = lib._xf_symbol((0, 0), 90)
    arc = lib._place({"center": (0, 0), "radius": 2.0, "start_angle": 330.0, "sweep": 30.0}, m, 4)
    assert arc["start_angle"] == pytest.approx(60) and arc["sweep"] == 30
    text = lib._place({"origin": (1, 0), "angle": 0.0}, m, 4)
    assert text["origin"] == [0, 1] and text["angle"] == pytest.approx(90)


def test_extent_of_arcs_and_ovals_is_exact(lib):
    quarter = {"center": (0, 0), "radius": 2.0, "start_angle": 45.0, "sweep": 90.0}
    assert lib._bbox_of(lib._extent_pts(quarter), 4) == [[-1.4142, 1.4142], [1.4142, 2]]
    clockwise = {"center": (0, 0), "radius": 1.0, "start_angle": 10.0, "sweep": -20.0}
    assert lib._bbox_of(lib._extent_pts(clockwise), 4) == [[0.9848, -0.1736], [1, 0.1736]]
    oval = {"center": (1, 1), "radii": (2, 1), "rotation": 90.0}
    assert lib._bbox_of(lib._extent_pts(oval), 4) == [[0, -1], [2, 3]]


def test_place_without_a_map_only_rounds(lib):
    arc = {"center": (0.123456, 0), "radius": 1.0, "start_angle": 330.0, "sweep": 30.0}
    assert lib._place(arc, None, 4) == {"center": [0.1235, 0], "radius": 1.0, "start_angle": 330.0, "sweep": 30.0}


# ---- export ------------------------------------------------------------------------

CHAIR = [poly("seat", [(0, 0), (1, 0), (1, 1), (0, 1)])]
TABLE = [line("edge", (0, 0), (2, 0)), symbol("chair-in-table", "chair", (3, 0), 90)]
DEFS = {"chair": CHAIR, "table": TABLE}


def by_uuid(data):
    out = {}
    for o in data["objects"]:
        out.setdefault(o["uuid"], []).append(o)
    return out


def test_symbol_instance_reports_placement_and_extent():
    data = export([symbol("s1", "chair", (10, 20), 90, cls="furniture")], DEFS)
    (s,) = data["objects"]
    assert s["type"] == "Symbol" and s["symbol"] == "chair" and s["class"] == "furniture"
    assert s["insert"] == [10, 20] and s["rotation"] == 90 and s["mirrored"] is False
    assert s["bbox"] == [[9, 20], [10, 21]] and s["center"] == [9.5, 20.5]
    assert "scale" not in s and "children" not in s and "bbox_view" not in s


def test_mirrored_and_scaled_instance():
    data = export([symbol("s1", "chair", (0, 0), 0, flipped=True, scale=2.0)], DEFS)
    (s,) = data["objects"]
    assert s["mirrored"] is True and s["scale"] == [2, 2]
    assert s["bbox"] == [[-2, 0], [0, 2]]


def test_expand_emits_children_in_layer_coordinates():
    data = export([symbol("s1", "chair", (10, 20), 90)], DEFS, symbols="expand")
    s, seat = data["objects"]
    assert s["children"] == 1
    assert seat["parent"] == "s1" and seat["depth"] == 1 and seat["type"] == "Polygon"
    assert seat["points"] == [[10, 20], [10, 21], [9, 21], [9, 20]]


def test_nested_symbols_expand_with_composed_maps():
    data = export([symbol("t1", "table", (10, 0), 90)], DEFS, symbols="expand")
    objs = by_uuid(data)
    assert objs["edge"][0]["points"] == [[10, 0], [10, 2]]
    inner = objs["chair-in-table"][0]
    assert inner["parent"] == "t1" and inner["depth"] == 1
    assert inner["insert"] == [10, 3] and inner["rotation"] == pytest.approx(180)
    seat = objs["seat"][0]
    assert seat["parent"] == "chair-in-table" and seat["depth"] == 2
    assert seat["points"] == [[10, 3], [9, 3], [9, 2], [10, 2]]
    # the outer extent includes the nested symbol
    assert objs["t1"][0]["bbox"] == [[9, 0], [10, 3]]


def test_symbol_depth_limits_the_expansion():
    data = export([symbol("t1", "table", (0, 0))], DEFS, symbols="expand", symbol_depth=1)
    objs = by_uuid(data)
    assert "seat" not in objs
    inner = objs["chair-in-table"][0]
    assert "children" not in inner and inner["bbox"] == [[2, 0], [3, 1]]
    assert [o["uuid"] for o in export([symbol("t1", "table", (0, 0))], DEFS, symbols="expand",
                                      symbol_depth=0)["objects"]] == ["t1"]


def test_each_definition_is_read_once():
    vs = FakeVS([symbol("a", "table", (0, 0)), symbol("b", "table", (5, 0), 90),
                 symbol("c", "chair", (9, 9))], DEFS)
    load(vs).export_geometry(symbols="expand")
    assert sorted(vs.definition_reads) == ["def-chair", "def-table"]


def test_stack_follows_drawing_order_through_groups_and_symbols():
    objects = [
        line("a", (0, 0), (1, 0)),
        group("g", [line("b", (0, 1), (1, 1)), group("g2", [line("c", (0, 2), (1, 2))])]),
        symbol("s", "chair", (5, 5)),
        line("d", (0, 3), (1, 3)),
    ]
    data = export(objects, DEFS, symbols="expand")
    assert [(o["uuid"], o["stack"]) for o in data["objects"]] == [
        ("a", 0), ("b", 1), ("c", 2), ("s", 3), ("seat", 4), ("d", 5)]
    objs = by_uuid(data)
    assert objs["b"][0]["group"] == "g" and objs["c"][0]["group"] == "g2" and "group" not in objs["a"][0]


def test_class_filter_keeps_stack_positions_and_symbol_children():
    objects = [line("a", (0, 0), (1, 0), cls="x"), symbol("s", "chair", (0, 0), cls="keep"),
               line("b", (0, 0), (1, 0), cls="keep")]
    data = export(objects, DEFS, classes=["keep"], symbols="expand")
    assert [(o["uuid"], o["stack"]) for o in data["objects"]] == [("s", 1), ("seat", 2), ("b", 3)]


def test_limit_counts_expanded_children():
    data = export([symbol("t1", "table", (0, 0)), line("z", (0, 0), (1, 1))], DEFS, symbols="expand", limit=3)
    assert len(data["objects"]) == 3 and data["truncated"] is True


def test_wall_exports_outline_style_and_width():
    data = export([Obj(68, "w", p1=(0, 0), p2=(4, 0), width=0.2, style="Brick 20")])
    (w,) = data["objects"]
    assert w["type"] == "Wall" and w["wall_style"] == "Brick 20" and w["width"] == 0.2 and w["closed"] is True
    assert w["points"] == [[0, 0.1], [4, 0.1], [4, -0.1], [0, -0.1]] and w["line"] == [[0, 0], [4, 0]]


def test_rectangle_in_a_rotated_symbol_keeps_its_shape():
    defs = {"box": [Obj(3, "r", center=(2, 1), w=4.0, h=2.0)]}
    data = export([Obj(3, "top", center=(2, 1), w=4.0, h=2.0), symbol("s", "box", (0, 0), 90)],
                  defs, symbols="expand")
    top, s, r = data["objects"]
    assert top["points"] == [[0, 0], [4, 0], [4, 2], [0, 2]] and top["closed"] is True
    assert top["bbox_view"] == [[0, 0], [4, 2]] and top["center"] == [2, 1]      # kept for old consumers
    assert r["points"] == [[0, 0], [0, 4], [-2, 4], [-2, 0]] and "bbox_view" not in r
    assert s["bbox"] == [[-2, 0], [0, 4]]


def test_oval_reports_radii_and_rotation():
    defs = {"o": [Obj(4, "oval", center=(0, 0), w=4.0, h=2.0)]}
    data = export([symbol("s", "o", (10, 10), 90)], defs, symbols="expand")
    s, oval = data["objects"]
    assert oval["center"] == [10, 10] and oval["radii"] == [2, 1] and oval["rotation"] == pytest.approx(90)
    assert s["bbox"] == [[9, 8], [11, 12]]


def test_text_reports_font_size_and_alignment():
    data = export([Obj(10, "t", origin=(1, 2), text="Room\r12.5", size=8.0)])
    (t,) = data["objects"]
    assert t["font"] == "Helvetica" and t["size_pt"] == 8 and t["size_raw"] == 8
    assert t["just"] == 1 and t["vertical_align"] == 1 and t["origin"] == [1, 2]


def test_attrs_report_hatch_name_and_opacity():
    data = export([Obj(5, "p", pts=[(0, 0), (1, 0), (1, 1)], closed=True, fpat=-5, hatch="Brick", opacity=40),
                   line("l", (0, 0), (1, 0))])
    p, ln = data["objects"]
    assert p["attrs"]["fill"]["hatch"] == "Brick" and p["attrs"]["opacity"] == 40
    assert "hatch" not in ln["attrs"]["fill"] and ln["attrs"]["opacity"] == 100
    assert "attrs" not in export([line("l", (0, 0), (1, 0))], attributes=False)["objects"][0]


def test_export_reports_layer_scale_and_units():
    data = export([line("l", (0, 0), (1, 0))], layer="plan")
    assert data["layer"] == "plan" and data["scale"] == 50 and data["units_per_inch"] == 25.4
    assert data["document"] == "Test.vwx" and data["truncated"] is False


def test_unknown_layer_and_bad_symbols_mode_raise():
    with pytest.raises(LookupError):
        export([], layer="nope")
    with pytest.raises(ValueError):
        export([], symbols="all")


def test_export_runs_through_the_bridge(root):
    """Same call as the MCP tool makes, through the real bridge code."""
    vs = FakeVS([symbol("t1", "table", (10, 0), 90)], DEFS)

    def trigger():
        threading.Thread(target=vwmcp_bridge.run_pending, args=(root,), kwargs={"vs_module": vs}).start()

    bridge = Bridge(root=root, trigger=trigger, poll_interval=0.01, timeout=5)
    data = calls.call(bridge, "export_geometry", symbols="expand", symbol_depth=3)
    assert [o["uuid"] for o in data["objects"]] == ["t1", "edge", "chair-in-table", "seat"]
    assert data["objects"][3]["points"] == [[10, 3], [9, 3], [9, 2], [10, 2]]
