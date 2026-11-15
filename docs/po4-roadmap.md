# PO4 roadmap (agreed with Yves, 2026-11-15)

Order by value for daily office work; 1-3 first.

1. [x] **Wrong-document guard.** Write tools take `document="…"` and refuse when
   another document is active; with `vw_switch_document` Claude can bring the
   right one to the front first. (Twice a real project was in front instead
   of the test file.) Generic.
2. **Wall styles in order.**
   - [x] `vw_wall_style_apply`: fill Bezeichnung, Aussen / Tragend / Brandmauer,
     component functions and "Schichten gestossen verbinden" from the names,
     after confirmation, revertible. Fire rating stays manual.
   - Clean the template's wall styles in one pass.
   - Later: a wall style standard (JSON in the Dropbox, like the class
     standard) so new projects start with clean styles.
3. **Doors and windows in the 3D model.** Native door/window objects in
   walls with sill/head as level references, slab openings. Learn first how
   the Zeughausstrasse project places them (read-only).
4. **Archive plan → 3D.** Let the archivplan skill turn a traced plan into
   walls with PO4 styles and level bounds (useful for surveys like LG).
5. **Project files to the class standard.** Merge with preview for rename
   conflicts (old and new class both exist; uh_vorprojekt: 116 differing,
   33 conflicts), missing in `vw_class_apply`.

Small, alongside:

- Upstream PRs: after PR 1, the pre-flight lint and document switching.
- CI on GitHub (`uv run pytest` before moving `stable`).
- Skills: point the archivplan skill to the 3D helpers; a short
  "PO4 3D modelling" skill with the rules from `docs/po4-3d.md`.
