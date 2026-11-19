# P05 · `vw_po4_new_sketch`: scaffold a sketch iteration

Label: po4 · Size: S · Files: `tools/po4.py`, template under `src/vwmcp/data/`, tests · Depends on: P01

## Goal

Every sketch starts the same way (the workflow of the skill
"po4-skizze-zeichnen"): folder, script with parameters and version header,
idempotent layer, stacking at the end, export + render for checking.

## Proposed interface

```python
vw_po4_new_sketch(project_dir, number, title, layer=None, scale=100)
# creates <project_dir>/skizze_<NN>/skizze_<NN>_grundriss.py from a template
# and returns its path; does not run it.
```

Template content: header (project, sketch number, date, "v1 <date> <title>"),
parameter block, `po4.layer(LAYER, scale, clear=True)`, sections for walls /
façade / doors / bath / kitchen / furniture / rooms (P02), final
`po4.stack_by_weight()` and a comment with the export + render calls to use
for checking.

## Acceptance

- Unit test: file created with the expected sections; refuses to overwrite an
  existing file; the generated script passes `vw_lint`.
