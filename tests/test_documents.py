"""Window menu parsing for vw_list_documents / vw_switch_document."""

import pytest

from vwmcp import documents

MENU = "\n".join([
    "Startbildschirm\t\t1\t0", "Paletten\t\t1\t1", "---",
    "Fenster vergrößern\t\t1\t0", "Dokument-Reiter anzeigen\t✓\t1\t0", "Aktives Dokument lösen\t\t1\t0", "---",
    "Ohne Titel 1\t\t1\t0", "zg_testfile.vwx\t✓\t1\t0", "Tabellen\t\t1\t1",
])


def test_documents_group_is_the_last_marked_group_without_submenus():
    out = documents.documents_from_menu(documents.parse_menu(MENU))
    assert out == {"documents": ["Ohne Titel 1", "zg_testfile.vwx"], "active": "zg_testfile.vwx"}


def test_no_document_open():
    with pytest.raises(documents.DocumentsError):
        documents.documents_from_menu(documents.parse_menu("Startbildschirm\t\t1\t0\n---\nTabellen\t\t1\t1"))


def test_switch_matches_name_without_extension(monkeypatch):
    state = {"active": "Ohne Titel 1"}

    def fake(script, *args):
        if args:
            state["active"] = args[0]
            return "ok"
        return "---\n" + "\n".join(f"{n}\t{'✓' if n == state['active'] else ''}\t1\t0"
                                   for n in ("Ohne Titel 1", "zg_testfile.vwx"))

    monkeypatch.setattr(documents, "_osascript", fake)
    out = documents.switch_document("zg_testfile")
    assert out["active"] == "zg_testfile.vwx" and out["switched"] and out["previous"] == "Ohne Titel 1"
    assert documents.switch_document("zg_testfile.vwx")["switched"] is False
    with pytest.raises(documents.DocumentsError):
        documents.switch_document("nope")
