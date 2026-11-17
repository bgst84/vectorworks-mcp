"""Drawing-side tools: libraries, plug-in objects, layers, classes, move,
delete, view. Writes are journaled for vw_revert_last."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.mcpserver.exceptions import ToolError

from vwmcp import app, library
from vwmcp.app import READ, WRITE, mcp, vw


def _journal(result: dict, tool: str, ops: list[dict] | None) -> dict:
    app.get_journal().record(result.pop("document"), tool, ops)
    return result


@mcp.tool(annotations=READ)
def vw_list_library_files(query: str = "", limit: int = 50) -> list[dict]:
    """Vectorworks library files (.vwx) on this Mac whose path contains every
    word of `query`, e.g. "lighting", "truss", "people", "stage deck", "audio".
    Searches the Vectorworks application libraries and the user libraries.
    Reads the disk only; then use vw_list_library_resources on a path."""
    return library.find_library_files(query, limit=limit)


@mcp.tool(annotations=READ)
def vw_list_library_resources(
    path: str, name_contains: str | None = None, type_code: int = 16, limit: int = 500
) -> dict:
    """Names of the resources inside a library file (from vw_list_library_files)
    without importing anything. type_code 16 = symbol definitions, which
    includes plug-in styles (truss, lighting pipe, fixture symbols); 47 =
    record formats."""
    return vw("library_resources", path=path, type_code=type_code,
              name_contains=name_contains, limit=limit)


@mcp.tool(annotations=WRITE)
def vw_import_resource(
    path: str, name: str, new_name: str | None = None, type_code: int = 16
) -> dict:
    """Import one resource (symbol or plug-in style) from a library file into
    the document through Vectorworks' own importer, so it can then be placed
    with vw_insert_symbol / vw_create_pio. If the document already has a
    resource with that name, give new_name to import a copy. Revertible."""
    out = vw("import_resource", path=path, name=name, type_code=type_code, new_name=new_name)
    return _journal(out, "vw_import_resource", [{"op": "resource", "name": out["name"]}])


@mcp.tool(annotations=WRITE)
def vw_create_pio(
    plugin: str,
    x: float,
    y: float,
    rotation: float = 0.0,
    parameters: dict[str, Any] | None = None,
    layer: str | None = None,
    class_name: str | None = None,
) -> dict:
    """Place a Spotlight/Vectorworks plug-in object by its internal name, e.g.
    "Lighting Device", "Truss", "Soft Goods", "Stage Deck", "Light Position Obj",
    at x, y (document units) with a rotation, and set parameters by field name
    (use vw_get_pio_parameters on an existing one to see the names). Unknown
    parameter names abort the call and nothing is placed. Revertible."""
    info = vw("create_pio", plugin=plugin, x=x, y=y, rotation=rotation,
              parameters=parameters, layer=layer, cls=class_name)
    return _journal(info, "vw_create_pio", [{"op": "created", "uuid": info["uuid"]}])


@mcp.tool(annotations=READ)
def vw_get_pio_parameters(uuid: str) -> dict:
    """All parameter fields of a plug-in object (truss, fixture, stage deck...)
    with their current values, plus the plug-in name."""
    return vw("pio_parameters", uuid=uuid)


@mcp.tool(annotations=WRITE)
def vw_set_pio_parameters(uuid: str, values: dict[str, Any]) -> dict:
    """Set parameter fields on a plug-in object by field name and regenerate
    it. All-or-nothing: an unknown field name changes nothing. Revertible."""
    out = vw("set_pio_parameters", uuid=uuid, values=values)
    ops = [{"op": "fields", "uuid": uuid, "record": out["record"], "before": out["before"]}]
    _journal(out, "vw_set_pio_parameters", ops)
    return {"uuid": uuid, "plugin": out["record"], "after": vw("get_record", uuid=uuid, record=out["record"])}


@mcp.tool(annotations=WRITE)
def vw_create_layer(
    name: str, kind: Literal["design", "sheet"] = "design", scale: float | None = None,
    activate: bool = False,
) -> dict:
    """Create a design or sheet layer (design layers: optional scale denominator,
    e.g. 48 for 1/4" = 1'). The user's active layer stays active unless
    activate=True. Revertible (the layer is deleted)."""
    out = vw("create_layer", name=name, kind=kind, scale=scale, activate=activate)
    return _journal(out, "vw_create_layer", [{"op": "layer", "name": name}])


@mcp.tool(annotations=WRITE)
def vw_create_class(name: str) -> dict:
    """Create a class (use "-" for hierarchy, e.g. "Lighting-Truss"). The active
    class is left unchanged. Revertible."""
    out = vw("create_class", name=name)
    return _journal(out, "vw_create_class", [{"op": "class", "name": name}])


@mcp.tool(annotations=WRITE)
def vw_delete_objects(uuids: list[str]) -> dict:
    """Delete objects by uuid. All-or-nothing: if any uuid is unknown nothing is
    deleted. NOT revertible with vw_revert_last (only Cmd-Z in Vectorworks),
    and it blocks reverting earlier edits, so confirm with the user first."""
    if not uuids:
        raise ToolError("no uuids given")
    out = vw("delete_objects", uuids=uuids)
    return _journal(out, "vw_delete_objects", None)


@mcp.tool(annotations=WRITE)
def vw_move_objects(uuids: list[str], dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> dict:
    """Move objects by an offset in document units (dz for 3D). All-or-nothing
    on unknown uuids. Revertible (moved back)."""
    if not uuids:
        raise ToolError("no uuids given")
    out = vw("move_objects", uuids=uuids, dx=dx, dy=dy, dz=dz)
    ops = [{"op": "move", "uuid": u, "dx": dx, "dy": dy, "dz": dz} for u in uuids]
    return _journal(out, "vw_move_objects", ops)


@mcp.tool(annotations=WRITE)
def vw_set_view(
    view: Literal["top_plan", "top", "bottom", "front", "back", "left", "right",
                  "iso", "iso_right", "iso_left"] | None = None,
    fit: bool = False,
) -> dict:
    """Change the drawing view (standard 3D views or Top/Plan) and/or zoom to
    fit all objects, e.g. before vw_screenshot. Changes no objects, so it is
    not journaled."""
    return vw("set_view", view=view, fit=fit)
