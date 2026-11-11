# PO4 drawing helpers, executed INSIDE Vectorworks as module `po4` when
# vw_exec_python / vw_exec_file are called with libs=["po4"]
# (registered in tools/po4.py).
#
# Encodes PO4's drawing conventions (classes, GT Pressura Light 8 pt,
# dimension standard "PO4", window details with rebate). Taken from the
# archive-plan workflow (LG, 2026-11) where these helpers were proven live.
# Keep it Python 3.9-compatible; `vs` is injected by the caller.
#
# Orientation for wall-relative helpers: o='h' (wall along x: a = x, w = y)
# or o='v' (wall along y: a = y, w = x). Units: document units (m at PO4).

import math

CONFIG = {
    # classes
    "BOLD": "0 graphics-a bold-neu",          # walls, rebates
    "MEDIUM": "0 graphics-b medium-neu",      # non-load-bearing cut, window frames/sashes/glass (detailed)
    "LIGHT": "0 graphics-c light-neu",        # everything else, texts, sills, lintels
    "SUPERLIGHT": "0 graphics-d superlight-neu",  # door and window swings
    "DASH": "0 graphics-e dash-neu",          # roof parts above the cut, existing terrain
    "DASHDOT": "0 graphics-g dashdot-neu",    # section lines
    "DIM": "2 dimensions-b rohbau",
    # text and dimensions
    "FONT": "GT Pressura Light",
    "TEXT_SIZE": 8,
    "DIM_STYLE": "PO4",
    # window details (m); adjust per project with configure()
    "AW": 0.08, "AT": 0.20,   # rebate: offset x depth
    "FW": 0.12, "FD": 0.07,   # frame: width in view x depth (FW = AW + 0.04)
    "SW": 0.07, "SD": 0.07,   # sash: width x depth
    "OV": 0.035,              # sash offset against frame
    "GE": 0.02, "GT": 0.02,   # glass bite into sash/frame, glass thickness
    "TWO_SASH_FROM": 1.40,    # clear width from which windows get two sashes
}

_font = [None]
WARNINGS = []   # collected during a call, returned by vw_exec_python


def warn(msg):
    if msg not in WARNINGS:
        WARNINGS.append(msg)


def configure(**kw):
    """Override CONFIG keys, e.g. po4.configure(AW=0.12, FW=0.16)."""
    unknown = [k for k in kw if k not in CONFIG]
    if unknown:
        raise KeyError("unknown po4 setting(s): %s" % ", ".join(unknown))
    CONFIG.update(kw)
    return dict(CONFIG)


def font_id():
    if _font[0] is None:
        _font[0] = vs.GetFontID(CONFIG["FONT"])
    return _font[0]


def _nil(h):
    return h is None or str(h) == "0"


# ---- layers -----------------------------------------------------------------

CONTAINER_NAMES = {11: "a group", 16: "a symbol", 86: "a plug-in object", 122: "a viewport"}


class EditModeError(RuntimeError):
    """New objects would not land on the layer (user is inside an edit mode)."""


def check_on_layer(name=None):
    """Make sure new objects land directly on a layer (on layer `name`, if
    given): draw a probe point, look at its parent, delete it. If the user is
    editing a symbol, group or viewport annotation, raise EditModeError
    (nothing else is touched)."""
    vs.Locus(0, 0)
    probe = vs.LNewObj()
    parent = vs.GetParent(probe)
    ptype = None if _nil(parent) else vs.GetTypeN(parent)
    on_layer = ptype == 31 and (name is None or str(vs.GetLName(parent)) == name)
    where = ""
    if not on_layer and ptype == 31:
        where = "layer %r" % str(vs.GetLName(parent))
    elif not on_layer and not _nil(parent):
        pname = str(vs.GetName(parent) or "")
        where = CONTAINER_NAMES.get(ptype, "an object of type %s" % ptype)
        if pname and pname != "none":
            where += " (%s)" % pname
    vs.DelObject(probe)
    if not on_layer:
        raise EditModeError(
            "Vectorworks is in an edit mode: new objects would land in %s instead of on "
            "%s. Leave the edit mode (Exit Group/Symbol/Annotations) and run again. "
            "Nothing was deleted or drawn." % (where or "another container",
                                               "layer %r" % name if name else "a layer"))


