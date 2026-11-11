# PO4 drawing helpers, executed INSIDE Vectorworks as module `po4` when
# vw_exec_python / vw_exec_file are called with po4=True.
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
