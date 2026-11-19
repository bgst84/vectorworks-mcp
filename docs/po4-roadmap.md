# Roadmap from the PO4 sketch test (2026-11-18)

On 2026-11-18 Claude drew a competition floor plan from a hand sketch through
this MCP ("Skizze 01": two flats on an access gallery, 19.35 × 5.58 m, five
iterations). This file lists what the test showed is missing, as one spec per
work item. Each spec is self-contained: goal, problem seen in the test,
proposed interface, acceptance criteria. Work through them one at a time.

Classification follows the fork policy in `CLAUDE.md`:
**general** specs live in `docs/specs/` and may become upstream PRs (no PO4
names in code or docs); **po4** specs live in `docs/po4-specs/` and stay in
the fork.

## Order

| # | Spec | Label | Size | Depends on |
|---|---|---|---|---|
| 1 ✅ | [G01 export: symbols, walls, stacking](specs/G01-export-geometry-complete.md) | general | M | – |
| 2 ✅ | [G02 render: symbols, texts, stacking](specs/G02-render-layers-complete.md) | general | M | G01 |
| 3 | [G03 exec_file provenance](specs/G03-exec-file-provenance.md) | general | S | – |
| 4 | [G04 UTF-8 and lint suggestions](specs/G04-utf8-and-lint-suggestions.md) | general | S | – |
| 5 | [G05 layer management](specs/G05-layer-management.md) | general | M | – |
| 6 | [G06 library resources](specs/G06-library-resources.md) | general | M | – |
| 7 | [G07 stacking order](specs/G07-stacking-order.md) | general | S | – |
| 8 | [G08 checkpoint for redrawing scripts](specs/G08-checkpoint-redraw.md) | general | M | G05 |
| 9 | [G09 view and screenshot guard](specs/G09-view-and-screenshot.md) | general | S | – |
| 10 | [P01 po4 plan helpers](po4-specs/P01-plan-helpers.md) | po4 | L | G06, G07 (can start without) |
| 11 | [P02 rooms and SIA 416 areas](po4-specs/P02-rooms-sia416.md) | po4 | M | P01 |
| 12 | [P03 po4_lint against the rulebook](po4-specs/P03-po4-lint.md) | po4 | L | G01, P02, rulebook CSV |
| 13 | [P04 competition template](po4-specs/P04-competition-template.md) | po4 | S | G05 |
| 14 | [P05 new_sketch scaffolding](po4-specs/P05-new-sketch.md) | po4 | S | P01 |

Quick wins first if time is short: G03, G04, G07, G09.

## Status

- **G01** done 2026-11-19, branch `spec/G01-export-geometry` (from
  `po4/exec-revert-and-inspection`, because the export does not exist on
  `main` / `upstream/main` yet). All acceptance criteria passed. The live
  check used two symbols made by script on a throwaway document (one nested
  in the other, turned and mirrored), not a library symbol.
- **G02** done 2026-11-19, branch `spec/G02-render-layers` (on top of G01).
  Live it rendered a test layer and a real floor plan layer of a project
  (5267 objects with symbols expanded): WC, tables with chairs (nested
  symbols), beds and label boxes are in place. That run found two bugs,
  both fixed: coordinates inside symbol definitions are shifted by the
  user origin (G01), and plug-in objects were filled as boxes (G02).
  Left out: stroke glyphs for texts (see the spec's "As built").
- Seen on the real plan, not part of G01/G02: the export does not know
  class visibility, so objects of classes that are hidden in Vectorworks
  (area proofs with solid fills) are drawn and can cover the plan in
  `order="stack"`. Since 2026-11-19 `vw_render_layers` has
  `exclude_classes` (prefix patterns with `*`), and PO4 leaves out
  `0 graphics-i highlight` and `7 nachweise*` by default (branch
  `po4/render-defaults`); `exclude_classes=[]` draws everything.
  Still a candidate for a spec: class visibility in the export.

## Material from the test

`tests/fixtures/po4_skizze_01/` (PO4 fixture, not for upstream):

- `skizze.png`: Yves' hand sketch (photo).
- `skizze_01_grundriss.py`: the final drawing script (v5). Source for the P01
  helpers; every helper replaces a block of this file.
- `_geometrie.json`: `vw_export_geometry` of the drawn layer (reference result).
- `_symbole.json`: definitions and insertion points of the 13 placed symbols.
- `_render_geometrie.py`: the matplotlib check renderer written during the
  test (what G01/G02 should make unnecessary).
- `kontrolle.png`: its output.

The PO4 rulebook ("PO4 Regelwerk Wettbewerb") is a Claude Sheet; it is the
master. P03 reads a CSV export of it at `docs/po4-regelwerk-wettbewerb.csv`
(Yves exports it from the Sheet page: download as CSV).

## Decisions taken (2026-11-19)

- PO4 walls: both modes behind one parameter: 2D poché (default, as in
  Skizze 01) or wall objects with competition wall styles.
- Rulebook in the repo: CSV export of the Sheet; the Sheet stays the master.
- SIA 416 areas: the drawing script declares rooms (polygon + use); no
  automatic room detection from walls.
- Nothing is pushed and no GitHub issues are created without Yves' OK.
