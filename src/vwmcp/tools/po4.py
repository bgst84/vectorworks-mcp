"""PO4 tools: class standard audit and apply (and, below, drawing helpers)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from vwmcp import app, classstd, wallstd
from vwmcp.app import READ, WRITE, mcp, vw

PO4LIB_SOURCE = (Path(__file__).resolve().parents[1] / "po4lib.py").read_text(encoding="utf-8")
PO4_VWLIB_SOURCE = (Path(__file__).resolve().parents[1] / "po4_vwlib.py").read_text(encoding="utf-8")
app.register_vw_prelude("po4", PO4_VWLIB_SOURCE)
app.register_exec_library(
    "po4", PO4LIB_SOURCE,
    "PO4 drawing helpers (PO4 classes, GT Pressura Light 8 pt, dimension standard PO4): "
    "po4.layer(name, scale, clear) - refuses inside an edit mode; po4.poly/rect/seg/line/box; "
    "po4.union; po4.clip; po4.rebate; po4.door; po4.window_simple; po4.window_detail; "
    "po4.fixed_detail; po4.leaf; po4.text (centred, '\\r' line breaks); po4.dim; po4.chain; "
    "po4.configure(AW=..., FW=..., DIM_STYLE=...); po4.CONFIG. "
    "3D (story levels by name, no fixed heights; see docs/po4-3d.md): po4.stories(); "
    "po4.level_types(); po4.wall(story, p1, p2, style, bottom='OK-RB', top='UK-RD', "
    "top_story=1, bottom_offset, top_offset); po4.walls(story, points, style, closed, join=True); po4.join_walls(a, b, kind='L'|'T'|'X'); "
    "po4.slab(story, outline, style, level='OK-RB') on '<story> Boden'; "
    "po4.floor(story, outline, structure, buildup); po4.wall_style(name, layers=[(name, width, class, function)], exterior, load_bearing, fire_rating, combustible, firewall) - layers exterior to interior.",
)


def _load(standard_path: str | None, mapping_path: str | None):
    try:
        return classstd.load_standard(standard_path), classstd.load_mapping(mapping_path)
    except (OSError, ValueError, KeyError) as e:
        raise ToolError(f"Could not read the class standard: {e}") from e


def _audit(standard: dict, mapping: dict, ignore=()) -> tuple[dict, str]:
    unknown = [f for f in ignore if f not in classstd.FIELDS]
    if unknown:
        raise ToolError(f"Unknown field(s) {unknown}; known: {classstd.FIELDS}")
    doc = vw("read_classes", _prelude="po4")
    return classstd.audit(doc["classes"], doc["all_names"], standard, mapping, ignore), doc["document"]


@mcp.tool(annotations=READ)
def vw_class_audit(
    standard_path: str | None = None,
    mapping_path: str | None = None,
    list_extra: bool = True,
    ignore_fields: list[str] | None = None,
) -> dict:
    """Compare the active document's classes with the PO4 class standard.

    Reports classes to rename (old name in klassen_mapping.json), rename
    conflicts (old and new name both exist), classes missing from the
    document, classes whose attributes differ ({field: [document, standard]};
    line weight in mm, colors 0-255, line/fill "none" | "solid" | "res:<name>"),
    and classes not in the standard ("extra"). Defaults:
    ~/PO4 Dropbox/PO4/00_Organisation/18_Vectorworks/klassen_standard.json and
    klassen_mapping.json (override with paths or VWMCP_PO4_DIR).
    ignore_fields: attribute names to leave out of the comparison, e.g.
    ["deckkraft_stift"] while the standard file is known to be wrong there."""
    standard, mapping = _load(standard_path, mapping_path)
    report, document = _audit(standard, mapping, ignore_fields or ())
    report["document"] = document
    if not list_extra:
        report.pop("extra")
    return report


@mcp.tool(annotations=WRITE)
def vw_class_apply(
    rename: bool = True,
    create_missing: bool = True,
    fix_attributes: bool = True,
    only: list[str] | None = None,
    standard_path: str | None = None,
    mapping_path: str | None = None,
    ignore_fields: list[str] | None = None,
) -> dict:
    """Bring the active document's classes in line with the PO4 class
    standard: rename old classes per the mapping, create missing classes,
    and set differing attributes. `only` limits it to these standard class
    names. Rename conflicts are never merged automatically; they are listed.
    Objects keep their class (a rename carries them along). Revertible with
    vw_revert_last (attributes restored, renames undone, new empty classes
    deleted). Save first; run vw_class_audit to see what will change.
    ignore_fields: attributes to leave untouched (same as in vw_class_audit)."""
    ignore = ignore_fields or ()
    standard, mapping = _load(standard_path, mapping_path)
    report, document = _audit(standard, mapping, ignore)
    p = classstd.plan(report, standard, rename, create_missing, fix_attributes, only)
    if not (p["renames"] or p["creates"] or p["updates"]):
        return {"document": document, "changed": False, "rename_conflicts": report["conflicts"]}
    out = vw("apply_classes", _prelude="po4", renames=p["renames"], creates=p["creates"],
             updates=p["updates"])
    app.get_journal().record(out["document"], "vw_class_apply", out["undo"], prelude="po4")
    after, _ = _audit(standard, mapping, ignore)
    names = {n for n in standard if (not only or n in only)}
    still = {n: d for n, d in after["differing"].items() if n in names}
    return {
        "document": out["document"], "changed": True,
        "renamed": out["renamed"], "created": out["created"], "updated": out["updated"],
        "problems": out["problems"], "rename_conflicts": report["conflicts"],
        "still_differing": still,
    }


@mcp.tool(annotations=WRITE)
def vw_class_export(out_path: str | None = None, overwrite: bool = False) -> dict:
    """Write the active document's classes as a klassen_standard.json (same
    format the audit reads). Run it on the PO4 template to (re)create the
    standard. Default path: the PO4 standard file; an existing file is only
    replaced with overwrite=True, and then kept as <name>.bak.json."""
    path = Path(out_path).expanduser() if out_path else classstd.DEFAULT_STANDARD
    if path.exists() and not overwrite:
        raise ToolError(f"{path} exists. Pass overwrite=True to replace it (a .bak.json copy is kept), "
                        "or give another out_path.")
    data = classstd.export_document(vw("read_classes", _prelude="po4"), datetime.now().isoformat(timespec="minutes"))
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = path.with_suffix(".bak.json")
        shutil.copy2(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"path": str(path), "backup": str(backup) if backup else None,
            "source": data["quelle"], "classes": len(data["klassen"])}


@mcp.tool(annotations=READ)
def vw_wall_style_audit(only: list[str] | None = None, skip_info: bool = False) -> dict:
    """Check the active document's wall styles against PO4 rules
    (docs/po4-3d.md): Data tab (Bezeichnung = W-code of the name,
    Feuerwiderstand set, Aussen / Tragend / Brandmauer agree with the name),
    every component has a class, preferably a material class ("3 material-")
    or facade class ("6 eBKP-e fassade-"), the class fits the material named
    in the component, component function set (info), name follows
    "W<n>.<m> ..." (info). Read-only. `only`: style names to check;
    skip_info=True leaves out info-level findings."""
    styles = vw("wall_styles")
    report = wallstd.audit(styles, only=only, skip_info=skip_info)
    report["document"] = vw("document_info")["name"]
    return report
