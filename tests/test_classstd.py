import json

import pytest

from vwmcp import app, classstd
from vwmcp.journal import Journal
from vwmcp.tools import generic, po4

BOLD = {"name": "0 graphics-a bold-neu", "automatisch_zuweisen": True, "strichstaerke_mm": 0.203,
        "linie": "solid", "fuellung": "solid", "stift_vorne": [221, 0, 0], "stift_hinten": [255, 255, 255],
        "fuellung_vorne": [0, 0, 0], "fuellung_hinten": [0, 0, 0],
        "deckkraft_fuellung": 30, "deckkraft_stift": 100}
LIGHT = {**BOLD, "name": "0 graphics-c light-neu", "strichstaerke_mm": 0.051, "fuellung": "none",
         "fuellung_hinten": [255, 255, 255], "deckkraft_fuellung": 100}
DASH = {**LIGHT, "name": "0 graphics-e dash-neu", "linie": "res:po4 dash"}
STANDARD = {c["name"]: c for c in (BOLD, LIGHT, DASH)}


def test_diff_reports_field_pairs_and_tolerates_rounding():
    actual = {**BOLD, "strichstaerke_mm": 0.2032, "deckkraft_fuellung": 100}
    assert classstd.diff_class(actual, BOLD) == {"deckkraft_fuellung": [100, 30]}


def test_diff_ignores_fill_colors_when_there_is_no_fill():
    actual = {**LIGHT, "fuellung_vorne": [9, 9, 9], "fuellung_hinten": [1, 2, 3]}
    assert classstd.diff_class(actual, LIGHT) == {}


def test_audit_finds_renames_conflicts_missing_differing_and_extra():
    doc = [{**BOLD, "strichstaerke_mm": 0.102}, {**LIGHT, "name": "0-light"},
           {**LIGHT, "name": "old dash"}, {**LIGHT, "name": "Projekt XY"}]
    names = [c["name"] for c in doc] + ["0 graphics-c light-neu"]
    doc.append(LIGHT)
    mapping = {"0-light": "0 graphics-c light-neu", "old dash": "0 graphics-e dash-neu",
               "not here": "0 graphics-a bold-neu"}
    r = classstd.audit(doc, names, STANDARD, mapping)
    assert r["renames"] == [["old dash", "0 graphics-e dash-neu"]]
    assert r["conflicts"] == [["0-light", "0 graphics-c light-neu"]]
    assert r["missing"] == []  # dash arrives through the rename
    assert r["differing"] == {"0 graphics-a bold-neu": {"strichstaerke_mm": [0.102, 0.203]}}
    assert r["extra"] == ["Projekt XY"]
    assert r["summary"]["to_rename"] == 1 and r["summary"]["rename_conflicts"] == 1


def test_plan_renames_then_sets_standard_attributes_on_renamed_class():
    doc = [{**LIGHT, "name": "old dash"}]
    r = classstd.audit(doc, ["old dash"], STANDARD, {"old dash": "0 graphics-e dash-neu"})
    p = classstd.plan(r, STANDARD)
    assert p["renames"] == [["old dash", "0 graphics-e dash-neu"]]
    assert {c["name"] for c in p["creates"]} == {BOLD["name"], LIGHT["name"]}
    assert p["updates"] == [DASH]


def test_plan_only_and_switches():
    r = classstd.audit([], [], STANDARD, {})
    p = classstd.plan(r, STANDARD, only=[BOLD["name"]])
    assert [c["name"] for c in p["creates"]] == [BOLD["name"]]
    assert classstd.plan(r, STANDARD, create_missing=False)["creates"] == []


def test_load_files(tmp_path):
    (tmp_path / "s.json").write_text(json.dumps({"klassen": [BOLD]}), encoding="utf-8")
    (tmp_path / "m.json").write_text(json.dumps({"mapping": {"a\t": "a"}}), encoding="utf-8")
    assert classstd.load_standard(tmp_path / "s.json") == {BOLD["name"]: BOLD}
    assert classstd.load_mapping(tmp_path / "m.json") == {"a\t": "a"}
    assert classstd.load_mapping(tmp_path / "none.json") == {}


