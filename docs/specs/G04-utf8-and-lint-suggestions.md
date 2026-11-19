# G04 · UTF-8 by default in executed code, lint suggests correct names

Label: general · Size: S · Files: `vwlib.py` / `exec_tracked`, `vslint.py`, tests

## Problem seen

1. `open(path, "w").write(json.dumps(..., ensure_ascii=False))` inside
   Vectorworks failed with `UnicodeEncodeError: 'ascii' codec` on "ü": the
   embedded Python's default encoding is ASCII.
2. Lint flagged `vs.SetLVis` and `vs.GetLWByClass` as unknown (good) but gave
   no hint; the agent had to guess replacements.

## Proposed change

1. In the scope used by `vw_exec_python` / `vw_exec_file`, provide an `open`
   whose text mode defaults to `encoding="utf-8"` (binary mode and explicit
   encodings unchanged). Document it in the tool docstring.
2. `vslint`: for an unknown `vs.*` name, add up to three suggestions from the
   bundled API list (`difflib.get_close_matches`, plus known renames table if
   useful), e.g. `vs.SetLVis is unknown; did you mean vs.SetLayerVisibility?`
   (verify real names against `data/vs_api_2027.json`).
3. `vslint`: warn on `open(` in text mode without `encoding=` (info level).

## Acceptance

- Unit test: executing code that writes "ü" to a temp file via the fake
  executor succeeds and the file is UTF-8.
- Unit test: lint of `vs.SetLVis(h, -1)` returns a warning with suggestions.
