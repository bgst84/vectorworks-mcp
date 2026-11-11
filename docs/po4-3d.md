# PO4 3D modelling convention (stories, levels, walls, slabs)

How PO4 builds 3D models in Vectorworks, so that tools and scripts model the
same way. Learned read-only from a PO4 project in execution phase (multi-storey
timber building on a concrete basement, Vectorworks 2027) and confirmed by
Yves on 2026-11-11.

## Principle: abstract references, no fixed heights

Nothing is modelled with a fixed height when an abstract reference exists.
Walls and slabs are bound to **story levels**; the actual elevations live only
in the story definitions. A change in floor build-up, slab thickness or storey
height (statics, acoustics, design) is then one edit to the levels, not a
re-modelling of every wall.

The **names** of the references are fixed office-wide; their **values** are
per project.

| Level | Meaning | Typical offset to the story (example project) |
|---|---|---|
| `OK-FB` | Oberkante Fertigboden (finished floor) = the story elevation | ±0 |
| `OK-RB` | Oberkante Rohboden (top of structural slab) | −170 (−120 in the EG with a thinner build-up) |
| `UK-RD` | Unterkante Rohdecke (underside of the structural slab) | −370 |
| Brüstung, Sturz | sill and head height, used in some projects | per project |

Never hard-code these numbers in tools: read the project's levels, or bind to
the level by name and let Vectorworks resolve the height.

## Stories

- One story per floor (UG, EG, OG1 … OG*n*, Attika, Dach), suffix = running
  number from the lowest (0, 1, 2 …).
- Story elevation = `OK-FB` of that floor.
- The story layer templates define the levels above (plus a default wall
  height); design layers carry no layer level type of their own.
- Design layers sit at the story elevation, scale 1:50.

## Two design layers per story

| Layer | Content | Vertical zone |
|---|---|---|
| `<story>` (e.g. `OG3`) | walls, columns, spaces, room tags, dimensions, 2D plan graphics | `OK-RB` of this story → `UK-RD` of the story above |
| `<story> Boden` (e.g. `OG3 Boden`) | the floor package of this story: structural slab, floor build-up, slab-edge walls, parapets / Dachrand, fire stops | `UK-RD` → `OK-FB` of this story |

So the structural slab under a floor belongs to the story **above** it
(`OG3 Boden` holds the slab between OG2 and OG3). This split is deliberate:
geometric control is easier when each floor package is one layer.

Other design layers (site, scans, variants, steel, sewers, visualisation
props) are attached to the story they belong to but are not part of this
scheme.

## Walls

- Bottom bound: story level `OK-RB` (offset 0) for walls on `<story>`.
- Top bound: level `UK-RD` of the story above (offset 0). Deviations are
  offsets on a level, never absolute heights: e.g. interior walls
  `UK-RD −0.20`, sill-height walls `OK-FB +0.97`.
- Slab-edge walls on `<story> Boden`: `UK-RD` → `OK-RB` of the same story
  (wall styles "Aussenwand Stirnbereich …", 225 mm, continuing the façade
  layers across the slab zone). Parapets / Dachrand: from `OK-RB` upwards.
- Wall styles come from the project's component catalogue, numbered by type:
  `W1.x` exterior wall load-bearing/bracing, `W3.x` exterior variants,
  `W4.x` exterior non-load-bearing, `W5.x` fire wall, `W6.x` interior
  bracing, `W7.x` interior, `W8.x`/`W9.x` basement exterior, `W10` masonry.
  Name pattern: `W<n>.<m> <type> <thickness mm> <finish> <structural role>`,
  e.g. `W1.1 Aussenwand 410 holzlatten aussteifend`. The catalogue content
  is per project; always use existing styles from the file, never invent
  unstyled walls.
- Thin finishes (tiling, sheet metal plinth) are modelled as thin walls with
  their own styles.

## Slabs

- Structural slab and floor build-up are **two separate slabs**, both on
  `<story> Boden`:
  - structural slab (e.g. `Bodenplatte BSP 20cm`, `Decke Beton 25cm`),
    top bound to `OK-RB`;
  - floor build-up (e.g. `Bodenaufbau Schüttung Anhydrit Parkett`,
    170 mm: 15 finish, 55 anhydrite, 2 × 20 impact insulation, 60 fill),
    bottom at `OK-RB`, top = `OK-FB`.
- Additional layers as their own slabs where needed (insulation below the
  basement ceiling, roof build-up on the top floor).

## Classes

Class standard: see `docs/po4-setup.md` and the class tools. For 3D:

- object classes: walls `6 eBKP-c konstruktion-wand-neu`, slabs
  `6 eBKP-c konstruktion-decke-neu`, columns `…-stütze-neu`, stairs
  `…-treppe-neu`; façade elements `6 eBKP-e fassade-…-neu`;
- component classes: materials `3 material-<material>-neu` (beton,
  holzwerkstoff, gkp, dämmung horizontal/vertikal, dämmung horizontal-neu
  dicht, kies, blech/metall …); ventilation gaps `0 graphics-c light-neu`;
- existing construction uses the `-bestand` variants.

## Level types in the file

Besides OK-FB / OK-RB / UK-RD a project can define more level types (the
example has UK-FD, UK-RB, OK-Granulat, OK-Dachrand, OK-Aussenraum).
`po4.stories()` lists every story with the levels it actually uses.

## po4lib functions (`libs=["po4"]`)

| Function | Does |
|---|---|
| `po4.stories()` | stories by elevation: name, elevation (m), suffix, levels {type: offset m}, layers |
| `po4.level_types()` | level type names in the document |
| `po4.wall(story, p1, p2, style, bottom="OK-RB", top="UK-RD", top_story=1, bottom_offset=0, top_offset=0)` | styled wall on layer `story`, bound to levels (offsets in m) |
| `po4.walls(story, points, style, closed=False, join=True, **kw)` | chain of walls, corners L-joined; draw closed outlines clockwise so the exterior face is outside |
| `po4.join_walls(a, b, kind="L")` | join like the Wall Join tool: `L` corner, `T` (b ends on a), `X`; pick points automatic |
| `po4.slab(story, outline, style, level="OK-RB", offset=0)` | styled slab on `<story> Boden`, datum bound to the level |
| `po4.floor(story, outline, structure, buildup)` | structural slab + floor build-up, both on OK-RB |

All of them check style, level and layer first and raise `ValueError`
before drawing anything; they never create layers or stories. Live-tested
on a copy of the example project (VW 2027): walls OK-RB → UK-RD above,
`top_offset=-0.2`, BSP slab under OK-RB, build-up on OK-RB; changing OG3's
OK-RB level moved all of them.

## Consequences for tools

- Tools take story and level **names** (`"OG3"`, `"OK-RB"`, `"UK-RD"`),
  plus optional offsets, never absolute Z.
- Before drawing, read the stories and the available wall/slab styles of the
  document; refuse or ask when a requested style or level does not exist.
- New walls go on `<story>`, floor packages on `<story> Boden`.
