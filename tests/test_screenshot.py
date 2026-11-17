from pathlib import Path

import pytest

from vwmcp import screenshot as ss


def win(id, title, layer=0, w=100, h=100):
    return ss.Window(id=id, title=title, layer=layer, x=0, y=0, width=w, height=h)


def test_pick_largest_normal_window_skips_palettes():
    palette = win(1, "", layer=103, w=300, h=100)
    doc = win(2, "plot.vwx", w=1728, h=978)
    small = win(3, "other.vwx", w=800, h=600)
    assert ss.pick_window([palette, small, doc]) == doc


def test_pick_by_title_substring_case_insensitive():
    a, b = win(1, "Plot A.vwx"), win(2, "Plot B.vwx")
    assert ss.pick_window([a, b], title="plot b") == b


def test_pick_reports_open_titles_when_title_not_found():
    with pytest.raises(ss.ScreenshotError, match="'Plot A.vwx'"):
        ss.pick_window([win(1, "Plot A.vwx")], title="nope")


def test_pick_fails_when_no_document_window():
    with pytest.raises(ss.ScreenshotError, match="no document window"):
        ss.pick_window([win(1, "", layer=103)])


class FakeRun:
    def __init__(self, rc=0):
        self.calls, self.rc = [], rc

    def __call__(self, args):
        self.calls.append(args)
        if args[0] == "screencapture" and self.rc == 0:
            Path(args[-1]).write_bytes(b"png")
        import subprocess

        return subprocess.CompletedProcess(args, self.rc, "", "denied" if self.rc else "")


def test_screenshot_captures_window_id_and_shrinks(tmp_path):
    run = FakeRun()
    path, window = ss.screenshot(
        root=tmp_path, windows=lambda owner: [win(42, "plot.vwx")], run=run, max_width=1200
    )
    assert path.parent == tmp_path / "screenshots" and path.read_bytes() == b"png"
    assert run.calls[0] == ["screencapture", "-x", "-o", "-l", "42", str(path)]
    assert run.calls[1] == ["sips", "-Z", "1200", str(path)]
    assert window.id == 42


def test_screenshot_uses_app_name_as_window_owner(tmp_path):
    seen = []

    def windows(owner):
        seen.append(owner)
        return [win(1, "x.vwx")]

    ss.screenshot(app="Vectorworks 2025", root=tmp_path, windows=windows, run=FakeRun())
    assert seen == ["Vectorworks"]


def test_screenshot_failure_mentions_screen_recording(tmp_path):
    with pytest.raises(ss.ScreenshotError, match="Screen Recording"):
        ss.screenshot(root=tmp_path, windows=lambda o: [win(1, "x.vwx")], run=FakeRun(rc=1))


def test_prune_keeps_newest(tmp_path):
    for i in range(5):
        (tmp_path / f"2026010{i}-000000.png").write_bytes(b"")
    ss.prune(tmp_path, keep=2)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "20260103-000000.png",
        "20260104-000000.png",
    ]
