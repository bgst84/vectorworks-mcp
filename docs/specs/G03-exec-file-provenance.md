# G03 · `vw_exec_file`: report what was actually run

Label: general · Size: S · Files: `tools/generic.py`, tests

## Problem seen

An agent wrote a new version of a script into a synced folder (iCloud
Desktop) and called `vw_exec_file` immediately; Vectorworks ran the *previous*
version. Only a missing object in the next export revealed it. Reading other
files in the same folder failed with `Resource deadlock avoided` (macOS
dataless files that are not downloaded yet).

## Proposed change

- Result gains `file: {"path", "sha256", "size", "mtime", "first_line"}` of
  the exact bytes that were sent.
- Optional parameter `expect_sha256: str | None`; if given and different,
  refuse with a clear error before running.
- If reading fails with `EDEADLK` (errno 11 on macOS, "Resource deadlock
  avoided") or the file is dataless, raise a ToolError that says the file is
  in cloud storage and not downloaded yet, and how to fix it (open it once or
  "Keep downloaded").

## Acceptance

- Unit tests: hash/mtime present; mismatch refuses without running; simulated
  `OSError(errno.EDEADLK)` yields the explanatory message.
