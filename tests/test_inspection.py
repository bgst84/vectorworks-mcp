import json

import pytest

from mcp.server.mcpserver.exceptions import ToolError

from vwmcp import app
from vwmcp.tools import generic


EXPORT = {
    "document": "plan.vwx", "layer": "Ground floor", "truncated": False,
    "objects": [
        {"uuid": "a", "type": "Line", "class": "light", "points": [[0, 0], [2, 0]]},
        {"uuid": "b", "type": "Polygon", "class": "bold", "points": [[0, 0], [1, 3], [-1, 1]]},
        {"uuid": "c", "type": "Text", "class": "light", "origin": [5, 1], "text": "Kitchen"},
    ],
}


def test_geometry_summary_counts_and_extent():
    s = generic.geometry_summary(EXPORT)
    assert s["count"] == 3
    assert s["by_type"] == {"Line": 1, "Polygon": 1, "Text": 1}
    assert s["by_class"] == {"light": 2, "bold": 1}
    assert s["extent"] == [[-1, 0], [5, 3]]


@pytest.fixture
def export_call(monkeypatch):
    seen = {}

    def call_result(bridge, fn, timeout=None, **kw):
        seen.update(fn=fn, timeout=timeout, **kw)
        return {"value": EXPORT, "stdout": ""}

    monkeypatch.setattr(generic.calls, "call_result", call_result)
    monkeypatch.setattr(app, "get_bridge", lambda: None)
    return seen


def test_export_geometry_returns_data_inline(export_call):
    assert generic.vw_export_geometry(layer="Ground floor") == EXPORT
    assert export_call["fn"] == "export_geometry" and export_call["layer"] == "Ground floor"


def test_export_geometry_writes_file_and_returns_summary(export_call, tmp_path):
    out = generic.vw_export_geometry(out_path=str(tmp_path / "sub" / "eg.json"))
    assert out["count"] == 3 and out["path"].endswith("eg.json")
    assert json.loads((tmp_path / "sub" / "eg.json").read_text()) == EXPORT


def test_export_geometry_asks_for_attributes_by_default(export_call):
    generic.vw_export_geometry()
    assert export_call["attributes"] is True
    generic.vw_export_geometry(attributes=False)
    assert export_call["attributes"] is False


def test_export_geometry_passes_symbol_expansion(export_call):
    generic.vw_export_geometry()
    assert export_call["symbols"] == "instances" and export_call["symbol_depth"] == 3
    generic.vw_export_geometry(symbols="expand", symbol_depth=1)
    assert export_call["symbols"] == "expand" and export_call["symbol_depth"] == 1
    with pytest.raises(ToolError):
        generic.vw_export_geometry(symbols="everything")


def test_geometry_summary_includes_symbol_extents():
    data = dict(EXPORT, objects=EXPORT["objects"] + [
        {"uuid": "s", "type": "Symbol", "class": "light", "symbol": "chair", "insert": [9, 9],
         "bbox": [[8, -2], [10, 9]], "center": [9, 3.5], "stack": 3},
        {"uuid": "d", "type": "Polygon", "class": "light", "parent": "s", "depth": 1, "stack": 4,
         "points": [[8, -2], [10, -2], [10, 9]]},
    ])
    s = generic.geometry_summary(data)
    assert s["count"] == 5 and s["by_type"]["Symbol"] == 1 and s["extent"] == [[-1, -2], [10, 9]]


def test_render_layers_exports_each_layer_and_returns_png_with_info(export_call, tmp_path):
    img, info = generic.vw_render_layers(layers=["Ground floor"], max_size=120, out_path=str(tmp_path / "v.png"))
    assert export_call["fn"] == "export_geometry" and export_call["attributes"] is True
    assert export_call["symbols"] == "expand"
    assert img.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert (tmp_path / "v.png").read_bytes() == img.data
    info = json.loads(info)
    assert info["layers"] == ["Ground floor"] and info["objects_drawn"] == 2 and info["texts_marked"] == 1
    assert info["order"] == "stack" and info["truncated"] is False and info["path"].endswith("v.png")


def test_render_layers_passes_modes_and_rejects_unknown_ones(export_call):
    generic.vw_render_layers(symbols="instances", texts="cross", order="fills_first", max_size=60)
    assert export_call["symbols"] == "instances"
    for bad in ({"symbols": "all"}, {"texts": "glyphs"}, {"order": "z"}):
        with pytest.raises(ToolError):
            generic.vw_render_layers(**bad)


def test_render_layers_returns_an_image_and_text_over_mcp(export_call):
    import asyncio

    result = asyncio.run(app.mcp.call_tool("vw_render_layers", {"max_size": 60}))
    blocks = result if isinstance(result, list) else getattr(result, "content", result)
    blocks = blocks[0] if isinstance(blocks, tuple) else blocks
    assert [b.type for b in blocks] == ["image", "text"]
    assert json.loads(blocks[1].text)["size"]


def test_render_layers_leaves_out_excluded_classes(export_call, monkeypatch):
    monkeypatch.setattr(app, "RENDER_EXCLUDED_CLASSES", [])       # extensions may have registered some
    _, info = generic.vw_render_layers(max_size=60)
    assert json.loads(info)["excluded_classes"] == [] and json.loads(info)["objects_excluded"] == 0
    _, info = generic.vw_render_layers(max_size=60, exclude_classes=["bold"])
    info = json.loads(info)
    assert info["excluded_classes"] == ["bold"] and info["objects_excluded"] == 1 and info["objects_drawn"] == 1


def test_render_layers_uses_registered_default_exclusions(export_call, monkeypatch):
    monkeypatch.setattr(app, "RENDER_EXCLUDED_CLASSES", [])
    app.register_render_excluded_classes(["light"])
    app.register_render_excluded_classes(["light"])
    assert app.RENDER_EXCLUDED_CLASSES == ["light"]
    _, info = generic.vw_render_layers(max_size=60)
    info = json.loads(info)
    assert info["excluded_classes"] == ["light"] and info["objects_excluded"] == 2 and info["texts_marked"] == 0
    _, info = generic.vw_render_layers(max_size=60, exclude_classes=[])       # explicit: draw everything
    assert json.loads(info)["objects_excluded"] == 0


def test_screenshot_points_to_render_layers():
    assert "vw_render_layers" in generic.vw_screenshot.__doc__