def layer(name, scale=None, clear=False):
    """Create (if needed) and activate a design layer; optionally set its
    scale (e.g. 50 for 1:50) and delete everything on it first, so scripts
    can be re-run (idempotent). Returns the number of objects deleted.
    Raises EditModeError, before changing anything, if Vectorworks is inside
    a symbol, group or viewport edit mode (objects would land there)."""
    check_on_layer()          # before anything changes: not inside a symbol/group
    vs.Layer(name)
    check_on_layer(name)      # and new objects really go to this layer
    h = vs.GetLayerByName(name)
    if scale:
        vs.SetLScale(h, scale)
    deleted = 0
    if clear:
        objs = []
        o = vs.FInLayer(h)
        while not _nil(o):
            objs.append(o)
            o = vs.NextObj(o)
        for o in objs:
            vs.DelObject(o)
        deleted = len(objs)
    return deleted


# ---- attributes and primitives ------------------------------------------------

def fin(h, cl=None):
    """Put h in a class and let it take all graphic attributes from it."""
    vs.SetClass(h, cl or CONFIG["LIGHT"])
    vs.SetPenColorByClass(h)
    vs.SetLWByClass(h)
    vs.SetLSByClass(h)
    vs.SetFPatByClass(h)
    vs.SetFillColorByClass(h)
    try:
        vs.SetOpacityByClass(h)
    except Exception:  # noqa: BLE001 - older versions
        pass
    return h


def P(o, a, w):
    return (a, w) if o == "h" else (w, a)


def seg(x1, y1, x2, y2, cl=None):
    vs.MoveTo(x1, y1)
    vs.LineTo(x2, y2)
    return fin(vs.LNewObj(), cl)


def line(o, a1, w1, a2, w2, cl=None):
    (x1, y1), (x2, y2) = P(o, a1, w1), P(o, a2, w2)
    return seg(x1, y1, x2, y2, cl)


def rect(x1, y1, x2, y2, cl=None):
    vs.Rect(min(x1, x2), max(y1, y2), max(x1, x2), min(y1, y2))
    return fin(vs.LNewObj(), cl or CONFIG["MEDIUM"])


def box(o, a1, a2, w1, w2, cl=None):
    (x1, y1), (x2, y2) = P(o, a1, w1), P(o, a2, w2)
    return rect(x1, y1, x2, y2, cl)


def poly(points, cl=None, closed=True):
    """Polygon from [(x, y), ...]; closed by default (walls: cl=BOLD)."""
    vs.ClosePoly() if closed else vs.OpenPoly()
    vs.BeginPoly()
    for x, y in points:
        vs.AddPoint(x, y)
    vs.EndPoly()
    return fin(vs.LNewObj(), cl or CONFIG["BOLD"])


def union(handles, cl=None):
    """Merge touching surfaces into one (no seams between pieces of the same
    material). Returns the remaining handles (separate groups stay separate)."""
    items = list(handles)
    merged = True
    while merged and len(items) > 1:
        merged = False
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                u = vs.AddSurface(items[i], items[j])
                if not _nil(u):
                    vs.DelObject(items[i])
                    vs.DelObject(items[j])
                    items = [x for k, x in enumerate(items) if k not in (i, j)] + [u]
                    merged = True
                    break
            if merged:
                break
    for h in items:
        fin(h, cl or CONFIG["BOLD"])
    return items


def clip(a, b, cl=None):
    """a minus b; replaces a (holes give a polyline). Returns the new handle."""
    n = vs.ClipSurfaceN(a, b)
    if not _nil(n):
        vs.DelObject(a)
        fin(n, cl or CONFIG["MEDIUM"])
        return n
    return a


def ang(o, da, dw):
    x, y = P(o, da, dw)
    return math.degrees(math.atan2(y, x))


