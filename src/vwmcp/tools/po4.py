"""PO4 tools: class standard audit and apply (and, below, drawing helpers)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

from vwmcp import app, classstd
from vwmcp.app import READ, WRITE, mcp, vw


def _load(standard_path: str | None, mapping_path: str | None):
    try:
        return classstd.load_standard(standard_path), classstd.load_mapping(mapping_path)
    except (OSError, ValueError, KeyError) as e:
        raise ToolError(f"Could not read the class standard: {e}") from e


def _audit(standard: dict, mapping: dict, ignore=()) -> tuple[dict, str]:
    unknown = [f for f in ignore if f not in classstd.FIELDS]
    if unknown:
        raise ToolError(f"Unknown field(s) {unknown}; known: {classstd.FIELDS}")
    doc = vw("read_classes")
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
    out = vw("apply_classes", renames=p["renames"], creates=p["creates"], updates=p["updates"])
    app.get_journal().record(out["document"], "vw_class_apply", out["undo"])
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
    data = classstd.export_document(vw("read_classes"), datetime.now().isoformat(timespec="minutes"))
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = path.with_suffix(".bak.json")
        shutil.copy2(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"path": str(path), "backup": str(backup) if backup else None,
            "source": data["quelle"], "classes": len(data["klassen"])}
