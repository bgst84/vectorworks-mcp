import json, math, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as P, Arc, Rectangle
d = json.load(open(sys.argv[1])); S = json.load(open(sys.argv[2])); out = sys.argv[3]
xlim = ylim = None
if len(sys.argv) > 4: x0,y0,x1,y1 = map(float, sys.argv[4].split(",")); xlim=(x0,x1); ylim=(y0,y1)
fig, ax = plt.subplots(figsize=(22, 12) if not xlim else (12, 12*(ylim[1]-ylim[0])/(xlim[1]-xlim[0])))
scale = 0.6 if not xlim else 2.5
def lw(o): return max(0.15, o["attrs"]["pen"]["weight"] * 0.0254 * 2.83 * scale)
def col(o): return o["attrs"]["pen"]["color"]
def fillc(o):
    f = o["attrs"]["fill"]; 
    if f["pattern"] == 0: return "none"
    return f["back"] if f["pattern"] == 1 else f["fore"]
z = {"0 graphics-a bold-neu": 5, "0 graphics-b medium-neu": 4}
for o in d["objects"]:
    t = o["type"]; zo = z.get(o["class"], 2)
    if t == "Line":
        (a,b),(c,e) = o["points"]; ax.plot([a,c],[b,e], color=col(o), lw=lw(o), zorder=zo)
    elif t == "Arc":
        cx,cy = o["center"]; r = o["radius"]
        ax.add_patch(Arc((cx,cy), 2*r, 2*r, theta1=o["start_angle"], theta2=o["start_angle"]+o["sweep"], color=col(o), lw=lw(o), zorder=zo))
    elif t == "Polygon":
        ax.add_patch(P(o["points"], closed=o.get("closed", True), fill=fillc(o)!="none", facecolor=fillc(o) if fillc(o)!="none" else None, edgecolor=col(o), lw=lw(o), zorder=zo))
    elif t == "Rectangle":
        (a,b),(c,e) = o["bbox_view"]
        ax.add_patch(Rectangle((a,b), c-a, e-b, fill=fillc(o)!="none", facecolor=fillc(o) if fillc(o)!="none" else None, edgecolor=col(o), lw=lw(o), zorder=zo))
    elif t == "Text":
        x,y = o["origin"]; ax.text(x, y, o["text"].replace("\r","\n"), fontsize=6*scale, va="top", ha="left", zorder=6)
for ins in S["ins"]:
    ox, oy = ins["loc"]; th = math.radians(ins["rot"]); ct, st = math.cos(th), math.sin(th)
    T = lambda p: (ox + p[0]*ct - p[1]*st, oy + p[0]*st + p[1]*ct)
    for g in S["defs"].get(ins["name"], []):
        if g["cls"].startswith("0 graphics-h"): continue
        if g["t"] == "line": ax.plot(*zip(*[T(p) for p in g["p"]]), color="#888", lw=0.3*scale, zorder=3)
        elif g["t"] == "poly": ax.add_patch(P([T(p) for p in g["p"]], closed=True, fill=False, edgecolor="#888", lw=0.3*scale, zorder=3))
        elif g["t"] == "arc":
            a,b,c,e = g["bb"]; cx, cy = T(((a+c)/2, (b+e)/2))
            ax.add_patch(Arc((cx,cy), abs(c-a), abs(b-e), angle=ins["rot"], theta1=g["s"], theta2=g["s"]+g["sw"], color="#888", lw=0.3*scale, zorder=3))
ax.set_aspect("equal"); ax.autoscale_view()
if xlim: ax.set_xlim(*xlim); ax.set_ylim(*ylim)
ax.axis("off"); fig.savefig(out, dpi=130, bbox_inches="tight")
