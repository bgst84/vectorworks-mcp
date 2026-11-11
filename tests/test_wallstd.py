"""Tests for the PO4 wall style audit (pure Python)."""

from vwmcp import wallstd


def _style(name, comps, **data):
    base = {"mark": "", "fire_rating": "", "exterior": False, "load_bearing": False, "firewall": False}
    base.update(data)
    return {"name": name, "components": comps, "data": base}


def _c(name, cl, function=1):
    return {"name": name, "width": 0.1, "class": cl, "function": function}


def test_clean_style_has_no_issues():
    st = _style("W1.1 Aussenwand 410 holzlatten aussteifend",
                [_c("BSP-Platte", "3 material-holzwerkstoff-neu"),
                 _c("Fassadenverkleidung", "6 eBKP-e fassade-holzlatten-neu")],
                mark="W1.1", fire_rating="EI30", exterior=True, load_bearing=True)
    rep = wallstd.audit([st])
    assert rep["clean"] == ["W1.1 Aussenwand 410 holzlatten aussteifend"]
    assert rep["summary"]["with_issues"] == 0


def test_flags_must_agree_with_name():
    st = _style("W4.1 Aussenwand 410 holzlatten nicht tragend", [_c("GKP", "3 material-gkp-neu")],
                mark="W4.1", fire_rating="EI30", exterior=False, load_bearing=True)
    msgs = [i["message"] for i in wallstd.audit_style(st)]
    assert any("Aussen is off, but the name says on" in m for m in msgs)
    assert any("Tragend is on, but the name says off" in m for m in msgs)


def test_component_checks():
    st = _style("Liftschacht gedämmt",
                [_c("Beton", "3 material-massivholz-neu"), _c("Eternit", ""),
                 _c("Hinterlüftung", "0 graphics-c light-neu", function=0)])
    issues = wallstd.audit_style(st)
    sev = {(i.get("component"), i["severity"]) for i in issues}
    assert ("2 Eternit", "error") in sev                      # no class
    assert ("1 Beton", "warning") in sev                      # material mismatch
    assert ("3 Hinterlüftung", "warning") in sev              # graphic class
    assert ("3 Hinterlüftung", "info") in sev                 # no function
    assert any(i["message"].startswith("Name does not follow") for i in issues)
    assert any("Feuerwiderstand empty" in i["message"] for i in issues)


def test_mark_must_match_code_and_skip_info():
    st = _style("W7.1 Innenwand 150", [_c("GKP", "3 material-gkp-neu", function=0)],
                mark="W7", fire_rating="EI30")
    rep = wallstd.audit([st, _style("<Raumabgrenzung>", [])], skip_info=True)
    assert list(rep["styles"]) == ["W7.1 Innenwand 150"]
    assert [i["severity"] for i in rep["styles"]["W7.1 Innenwand 150"]] == ["warning"]


def test_aussteifend_is_not_load_bearing_and_air_gap_class():
    st = _style("W1.2 Aussenwand 410 eternit rot aussteifend",
                [_c("Hinterlüftung", "0 graphics-c light-neu"), _c("Hinterlüftung", "3 material-hinterlüftung-neu")],
                mark="W1.2", fire_rating="EI30", exterior=True, load_bearing=False)
    issues = wallstd.audit_style(st)
    assert not any("Tragend" in i["message"] for i in issues)
    assert {i.get("component") for i in issues} == {"1 Hinterlüftung"}
