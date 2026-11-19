import struct
import zlib

import pytest

from vwmcp import render


def decode(png):
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", png[16:24])
    pos, idat = 8, b""
    while pos < len(png):
        n, tag = struct.unpack(">I", png[pos:pos + 4])[0], png[pos + 4:pos + 8]
        if tag == b"IDAT":
            idat += png[pos + 8:pos + 8 + n]
        pos += 12 + n
    raw = zlib.decompress(idat)
    rows = [raw[r * (w * 3 + 1) + 1:(r + 1) * (w * 3 + 1)] for r in range(h)]
    return w, h, lambda x, y: tuple(rows[y][x * 3:x * 3 + 3])


def test_canvas_png_roundtrip_and_line():
    cv = render.Canvas(20, 10)
    cv.line(2, 5, 17, 5, (0, 0, 0))
    w, h, px = decode(cv.png())
    assert (w, h) == (20, 10)
    assert px(10, 5) == (0, 0, 0) and px(10, 1) == (255, 255, 255)


def test_fill_is_even_odd_and_clipped():
    cv = render.Canvas(10, 10)
    cv.fill([(-5, 2), (5, 2), (5, 8), (-5, 8)], (221, 0, 0))
    assert cv.pixel(2, 5) == (221, 0, 0) and cv.pixel(7, 5) == (255, 255, 255)


def test_arc_points_follow_vectorworks_angles():
    pts = render.arc_points([0, 0], 2.0, 90.0, 90.0)
    assert pts[0] == pytest.approx([0, 2]) and pts[-1] == pytest.approx([-2, 0])


def test_outline_of_rectangle_uses_bbox_and_arc_uses_center():
    assert render.outline({"type": "Rectangle", "bbox_view": [[0, 0], [2, 1]]}) == (
        [[0, 0], [2, 0], [2, 1], [0, 1]], True)
    path, closed = render.outline({"type": "Arc", "center": [0, 0], "radius": 1, "start_angle": 0, "sweep": 30})
    assert not closed and path[0] == pytest.approx([1, 0])


LAYER = {"layer": "plan", "objects": [
    {"type": "Polygon", "closed": True, "points": [[0, 0], [10, 0], [10, 10], [0, 10]],
     "attrs": {"fill": {"pattern": 1, "back": "#dd0000", "fore": "#000000"},
               "pen": {"color": "#0000ff", "weight": 4, "style": 2}}},
    {"type": "Line", "points": [[0, 5], [10, 5]], "attrs": {"pen": {"color": "#000000", "weight": 4, "style": 2}}},
    {"type": "Text", "origin": [5, 8], "text": "Room"},
]}


def test_render_draws_fill_below_lines_and_reports_view():
    png, info = render.render([LAYER], bbox=[0, 0, 10, 10], max_size=100)
    w, h, px = decode(png)
    assert (w, h) == (100, 100) and info["pixels_per_unit"] == 10
    assert px(30, 20) == (221, 0, 0)          # solid fill
    assert px(50, 50) == (0, 0, 0)            # the line at y=5 lies on top of the fill
    assert info["objects_drawn"] == 2 and info["texts_marked"] == 1


def test_render_without_fills_and_default_bbox_has_margin():
    png, info = render.render([LAYER], max_size=200, fills=False)
    _, _, px = decode(png)
    assert px(100, 60) == (255, 255, 255)
    assert info["bbox"][0] < 0 and info["bbox"][2] > 10


def test_render_rejects_empty_and_bad_bbox():
    with pytest.raises(ValueError):
        render.render([{"layer": "x", "objects": []}])
    with pytest.raises(ValueError):
        render.render([LAYER], bbox=[5, 5, 5, 9])


# ---- exports with symbols, stacking order, scale (new format) -----------------------

def pen(color="#000000", weight=4):
    return {"pen": {"color": color, "weight": weight, "style": 2}}


def solid(back, color="#000000", weight=4, opacity=100):
    return {"fill": {"pattern": 1, "back": back, "fore": "#000000"}, "opacity": opacity, **pen(color, weight)}