@pytest.fixture
def fake_doc(tmp_path, monkeypatch):
    state = {"classes": {"0 graphics-a bold-neu": {**BOLD, "deckkraft_fuellung": 100}}, "calls": []}

    def vw(fn, **kw):
        state["calls"].append((fn, kw))
        if fn == "read_classes":
            cls = list(state["classes"].values())
            return {"document": "t.vwx", "classes": cls, "all_names": [c["name"] for c in cls]}
        if fn == "apply_classes":
            for u in kw["updates"]:
                state["classes"][u["name"]].update(u)
            for c in kw["creates"]:
                state["classes"][c["name"]] = dict(c)
            undo = [{"op": "class_attrs", "name": u["name"], "raw": {}} for u in kw["updates"]]
            undo += [{"op": "class_created", "name": c["name"]} for c in kw["creates"]]
            return {"document": "t.vwx", "undo": undo, "problems": {}, "renamed": 0,
                    "created": len(kw["creates"]), "updated": len(kw["updates"])}
        if fn == "current_document":
            return "t.vwx"
        if fn == "revert":
            return {"document": "t.vwx", "reverted": len(kw["ops"])}
        raise AssertionError(fn)

    for mod in (app, generic, po4):
        monkeypatch.setattr(mod, "vw", vw)
    monkeypatch.setattr(app, "get_journal", lambda: Journal(tmp_path / "j.jsonl"))
    monkeypatch.setattr(classstd, "load_standard", lambda p=None: STANDARD)
    monkeypatch.setattr(classstd, "load_mapping", lambda p=None: {})
    return state


def test_class_audit_tool(fake_doc):
    r = po4.vw_class_audit()
    assert r["document"] == "t.vwx"
    assert r["differing"] == {BOLD["name"]: {"deckkraft_fuellung": [100, 30]}}
    assert sorted(r["missing"]) == [LIGHT["name"], DASH["name"]]


def test_class_apply_tool_applies_verifies_and_is_revertible(fake_doc):
    out = po4.vw_class_apply()
    assert out["changed"] and out["created"] == 2 and out["updated"] == 1
    assert out["still_differing"] == {}
    rev = generic.vw_revert_last()
    assert rev["reverted_tool"] == "vw_class_apply"
    assert fake_doc["calls"][-1][0] == "revert" and len(fake_doc["calls"][-1][1]["ops"]) == 3


def test_class_apply_nothing_to_do(fake_doc):
    po4.vw_class_apply()
    assert po4.vw_class_apply()["changed"] is False


def test_audit_can_ignore_fields():
    doc = [{**BOLD, "deckkraft_stift": 30}]
    r = classstd.audit(doc, [BOLD["name"]], {BOLD["name"]: BOLD}, {})
    assert r["differing"] == {BOLD["name"]: {"deckkraft_stift": [30, 100]}}
    r = classstd.audit(doc, [BOLD["name"]], {BOLD["name"]: BOLD}, {}, ignore=["deckkraft_stift"])
    assert r["differing"] == {}


def test_audit_tool_rejects_unknown_ignore_field(fake_doc):
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="Unknown field"):
        po4.vw_class_audit(ignore_fields=["deckkraft"])


def test_class_export_writes_standard_and_protects_existing(fake_doc, tmp_path):
    from mcp.server.mcpserver.exceptions import ToolError

    out = tmp_path / "klassen_standard.json"
    r = po4.vw_class_export(str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert r["classes"] == 1 and data["quelle"] == "t.vwx" and data["klassen"][0]["name"] == BOLD["name"]
    with pytest.raises(ToolError, match="overwrite=True"):
        po4.vw_class_export(str(out))
    r = po4.vw_class_export(str(out), overwrite=True)
    assert r["backup"].endswith("klassen_standard.bak.json")
    assert (tmp_path / "klassen_standard.bak.json").exists()
