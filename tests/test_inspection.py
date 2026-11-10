import json

import pytest

from vwmcp import app, screenshot
from vwmcp.tools import generic


def win(id, title="", w=100, h=100, onscreen=True):
    return {"id": id, "title": title, "bounds": {"Width": w, "Height": h}, "onscreen": onscreen}


def test_pick_window_prefers_document_title():
    wins = [win(1, "", 3000, 1800), win(2, "lg_grundlage.vwx", 2000, 1200)]
    assert screenshot.pick_window(wins, "lg_grundlage.vwx")["id"] == 2


def test_pick_window_matches_title_without_extension():
    wins = [win(1, "Palette", 300, 300), win(2, "lg_grundlage - Konstruktionsebene", 2000, 1200)]
    assert screenshot.pick_window(wins, "lg_grundlage.vwx")["id"] == 2


def test_pick_window_falls_back_to_largest_onscreen():
    # Without Screen Recording permission titles are empty.
    wins = [win(1, "", 300, 400), win(2, "", 3000, 1800), win(3, "", 4000, 2000, onscreen=False)]
    assert screenshot.pick_window(wins, "x.vwx")["id"] == 2


def test_pick_window_errors_without_document_window():
    with pytest.raises(screenshot.ScreenshotError):
        screenshot.pick_window([], "x.vwx")
    with pytest.raises(screenshot.ScreenshotError, match="palettes"):
        screenshot.pick_window([win(1, "", 150, 200)], None)


EXPORT = {
    "document": "lg.vwx", "layer": "LG_EG_1928", "truncated": False,
    "objects": [
        {"uuid": "a", "type": "Line", "class": "light", "points": [[0, 0], [2, 0]]},
        {"uuid": "b", "type": "Polygon", "class": "bold", "points": [[0, 0], [1, 3], [-1, 1]]},
        {"uuid": "c", "type": "Text", "class": "light", "origin": [5, 1], "text": "Keller"},
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
    assert generic.vw_export_geometry(layer="LG_EG_1928") == EXPORT
    assert export_call["fn"] == "export_geometry" and export_call["layer"] == "LG_EG_1928"


def test_export_geometry_writes_file_and_returns_summary(export_call, tmp_path):
    out = generic.vw_export_geometry(out_path=str(tmp_path / "sub" / "eg.json"))
    assert out["count"] == 3 and out["path"].endswith("eg.json")
    assert json.loads((tmp_path / "sub" / "eg.json").read_text()) == EXPORT
