from vwmcp import app, install


def test_plugin_dir_macos(tmp_path):
    d = install.plugin_dir("2026", platform="darwin", home=tmp_path)
    assert d == tmp_path / "Library/Application Support/Vectorworks/2026/Plug-ins/vwmcp"


def test_plugin_dir_windows(tmp_path):
    d = install.plugin_dir("2026", platform="win32", appdata=tmp_path)
    assert d == tmp_path / "Nemetschek/Vectorworks/2026/Plug-ins/vwmcp"


def test_install_writes_package_and_reports_version(tmp_path):
    target = tmp_path / "Plug-ins" / "vwmcp"
    msg = install.install_plugin(target)
    assert (target / "vwmcp_bridge.py").read_text() == app.bundled_bridge_source()
    assert (target / "__init__.py").exists()
    assert app.EXPECTED_BRIDGE_VERSION in msg


def test_install_is_idempotent(tmp_path):
    target = tmp_path / "vwmcp"
    install.install_plugin(target)
    install.install_plugin(target)
    assert sorted(p.name for p in target.iterdir()) == ["__init__.py", "vwmcp_bridge.py"]


def test_install_copies_menu_command_next_to_bridge(tmp_path):
    vsm = tmp_path / "MCP Run Job.vsm"
    vsm.write_bytes(b"\x00vsm")
    target = tmp_path / "Plug-ins" / "vwmcp"
    msg = install.install_plugin(target, menu_command=vsm)
    assert (tmp_path / "Plug-ins" / "MCP Run Job.vsm").read_bytes() == b"\x00vsm"
    assert "menu command" in msg


def test_detects_newest_installed_vectorworks(tmp_path, monkeypatch):
    from vwmcp import vwversion

    monkeypatch.delenv("VW_VERSION", raising=False)
    monkeypatch.delenv("VWMCP_APP", raising=False)
    for year in ("2026", "2027"):
        (tmp_path / f"Vectorworks {year}" / f"Vectorworks {year}.app").mkdir(parents=True)
    (tmp_path / "Vectorworks 2028").mkdir()  # installer leftovers without the app
    (tmp_path / "Vectorworks Cloud Services.app").mkdir()
    assert vwversion.installed_versions(tmp_path) == ["2026", "2027"]
    assert vwversion.default_version(tmp_path) == "2027"
    assert vwversion.default_app(tmp_path) == "Vectorworks 2027"


def test_env_overrides_detection(tmp_path, monkeypatch):
    from vwmcp import vwversion

    monkeypatch.setenv("VW_VERSION", "2025")
    monkeypatch.setenv("VWMCP_APP", "Vectorworks 2025 Beta")
    assert vwversion.default_version(tmp_path) == "2025"
    assert vwversion.default_app(tmp_path) == "Vectorworks 2025 Beta"
    monkeypatch.delenv("VW_VERSION")
    monkeypatch.delenv("VWMCP_APP")
    assert vwversion.default_version(tmp_path) == "2026"  # nothing installed