def leaf(o, ah, wh, dir_a, dir_w, length, deg):
    """Door/window leaf: hinge at (ah, wh), closed along dir_a (+1/-1),
    opens towards dir_w (+1/-1) by deg degrees (doors 90, windows 30)."""
    a0 = ang(o, dir_a, 0)
    a1 = ang(o, 0, dir_w)
    sw = (a1 - a0 + 540) % 360 - 180
    sw = math.copysign(deg, sw)
    e = math.radians(a0 + sw)
    x, y = P(o, ah, wh)
    seg(x, y, x + length * math.cos(e), y + length * math.sin(e), CONFIG["SUPERLIGHT"])
    vs.ArcByCenter(x, y, length, a0, sw)
    fin(vs.LNewObj(), CONFIG["SUPERLIGHT"])


# ---- openings -------------------------------------------------------------------

def rebate(o, a0, a1, wo, s):
    """Window rebate at the outer face wo (s = +1/-1 towards inside): two bold
    boxes AW x AT at both reveals. Returns them (union them with the wall)."""
    c = CONFIG
    return [box(o, a0 - c["AW"], a0, wo, wo + s * c["AT"], c["BOLD"]),
            box(o, a1, a1 + c["AW"], wo, wo + s * c["AT"], c["BOLD"])]


def door(o, a0, a1, w0, w1, hinge=-1, swing=1, threshold=True):
    """Door between reveals a0..a1 in a wall w0..w1: leaf + 90 deg arc on the
    face it swings to; hinge -1 at a0, +1 at a1; threshold lines on both faces."""
    face = w1 if swing > 0 else w0
    ah, dir_a = (a0, 1) if hinge < 0 else (a1, -1)
    leaf(o, ah, face, dir_a, swing, a1 - a0, 90)
    if threshold:
        line(o, a0, w0, a1, w0)
        line(o, a0, w1, a1, w1)


def window_simple(o, a0, a1, wo, s, sill_inside=None):
    """Simple window: frame as double line behind the rebate, sash line + 30 deg
    arc, two sashes from TWO_SASH_FROM. sill_inside: inner wall face for the sill."""
    c = CONFIG
    f0 = wo + s * c["AT"]
    line(o, a0, f0, a1, f0)
    line(o, a0, f0 + s * 0.05, a1, f0 + s * 0.05)
    b = a1 - a0
    if b > c["TWO_SASH_FROM"]:
        leaf(o, a0, f0 + s * 0.05, 1, s, b / 2, 30)
        leaf(o, a1, f0 + s * 0.05, -1, s, b / 2, 30)
    else:
        leaf(o, a0, f0 + s * 0.05, 1, s, b, 30)
    line(o, a0, wo, a1, wo)
    if sill_inside is not None:
        line(o, a0 - c["AW"], sill_inside, a1 + c["AW"], sill_inside)


def _sash(o, b0, b1, f0, s, mid_l=False, mid_r=False):
    c = CONFIG
    s0 = f0 + s * c["OV"]
    s1 = s0 + s * c["SD"]
    fc = s0 + s * c["SD"] / 2
    l0 = b0 if mid_l else b0 - c["OV"]
    r1 = b1 if mid_r else b1 + c["OV"]
    g = box(o, l0 + c["SW"] - c["GE"], r1 - c["SW"] + c["GE"], fc - c["GT"] / 2, fc + c["GT"] / 2)
    sq = [clip(box(o, l0, l0 + c["SW"], s0, s1), g), clip(box(o, r1 - c["SW"], r1, s0, s1), g)]
    line(o, l0 + c["SW"], s0, r1 - c["SW"], s0)
    line(o, l0 + c["SW"], s1, r1 - c["SW"], s1)
    return sq


def window_detail(o, a0, a1, wo, s):
    """Detailed window (1:20/1:50): frame, sash(es) and glass in MEDIUM,
    clipped so no outlines overlap; two sashes from TWO_SASH_FROM."""
    c = CONFIG
    f0 = wo + s * c["AT"]
    fr = [box(o, a0, a0 + c["FW"], f0, f0 + s * c["FD"]), box(o, a1 - c["FW"], a1, f0, f0 + s * c["FD"])]
    b0, b1 = a0 + c["FW"], a1 - c["FW"]
    if a1 - a0 > c["TWO_SASH_FROM"]:
        am = (a0 + a1) / 2
        sq = _sash(o, b0, am, f0, s, mid_r=True) + _sash(o, am, b1, f0, s, mid_l=True)
    else:
        sq = _sash(o, b0, b1, f0, s)
    for f in fr:
        for q in sq:
            f = clip(f, q)


