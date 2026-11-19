# Windows trigger: notes from other projects' in-app listeners

Status (2026-11-17): research only. We have no Windows machine; the design
below needs a tester. Everything here was read from public code, not run.

## The problem

On macOS the server pokes Vectorworks with one Apple Event (`run
VectorScript` calling `DoMenuTextByName('MCP Run Job')`). Windows has no
equivalent, so today the user runs **MCP Run Job** by hand for each request.

## What the pure-Python projects do

Two projects run a Python listener *inside* Vectorworks and reached the same
answer: a **modal layout dialog with a timer** is the only pure-Python context
that can both stay alive and safely call `vs.*`.

**edmacovaz/rt-vectorworks-mcp** (`vw_mcp/listener.py`, VW 2026, macOS):

```python
dialog_id = vs.CreateLayout("VW MCP Session", False, "Stop", "")
vs.CreateStaticText(dialog_id, 4, "Agent session on 127.0.0.1:9877", 48)
vs.CreateStaticText(dialog_id, 5, "Agent drives VW while this is open; close to hand it back.", 56)
vs.SetFirstLayoutItem(dialog_id, 4)
vs.SetBelowItem(dialog_id, 4, 5, 0, 0)

def handler(item, data):
    if item == 12255:                      # SetupDialogC: dialog just opened
        vs.RegisterDialogForTimerEvents(dialog_id, 50)   # tick every 50 ms
        pump()
        return
    if item in (1, 2):                     # OK ("Stop") / Cancel: end session
        return
    pump()                                 # timer tick (or any other event)

try:
    vs.RunLayoutDialog(dialog_id, handler)
finally:
    vs.DeregisterDialogFromTimerEvents(dialog_id)
```

`pump()` does one non-blocking `select()` on a loopback TCP socket, reads
newline-delimited JSON, dispatches, replies. Their tools are read-only so far,
so this proves the *lifecycle*, not writes. They call the non-modal modes
"freeze or can't schedule" and name a native C++ bridge as the upgrade path.

**BhaveshY/vectorworks-mcp** (`legacy/vw_listener.py`, VW 2024/2025,
Windows; 0.3.0, later replaced by a native plug-in): same dialog pattern,
default mode `dialog`, `VW_MCP_DIALOG_TIMER_MS=50`. Their docstring records
why the alternatives were demoted to "transport-only diagnostics":

- `background` (Python thread): "real CAD handlers can deadlock outside that
  script context".
- `win_timer` (`user32.SetTimer` via ctypes, Windows only): same deadlock.
- `foreground` (busy loop in the script): "can monopolize the Vectorworks UI".

So: timer-driven modal dialog = safe `vs` context, including writes in their
case (their 20 tools draw walls, doors, slabs through it). The cost is that
the user cannot edit while the dialog is open; it is explicit turn-taking.

**vicquick/vwx-mcp** avoids the dialog with a native C++ palette (100 ms
timer; reads through an `OnIdle` notification, writes by calling the Python
menu command via `ISDK::DoMenuName` from a message-only window). That is the
non-modal answer, but it needs the SDK and a compiler per Vectorworks
version. Its macOS path is still the TCP dialog bridge.

## Proposed design for vwmcp (untested)

Keep the file protocol; add a second menu command, **MCP Listen**, whose
script opens the modal dialog above and, on every timer tick, calls
`vwmcp_bridge.run_pending()` (which already drains `~/.vwmcp/jobs`). No
sockets, no new wire format, and the existing bridge file stays the executor.

- Server side: on Windows the trigger becomes a no-op (`manual_trigger`),
  because the listener polls. The timeout message should say "run MCP Listen".
  On macOS the same command could be offered as an alternative to the
  AppleScript hop for people who prefer an explicit session.
- Dialog text: the job folder, a counter of jobs run, "Close to stop".
- Tick interval 100 ms is plenty for a file poll (`os.listdir` of a tiny folder).
- Open question: whether a write done from a timer event inside the dialog
  creates its own undo step or none. BhaveshY's listener worked, but check
  Cmd-Z behaviour and the journal (`vw_revert_last`) on the first live test.
- Open question: `vs.SetupDialogC` exists as a constant in VW 2026 Python
  (rt-vectorworks-mcp falls back to 12255 if it doesn't).

First live test (macOS, throwaway doc, user watching): open the dialog, send
`vw_ping` with the trigger disabled, confirm the result lands; then one
`vw_set_record` and Cmd-Z.