# A symbol turned by 90 degrees that contains a square and a nested symbol with one line.
SYMBOLS = {"layer": "plan", "objects": [
    {"type": "Symbol", "symbol": "table", "uuid": "t", "stack": 0, "children": 2,
     "insert": [10, 0], "rotation": 90, "bbox": [[4, 0], [10, 8]]},
    {"type": "Polygon", "uuid": "top", "parent": "t", "depth": 1, "stack": 1, "closed": True,
     "points": [[10, 0], [10, 4], [6, 4], [6, 0]], "attrs": pen()},
    {"type": "Symbol", "symbol": "chair", "uuid": "c", "parent": "t", "depth": 1, "stack": 2, "children": 1,
     "insert": [10, 6], "rotation": 180, "bbox": [[4, 6], [10, 8]]},
    {"type": "Line", "uuid": "leg", "parent": "c", "depth": 2, "stack": 3,
     "points": [[4, 7], [10, 7]], "attrs": pen()},
]}


def test_expanded_symbol_is_drawn_from_its_children():
    png, info = render.render([SYMBOLS], bbox=[0, 0, 10, 10], max_size=100)
    _, _, px = decode(png)
    assert px(60, 80) == (0, 0, 0)            # left edge of the turned square (x = 6)
    assert px(80, 60) == (0, 0, 0)            # its top edge (y = 4)
    assert px(70, 30) == (0, 0, 0)            # the line of the nested symbol (y = 7)
    assert px(40, 50) == (255, 255, 255)      # no box around the symbol extent (x = 4)
    assert info["symbols_expanded"] == 2 and info["symbols_boxed"] == 0 and info["objects_drawn"] == 2


def test_unexpanded_symbol_is_a_gray_box_of_its_extent():
    layer = {"layer": "plan", "objects": [dict(SYMBOLS["objects"][0], children=0)]}
    png, info = render.render([layer], bbox=[0, 0, 10, 10], max_size=100)
    _, _, px = decode(png)
    assert px(40, 50) == render.BOX_GRAY and info["symbols_boxed"] == 1


# A thin light line (drawn first) under a bold filled rectangle (drawn second).
COVERED = {"layer": "plan", "objects": [
    {"type": "Rectangle", "stack": 1, "closed": True, "points": [[2, 2], [8, 2], [8, 8], [2, 8]],
     "attrs": solid("#dd0000", weight=28)},
    {"type": "Line", "stack": 0, "points": [[0, 5], [10, 5]], "attrs": pen("#0000ff", 2)},
]}


def test_stack_order_shows_what_covers_what():
    _, _, stack = decode(render.render([COVERED], bbox=[0, 0, 10, 10], max_size=100)[0])
    _, _, flat = decode(render.render([COVERED], bbox=[0, 0, 10, 10], max_size=100, order="fills_first")[0])
    assert stack(50, 50) == (221, 0, 0)       # the rectangle lies on top of the line
    assert flat(50, 50) == (0, 0, 255)        # all lines above all fills
    assert stack(10, 50) == flat(10, 50) == (0, 0, 255)   # outside the rectangle both show the line


def test_objects_without_stack_are_drawn_in_list_order():
    objs = [{k: v for k, v in o.items() if k != "stack"} for o in COVERED["objects"]]
    _, _, px = decode(render.render([{"layer": "plan", "objects": objs}], bbox=[0, 0, 10, 10], max_size=100)[0])
    assert px(50, 50) == (0, 0, 255)          # the line comes later in the list


def test_fill_opacity_blends_with_what_is_below():
    layer = {"layer": "plan", "objects": [
        {"type": "Polygon", "closed": True, "points": [[0, 0], [10, 0], [10, 10], [0, 10]],
         "attrs": dict(solid("#000000", opacity=50), pen={"style": 0})}]}
    _, _, px = decode(render.render([layer], bbox=[0, 0, 10, 10], max_size=50)[0])
    assert px(25, 25) == (128, 128, 128)


# Meters at 1:100: one point on paper is 0.0254 * 100 / 72 m.
PT = 0.0254 * 100 / 72


