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


def test_butt_join_rule():
    comps = [dict(_c("Putz", "3 material-verputz-neu"), auto_join=True),
             dict(_c("Backstein", "3 material-backstein-bestand"), auto_join=False),
             dict(_c("Dämmung", "3 material-dämmung horizontal-neu"), auto_join=True)]
    st = _style("W11.1 Aussenwand 595 massiv gedämmt tragend", comps, mark="W11.1", fire_rating="REI60",
                exterior=True, load_bearing=True)
    issues = wallstd.audit_style(st)
    assert {i["component"] for i in issues} == {"1 Putz", "2 Backstein"}


def test_plan_fixes_flags_functions_and_joins():
    comps = [dict(_c("Fassadenverkleidung", "6 eBKP-e fassade-holzlatten-neu", function=0), auto_join=True),
             dict(_c("Hinterlüftung", "3 material-hinterlüftung-neu", function=0), auto_join=True),
             dict(_c("Dämmung Mineralwolle", "3 material-dämmung horizontal-neu", function=0), auto_join=False),
             dict(_c("BSP-Platte", "3 material-holzwerkstoff-neu", function=0), auto_join=True),
             dict(_c("GKP", "3 material-gkp-neu", function=0), auto_join=True)]
    st = _style("W2.1 Aussenwand 410 holzlatten aussteifend tragend", comps, mark="", exterior=True)
    st["core"] = 4
    ch = wallstd.plan_style(st)
    assert ch["data"] == {"mark": "W2.1", "load_bearing": True}
    fns = {c["index"]: c.get("function") for c in ch["components"]}
    assert fns == {1: 4, 2: 5, 3: 2, 4: 1, 5: 3}
    assert {"index": 3, "function": 2, "auto_join": True} in ch["components"]
    assert any("Feuerwiderstand fehlt" in n for n in ch["notes"])


def test_plan_keeps_set_functions_and_skips_clean_styles():
    st = _style("W7.1 Innenwand 150", [dict(_c("GKP", "3 material-gkp-neu", function=3), auto_join=True)],
                mark="W7.1", fire_rating="EI30")
    assert wallstd.plan([st]) == []


def test_structural_layers_are_never_finishes():
    comps = [dict(_c("Beton", "3 material-beton-neu", function=0), auto_join=True),
             dict(_c("Dämmung", "3 material-dämmung horizontal-neu", function=0), auto_join=True)]
    ch = wallstd.plan_style(_style("Brandschutzwand ZG3", comps))
    assert [c.get("function") for c in ch["components"]] == [2]  # only the insulation
    comps = [dict(_c("Dämmung/Toleranz", "3 material-dämmung horizontal-neu dicht", function=0), auto_join=True),
             dict(_c("BSP", "3 material-massivholz-neu", function=0), auto_join=True),
             dict(_c("Holzlattung", "3 material-massivholz-neu", function=0), auto_join=True)]
    ch = wallstd.plan_style(_style("W5.2  Brandmauer tragend aussteifend hinterlüftet", comps,
                                   mark="W5.2", load_bearing=True, firewall=True))
    assert {c["index"]: c.get("function") for c in ch["components"]} == {1: 2, 2: 1, 3: 4}
