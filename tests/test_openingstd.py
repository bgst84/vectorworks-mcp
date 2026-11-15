"""PO4 door/window audit."""

from vwmcp import openingstd


def _o(kind, cl, style="zg_typ1", wall="W1.1", uuid="u"):
    return {"uuid": uuid, "kind": kind, "class": cl, "style": style, "layer": "OG3", "wall_style": wall}


def test_classes_styles_and_walls():
    rep = openingstd.audit([
        _o("Door CW", "6 eBKP-g ausbau-tür-neu", uuid="ok"),
        _o("Door CW", "0 graphics-c light-neu", uuid="badclass"),
        _o("Window CW", "6 eBKP-e fassade-fenster-bestand", style="", uuid="nostyle"),
        _o("Window CW", "6 eBKP-e fassade-fenster-neu", wall=None, uuid="nowall"),
    ])
    bad = {i["uuid"]: i["problems"] for i in rep["issues"]}
    assert set(bad) == {"badclass", "nostyle", "nowall"}
    assert rep["summary"]["with_issues"] == 3
