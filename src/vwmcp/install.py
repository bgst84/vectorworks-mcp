"""Install the in-app bridge into a Vectorworks user Plug-ins folder."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from vwmcp import app

MENU_SCRIPT = "from vwmcp import vwmcp_bridge\nvwmcp_bridge.run_pending()\n"


def plugin_dir(
    vw_version: str | None = None,
    platform: str = sys.platform,
    home: Path | None = None,
    appdata: Path | None = None,
) -> Path:
    if vw_version is None:
        from vwmcp.vwversion import default_version

        vw_version = default_version()
    if platform == "darwin":
        home = home or Path.home()
        base = home / "Library/Application Support/Vectorworks"
    elif platform == "win32":
        appdata = appdata or Path(os.environ["APPDATA"])
        base = appdata / "Nemetschek/Vectorworks"
    else:
        raise SystemExit(f"Vectorworks does not run on {platform}")
    return base / vw_version / "Plug-ins" / "vwmcp"


MENU_COMMAND_FILE = "MCP Run Job.vsm"


def bundled_menu_command() -> Path | None:
    """The prebuilt 'MCP Run Job' menu command (.vsm), if this build ships one.
    Vectorworks can't create .vsm files from text, but a copy works."""
    # Lives inside the package (src/vwmcp/menu/), so wheels include it as-is.
    path = Path(__file__).resolve().parent / "menu" / MENU_COMMAND_FILE
    return path if path.is_file() else None


def install_plugin(target: Path, menu_command: Path | None = None) -> str:
    """Install the bridge package into target (…/Plug-ins/vwmcp) and, when
    available, the menu command next to it in the Plug-ins folder."""
    target.mkdir(parents=True, exist_ok=True)
    (target / "__init__.py").write_text(
        '"""vectorworks-mcp bridge package (see vwmcp_bridge.py)."""\n', encoding="utf-8"
    )
    (target / "vwmcp_bridge.py").write_text(app.bundled_bridge_source(), encoding="utf-8")
    vsm = menu_command if menu_command is not None else bundled_menu_command()
    if vsm is not None:
        (target.parent / MENU_COMMAND_FILE).write_bytes(Path(vsm).read_bytes())
        return (
            f"Installed vwmcp bridge {app.EXPECTED_BRIDGE_VERSION} to {target}\n"
            f"Installed the 'MCP Run Job' menu command to {target.parent}.\n"
            "Restart Vectorworks once so it loads the command."
        )
    return (
        f"Installed vwmcp bridge {app.EXPECTED_BRIDGE_VERSION} to {target}\n\n"
        "If you haven't yet, create the 'MCP Run Job' menu command once in Vectorworks "
        "(Tools > Plug-ins > Plug-in Manager > New > Command, Language: Python) with:\n\n"
        + MENU_SCRIPT
    )
