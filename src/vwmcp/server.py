"""Entry point: `vwmcp` runs the MCP server (stdio); `vwmcp install-plugin`
installs the in-app bridge; `vwmcp doctor` checks the install; `vwmcp lint FILE...`
checks scripts."""

from __future__ import annotations

import argparse
import importlib
import os
import pkgutil

from vwmcp import install, tools
from vwmcp.app import mcp

# Every module in vwmcp.tools registers its tools on import (extensions included).
for _m in pkgutil.iter_modules(tools.__path__):
    importlib.import_module(f"vwmcp.tools.{_m.name}")

# PO4 fork: architecture work only. The Spotlight and stage tools stay in the
# code (so merges from upstream stay simple) but are only offered to Claude
# with VWMCP_SPOTLIGHT=1.
SPOTLIGHT_TOOLS = (
    "vw_list_lighting_devices", "vw_set_lighting_device_fields", "vw_list_positions",
    "vw_lighting_device_report", "vw_insert_lighting_devices", "vw_insert_truss_run",
    "vw_list_truss", "vw_insert_stage_decks", "vw_insert_stage_steps",
)


def spotlight_enabled() -> bool:
    return os.environ.get("VWMCP_SPOTLIGHT", "").strip().lower() in ("1", "true", "yes")


if not spotlight_enabled():
    for _name in SPOTLIGHT_TOOLS:
        mcp.remove_tool(_name)


def main() -> None:
    parser = argparse.ArgumentParser(prog="vwmcp", description=__doc__)
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("install-plugin", help="copy the bridge into Vectorworks' Plug-ins folder")
    p.add_argument("--vw-version", default=None, help="default: newest installed Vectorworks")
    p.add_argument("--target", help="explicit folder (default: user Plug-ins/vwmcp)")
    lp = sub.add_parser("lint", help="check Python files for Vectorworks (syntax, vs.* signatures)")
    lp.add_argument("files", nargs="+")
    d = sub.add_parser("doctor", help="check bridge, Claude configs, Vectorworks process, runtime folder")
    d.add_argument("--vw-version", default=None, help="default: newest installed Vectorworks")
    d.add_argument("--fix", action="store_true", help="remove stale job/result files")
    args = parser.parse_args()

    if args.cmd == "lint":
        import sys

        from vwmcp import vslint

        bad = 0
        for f in args.files:
            report = vslint.lint(open(f, encoding="utf-8").read(), f)
            text = vslint.format_report(report, f)
            print(text or f"{f}: ok")
            bad += len(report["errors"])
        sys.exit(1 if bad else 0)

    if args.cmd == "doctor":
        from vwmcp import doctor

        checks = doctor.run_checks(vw_version=args.vw_version, fix=args.fix)
        print(doctor.format_report(checks))
        raise SystemExit(0 if all(c.ok is not False for c in checks) else 1)

    if args.cmd == "install-plugin":
        from pathlib import Path

        target = Path(args.target) if args.target else install.plugin_dir(args.vw_version)
        print(install.install_plugin(target))
        return
    mcp.run("stdio")


if __name__ == "__main__":
    main()