def fixed_detail(o, a0, a1, f0, s):
    """Detailed fixed glazing: frames + glass centred in the frame depth."""
    c = CONFIG
    fc = f0 + s * c["FD"] / 2
    g = box(o, a0 + c["FW"] - c["GE"], a1 - c["FW"] + c["GE"], fc - c["GT"] / 2, fc + c["GT"] / 2)
    for f in (box(o, a0, a0 + c["FW"], f0, f0 + s * c["FD"]), box(o, a1 - c["FW"], a1, f0, f0 + s * c["FD"])):
        clip(f, g)
    line(o, a0 + c["FW"], f0, a1 - c["FW"], f0)
    line(o, a0 + c["FW"], f0 + s * c["FD"], a1 - c["FW"], f0 + s * c["FD"])


# ---- text and dimensions ------------------------------------------------------------

def text(x, y, s, cl=None, size=None):
    """Text centred horizontally and vertically at (x, y); '\\r' for line breaks
    (room name + level as ONE text object: 'Küche\\r+0.00')."""
    vs.TextOrigin(x, y)
    vs.CreateText(s)
    t = vs.LNewObj()
    n = len(s)
    vs.SetTextFont(t, 0, n, font_id())
    vs.SetTextSize(t, 0, n, size or CONFIG["TEXT_SIZE"])
    vs.SetTextJust(t, 2)
    vs.SetTextVerticalAlign(t, 3)
    vs.SetClass(t, cl or CONFIG["LIGHT"])
    vs.SetPenColorByClass(t)
    return t


def dim(p1, p2, offset, vertical=False):
    """One dimension: style PO4, precision 0.01 without unit, text centred, 8 pt."""
    vs.TextFont(font_id())
    vs.TextSize(CONFIG["TEXT_SIZE"])           # only this reaches the dimension text
    vs.LinearDim(p1, p2, offset, 1 if vertical else 0, 0, 1, 0)
    d = vs.LNewObj()
    vs.SetObjectVariableString(d, 27, CONFIG["DIM_STYLE"])
    got = vs.GetObjectVariableString(d, 27)
    if got != CONFIG["DIM_STYLE"]:
        # Vectorworks silently falls back to another standard if the name doesn't exist.
        warn("Dimension standard %r is not in this document; Vectorworks used %r. "
             "Add it (Vectorworks Preferences > Dimensions > Custom) or "
             "po4.configure(DIM_STYLE=...)." % (CONFIG["DIM_STYLE"], got))
    vs.SetPrimaryDim(d, True, False, "", "", 2)   # after the style, or a unit sign appears
    vs.SetClass(d, CONFIG["DIM"])
    return d


def chain(pts, o, at, offset):
    """Chain dimension: o='h' -> pts are x values on y=at, offset in +y;
    o='v' -> pts are y values on x=at, offset in +x. One chain object."""
    c = None
    for a, b in zip(pts, pts[1:]):
        p1, p2 = ((a, at), (b, at)) if o == "h" else ((at, a), (at, b))
        d = dim(p1, p2, offset, vertical=(o != "h"))
        c = d if c is None else vs.CreateChainDimension(c, d)
    vs.SetClass(c, CONFIG["DIM"])
    return c


# ---- 3D: stories, levels, walls, slabs ------------------------------------------
# PO4 convention (docs/po4-3d.md): no fixed heights. Walls and slabs are bound
# to story levels by name (OK-FB, OK-RB, UK-RD, ...); the values live in the
# stories only. Two design layers per story: "<story>" (walls, columns, plan)
# and "<story> Boden" (structural slab + floor build-up, slab-edge walls).
# Everything is validated before anything is drawn.
#
# Live findings (VW 2027): the boundStory argument of SetWallOverallHeights /
# SetObjectStoryBound is a RELATIVE story index (0 = this story, 1 = above,
# -1 = below), not a handle; a handle pops a modal Script Errors dialog.
# CreateSlab needs a polygon (a rectangle pops a modal "self-intersecting"
# alert). Story and level elevations come back in mm, geometry in m.

