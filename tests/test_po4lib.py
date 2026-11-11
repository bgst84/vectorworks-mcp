"""Tests for the PO4 drawing library (po4lib) as used through vw_exec_python."""

import pytest

from vwmcp.tools import generic as server
from vwmcp.tools import po4 as po4_tools  # registers the po4 library and prelude
from test_server import bridge, journal, vs  # noqa: F401  (fixtures)

def _layer_vs(vs, parent_type, parent_name="LG_EG", parent_obj_name=""):
    calls = vs.calls
    vs.Layer = lambda n: calls.append(("Layer", n))
    vs.GetLayerByName = lambda n: "layer-handle"
    vs.Locus = lambda x, y: calls.append(("Locus",))
    vs.LNewObj = lambda: "probe"
    vs.GetParent = lambda h: "parent"
    vs.GetTypeN = lambda h: parent_type
    vs.GetLName = lambda h: parent_name
    vs.GetName = lambda h: parent_obj_name
    vs.SetLScale = lambda h, s: calls.append(("SetLScale", s))
    vs.FInLayer = lambda h: "o1"
    vs.NextObj = lambda h: 0
    vs.DelObject = lambda h: calls.append(("DelObject", h))


def test_po4lib_is_python39_compatible():
    import ast

    ast.parse(po4_tools.PO4LIB_SOURCE, feature_version=(3, 9))


def test_exec_python_po4_library_is_available(vs):
    out = server.vw_exec_python("po4.configure(AW=0.12)['AW'], po4.CONFIG['BOLD']", libs=["po4"])
    assert out["ok"] and out["value"] == [0.12, "0 graphics-a bold-neu"]


def test_exec_python_po4_read_only_does_not_journal(journal):
    out = server.vw_exec_python("po4.CONFIG['DIM']", modifies_document=False, libs=["po4"])
    assert out == {"ok": True, "value": "2 dimensions-b rohbau", "stdout": "", "error": None,
                   "traceback": None}
    assert journal._load() == []


def test_po4_configure_rejects_unknown_keys():
    out = server.vw_exec_python("po4.configure(XX=1)", libs=["po4"])
    assert out["ok"] is False and "XX" in out["error"]


def test_exec_python_returns_po4_library_warnings(vs):
    out = server.vw_exec_python("po4.warn('Dimension standard missing')\npo4.warn('Dimension standard missing')", libs=["po4"])
    assert out["warning"] == "Dimension standard missing"


def test_po4_layer_on_layer_clears_and_removes_probe(vs):
    _layer_vs(vs, 31)
    out = server.vw_exec_python("po4.layer('LG_EG', scale=50, clear=True)", libs=["po4"], modifies_document=False)
    assert out["ok"] and out["value"] == 1
    assert ("DelObject", "probe") in vs.calls and ("DelObject", "o1") in vs.calls
    assert ("SetLScale", 50) in vs.calls


def test_po4_layer_refuses_inside_symbol_edit_mode(vs):
    _layer_vs(vs, 16, parent_obj_name="Fenster 120")
    out = server.vw_exec_python("po4.layer('LG_EG', scale=50, clear=True)", libs=["po4"], modifies_document=False)
    assert out["ok"] is False and "EditModeError" in out["error"]
    assert "a symbol (Fenster 120)" in out["error"]
    assert ("DelObject", "o1") not in vs.calls and ("SetLScale", 50) not in vs.calls
    assert ("DelObject", "probe") in vs.calls  # probe cleaned up even when refusing
    assert ("Layer", "LG_EG") not in vs.calls  # refused before the layer is created/activated


def test_po4_layer_refuses_when_parent_is_another_layer(vs):
    _layer_vs(vs, 31, parent_name="Other")
    out = server.vw_exec_python("po4.layer('LG_EG')", libs=["po4"], modifies_document=False)
    assert out["ok"] is False and "layer 'Other' instead of on layer 'LG_EG'" in out["error"]


def test_ping_lists_the_po4_library():
    out = server.vw_ping()
    assert "po4" in out["exec_libraries"] and "po4.layer" in out["exec_libraries"]["po4"]


def test_po4_tools_are_registered():
    import asyncio

    import vwmcp.server  # noqa: F401
    from vwmcp.app import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"vw_class_audit", "vw_class_apply", "vw_class_export"} <= names


def test_po4_vwlib_is_python39_compatible():
    import ast

    ast.parse(po4_tools.PO4_VWLIB_SOURCE, feature_version=(3, 9))