def test_pen_weight_is_drawn_at_the_scale_of_the_picture():
    line = {"type": "Line", "points": [[0, 5], [10, 5]], "attrs": pen(weight=28)}     # 0.7 mm
    scaled = {"layer": "plan", "scale": 100, "units_per_inch": 0.0254, "objects": [line]}
    _, _, px = decode(render.render([scaled], bbox=[0, 0, 10, 10], max_size=1000)[0])
    assert px(500, 497) == (0, 0, 0) and px(500, 503) == (0, 0, 0)    # 0.07 m = 7 px wide
    assert px(500, 506) == (255, 255, 255)
    fine = {"type": "Line", "points": [[0, 5], [10, 5]], "attrs": pen(weight=1)}
    _, _, px = decode(render.render([dict(scaled, objects=[fine])], bbox=[0, 0, 10, 10], max_size=100)[0])
    assert px(50, 50) != (255, 255, 255)                              # never thinner than 1 px
    _, _, px = decode(render.render([{"layer": "plan", "objects": [line]}], bbox=[0, 0, 10, 10], max_size=1000)[0])
    assert px(500, 503) == (255, 255, 255)                            # no scale: fixed steps


def test_text_box_estimates_two_lines_at_the_anchor():
    text = {"type": "Text", "text": "AB\rC", "origin": [1, 5], "size_pt": 10, "just": 1, "vertical_align": 1}
    h = 10 * PT
    box = render.text_box(text, PT)
    assert box[0] == pytest.approx([1, 5 - 2 * 1.2 * h]) and box[2] == pytest.approx([1 + 2 * 0.55 * h, 5])
    right_bottom = render.text_box(dict(text, just=3, vertical_align=5), PT)
    assert right_bottom[0] == pytest.approx([1 - 2 * 0.55 * h, 5]) and right_bottom[2] == pytest.approx([1, 5 + 2.4 * h])
    centered = render.text_box(dict(text, just=2, vertical_align=3), PT)
    assert [(centered[0][0] + centered[2][0]) / 2, (centered[0][1] + centered[2][1]) / 2] == pytest.approx([1, 5])
    turned = render.text_box(dict(text, angle=90), PT)
    assert turned[2] == pytest.approx([1, 5 + 2 * 0.55 * h])
    assert render.text_box(text, None) is None and render.text_box({"origin": [0, 0], "text": "x"}, PT) is None


def test_texts_are_drawn_as_boxes_or_crosses():
    text = {"type": "Text", "text": "AB\rC", "origin": [1, 9], "size_pt": 100, "just": 1, "vertical_align": 1}
    layer = {"layer": "plan", "scale": 100, "units_per_inch": 0.0254, "objects": [text]}
    # box: x 1 .. 4.88, y 0.53 .. 9
    png, info = render.render([layer], bbox=[0, 0, 10, 10], max_size=100)
    _, _, px = decode(png)
    assert px(30, 10) == render.TEXT_MARK and px(10, 50) == render.TEXT_MARK      # top and left edge
    assert px(30, 50) == (255, 255, 255) and info["texts_marked"] == 1 and info["texts"] == "boxes"
    _, _, px = decode(render.render([layer], bbox=[0, 0, 10, 10], max_size=100, texts="cross")[0])
    assert px(10, 50) == (255, 255, 255) and px(12, 10) == render.TEXT_MARK
    assert render.extent([layer]) == pytest.approx([1, 9 - 2.4 * 100 * PT, 1 + 1.1 * 100 * PT, 9])


def test_rotated_oval_is_drawn_from_center_and_radii():
    path, closed = render.outline({"type": "Oval", "center": [5, 5], "radii": [3, 1], "rotation": 90})
    assert closed and path[0] == pytest.approx([5, 8])
    assert max(p[0] for p in path) == pytest.approx(6, abs=0.02)


def test_render_rejects_unknown_modes():
    with pytest.raises(ValueError):
        render.render([LAYER], texts="glyphs")
    with pytest.raises(ValueError):
        render.render([LAYER], order="z")