BODEN_SUFFIX = " Boden"


def level_types():
    """Names of the story level types defined in the document."""
    return [str(vs.GetLevelTypeName(i)) for i in range(1, vs.GetNumLayerLevelTypes() + 1)]


def _story_handles():
    """{story name: story handle}, in layer order."""
    out = {}
    h = vs.FLayer()
    while not _nil(h):
        st = vs.GetStoryOfLayer(h)
        if not _nil(st):
            out.setdefault(str(vs.GetName(st)), st)
        h = vs.NextLayer(h)
    return out


def stories():
    """Stories sorted by elevation: name, elevation (m), suffix, levels
    {type: offset to the story in m} (types that are 0 and not OK-FB are left
    out: Vectorworks returns 0 for missing levels), and the layers."""
    types = level_types()
    layers = {}
    h = vs.FLayer()
    while not _nil(h):
        st = vs.GetStoryOfLayer(h)
        if not _nil(st):
            layers.setdefault(str(vs.GetName(st)), []).append(str(vs.GetLName(h)))
        h = vs.NextLayer(h)
    out = []
    for name, st in _story_handles().items():
        lv = {}
        for t in types:
            e = vs.GetLevelElevation(st, t)
            if e or t == "OK-FB":
                lv[t] = round(e / 1000.0, 4)
        out.append({"name": name, "elevation": round(vs.GetStoryElevation(st) / 1000.0, 4),
                    "suffix": str(vs.GetStorySuffix(st)), "levels": lv,
                    "layers": layers.get(name, [])})
    out.sort(key=lambda s: s["elevation"])
    return out


def _need_level(level):
    if level not in level_types():
        raise ValueError("Story level %r does not exist in this document (have: %s)."
                         % (level, ", ".join(level_types())))


def _need_style(name, what):
    idx = vs.Name2Index(name)
    if not idx or idx < 0:
        raise ValueError("%s style %r does not exist in this document." % (what, name))
    return idx


def _need_layer(name):
    h = vs.GetLayerByName(name)
    if _nil(h):
        raise ValueError("Design layer %r does not exist in this document." % name)
    return h


def _goto(layer_name):
    """Activate an EXISTING layer (never creates one) and make sure new
    objects land on it."""
    _need_layer(layer_name)
    check_on_layer()
    vs.Layer(layer_name)
    check_on_layer(layer_name)


def wall(story, p1, p2, style, bottom="OK-RB", top="UK-RD", top_story=1,
         bottom_offset=0.0, top_offset=0.0, bottom_story=0, layer=None):
    """Styled wall from p1 to p2 on layer `story` (or `layer`), bound to story
    levels: by default OK-RB of this story to UK-RD of the story above.
    Offsets in m relative to the level (e.g. top_offset=-0.2). Returns the
    wall handle."""
    layer = layer or story
    _need_level(bottom)
    _need_level(top)
    _need_style(style, "Wall")
    _goto(layer)
    vs.Wall(tuple(p1), tuple(p2))
    w = vs.LNewObj()
    vs.SetWallStyle(w, style, 0, 0)
    vs.SetWallOverallHeights(w, 2, bottom_story, bottom, bottom_offset,
                             2, top_story, top, top_offset)
    vs.ResetObject(w)
    return w


def walls(story, points, style, closed=False, join=True, **kw):
    """Chain of walls through points (closed=True joins the last to the
    first), corners L-joined unless join=False; same keywords as wall().
    Draw closed outlines clockwise so the style's first component (the
    exterior face) lies outside. Returns the handles."""
    pts = [tuple(p) for p in points]
    if closed:
        pts.append(pts[0])
    hs = [wall(story, a, b, style, **kw) for a, b in zip(pts, pts[1:])]
    if join:
        pairs = list(zip(hs, hs[1:]))
        if closed and len(hs) > 2:
            pairs.append((hs[-1], hs[0]))
        for a, b in pairs:
            join_walls(a, b, "L")
    return hs


