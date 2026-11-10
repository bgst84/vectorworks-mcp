"""Find the installed Vectorworks version, so nobody has to type it.

macOS installs into /Applications/Vectorworks <year>/Vectorworks <year>.app.
VW_VERSION (year) and VWMCP_APP (app name) still override the detection.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

FALLBACK = "2026"


def installed_versions(apps: Path = Path("/Applications")) -> list[str]:
    """Years of all installed Vectorworks versions, oldest first."""
    years = []
    if apps.is_dir():
        for d in apps.iterdir():
            m = re.fullmatch(r"Vectorworks (20\d\d)", d.name)
            if m and (d / f"{d.name}.app").exists():
                years.append(m.group(1))
    return sorted(years)


def default_version(apps: Path = Path("/Applications")) -> str:
    """VW_VERSION, else the newest installed version, else 2026."""
    env = os.environ.get("VW_VERSION")
    if env:
        return env
    found = installed_versions(apps)
    return found[-1] if found else FALLBACK


def default_app(apps: Path = Path("/Applications")) -> str:
    """VWMCP_APP, else 'Vectorworks <newest installed year>'."""
    return os.environ.get("VWMCP_APP") or f"Vectorworks {default_version(apps)}"
