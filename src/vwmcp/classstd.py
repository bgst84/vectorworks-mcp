"""PO4 class standard: compare a document's classes with klassen_standard.json
and plan the changes (renames from klassen_mapping.json, missing classes,
attribute fixes). Pure Python, so it is tested without Vectorworks."""

from __future__ import annotations

import json
import os
from pathlib import Path

PO4_DIR = Path(os.environ.get(
    "VWMCP_PO4_DIR", Path.home() / "PO4 Dropbox/PO4/00_Organisation/18_Vectorworks"
))
DEFAULT_STANDARD = PO4_DIR / "klassen_standard.json"
DEFAULT_MAPPING = PO4_DIR / "klassen_mapping.json"

FIELDS = [
    "automatisch_zuweisen", "strichstaerke_mm", "linie", "fuellung",
    "stift_vorne", "stift_hinten", "fuellung_vorne", "fuellung_hinten",
    "deckkraft_fuellung", "deckkraft_stift",
]
# Colors that don't show: background colors of solid/none fills and the pen
# background are ignored unless the fill uses them (hatches, patterns).
IGNORE_WHEN = {
    "fuellung_hinten": lambda std: std.get("fuellung") == "none",
    "fuellung_vorne": lambda std: std.get("fuellung") == "none",
}


def load_standard(path: str | Path | None = None) -> dict[str, dict]:
    p = Path(path).expanduser() if path else DEFAULT_STANDARD
    data = json.loads(p.read_text(encoding="utf-8"))
    return {c["name"]: c for c in data["klassen"]}


def load_mapping(path: str | Path | None = None) -> dict[str, str]:
    p = Path(path).expanduser() if path else DEFAULT_MAPPING
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))["mapping"]


def _same(field: str, a, b) -> bool:
    if field == "strichstaerke_mm":
        return abs(float(a) - float(b)) < 0.002
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return list(a) == list(b)
    return a == b


def diff_class(actual: dict, std: dict, ignore=()) -> dict[str, list]:
    """{field: [actual, standard]} for every field that differs."""
    out = {}
    for f in FIELDS:
        if f not in std or f in ignore:
            continue
        skip_if = IGNORE_WHEN.get(f)
        if skip_if and skip_if(std):
            continue
        if not _same(f, actual.get(f), std[f]):
            out[f] = [actual.get(f), std[f]]
    return out


def audit(doc_classes: list[dict], all_names: list[str], standard: dict[str, dict],
          mapping: dict[str, str], ignore=()) -> dict:
    names = set(all_names)
    actual = {c["name"]: c for c in doc_classes}
    renames, conflicts = [], []
    for old, new in mapping.items():
        if old in names and old != new:
            (conflicts if new in names else renames).append([old, new])
    renamed_to = {new for _, new in renames}
    missing = [n for n in standard if n not in names and n not in renamed_to]
    differing = {}
    for n, std in standard.items():
        if n in actual:
            d = diff_class(actual[n], std, ignore)
            if d:
                differing[n] = d
    mapped_old = {old for old, _ in renames + conflicts}
    extra = sorted(n for n in names if n not in standard and n not in mapped_old)
    return {
        "renames": renames, "conflicts": conflicts, "missing": missing,
        "differing": differing, "extra": extra,
        "summary": {
            "classes_in_document": len(names), "classes_in_standard": len(standard),
            "to_rename": len(renames), "rename_conflicts": len(conflicts),
            "missing": len(missing), "differing": len(differing), "extra": len(extra),
        },
    }


def plan(report: dict, standard: dict[str, dict], rename: bool = True, create_missing: bool = True,
         fix_attributes: bool = True, only: list[str] | None = None) -> dict:
    """Turn an audit into the apply_classes arguments. `only` limits it to
    these standard class names (and renames onto them)."""
    keep = (lambda n: True) if not only else (lambda n: n in set(only))
    renames = [r for r in report["renames"] if keep(r[1])] if rename else []
    creates = [standard[n] for n in report["missing"] if keep(n)] if create_missing else []
    updates = []
    if fix_attributes:
        for n, d in report["differing"].items():
            if keep(n):
                updates.append({"name": n, **{f: standard[n][f] for f in d}})
        # Renamed classes take the standard's attributes too.
        for _, new in renames:
            if new in standard and new not in report["differing"]:
                updates.append(dict(standard[new]))
    return {"renames": renames, "creates": creates, "updates": updates}


def export_document(read: dict, exported: str) -> dict:
    """A klassen_standard.json document from read_classes() output."""
    return {"quelle": read["document"], "exportiert": exported, "klassen": read["classes"]}