JOIN_KINDS = {"T": 1, "L": 2, "X": 3, "auto": 4}


def _ends(w):
    return tuple(vs.GetSegPt1(w)), tuple(vs.GetSegPt2(w))


def _toward(p, q, d):
    """Point at distance d from p towards q (at most half way)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    ln = math.hypot(dx, dy) or 1.0
    t = min(d / ln, 0.5)
    return (p[0] + dx * t, p[1] + dy * t)


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _project(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln2 = dx * dx + dy * dy or 1.0
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ln2))
    return (a[0] + dx * t, a[1] + dy * t)


def join_walls(a, b, kind="L", pick=0.3):
    """Join two walls like the Wall Join tool. kind "L": corner at the
    closest pair of end points; "T": wall `b` ends on wall `a` (b is
    trimmed/extended to a's face); "X": crossing. Pick points are placed
    automatically `pick` m from the junction. Returns True on success
    (warns otherwise). Live-tested L and T on VW 2027."""
    if kind not in JOIN_KINDS:
        raise ValueError("kind must be one of %s" % ", ".join(JOIN_KINDS))
    a1, a2 = _ends(a)
    b1, b2 = _ends(b)
    if kind == "T":
        # stem b: its end nearest to a's line; first argument is the stem
        ja = [(_dist(e, _project(e, a1, a2)), e, o) for e, o in ((b1, b2), (b2, b1))]
        _, be, bo = min(ja)
        on_a = _project(be, a1, a2)
        pa = _toward(on_a, a2 if _dist(on_a, a1) < _dist(on_a, a2) else a1, pick)
        ok = vs.JoinWalls(b, a, _toward(be, bo, pick), pa, JOIN_KINDS[kind], False, False)
    else:
        cands = [(_dist(ea, eb), ea, oa, eb, ob)
                 for ea, oa in ((a1, a2), (a2, a1)) for eb, ob in ((b1, b2), (b2, b1))]
        _, ea, oa, eb, ob = min(cands)
        ok = vs.JoinWalls(a, b, _toward(ea, oa, pick), _toward(eb, ob, pick),
                          JOIN_KINDS[kind], False, False)
    vs.ResetObject(a)
    vs.ResetObject(b)
    if not ok:
        warn("Wall join %s failed between %s and %s." % (kind, vs.GetObjectUuid(a), vs.GetObjectUuid(b)))
    return bool(ok)


def _polygon(points):
    vs.ClosePoly()
    vs.BeginPoly()
    for p in points:
        vs.AddPoint(tuple(p))
    vs.EndPoly()
    return vs.LNewObj()


def slab(story, outline, style, level="OK-RB", offset=0.0, layer=None, story_rel=0):
    """Styled slab from a polygon outline [(x, y), ...] on layer
    "<story> Boden" (or `layer`), its datum bound to `level` of this story
    (the style's datum component decides what sits on/under the level).
    Returns the slab handle. Elevations update after the script ends."""
    layer = layer or (story + BODEN_SUFFIX)
    if len(outline) < 3:
        raise ValueError("A slab outline needs at least 3 points.")
    _need_level(level)
    idx = _need_style(style, "Slab")
    _goto(layer)
    s = vs.CreateSlab(_polygon(outline))
    if _nil(s):
        raise RuntimeError("Vectorworks could not create a slab from this outline.")
    vs.SetSlabStyle(s, idx)
    vs.SetObjectStoryBound(s, 0, 2, story_rel, level, offset)
    vs.ResetObject(s)
    return s


def floor(story, outline, structure, buildup, level="OK-RB"):
    """PO4 floor package on "<story> Boden": structural slab and floor
    build-up as two slabs with the same outline, both bound to OK-RB (the
    structural slab's datum is its top, the build-up's its bottom, as defined
    in the styles). Returns (structure, buildup)."""
    _need_style(structure, "Slab")
    _need_style(buildup, "Slab")
    return (slab(story, outline, structure, level),
            slab(story, outline, buildup, level))
