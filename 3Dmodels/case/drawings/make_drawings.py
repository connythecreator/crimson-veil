#!/usr/bin/env python3
"""
Dimensioned mechanical drawings for the Crimson Veil Pi-stack case v0.7.

Everything is derived from the constants in ../pi-stack-v0.7.scad.  The Scad
file is parsed as a small expression language, in source order, so a change to
a constant or to a formula in the Scad propagates here without hand editing.

Output: eight A3-landscape SVG sheets in this directory.  One SVG user unit is
one millimetre of paper; a view at 1:1 draws one model millimetre per unit.

    python3 make_drawings.py            # write the SVG sheets and run checks
    python3 make_drawings.py --png      # ...and render PNG previews
    python3 make_drawings.py --check    # checks only, no files written

Only the Python standard library is used.  PNG previews use a headless
Chromium if one is present (optional, for visual checking only).
"""

from __future__ import annotations

import ast
import math
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
SCAD = CASE / "pi-stack-v0.7.scad"
VERIFY = CASE / "verify.py"
OUT = HERE

# =====================================================================
#  1.  Parse the Scad's constants
# =====================================================================
#  The Scad is not Python, but its constant block is arithmetic plus arrays
#  and one ternary.  OpenSCAD's trig functions take and return DEGREES; the
#  wrappers below mirror that.  Statements are joined until a semicolon so the
#  multi-line arrays (SCREWS, PLATE_BOLTS, LCD_PADS) parse as one expression.

D2R = math.pi / 180.0


def _sin(d):
    return math.sin(d * D2R)


def _cos(d):
    return math.cos(d * D2R)


def _tan(d):
    return math.tan(d * D2R)


def _asin(x):
    return math.degrees(math.asin(x))


def _acos(x):
    return math.degrees(math.acos(x))


def _atan(x):
    return math.degrees(math.atan(x))


def _atan2(y, x):
    return math.degrees(math.atan2(y, x))


BASE_ENV = {
    "__builtins__": {},
    "math": math,
    "pi": math.pi,
    "PI": math.pi,
    "sqrt": math.sqrt,
    "abs": abs,
    "min": min,
    "max": max,
    "pow": pow,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "sin": _sin,
    "cos": _cos,
    "tan": _tan,
    "asin": _asin,
    "acos": _acos,
    "atan": _atan,
    "atan2": _atan2,
    "true": True,
    "false": False,
    "undef": None,
}


def _statements(path: Path):
    """Yield the file's 'NAME = expression' statements, joined across lines."""
    buf = ""
    for raw in path.read_text().splitlines():
        line = raw.split("//")[0].split("#")[0].strip()
        if not line:
            continue
        buf = (buf + " " + line).strip()
        if buf.endswith(";"):
            for part in buf.split(";"):
                part = part.strip()
                if part:
                    yield part
            buf = ""
    if buf:
        yield buf


def parse_constants(path: Path):
    """Evaluate every top-level constant assignment in source order."""
    env = dict(BASE_ENV)
    skipped = []
    for stmt in _statements(path):
        m = re.match(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.+)$", stmt, re.S)
        if not m:
            continue
        name, expr = m.group(1), m.group(2).strip()
        # OpenSCAD ternary, written once in the file (LCD_UNDER).
        if "?" in expr:
            tm = re.match(r"^(.*?)\?\s*(.*?)\s*:\s*(.*)$", expr, re.S)
            if not tm:
                skipped.append(name)
                continue
            expr = f"(({tm.group(2)}) if ({tm.group(1)}) else ({tm.group(3)}))"
        if any(tok in expr for tok in ("str(", "echo(", "import", "$", "for (",
                                       "function(", "children(", "linear_ext")):
            skipped.append(name)
            continue
        try:
            value = eval(expr, env)  # noqa: S307 - a deliberately tiny evaluator
        except Exception:
            skipped.append(name)
            continue
        env[name] = value
    return env, skipped


SCAD_ENV, SCAD_SKIPPED = parse_constants(SCAD)
VERIFY_ENV, VERIFY_SKIPPED = parse_constants(VERIFY)

#  Multi-line arrays parse, but the six screw columns are asserted here too:
#  every drawing refers to them, and a silent drift would move every callout.
SCREWS = [tuple(float(v) for v in s) for s in SCAD_ENV["SCREWS"]]
PLATE_BOLTS = [tuple(float(v) for v in b) for b in SCAD_ENV["PLATE_BOLTS"]]
PI_OFF = [float(v) for v in SCAD_ENV["OFF"]]


class Dims:
    """Attribute access to the parsed Scad constants."""

    def __init__(self, env):
        self.__dict__.update(env)

    def __getattr__(self, name):
        raise AttributeError(f"constant {name!r} was not parsed from the .scad")


D = Dims(SCAD_ENV)

#  A few values the Scad draws inside modules rather than naming as constants.
PI_HOLES = [
    (D.PCB_X + D.PI_HOLE_IN + i * D.PI_HOLE_DX,
     D.PCB_Y + D.PI_HOLE_IN + j * D.PI_HOLE_DY)
    for i in (0, 1) for j in (0, 1)
]

PI_W = D.OW
PI_D = D.OD
MID_LO = D.JOINT_A + D.MATE_GAP             # 5.70, the MID's underside
BEZEL_LO = D.SPLIT_B + D.MATE_GAP           # 40.80, the BEZEL's underside
PLATE_Z0 = -(D.PLATE_GAP + D.PLATE_T)       # -4.50
PLATE_Z1 = -D.PLATE_GAP                     # -0.50
SKIRT_Z0 = -(D.PLATE_GAP + D.PLATE_SKIRT_OVERLAP)   # -1.00
SKIRT_Z1 = D.PLATE_SKIRT_TOP                # +3.00
PLATE_PRINT_H = SKIRT_Z1 - PLATE_Z0         # 7.50, in print orientation
PLATE_FLOOR_T = D.PLATE_T                   # 4.00, printed on the bed

#  A port box in case coordinates, with the clearance and the "open to the
#  MID's bottom edge" override the Scad's wall_cut() applies.
def port_box(box, g=None, zb=None):
    g = D.PORT_G if g is None else g
    return {
        "x0": box[0] + D.OFF[0] - g,
        "x1": box[1] + D.OFF[0] + g,
        "y0": box[2] + D.OFF[1] - g,
        "y1": box[3] + D.OFF[1] + g,
        "z0": (box[4] + D.OFF[2] - g) if zb is None else zb,
        "z1": box[5] + D.OFF[2] + g,
    }


_ZB = D.JOINT_A - 2.0
PORTS = {
    "ETH": (port_box(D.ETH, zb=_ZB), "+X"),
    "USB": (port_box(D.USB, zb=_ZB), "+X"),
    "PWR": (port_box(D.PWR, zb=_ZB), "-Y"),
    "HDMI": (port_box(D.HDMI, zb=_ZB), "-Y"),
    "AUDIO": (port_box(D.AUDIO, zb=_ZB), "-Y"),
    "SD": (port_box(D.SD, zb=_ZB), "-X"),
}

#  The web between ETH and USB is removed by its own overlapping cut; these
#  are the Scad's own expressions for that box.
WEB_Y0 = D.ETH[3] + D.OFF[1] + D.PORT_G - 1.00
WEB_Y1 = D.USB[2] + D.OFF[1] - D.PORT_G + 1.00
WEB_Z1 = D.USB[5] + D.OFF[2] + D.PORT_G + 0.50
WEB = {"y0": WEB_Y0, "y1": WEB_Y1, "z0": _ZB, "z1": WEB_Z1}

#  The +X opening as one stepped polygon, in (y, z).  Derived by unioning the
#  three cuts: ETH to 6.68, the removed web to 25.57, USB to 25.07.
ETH = PORTS["ETH"][0]
USB = PORTS["USB"][0]
STEP_X = [
    (ETH["y0"], MID_LO),
    (ETH["y0"], ETH["z1"]),
    (WEB_Y0, ETH["z1"]),
    (WEB_Y0, WEB_Z1),
    (WEB_Y1, WEB_Z1),
    (WEB_Y1, USB["z1"]),
    (USB["y1"], USB["z1"]),
    (USB["y1"], MID_LO),
]

HEXES = []
for i in range(int(D.HEX_NX)):
    for j in range(int(D.HEX_NZ)):
        HEXES.append((
            D.HEX_X0 + i * D.HEX_DX,
            D.HEX_Z0 + j * D.HEX_DZ + (i % 2) * D.HEX_DZ / 2.0,
        ))

VENT_X = [D.OW / 2 + (i - (D.VENT_N - 1) / 2.0) * D.VENT_P
          for i in range(int(D.VENT_N))]

ACC_X0 = D.ACC_CX - D.ACC_W / 2.0
ACC_X1 = D.ACC_CX + D.ACC_W / 2.0
ACC_Z0 = D.ACC_CZ - D.ACC_H / 2.0
ACC_Z1 = D.ACC_CZ + D.ACC_H / 2.0

LED_X = [D.LED_X0 + i * D.LED_PITCH for i in range(int(D.LED_N))]
SW_X = [D.SW_X0 + i * D.SW_PITCH for i in range(int(D.SW_N))]
SW_Z0 = D.PANEL_Z - D.SW_POCKET / 2.0
SW_Z1 = D.PANEL_Z + D.SW_POCKET / 2.0

SHELF_Z0 = D.SPLIT_B - D.SHELF_T            # 38.60
SHELF_OPEN_W = D.IW - 2 * D.SHELF_W         # 80.12
SHELF_OPEN_D = D.ID - 2 * D.SHELF_W         # 51.20

#  The strap arms: four copies of a two-lobe hull on the corner diagonal,
#  each with a CUT waist.  The tip paddle's rear arc reaches back to r 60.00,
#  so the neck circle alone is not a waist: two Ø8.00 circles at r 64.00,
#  ±10.00 off the arm axis, cut the outline and leave a 12.00 seat.
ARM_ANG = math.radians(D.PLATE_ARM_ANG)
ARM_C = math.cos(ARM_ANG)
ARM_S = math.sin(ARM_ANG)
ARM_ANGLES = (D.PLATE_ARM_ANG, 180 - D.PLATE_ARM_ANG,
              180 + D.PLATE_ARM_ANG, -D.PLATE_ARM_ANG)
ARM_REACH_X = D.PLATE_ARM_TIP_R * ARM_C + D.PLATE_ARM_TIP_D / 2.0
ARM_REACH_Y = D.PLATE_ARM_TIP_R * ARM_S + D.PLATE_ARM_TIP_D / 2.0
ARM_X0 = D.PLATE_CX - ARM_REACH_X
ARM_X1 = D.PLATE_CX + ARM_REACH_X
ARM_Y0 = D.PLATE_CY - ARM_REACH_Y
ARM_Y1 = D.PLATE_CY + ARM_REACH_Y
ARM_SPAN_X = ARM_X1 - ARM_X0
ARM_SPAN_Y = ARM_Y1 - ARM_Y0
WAIST_OFF = D.PLATE_ARM_WAIST_OFF
WAIST_R = D.PLATE_ARM_GROOVE_R
WAIST_W = D.PLATE_ARM_WAIST_D

#  The exported mesh is polygonised at $fn = 48, so its bounding box is a
#  hair smaller than the analytic tip-circle extremes.  Both are stated on
#  the plate sheet; these are the export figures the Scad echo reports.
ARM_EXPORT_X = 134.89
ARM_EXPORT_Y = 99.95


def _in_rrect(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _in_hull(u, v, x0, r0, x1, r1):
    """Membership of the convex hull of two circles (same as hull() in 2-D)."""
    if u <= x0:
        return (u - x0) ** 2 + v * v <= r0 * r0
    if u >= x1:
        return (u - x1) ** 2 + v * v <= r1 * r1
    t = (u - x0) / (x1 - x0)
    rr = r0 + (r1 - r0) * t
    return v * v <= rr * rr


def _arm_base(u, v):
    return (_in_hull(u, v, D.PLATE_ARM_ROOT_R, D.PLATE_ARM_ROOT_D / 2,
                     D.PLATE_ARM_NECK_R, D.PLATE_ARM_NECK_D / 2)
            or _in_hull(u, v, D.PLATE_ARM_NECK_R, D.PLATE_ARM_NECK_D / 2,
                        D.PLATE_ARM_TIP_R, D.PLATE_ARM_TIP_D / 2))


def plate_member(x, y):
    """The strap plate's floor outline, including the four cut waists."""
    inside = _in_rrect(x, y, D.PLATE_TRAY_X0, D.PLATE_TRAY_Y0,
                       D.PLATE_TRAY_X1, D.PLATE_TRAY_Y1, D.PLATE_TRAY_R)
    if not inside:
        for a in ARM_ANGLES:
            ca, sa = _cos(a), _sin(a)
            dx, dy = x - D.PLATE_CX, y - D.PLATE_CY
            u, v = dx * ca + dy * sa, -dx * sa + dy * ca
            if _arm_base(u, v):
                inside = True
                break
    if not inside:
        return False
    for a in ARM_ANGLES:
        ca, sa = _cos(a), _sin(a)
        dx, dy = x - D.PLATE_CX, y - D.PLATE_CY
        u, v = dx * ca + dy * sa, -dx * sa + dy * ca
        for sv in (-WAIST_OFF, WAIST_OFF):
            if (u - D.PLATE_ARM_NECK_R) ** 2 + (v - sv) ** 2 < WAIST_R ** 2:
                return False
    return True


def trace_outline(fn, x0, y0, x1, y1, step=0.2):
    """Marching-squares segments of a membership function, in model coords.

    Segments are returned unconnected: at this resolution the drawing reads
    as a continuous outline, and no contour stitching is needed.
    """
    nx = max(2, int(math.ceil((x1 - x0) / step)))
    ny = max(2, int(math.ceil((y1 - y0) / step)))
    dx, dy = (x1 - x0) / nx, (y1 - y0) / ny
    vals = [[fn(x0 + i * dx, y0 + j * dy) for i in range(nx + 1)]
            for j in range(ny + 1)]
    segs = []
    for j in range(ny):
        for i in range(nx):
            corners = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
            pts = []
            for k in range(4):
                a = corners[k]
                b = corners[(k + 1) % 4]
                va, vb = vals[a[1]][a[0]], vals[b[1]][b[0]]
                if va != vb:
                    t = (0.5 - va) / (vb - va) if va != vb else 0.5
                    t = min(1.0, max(0.0, t))
                    ax, ay = x0 + a[0] * dx, y0 + a[1] * dy
                    bx, by = x0 + b[0] * dx, y0 + b[1] * dy
                    pts.append((ax + t * (bx - ax), ay + t * (by - ay)))
            if len(pts) == 2:
                segs.append((pts[0], pts[1]))
            elif len(pts) == 4:
                segs.append((pts[0], pts[1]))
                segs.append((pts[2], pts[3]))
    return segs


_PLATE_SEGS = None


def plate_outline_segments(step=0.2):
    global _PLATE_SEGS
    if _PLATE_SEGS is None:
        _PLATE_SEGS = trace_outline(plate_member, ARM_X0 - 0.5,
                                    ARM_Y0 - 0.5, ARM_X1 + 0.5,
                                    ARM_Y1 + 0.5, step)
    return _PLATE_SEGS


def outline_topology(step=0.16):
    """Return (segments, vertices not of degree 2, connected loops).

    The traced plate outline is drawn as unconnected marching-squares
    segments, so close it explicitly here: every junction must have exactly
    two neighbours and all segments must form one loop.
    """
    segs = plate_outline_segments(step)
    key = lambda p: (round(p[0], 6), round(p[1], 6))
    deg, adj = {}, {}
    for a, b in segs:
        ka, kb = key(a), key(b)
        if ka == kb:
            continue
        deg[ka] = deg.get(ka, 0) + 1
        deg[kb] = deg.get(kb, 0) + 1
        adj.setdefault(ka, set()).add(kb)
        adj.setdefault(kb, set()).add(ka)
    bad = [k for k, d in deg.items() if d != 2]
    seen, loops = set(), 0
    for start in adj:
        if start in seen:
            continue
        loops += 1
        seen.add(start)
        stack = [start]
        while stack:
            p = stack.pop()
            for q in adj[p]:
                if q not in seen:
                    seen.add(q)
                    stack.append(q)
    return len(segs), bad, loops

#  Expected values, checked against the parse.  These are the brief's numbers
#  and the Scad's own echo lines, never inputs to the drawing.
EXPECT = {
    "OW": 95.12, "OD": 66.20, "OH": 49.20, "IW": 86.12, "ID": 57.20,
    "JOINT_A": 5.50, "MID_H": 34.90, "SPLIT_B": 40.60,
    "POCK_W": 86.60, "POCK_D": 57.20, "WIN_W": 81.80, "WIN_D": 51.60,
    "PLATE_ARM_ANG": 34.84,
    "PLATE_TRAY_X1": 98.62, "PLATE_TRAY_Y1": 69.70,
}

COMPARE_NAMES = [
    "OW", "OD", "WALL", "CLR", "FLOOR", "JOINT_A", "MATE_GAP", "IW", "ID",
    "SHELF_T", "SHELF_W", "LCD_T", "BEZEL_T", "LCD_W", "LCD_D", "LCD_FIT",
    "LCD_LIP", "PCB_X", "PCB_Y", "PCB_Z", "PI_PCB_T", "PI_HOLE_DX",
    "PI_HOLE_DY", "PI_HOLE_D", "PI_HOLE_IN", "PI_SCREW_CLR", "PI_CBORE_D",
    "PI_CBORE_H", "BOSS_D", "SCREW_CLR", "SCREW_PILOT", "SCREW_DEEP",
    "SCREW_CBORE_D", "SCREW_CBORE_H", "SCREW_CSK_D", "SCREW_CSK_H",
    "SCREW_L", "STACK_MEASURED", "LCD_TOP_Z", "LCD_UNDER", "LCD_DROP",
    "WP_H", "WITTY_Z", "EXT_HEADER", "HDR_BODY", "HDR_BODY_W", "HDR_BODY_D",
    "HDR_PIN_L", "HDR_STANDOFF", "HDR_TIP_Z", "SPLIT_B", "MID_H", "OH",
    "PLATE_CX", "PLATE_CY", "PLATE_BOLT_DX", "PLATE_BOLT_DY", "PLATE_GAP",
    "PLATE_T", "PLATE_R", "PLATE_CBORE_D", "PLATE_CBORE_H", "PLATE_PILOT_D",
    "PLATE_PILOT_DEEP", "PLATE_BOSS_D", "PLATE_BOSS_H", "PLATE_SCREW_L",
    "PLATE_SKIRT_CLR", "PLATE_SKIRT_T", "PLATE_SKIRT_TOP",
    "PLATE_SKIRT_OVERLAP", "PLATE_TRAY_R", "PLATE_ARM_ROOT_R",
    "PLATE_ARM_ROOT_D", "PLATE_ARM_NECK_R", "PLATE_ARM_NECK_D",
    "PLATE_ARM_TIP_R", "PLATE_ARM_TIP_D", "HEX_R", "HEX_DX", "HEX_DZ",
    "HEX_X0", "HEX_NX", "HEX_Z0", "HEX_NZ", "LEAD_RX0", "LEAD_RX1",
    "LEAD_RZ0", "LEAD_RZ1", "VENT_N", "VENT_W", "VENT_H", "VENT_P",
    "VENT_Z", "PANEL_Z", "LED_N", "LED_D", "LED_PITCH", "LED_X0", "SW_N",
    "SW_BODY", "SW_H", "SW_POCKET", "SW_LIP", "SW_BTN_D", "SW_PITCH",
    "SW_X0", "SW_RIB", "ACC_MIN_W", "ACC_MIN_H", "ACC_W", "ACC_H", "ACC_R",
]


def compare_sources():
    """Report every value the Scad and verify.py both carry and disagree on."""
    diffs = []
    for name in COMPARE_NAMES:
        a = SCAD_ENV.get(name)
        b = VERIFY_ENV.get(name)
        if a is None or b is None:
            continue
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if abs(float(a) - float(b)) > 5e-4:
                diffs.append((name, float(a), float(b)))
    return diffs


# =====================================================================
#  2.  SVG drawing library
# =====================================================================

STYLE = {
    "outline":   ("#101010", 0.50, None),
    "feature":   ("#101010", 0.30, None),
    "hidden":    ("#333333", 0.24, "2.0 1.2"),
    "centre":    ("#444444", 0.18, "5 1 0.8 1"),
    "seam":      ("#666666", 0.20, "3 1.2"),
    "dim":       ("#1a1a48", 0.18, None),
    "ext":       ("#1a1a48", 0.15, None),
    "leader":    ("#1a1a48", 0.18, None),
    "section":   ("#101010", 0.35, None),
    "frame":     ("#000000", 0.50, None),
    "frame2":    ("#000000", 0.22, None),
    "border":    ("#000000", 0.25, None),
}


def fmt(v, nd=2):
    """Format a millimetre value the way the sheets read it."""
    if abs(v - round(v)) < 5e-4 and nd == 2:
        return f"{v:.2f}"
    return f"{v:.{nd}f}"


def clean(v):
    """Round away floating-point grit before display."""
    return round(float(v), 6)


class Sheet:
    """One A3 page: frame, title block, drawing primitives, checks."""

    def __init__(self, number, title, subtitle, sheet_scale="1:1"):
        self.number = number
        self.title = title
        self.subtitle = subtitle
        self.sheet_scale = sheet_scale
        self.items = []
        self.texts = []         # (x, y, w, h, text, kind)
        self.checks = []
        self.dim_values = []
        self.views = []         # (name, x0, y0, x1, y1) in paper mm

    # ---- primitive output ------------------------------------------------
    def add(self, markup):
        self.items.append(markup)

    def line(self, x1, y1, x2, y2, kind="feature"):
        colour, width, dash = STYLE[kind]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" '
                 f'y2="{y2:.3f}" stroke="{colour}" stroke-width="{width}"'
                 f'{d} stroke-linecap="round"/>')

    def polyline(self, pts, kind="outline", closed=False):
        colour, width, dash = STYLE[kind]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
        tag = "polygon" if closed else "polyline"
        self.add(f'<{tag} points="{p}" fill="none" stroke="{colour}" '
                 f'stroke-width="{width}"{d} stroke-linejoin="round" '
                 f'stroke-linecap="round"/>')

    def rect(self, x, y, w, h, kind="outline", rx=0, fill="none",
             opacity=None):
        colour, width, dash = STYLE[kind]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' fill-opacity="{opacity}"' if opacity is not None else ""
        self.add(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" '
                 f'height="{h:.3f}" rx="{rx:.3f}" fill="{fill}" '
                 f'stroke="{colour}" stroke-width="{width}"{d}{o}/>')

    def rrect(self, x, y, w, h, r, kind="outline", fill="none"):
        """Rounded rectangle in paper coords (x, y is the top-left)."""
        colour, width, dash = STYLE[kind]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        r = max(0.0, min(r, w / 2, h / 2))
        path = (f"M{x+r:.3f},{y:.3f} H{x+w-r:.3f} "
                f"A{r:.3f},{r:.3f} 0 0 1 {x+w:.3f},{y+r:.3f} "
                f"V{y+h-r:.3f} A{r:.3f},{r:.3f} 0 0 1 {x+w-r:.3f},{y+h:.3f} "
                f"H{x+r:.3f} A{r:.3f},{r:.3f} 0 0 1 {x:.3f},{y+h-r:.3f} "
                f"V{y+r:.3f} A{r:.3f},{r:.3f} 0 0 1 {x+r:.3f},{y:.3f} Z")
        self.add(f'<path d="{path}" fill="{fill}" stroke="{colour}" '
                 f'stroke-width="{width}"{d}/>')

    def circle(self, cx, cy, r, kind="feature", fill="none"):
        colour, width, dash = STYLE[kind]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" '
                 f'fill="{fill}" stroke="{colour}" stroke-width="{width}"{d}/>')

    def hatch(self, pts, pattern="hatch"):
        p = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
        self.add(f'<polygon points="{p}" fill="url(#{pattern})" '
                 f'stroke="#101010" stroke-width="0.35" '
                 f'stroke-linejoin="round"/>')

    def text(self, x, y, s, size=2.35, anchor="start", weight="normal",
             rot=None, italic=False, kind="dim", halo=True, fill=None):
        colour = fill or ("#1a1a48" if kind == "dim" else "#101010")
        style = ""
        if halo:
            style = ' style="paint-order:stroke;stroke:#ffffff;' \
                    'stroke-width:1.55;stroke-linejoin:round"'
        tr = f' transform="rotate({rot} {x:.3f} {y:.3f})"' if rot else ""
        extra = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x:.3f}" y="{y:.3f}" font-family="DejaVu Sans, '
                 f'Arial, sans-serif" font-size="{size}" fill="{colour}" '
                 f'font-weight="{weight}" text-anchor="{anchor}"{tr}{style}'
                 f'{extra}>{escape(str(s))}</text>')
        # Approximate text box, for overlap checks.
        w = 0.56 * size * len(str(s))
        h = size * 0.95
        if anchor == "middle":
            bx = x - w / 2
        elif anchor == "end":
            bx = x - w
        else:
            bx = x
        if rot:
            bx, w, h = x - h / 2, h, w
        self.texts.append((bx, y - h, w, h * 1.2, str(s), kind))

    # ---- dimensions ------------------------------------------------------
    def arrow(self, x, y, dx, dy, size=2.0, half=0.72):
        """A filled arrowhead at (x, y), pointing along (dx, dy)."""
        n = math.hypot(dx, dy)
        if n < 1e-9:
            return
        ux, uy = dx / n, dy / n
        px, py = -uy, ux
        bx, by = x - ux * size, y - uy * size
        self.add(f'<polygon points="{x:.3f},{y:.3f} '
                 f'{bx+px*half:.3f},{by+py*half:.3f} '
                 f'{bx-px*half:.3f},{by-py*half:.3f}" '
                 f'fill="#1a1a48" stroke="none"/>')

    def dim_h(self, x1, x2, yl, label, f1, f2, text_out="auto",
              size=2.25, gap=1.1, over=1.6):
        """Horizontal dimension in paper coords.

        x1, x2   measured points on the dimension line
        yl       the dimension line
        f1, f2   the feature y each extension line starts from
        """
        s = 1 if x2 >= x1 else -1
        self.line(min(x1, x2) - over * s, yl, max(x1, x2) + over * s, yl, "dim")
        for x, fy in ((x1, f1), (x2, f2)):
            sy = 1 if yl > fy else -1
            self.line(x, fy + sy * gap, x, yl + sy * over, "ext")
        self.arrow(x1, yl, -s, 0)
        self.arrow(x2, yl, s, 0)
        outward_up = yl < f1
        if text_out == "auto":
            ty = yl - 1.0 if outward_up else yl + size + 0.6
        elif text_out == "above":
            ty = yl - 1.0
        else:
            ty = yl + size + 0.6
        self.text((x1 + x2) / 2.0, ty, label, size=size, anchor="middle")
        self.dim_values.append(label)

    def dim_v(self, y1, y2, xl, label, f1, f2, text_out="auto",
              size=2.25, gap=1.1, over=1.6):
        """Vertical dimension in paper coords (y grows downward)."""
        s = 1 if y2 >= y1 else -1
        self.line(xl, min(y1, y2) - over * s, xl, max(y1, y2) + over * s, "dim")
        for y, fx in ((y1, f1), (y2, f2)):
            sx = 1 if xl > fx else -1
            self.line(fx + sx * gap, y, xl + sx * over, y, "ext")
        self.arrow(xl, y1, 0, -s)
        self.arrow(xl, y2, 0, s)
        out_left = xl < f1
        if text_out == "auto":
            tx = xl - 1.1 if out_left else xl + 1.1
        elif text_out == "left":
            tx = xl - 1.1
        else:
            tx = xl + 1.1
        self.text(tx, (y1 + y2) / 2.0, label, size=size, anchor="middle",
                  rot=-90)
        self.dim_values.append(label)

    def dim_small_v(self, y1, y2, xl, label, f1, f2, size=2.1):
        """A short vertical dimension: arrows outside, text beside the span."""
        mid = (y1 + y2) / 2.0
        lo, hi = min(y1, y2), max(y1, y2)
        self.line(xl, lo, xl, hi, "dim")
        for y, fx in ((y1, f1), (y2, f2)):
            sx = 1 if xl > fx else -1
            self.line(fx + sx * 1.0, y, xl + sx * 1.0, y, "ext")
        self.arrow(xl, lo, 0, 1)
        self.arrow(xl, hi, 0, -1)
        self.text(xl + 1.6, mid + size * 0.35, label, size=size,
                  anchor="start")
        self.dim_values.append(label)

    def ordinate_h(self, xs, yl, ref, f, labels=None, size=2.05,
                   above=True, over=1.6):
        """Ordinate x dimension: one line, a tick at each unique x."""
        if not xs:
            return
        self.line(min(min(xs), ref) - over, yl, max(xs) + over, yl, "dim")
        self.line(ref, f + (1.0 if yl > f else -1.0), ref,
                  yl + (1.0 if yl > f else -1.0), "ext")
        self.circle(ref, yl, 0.55, "dim", fill="#1a1a48")
        for i, x in enumerate(xs):
            self.line(x, f + (1.0 if yl > f else -1.0), x,
                      yl + (1.0 if yl > f else -1.0), "ext")
            self.line(x - 0.8, yl + 0.8, x + 0.8, yl - 0.8, "dim")
            if labels is not None:
                lab = labels[i]
            else:
                v = x - ref
                lab = fmt(v)
                self.dim_values.append(lab)
            ty = yl - 1.0 if above else yl + size + 0.7
            self.text(x, ty, lab, size=size, anchor="middle")

    def ordinate_v(self, ys, xl, ref, f, labels=None, size=2.05,
                   right=True, over=1.6):
        """Ordinate y (vertical) dimension, ticks pointing out of the part."""
        if not ys:
            return
        self.line(xl, min(min(ys), ref) - over, xl, max(ys) + over, "dim")
        self.line(f + (1.0 if xl > f else -1.0), ref, xl + (1.0 if xl > f else -1.0),
                  ref, "ext")
        self.circle(xl, ref, 0.55, "dim", fill="#1a1a48")
        for i, y in enumerate(ys):
            self.line(f + (1.0 if xl > f else -1.0), y,
                      xl + (1.0 if xl > f else -1.0), y, "ext")
            self.line(xl - 0.8, y + 0.8, xl + 0.8, y - 0.8, "dim")
            if labels is not None:
                lab = labels[i]
            else:
                v = ref - y
                lab = fmt(v)
                self.dim_values.append(lab)
            tx = xl + 1.4 if right else xl - 1.4
            self.text(tx, y + size * 0.35, lab, size=size,
                      anchor="start" if right else "end")

    def leader(self, x, y, tx, ty, text, anchor="start", size=2.2,
               tail=2.6):
        """Leader from feature (x, y) to a text shoulder at (tx, ty)."""
        dx, dy = x - tx, y - ty
        n = math.hypot(dx, dy) or 1.0
        # Arrow points INTO the feature.
        start_x, start_y = x - dx / n * 1.4, y - dy / n * 1.4
        self.line(start_x, start_y, tx, ty, "leader")
        if anchor == "start":
            self.line(tx - tail, ty, tx, ty, "leader")
            self.arrow(x, y, dx, dy, size=1.8, half=0.62)
            self.text(tx + 0.9, ty + size * 0.38, text, size=size,
                      anchor="start")
        else:
            self.line(tx, ty, tx + tail, ty, "leader")
            self.arrow(x, y, dx, dy, size=1.8, half=0.62)
            self.text(tx - 0.9, ty + size * 0.38, text, size=size,
                      anchor="end")

    def centre_cross(self, cx, cy, r=3.5, kind="centre"):
        self.line(cx - r, cy, cx + r, cy, kind)
        self.line(cx, cy - r, cx, cy + r, kind)

    # ---- view bookkeeping and checks ------------------------------------
    def view(self, name, x0, y0, x1, y1):
        self.views.append((name, min(x0, x1), min(y0, y1),
                           max(x0, x1), max(y0, y1)))

    def view_label(self, text, x, y, size=2.9, anchor="start"):
        self.text(x, y, text, size=size, anchor=anchor, weight="bold",
                  kind="note", halo=False)
        w = 0.56 * size * len(text)
        bx = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        self.line(bx, y + 0.8, bx + w, y + 0.8, "border")

    def note(self, x, y, lines, size=2.4, spacing=3.5, title=None):
        yy = y
        if title:
            self.text(x, yy, title, size=size + 0.35, weight="bold",
                      kind="note", halo=False)
            self.line(x, yy + 1.0, x + 0.56 * (size + 0.35) * len(title),
                      yy + 1.0, "border")
            yy += spacing + 1.2
        for ln in lines:
            self.text(x, yy, ln, size=size, kind="note", halo=False)
            yy += spacing
        return yy

    def check(self, ok, msg):
        self.checks.append((bool(ok), msg))

    def run_checks(self):
        problems = list(self.checks)
        # Text-on-text collisions, excluding tiny intentional overlaps.
        for i in range(len(self.texts)):
            ax, ay, aw, ah, at, ak = self.texts[i]
            for j in range(i + 1, len(self.texts)):
                bx, by, bw, bh, bt, bk = self.texts[j]
                ox = min(ax + aw, bx + bw) - max(ax, bx)
                oy = min(ay + ah, by + bh) - max(ay, by)
                if ox > 0.35 and oy > 0.35:
                    area = ox * oy
                    if area > 1.2:
                        problems.append(
                            (False, f"text overlap: {at!r} / {bt!r} "
                                    f"({ox:.1f}x{oy:.1f} mm)"))
        # Views inside the drawing area.
        for name, x0, y0, x1, y1 in self.views:
            if x0 < 11.5 or x1 > 408.5 or y0 < 22.0 or y1 > 243.0:
                problems.append((False, f"view {name} outside drawing area: "
                                        f"{x0:.1f},{y0:.1f}..{x1:.1f},{y1:.1f}"))
        # Absurd dimension values.
        for v in self.dim_values:
            try:
                num = float(v)
            except ValueError:
                continue
            if abs(num) > 500:
                problems.append((False, f"absurd dimension {v}"))
            if num < -0.001:
                problems.append((False, f"negative dimension {v}"))
        return problems

    # ---- frame and title block ------------------------------------------
    def frame(self):
        self.rect(8, 8, 404, 281, "frame")
        self.rect(10, 10, 400, 277, "frame2")
        # Zone marks, A3 sheet: 8 columns and 6 rows.
        for i in range(1, 8):
            x = 10 + 400 * i / 8
            self.line(x, 10, x, 12, "frame2")
            self.line(x, 285, x, 287, "frame2")
            # The top band carries the sheet header, so zone numbers are
            # printed along the bottom only.
            self.text(x, 284, str(8 - i), size=1.8, anchor="middle",
                      kind="note", halo=False)
        for j in range(1, 6):
            y = 10 + 277 * j / 6
            self.line(10, y, 12, y, "frame2")
            self.line(408, y, 410, y, "frame2")
            self.text(6.6, y + 1.0, "ABCDEF"[j - 1], size=1.8,
                      anchor="middle", kind="note", halo=False)
            self.text(413.3, y + 1.0, "ABCDEF"[j - 1], size=1.8,
                      anchor="middle", kind="note", halo=False)
        # Header.
        self.text(14, 17.5, "CRIMSON VEIL  —  PI-STACK CASE v0.7",
                  size=4.2, weight="bold", kind="note", halo=False)
        self.text(14, 12.0, "DIMENSIONED MECHANICAL DRAWINGS  ·  "
                            "DERIVED FROM pi-stack-v0.7.scad",
                  size=2.2, kind="note", halo=False, italic=True)
        self.text(406, 17.0, f"SHEET {self.number} OF 8", size=3.0,
                  anchor="end", weight="bold", kind="note", halo=False)
        self.line(12, 20.2, 408, 20.2, "border")

    def title_block(self, material="PLA, 0.4 mm nozzle", projection="THIRD ANGLE"):
        x, y, w, h = 250.0, 244.0, 160.0, 43.0
        self.rect(x, y, w, h, "frame")
        rows = [0, 9.5, 18.0, 27.0, 35.0, h]
        for r in rows[1:-1]:
            self.line(x, y + r, x + w, y + r, "border")
        self.line(x + 82, y + 9.5, x + 82, y + 35.0, "border")
        # Row 1
        self.text(x + 2.5, y + 3.2, "CRIMSON VEIL", size=2.3,
                  weight="bold", kind="note", halo=False)
        self.text(x + 2.5, y + 7.2, "PI-STACK CASE  ·  FOUR-PART SHELL", size=2.1,
                  kind="note", halo=False)
        self.text(x + 84.5, y + 3.2, "DRAWING No.", size=1.9,
                  kind="note", halo=False)
        self.text(x + 84.5, y + 7.4, f"CV-PSC-{self.number:02d}", size=3.0,
                  weight="bold", kind="note", halo=False)
        # Row 2: sheet title + scale
        self.text(x + 2.5, y + 12.8, "TITLE", size=1.9, kind="note", halo=False)
        self.text(x + 2.5, y + 16.7, self.title, size=2.7, weight="bold",
                  kind="note", halo=False)
        self.text(x + 84.5, y + 12.8, "SCALE", size=1.9, kind="note", halo=False)
        self.text(x + 84.5, y + 16.6, self.sheet_scale, size=2.5,
                  kind="note", halo=False)
        # Row 3: material / units / projection
        self.text(x + 2.5, y + 22.0, "MATERIAL / PROCESS", size=1.9,
                  kind="note", halo=False)
        self.text(x + 2.5, y + 25.7, material, size=2.1, kind="note", halo=False)
        self.text(x + 84.5, y + 22.0, "UNITS / PROJECTION", size=1.9,
                  kind="note", halo=False)
        self.text(x + 84.5, y + 25.7, f"mm  ·  {projection}", size=2.1,
                  kind="note", halo=False)
        # Row 4: source / date / drawn
        self.text(x + 2.5, y + 30.7, "SOURCE", size=1.9, kind="note", halo=False)
        self.text(x + 2.5, y + 34.1, "pi-stack-v0.7.scad  (constants parsed)",
                  size=1.95, kind="note", halo=False)
        self.text(x + 84.5, y + 30.7, "DATE / DRAWN", size=1.9,
                  kind="note", halo=False)
        self.text(x + 84.5, y + 34.1, "2026-10-25  ·  generated", size=1.95,
                  kind="note", halo=False)
        # Row 5: status
        self.text(x + 2.5, y + 38.7, self.subtitle, size=1.95,
                  kind="note", halo=False)
        self.text(x + 155.0, y + 38.7, "DO NOT SCALE", size=2.0,
                  anchor="end", weight="bold", kind="note", halo=False)

    def scale_bar(self, x, y, scale=1.0, span_mm=50.0):
        """A graphic scale bar; span_mm is model millimetres."""
        paper_span = span_mm * scale
        n = 5
        seg = paper_span / n
        for i in range(n):
            fill = "#101010" if i % 2 == 0 else "#ffffff"
            self.add(f'<rect x="{x + i*seg:.3f}" y="{y:.3f}" '
                     f'width="{seg:.3f}" height="2.2" fill="{fill}" '
                     f'stroke="#101010" stroke-width="0.2"/>')
            self.text(x + i * seg, y + 5.6, fmt(span_mm * i / n, 0),
                      size=1.8, anchor="middle", kind="note", halo=False)
        self.text(x + paper_span, y + 5.6, fmt(span_mm, 0), size=1.8,
                  anchor="middle", kind="note", halo=False)
        self.text(x + paper_span + 4, y + 2.0,
                  f"1:{fmt(1/scale, 2).rstrip('0').rstrip('.')}"
                  if scale < 1 else f"{fmt(scale, 1).rstrip('0').rstrip('.')}:1",
                  size=2.1, kind="note", halo=False)

    # ---- serialise -------------------------------------------------------
    def svg(self):
        defs = """
<defs>
  <pattern id="hatch" width="2.2" height="2.2" patternUnits="userSpaceOnUse"
           patternTransform="rotate(45)">
    <line x1="0" y1="0" x2="0" y2="2.2" stroke="#101010" stroke-width="0.22"/>
  </pattern>
  <pattern id="hatch2" width="1.4" height="1.4" patternUnits="userSpaceOnUse"
           patternTransform="rotate(-45)">
    <line x1="0" y1="0" x2="0" y2="1.4" stroke="#101010" stroke-width="0.18"/>
  </pattern>
</defs>"""
        body = "\n".join(self.items)
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="420mm" height="297mm" viewBox="0 0 420 297">\n'
                f'{defs}\n'
                f'<rect x="0" y="0" width="420" height="297" fill="#ffffff"/>\n'
                f'{body}\n</svg>\n')


class View:
    """Maps model (horizontal, vertical) to paper millimetres, Y up.

    `mirror` names the model coordinate that lands at the view's left-hand
    paper edge: pass the part's width to draw a rear view seen from +Y (or
    the part's depth for a left view seen from -X).  This is what makes the
    projection third-angle rather than a mirrored sketch.
    """

    def __init__(self, sheet, ox, oy, scale=1.0, mirror=None):
        self.s = sheet
        self.ox = ox
        self.oy = oy
        self.k = scale
        self.mirror = mirror

    def p(self, a, b):
        if self.mirror is not None:
            a = self.mirror - a
        return (self.ox + self.k * a, self.oy - self.k * b)

    def d(self, v):
        return self.k * v

    def line(self, a1, b1, a2, b2, kind="feature"):
        x1, y1 = self.p(a1, b1)
        x2, y2 = self.p(a2, b2)
        self.s.line(x1, y1, x2, y2, kind)

    def poly(self, pts, kind="outline", closed=False):
        self.s.polyline([self.p(a, b) for a, b in pts], kind, closed)

    def rect(self, a, b, w, h, kind="outline", fill="none", dash=None):
        x0, y0 = self.p(a, b + h)
        x1, y1 = self.p(a + w, b)
        self.s.rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0),
                    kind, fill=fill)

    def rrect(self, a, b, w, h, r, kind="outline", fill="none"):
        x0, y0 = self.p(a, b + h)
        x1, y1 = self.p(a + w, b)
        self.s.rrect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0),
                     self.d(r), kind, fill)

    def circle(self, a, b, dia, kind="feature", fill="none"):
        cx, cy = self.p(a, b)
        self.s.circle(cx, cy, self.d(dia) / 2.0, kind, fill)

    def cross(self, a, b, r=3.5, kind="centre"):
        cx, cy = self.p(a, b)
        self.s.centre_cross(cx, cy, self.d(r), kind)

    def trace(self, segs, kind="outline"):
        for (ax, ay), (bx, by) in segs:
            self.line(ax, ay, bx, by, kind)

    def leader_p(self, a, b, tx, ty, text, **kw):
        """Leader from a model point to a paper-coordinate text shoulder."""
        x, y = self.p(a, b)
        self.s.leader(x, y, tx, ty, text, **kw)

    def label_p(self, text, tx, ty, **kw):
        self.s.view_label(text, tx, ty, **kw)

    def hdim(self, a1, a2, b_line, label, b_from1, b_from2=None, **kw):
        x1, _ = self.p(a1, b_line)
        x2, _ = self.p(a2, b_line)
        _, yl = self.p(0, b_line)
        _, f1 = self.p(0, b_from1)
        _, f2 = self.p(0, b_from2 if b_from2 is not None else b_from1)
        self.s.dim_h(x1, x2, yl, label, f1, f2, **kw)

    def vdim(self, b1, b2, a_line, label, a_from1, a_from2=None, **kw):
        _, y1 = self.p(0, b1)
        _, y2 = self.p(0, b2)
        xl, _ = self.p(a_line, 0)
        f1, _ = self.p(a_from1, 0)
        f2, _ = self.p(a_from2 if a_from2 is not None else a_from1, 0)
        self.s.dim_v(y1, y2, xl, label, f1, f2, **kw)

    def small_v(self, b1, b2, a_line, label, a_from, **kw):
        _, y1 = self.p(0, b1)
        _, y2 = self.p(0, b2)
        xl, _ = self.p(a_line, 0)
        f, _ = self.p(a_from, 0)
        self.s.dim_small_v(y1, y2, xl, label, f, f, **kw)

    def ord_x(self, values, b_line, ref, b_from, labels=None, **kw):
        xs = [self.p(v, b_line)[0] for v in values]
        xr = self.p(ref, b_line)[0]
        _, yl = self.p(0, b_line)
        _, f = self.p(0, b_from)
        self.s.ordinate_h(xs, yl, xr, f, labels, **kw)

    def ord_y(self, values, a_line, ref, a_from, labels=None, **kw):
        ys = [self.p(a_line, v)[1] for v in values]
        yr = self.p(a_line, ref)[1]
        xl, _ = self.p(a_line, 0)
        f, _ = self.p(a_from, 0)
        self.s.ordinate_v(ys, xl, yr, f, labels, **kw)

    def leader(self, a, b, ta, tb, text, **kw):
        x, y = self.p(a, b)
        tx, ty = self.p(ta, tb)
        self.s.leader(x, y, tx, ty, text, **kw)

    def label(self, text, a, b, **kw):
        x, y = self.p(a, b)
        self.s.view_label(text, x, y, **kw)

    def bounds(self, a0, b0, a1, b1, name):
        x0, y0 = self.p(a0, b1)
        x1, y1 = self.p(a1, b0)
        self.s.view(name, x0, y0, x1, y1)
        return (x0, y0, x1, y1)

    def fill_poly(self, pts, fill="#ffffff"):
        p = " ".join(f"{a:.3f},{b:.3f}" for a, b in
                     (self.p(x, y) for x, y in pts))
        self.s.add(f'<polygon points="{p}" fill="{fill}" stroke="none"/>')

    def slot(self, a0, a1, b0, b1, fill=True):
        """A rectangular opening, drawn as a closed rectangle in elevation."""
        if fill:
            self.fill_poly([(a0, b0), (a0, b1), (a1, b1), (a1, b0)])
        self.poly([(a0, b0), (a0, b1), (a1, b1), (a1, b0)], "outline",
                  closed=True)

    def notch(self, a0, a1, b_bottom, b_top, fill=True):
        """An opening that breaks out of the part's bottom edge."""
        if fill:
            self.fill_poly([(a0, b_bottom), (a0, b_top), (a1, b_top),
                            (a1, b_bottom)])
        self.poly([(a0, b_bottom), (a0, b_top), (a1, b_top), (a1, b_bottom)],
                  "outline", closed=False)

    def hexagon(self, a, b, r, kind="outline"):
        pts = [(a + r * _cos(60 * k), b + r * _sin(60 * k)) for k in range(6)]
        self.poly(pts, kind, closed=True)


def _callout_notes(sheet, x, y, title, lines, size=2.15, spacing=3.25):
    return sheet.note(x, y, lines, size=size, spacing=spacing, title=title)


def _table(sheet, x, y, widths, header, rows, size=1.85, row_h=5.0):
    """A plain ruled feature table; returns the y below the last row."""
    total = sum(widths)
    ys = y
    sheet.text(x, ys, "  ".join(header), size=size, weight="bold",
               kind="note", halo=False)
    sheet.line(x, ys + 1.2, x + total, ys + 1.2, "border")
    ys += row_h
    for row in rows:
        cx = x
        for w, cell in zip(widths, row):
            sheet.text(cx, ys, cell, size=size, kind="note", halo=False)
            cx += w
        sheet.line(x, ys + 1.2, x + total, ys + 1.2, "border")
        ys += row_h
    return ys


def _section_poly(v, pts):
    """Hatch a section cut polygon given in model coordinates."""
    paper = [v.p(a, b) for a, b in pts]
    v.s.hatch(paper)
    v.poly(pts, "outline", closed=True)


# =====================================================================
#  Sheet 5  -  PLATE (strap)
# =====================================================================

def sheet_plate():
    s = Sheet(5, "PLATE  —  STRAP STYLE",
              "Tray, four arms with cut waist, bolt pattern, print section",
              "1:1  ·  SECTION 1:1")
    s.frame()
    v = View(s, 65.0, 195.0, 1.0)
    v.bounds(ARM_X0, ARM_Y0, ARM_X1, ARM_Y1, "plate plan")

    # Outer-face view: one flat floor, silhouette traced through the waists.
    v.trace(plate_outline_segments(0.16), "outline")
    v.rrect(D.PLATE_TRAY_X0, D.PLATE_TRAY_Y0,
            D.PLATE_TRAY_X1 - D.PLATE_TRAY_X0,
            D.PLATE_TRAY_Y1 - D.PLATE_TRAY_Y0, D.PLATE_TRAY_R, "hidden")
    v.rrect(-D.PLATE_SKIRT_CLR, -D.PLATE_SKIRT_CLR,
            D.OW + 2 * D.PLATE_SKIRT_CLR, D.OD + 2 * D.PLATE_SKIRT_CLR,
            D.PLATE_SKIRT_R, "hidden")

    # Four bolts, counterbored in this outer face.
    for (x, y) in PLATE_BOLTS:
        v.circle(x, y, D.PLATE_CBORE_D, "outline")
        v.circle(x, y, D.PLATE_CLR, "feature")
        v.cross(x, y, 2.4)
    # Skirt vent notches, hidden above the floor.
    for x in VENT_X:
        v.rect(x - D.VENT_W / 2, D.PLATE_TRAY_Y0, D.VENT_W,
               -D.PLATE_TRAY_Y0, "hidden")

    # Arm axes and stations.  The waist cuts are shown on the upper-right arm.
    for a in ARM_ANGLES:
        ca, sa = _cos(a), _sin(a)
        p0 = (D.PLATE_CX + (D.PLATE_ARM_ROOT_R - 6) * ca,
              D.PLATE_CY + (D.PLATE_ARM_ROOT_R - 6) * sa)
        p1 = (D.PLATE_CX + (D.PLATE_ARM_TIP_R + 6) * ca,
              D.PLATE_CY + (D.PLATE_ARM_TIP_R + 6) * sa)
        v.line(p0[0], p0[1], p1[0], p1[1], "centre")
        for r in (D.PLATE_ARM_ROOT_R, D.PLATE_ARM_NECK_R,
                  D.PLATE_ARM_TIP_R):
            v.cross(D.PLATE_CX + r * ca, D.PLATE_CY + r * sa, 2.6)
    ca, sa = ARM_C, ARM_S
    ux, uy = ca, sa
    px, py = -sa, ca
    wrx = D.PLATE_CX + D.PLATE_ARM_NECK_R * ca
    wry = D.PLATE_CY + D.PLATE_ARM_NECK_R * sa
    for off in (-WAIST_OFF, WAIST_OFF):
        v.circle(wrx + off * px, wry + off * py, WAIST_R, "centre")
    v.cross(D.PLATE_CX, D.PLATE_CY, 7.0)

    # Section A-A cut line.
    ax0, ay0 = v.p(ARM_X0 - 4.0, D.PLATE_CY)
    ax1, ay1 = v.p(ARM_X1 + 4.0, D.PLATE_CY)
    s.line(ax0, ay0, ax1, ay1, "centre")
    s.arrow(ax0, ay0, -1, 0, size=2.2, half=0.8)
    s.arrow(ax1, ay1, 1, 0, size=2.2, half=0.8)
    s.text(ax0 - 1.0, ay0 - 1.5, "A", size=2.6, anchor="end",
           weight="bold", kind="note")
    s.text(ax1 + 1.0, ay1 - 1.5, "A", size=2.6, kind="note",
           weight="bold")

    # ---- plan dimensions ------------------------------------------------
    bx = sorted({clean(x) for x, _ in PLATE_BOLTS})
    by = sorted({clean(y) for _, y in PLATE_BOLTS})
    v.hdim(ARM_X0, ARM_X1, ARM_Y1 + 8.0, fmt(ARM_EXPORT_X), ARM_Y1)
    v.vdim(ARM_Y0, ARM_Y1, ARM_X1 + 22.0, fmt(ARM_EXPORT_Y), ARM_X1)
    v.hdim(D.PLATE_TRAY_X0, D.PLATE_TRAY_X1, ARM_Y0 - 6.0,
           fmt(D.PLATE_TRAY_X1 - D.PLATE_TRAY_X0), D.PLATE_TRAY_Y0)
    v.vdim(D.PLATE_TRAY_Y0, D.PLATE_TRAY_Y1, ARM_X0 - 10.0,
           fmt(D.PLATE_TRAY_Y1 - D.PLATE_TRAY_Y0), D.PLATE_TRAY_X0)
    v.hdim(bx[0], bx[1], D.PLATE_CY + 6.0, fmt(bx[1] - bx[0]), by[0])
    v.vdim(by[0], by[1], D.PLATE_CX - 6.0, fmt(by[1] - by[0]), bx[0])
    v.label("OUTER-FACE PLAN  —  PRINT SIDE DOWN", 0.0,
            ARM_Y1 + 22.0, size=2.9)

    # ---- print section --------------------------------------------------
    # plate_placed() is a pure Z lift: outer face on the bed, tray open up.
    pv = View(s, 65.0, 236.0, 1.0)
    pv.bounds(D.PLATE_TRAY_X0, 0.0, D.PLATE_TRAY_X1, PLATE_PRINT_H,
              "plate section")
    zf = D.PLATE_T  # floor top, 4.00
    _section_poly(pv, [(D.PLATE_TRAY_X0, 0.0),
                       (D.PLATE_TRAY_X1, 0.0),
                       (D.PLATE_TRAY_X1, zf),
                       (D.PLATE_TRAY_X0, zf)])
    wall_lo = D.PLATE_TRAY_X0
    wall_hi = wall_lo + D.PLATE_SKIRT_T
    zs0 = zf - D.PLATE_SKIRT_OVERLAP   # 3.50, skirt bottom in print
    _section_poly(pv, [(wall_lo, zs0), (wall_hi, zs0),
                       (wall_hi, PLATE_PRINT_H), (wall_lo, PLATE_PRINT_H)])
    wall_hi2 = D.PLATE_TRAY_X1
    wall_lo2 = wall_hi2 - D.PLATE_SKIRT_T
    _section_poly(pv, [(wall_lo2, zs0), (wall_hi2, zs0),
                       (wall_hi2, PLATE_PRINT_H), (wall_lo2, PLATE_PRINT_H)])
    # Build plate.
    pv.line(D.PLATE_TRAY_X0 - 4, 0, D.PLATE_TRAY_X1 + 4, 0, "outline")
    for i in range(9):
        x = D.PLATE_TRAY_X0 - 3.0 + i * 13.0
        pv.line(x, 0, x - 1.5, -1.2, "feature")
    s.text(*(pv.p(D.PLATE_TRAY_X1 + 1.0, 0.7)), "BUILD PLATE",
           size=1.9, kind="note")

    pv.vdim(0.0, PLATE_PRINT_H, D.PLATE_TRAY_X0 - 9.0,
            fmt(PLATE_PRINT_H), D.PLATE_TRAY_X0)
    pv.vdim(0.0, zf, D.PLATE_TRAY_X0 - 15.0, fmt(D.PLATE_T), D.PLATE_TRAY_X0)
    pv.vdim(zf, PLATE_PRINT_H, D.PLATE_TRAY_X1 + 8.0,
            fmt(PLATE_PRINT_H - zf), D.PLATE_TRAY_X1)
    pv.hdim(D.PLATE_TRAY_X0, D.PLATE_TRAY_X1, -3.0,
            fmt(D.PLATE_TRAY_X1 - D.PLATE_TRAY_X0), 0.0)
    s.view_label("SECTION A-A  —  PRINT ORIENTATION", 45.0, 226.0,
                 size=2.7)

    # ---- notes ----------------------------------------------------------
    arm_lines = [
        f"4 arms, each a hull of circles on the corner diagonal",
        f"at {fmt(D.PLATE_ARM_ANG)}° (atan(66.20/95.12)):",
        f"  root Ø{fmt(D.PLATE_ARM_ROOT_D)} at r {fmt(D.PLATE_ARM_ROOT_R)}",
        f"  tip  Ø{fmt(D.PLATE_ARM_TIP_D)} at r {fmt(D.PLATE_ARM_TIP_R)}",
        f"  waist CUT by 2 × Ø{fmt(2 * WAIST_R)} at r "
        f"{fmt(D.PLATE_ARM_NECK_R)},",
        f"  offset ±{fmt(WAIST_OFF)} from the axis, leaving",
        f"  a {fmt(WAIST_W)} strap seat (about 6 long).",
        f"Exported envelope {fmt(ARM_EXPORT_X)} × {fmt(ARM_EXPORT_Y)};",
        f"analytic tip-circle extremes {fmt(ARM_SPAN_X)} × "
        f"{fmt(ARM_SPAN_Y)} ($fn=48).",
    ]
    s.note(215.0, 30.0, arm_lines, size=2.05, spacing=3.35,
           title="ARM GEOMETRY")

    _callout_notes(
        s, 215.0, 74.0, "NOTES — PLATE",
        [
            f"1.  Tray {fmt(D.PLATE_TRAY_X1 - D.PLATE_TRAY_X0)} × "
            f"{fmt(D.PLATE_TRAY_Y1 - D.PLATE_TRAY_Y0)} R"
            f"{fmt(D.PLATE_TRAY_R)}; skirt {fmt(D.PLATE_SKIRT_T)} thick",
            f"    with {fmt(D.PLATE_SKIRT_CLR)} clearance to the case.",
            f"2.  Skirt top is {fmt(D.PLATE_SKIRT_TOP)} above the case",
            f"    underside and {fmt(SKIRT_Z1 - PLATE_Z1)} above the floor",
            "    in print orientation.",
            f"3.  4× Ø{fmt(D.PLATE_CBORE_D)} × {fmt(D.PLATE_CBORE_H)} "
            f"cbore from the OUTER face, Ø{fmt(D.PLATE_CLR)} through.",
            f"    M3 × {fmt(D.PLATE_SCREW_L, 0)} into blind Ø"
            f"{fmt(D.PLATE_PILOT_D)} × {fmt(D.PLATE_PILOT_DEEP)} pilots.",
            f"4.  Bolt pattern {fmt(2 * D.PLATE_BOLT_DX)} × "
            f"{fmt(2 * D.PLATE_BOLT_DY)} about the plate centre "
            f"({fmt(D.PLATE_CX)}, {fmt(D.PLATE_CY)}).",
            f"5.  5 skirt notches {fmt(D.VENT_W)} wide on "
            f"{fmt(D.VENT_P)} pitch expose the BASE vents.",
            "6.  Print flat on the outer face; no supports.",
        ])
    s.scale_bar(215.0, 158.0, 1.0, 50.0)
    s.title_block(material="PLA, 0.4 mm nozzle")
    return s


# =====================================================================
#  Sheet 6  -  BASE
# =====================================================================

def sheet_base():
    s = Sheet(6, "BASE",
              "Floor, rim, Pi bosses, plate bosses, six case-screw bores, vents",
              "1:1  ·  SECTION 2:1")
    s.frame()
    v = View(s, 65.0, 196.0, 1.0)
    v.bounds(0, 0, D.OW, D.OD, "base plan")

    v.rrect(0, 0, D.OW, D.OD, 3.0, "outline")
    v.rrect(D.WALL, D.WALL, D.IW, D.ID, 2.0, "outline")
    # Pi bosses (to z 7.60) and plate bosses (to the rim, 5.50).
    for (x, y) in PI_HOLES:
        v.circle(x, y, D.BOSS_D, "outline")
        v.circle(x, y, D.PI_SCREW_CLR, "feature")
        v.circle(x, y, D.PI_CBORE_D, "hidden")
        v.cross(x, y, 2.4)
    for (x, y) in PLATE_BOLTS:
        v.circle(x, y, D.PLATE_BOSS_D, "outline")
        v.circle(x, y, D.PLATE_PILOT_D, "feature")
        v.cross(x, y, 2.4)
    # Six rim bores: through from the top, cbore/csk on the underside.
    for (x, y) in SCREWS:
        v.circle(x, y, D.SCREW_CLR, "feature")
        v.circle(x, y, D.SCREW_CBORE_D, "hidden")
        v.circle(x, y, D.SCREW_CSK_D, "hidden")
        v.cross(x, y, 2.2)
    # Five vents in the -Y wall (hidden under the rim).
    for x in VENT_X:
        v.rect(x - D.VENT_W / 2, 0, D.VENT_W, D.WALL, "hidden")
    v.cross(D.OW / 2, D.OD / 2, 7.0)

    # Section B-B cut line, through the middle of the tray.
    bx0, by0 = v.p(-4.0, D.OD / 2)
    bx1, by1 = v.p(D.OW + 4.0, D.OD / 2)
    s.line(bx0, by0, bx1, by1, "centre")
    s.arrow(bx0, by0, -1, 0, size=2.2, half=0.8)
    s.arrow(bx1, by1, 1, 0, size=2.2, half=0.8)
    s.text(bx0 - 1.0, by0 - 1.5, "B", size=2.6, anchor="end",
           weight="bold", kind="note")
    s.text(bx1 + 1.0, by1 - 1.5, "B", size=2.6, kind="note",
           weight="bold")

    # ---- plan dimensions ------------------------------------------------
    v.hdim(0.0, D.OW, D.OD + 8.0, fmt(D.OW), D.OD)
    v.vdim(0.0, D.OD, -16.0, fmt(D.OD), 0.0)
    v.hdim(0.0, D.WALL, D.OD + 3.0, fmt(D.WALL), D.OD)
    v.hdim(D.WALL, D.WALL + D.IW, D.OD + 3.0, fmt(D.IW), D.OD)
    v.hdim(D.WALL + D.IW, D.OW, D.OD + 3.0, fmt(D.WALL), D.OD)
    v.vdim(0.0, D.WALL, -8.0, fmt(D.WALL), 0.0)
    v.vdim(D.WALL, D.WALL + D.ID, -8.0, fmt(D.ID), 0.0)
    v.vdim(D.WALL + D.ID, D.OD, -8.0, fmt(D.WALL), 0.0)
    v.label("PLAN  —  FROM +Z (INSIDE OF TRAY)", 0.0, D.OD + 16.0,
            size=2.9)

    # ---- front elevation ------------------------------------------------
    fv = View(s, 180.0, 205.0, 1.0)
    fv.bounds(0, 0, D.OW, D.PCB_Z, "base front")
    fv.rect(0, 0, D.OW, D.JOINT_A, "outline")
    for x in VENT_X:
        fv.slot(x - D.VENT_W / 2, x + D.VENT_W / 2,
                D.VENT_Z - D.VENT_H / 2, D.VENT_Z + D.VENT_H / 2)
    # The Pi bosses stand 2.10 above the rim and are visible over it.
    for x in sorted({clean(px) for px, _ in PI_HOLES}):
        fv.rect(x - D.BOSS_D / 2, D.JOINT_A, D.BOSS_D,
                D.PCB_Z - D.JOINT_A, "outline")
    fv.label("FRONT ELEVATION  —  -Y (FROM -Y)", 0.0, D.PCB_Z + 5.0,
             size=2.7)
    fv.vdim(0.0, D.JOINT_A, -10.0, fmt(D.JOINT_A), 0.0)
    fv.vdim(0.0, D.PCB_Z, -16.0, fmt(D.PCB_Z), 0.0)
    fv.hdim(0.0, D.OW, -3.0, fmt(D.OW), 0.0)
    s.text(180.0 + D.OW + 2.0, 205.0 - D.JOINT_A + 1.0,
           "Pi bosses to z 7.60", size=2.0, kind="note")

    # ---- section B-B, 2:1 ----------------------------------------------
    pv = View(s, 180.0, 230.0, 2.0)
    pv.bounds(0, 0, D.OW, D.JOINT_A, "base section")
    _section_poly(pv, [(0, 0), (D.OW, 0), (D.OW, D.FLOOR), (0, D.FLOOR)])
    _section_poly(pv, [(0, D.FLOOR), (D.WALL, D.FLOOR),
                       (D.WALL, D.JOINT_A), (0, D.JOINT_A)])
    _section_poly(pv, [(D.OW - D.WALL, D.FLOOR), (D.OW, D.FLOOR),
                       (D.OW, D.JOINT_A), (D.OW - D.WALL, D.JOINT_A)])
    pv.vdim(0.0, D.FLOOR, D.OW + 8.0, fmt(D.FLOOR), D.OW)
    pv.vdim(0.0, D.JOINT_A, D.OW + 14.0, fmt(D.JOINT_A), D.OW)
    pv.hdim(0.0, D.OW, -2.0, fmt(D.OW), 0.0)
    s.view_label("SECTION B-B  —  FLOOR AND WALL", 180.0, 215.0, size=2.7)

    # ---- schedule and notes --------------------------------------------
    pcols = " / ".join(fmt(x) for x in sorted({clean(x) for x, _ in PI_HOLES}))
    prows = " / ".join(fmt(y) for y in sorted({clean(y) for _, y in PI_HOLES}))
    bcols = " / ".join(fmt(x) for x in sorted({clean(x) for x, _ in PLATE_BOLTS}))
    brows = " / ".join(fmt(y) for y in sorted({clean(y) for _, y in PLATE_BOLTS}))
    scols = " / ".join(fmt(x) for x in sorted({clean(x) for x, _ in SCREWS}))
    srows = " / ".join(fmt(y) for y in sorted({clean(y) for _, y in SCREWS}))
    rows = [
        ("PI BOSS",
         f"4× Ø{fmt(D.BOSS_D)} boss, Ø{fmt(D.PI_SCREW_CLR)} THRU, "
         f"Ø{fmt(D.PI_CBORE_D)} × {fmt(D.PI_CBORE_H)} cbore",
         f"X {pcols} × Y {prows}"),
        ("PLATE BOSS",
         f"4× Ø{fmt(D.PLATE_BOSS_D)} boss to z {fmt(D.JOINT_A)}, "
         f"Ø{fmt(D.PLATE_PILOT_D)} × {fmt(D.PLATE_PILOT_DEEP)} blind",
         f"X {bcols} × Y {brows}"),
        ("CASE SCREW",
         f"6× Ø{fmt(D.SCREW_CLR)} THRU, Ø{fmt(D.SCREW_CBORE_D)} × "
         f"{fmt(D.SCREW_CBORE_H)} cbore,",
         f"X {scols}"),
        ("", f"Ø{fmt(D.SCREW_CSK_D)} × {fmt(D.SCREW_CSK_H)} csk from below",
         f"Y {srows}"),
        ("VENT",
         f"5× {fmt(D.VENT_W)} × {fmt(D.VENT_H)} THRU, -Y wall",
         f"X {fmt(VENT_X[0])}..{fmt(VENT_X[-1])} P{fmt(D.VENT_P)}, "
         f"Z {fmt(D.VENT_Z)}"),
    ]
    _table(s, 218.0, 30.0, [24.0, 88.0, 74.0],
           ["FEATURE", "SIZE / DEPTH", "POSITION (DATUM = CASE 0,0)"],
           rows, size=1.8, row_h=7.2)

    _callout_notes(
        s, 218.0, 76.0, "NOTES — BASE",
        [
            "1.  The plan is from +Z, into the tray. Dashed circles are",
            "    on the underside (counterbores and countersinks).",
            f"2.  Rim and wall are z 0.00 .. {fmt(D.JOINT_A)}; the floor",
            f"    is {fmt(D.FLOOR)} thick and the wall {fmt(D.WALL)}.",
            f"3.  The four Pi bosses run to z {fmt(D.PCB_Z)}, 2.10 above",
            "    the rim, inside the MID's open bottom. The part's true",
            f"    envelope is therefore z 0.00 .. {fmt(D.PCB_Z)}.",
            f"4.  The plate bosses stop at z {fmt(D.JOINT_A)}. The +X/-Y",
            f"    one ({fmt(PLATE_BOLTS[1][0])}, {fmt(PLATE_BOLTS[1][1])}) "
            "sits under the",
            "    Ethernet shell; all four cap the plate's M3 × 6 screws.",
            "5.  No port cuts: the rim is below every connector.",
            f"6.  Vents at z {fmt(D.VENT_Z)} pass through the -Y wall.",
            f"7.  Case screws: M3 × {fmt(D.SCREW_L, 0)} up from below into",
            "    the MID; cbores break out 0.65 through the side faces.",
        ])
    s.scale_bar(218.0, 156.0, 1.0, 50.0)
    s.title_block(material="PLA, 0.4 mm nozzle")
    return s


# =====================================================================
#  Sheet 1  -  assembly, top view (bezel side)
# =====================================================================

def sheet_assembly_top():
    s = Sheet(1, "ASSEMBLY  —  TOP VIEW (BEZEL SIDE)",
              "Overall envelope, LCD window, six flush screw columns",
              "1:1")
    s.frame()
    v = View(s, 75.0, 225.0, 1.0)
    v.bounds(0, 0, D.OW, D.OD, "top")

    # Case envelope and the visible bezel face.
    v.rrect(0, 0, D.OW, D.OD, 3.0, "outline")
    v.rect(D.WIN_X, D.WIN_Y, D.WIN_W, D.WIN_D, "outline")
    lcd_cx = D.PCB_X + D.PI_PCB_W / 2.0
    lcd_cy = D.PCB_Y + D.PI_PCB_D / 2.0
    v.rect(lcd_cx - D.LCD_ACT_W / 2.0, lcd_cy - D.LCD_ACT_D / 2.0,
           D.LCD_ACT_W, D.LCD_ACT_D, "hidden")
    v.cross(D.OW / 2, D.OD / 2, 6.0)

    # Six counterbores, seen from the top: csk 6.20, cbore 5.80, through 3.40.
    for (x, y) in SCREWS:
        v.circle(x, y, D.SCREW_CSK_D, "feature")
        v.circle(x, y, D.SCREW_CBORE_D, "feature")
        v.circle(x, y, D.SCREW_CLR, "feature")
        v.cross(x, y, 2.2)

    # ---- dimensions -----------------------------------------------------
    # Window chain across the top: 6.66 / 81.80 / 6.66.
    bl = D.OD + 12.0
    wtop = D.WIN_Y + D.WIN_D
    v.hdim(0.0, D.WIN_X, bl, fmt(D.WIN_X), D.OD, wtop)
    v.hdim(D.WIN_X, D.WIN_X + D.WIN_W, bl, fmt(D.WIN_W), wtop, wtop)
    v.hdim(D.WIN_X + D.WIN_W, D.OW, bl, fmt(D.OW - D.WIN_X - D.WIN_W),
           wtop, D.OD)
    # Window height and overall height, on the left.
    v.vdim(D.WIN_Y, D.WIN_Y + D.WIN_D, -8.0, fmt(D.WIN_D), 0.0)
    v.vdim(0.0, D.OD, -14.0, fmt(D.OD), 0.0)
    # Overall width, below.
    v.hdim(0.0, D.OW, -14.0, fmt(D.OW), 0.0)
    # Screw pattern: ordinates from the left and bottom datums.
    xs = sorted({clean(x) for x, _ in SCREWS})
    ys = sorted({clean(y) for _, y in SCREWS})
    v.ord_x(xs, -7.0, 0.0, 0.0, labels=[fmt(x) for x in xs])
    v.ord_y(ys, D.OW + 6.0, 0.0, D.OW, labels=[fmt(y) for y in ys])

    # ---- callouts and notes --------------------------------------------
    v.leader_p(SCREWS[3][0], SCREWS[3][1], 214.0, 34.0,
               f"6× Ø{fmt(D.SCREW_CSK_D)} × {fmt(D.SCREW_CSK_H)} CSK / "
               f"Ø{fmt(D.SCREW_CBORE_D)} × {fmt(D.SCREW_CBORE_H)} CBORE / "
               f"Ø{fmt(D.SCREW_CLR)} THRU",
               size=2.0)
    v.leader_p(D.WIN_X + D.WIN_W, D.WIN_Y + D.WIN_D, 214.0, 46.0,
               f"LCD WINDOW {fmt(D.WIN_W)} × {fmt(D.WIN_D)}, CENTRED: "
               f"{fmt(D.WIN_X)} / {fmt(D.WIN_Y)} FROM EDGES",
               size=2.0)

    v.label("TOP VIEW  —  BEZEL SIDE (FROM +Z)", 0.0, D.OD + 17.0,
            size=2.9)

    _callout_notes(
        s, 214.0, 78.0, "NOTES — TOP VIEW",
        [
            "1.  All dimensions in millimetres. Third-angle projection.",
            f"2.  Outer envelope {fmt(D.OW)} × {fmt(D.OD)} × {fmt(D.OH)};",
            f"    this is the BEZEL's top face at z {fmt(D.OH)}.",
            f"3.  6 × M3 × {fmt(D.SCREW_L, 0)} button head on the wall",
            f"    centrelines ({fmt(D.WALL / 2)} from either face), driven",
            "    down into the MID. Heads flush; each counterbore is",
            "    0.65 wider than the wall and breaks out through the side.",
            f"4.  LCD visible area {fmt(D.LCD_ACT_W)} × "
            f"{fmt(D.LCD_ACT_D)}, shown dashed.",
            f"5.  Butt joints at z {fmt(D.SPLIT_B)} / {fmt(BEZEL_LO)} "
            "are shown on sheet 3.",
            "6.  For the underside see sheet 4; for the BEZEL alone, 8.",
        ])

    # Envelope annotation.
    s.text(214.0, 128.0, "ENVELOPE", size=2.4, weight="bold", kind="note",
           halo=False)
    s.text(214.0, 132.0,
           f"{fmt(D.OW)} × {fmt(D.OD)} × {fmt(D.OH)}", size=2.6,
           kind="note", halo=False)
    s.text(214.0, 137.0, f"CASE  z 0.00 .. {fmt(D.OH)}", size=2.2,
           kind="note", halo=False)
    s.text(214.0, 141.0,
           f"WITH PLATE  z {fmt(PLATE_Z0)} .. {fmt(D.OH)} = "
           f"{fmt(D.OH - PLATE_Z0)}", size=2.2, kind="note", halo=False)
    s.scale_bar(214.0, 154.0, 1.0, 50.0)
    s.title_block()
    return s


# =====================================================================
#  Sheet 2  -  assembly, front view (-Y panel)
# =====================================================================

def sheet_assembly_front():
    s = Sheet(2, "ASSEMBLY  —  FRONT VIEW (-Y PANEL)",
              "Ports, panel row, accessory opening, BASE vents, plate below",
              "1:1")
    s.frame()
    v = View(s, 70.0, 220.0, 1.0)
    v.bounds(ARM_X0, PLATE_Z0, ARM_X1, D.OH, "front")

    # Plate slab: the four arm tips make the widest silhouette.
    v.rect(ARM_X0, PLATE_Z0, ARM_SPAN_X, D.PLATE_T, "outline")
    # Case body.
    v.rect(0, 0, D.OW, D.OH, "outline")
    # BEZEL / MID / BASE seam lines.
    for z, kind in ((D.JOINT_A, "seam"), (MID_LO, "seam"),
                    (D.SPLIT_B, "seam"), (BEZEL_LO, "seam")):
        v.line(0, z, D.OW, z, kind)

    # Front-wall openings.  All three ports are slots open to the MID's
    # underside; the BASE's rim closes them from below on the assembly.
    for name in ("PWR", "HDMI", "AUDIO"):
        p = PORTS[name][0]
        v.notch(p["x0"], p["x1"], MID_LO, p["z1"])
    # Accessory opening (closed, R1.50).
    v.rrect(ACC_X0, ACC_Z0, D.ACC_W, D.ACC_H, D.ACC_R, "outline")
    # LEDs and switches.
    for x in LED_X:
        v.circle(x, D.PANEL_Z, D.LED_D, "outline")
    for x in SW_X:
        v.rect(x - D.SW_POCKET / 2, SW_Z0, D.SW_POCKET, D.SW_POCKET,
               "hidden")
        v.circle(x, D.PANEL_Z, D.SW_BTN_D, "outline")

    # Plate skirt over the case's lower 3.00, white so it occludes.
    v.rect(D.PLATE_TRAY_X0, SKIRT_Z0, D.PLATE_TRAY_X1 - D.PLATE_TRAY_X0,
           SKIRT_Z1 - SKIRT_Z0, "outline", fill="#ffffff")
    # The five vents, and the skirt notches that expose them.
    for x in VENT_X:
        v.slot(x - D.VENT_W / 2, x + D.VENT_W / 2,
               D.VENT_Z - D.VENT_H / 2, D.VENT_Z + D.VENT_H / 2)

    # ---- dimensions -----------------------------------------------------
    # Overall heights, left of the plate silhouette.
    v.vdim(PLATE_Z0, D.OH, -34.0, fmt(D.OH - PLATE_Z0), ARM_X0, 0.0)
    v.vdim(0.0, D.OH, -28.0, fmt(D.OH), 0.0)
    # Part heights, right of the plate silhouette.
    v.small_v(0.0, D.JOINT_A, D.OW + 11.0, fmt(D.JOINT_A), D.OW)
    v.vdim(MID_LO, D.SPLIT_B, D.OW + 17.0, fmt(D.MID_H), D.OW)
    v.vdim(BEZEL_LO, D.OH, D.OW + 11.0, fmt(D.OH - BEZEL_LO), D.OW)
    # Widths: case above, plate envelope below.
    v.hdim(0.0, D.OW, D.OH + 10.0, fmt(D.OW), D.OH)
    v.hdim(ARM_X0, ARM_X1, -14.0, fmt(ARM_EXPORT_X), PLATE_Z0)

    v.label("FRONT VIEW  —  -Y PANEL (FROM -Y)", 0.0, D.OH + 17.0,
            size=2.9)

    # ---- feature table --------------------------------------------------
    port_rows = []
    for name in ("PWR", "HDMI", "AUDIO"):
        p = PORTS[name][0]
        port_rows.append((
            name,
            f"{fmt(p['x1'] - p['x0'])} × {fmt(p['z1'] - p['z0'])} SLOT",
            f"{fmt(p['x0'])}..{fmt(p['x1'])}",
            f"{fmt(p['z0'])}..{fmt(p['z1'])}",
        ))
    rows = port_rows + [
        ("ACCESSORY",
         f"{fmt(D.ACC_W)} × {fmt(D.ACC_H)} R{fmt(D.ACC_R)}",
         f"{fmt(ACC_X0)}..{fmt(ACC_X1)}",
         f"{fmt(ACC_Z0)}..{fmt(ACC_Z1)}"),
        ("LED",
         f"3× Ø{fmt(D.LED_D)} THRU",
         " / ".join(fmt(x) for x in LED_X),
         fmt(D.PANEL_Z)),
        ("SWITCH",
         f"3× Ø{fmt(D.SW_BTN_D)} + {fmt(D.SW_POCKET)} SQ × "
         f"{fmt(D.SW_POCKET_D)}",
         " / ".join(fmt(x) for x in SW_X),
         fmt(D.PANEL_Z)),
        ("VENT",
         f"5× {fmt(D.VENT_W)} × {fmt(D.VENT_H)} THRU",
         f"{fmt(VENT_X[0])}..{fmt(VENT_X[-1])} P{fmt(D.VENT_P)}",
         f"{fmt(D.VENT_Z - D.VENT_H / 2)}.."
         f"{fmt(D.VENT_Z + D.VENT_H / 2)}"),
        ("PLATE",
         f"{fmt(D.PLATE_T)} SLAB + {fmt(D.PLATE_SKIRT_T)} SKIRT",
         f"{fmt(ARM_X0)}..{fmt(ARM_X1)}",
         f"{fmt(PLATE_Z0)}..{fmt(SKIRT_Z1)}"),
    ]
    _table(s, 246.0, 34.0, [30.0, 55.0, 42.0, 31.0],
           ["FEATURE", "SIZE / DEPTH", "X (MM)", "Z (MM)"], rows,
           size=1.8, row_h=5.2)

    _callout_notes(
        s, 246.0, 96.0, "NOTES — FRONT VIEW",
        [
            "1.  Port openings are slots cut down through the MID's",
            f"    bottom edge (z {fmt(MID_LO)}), so the MID drops over",
            "    plugged connectors. The BASE rim closes them below.",
            f"2.  The BASE has NO port cuts: its rim stops at z "
            f"{fmt(D.JOINT_A)}.",
            f"3.  Panel row is at z {fmt(D.PANEL_Z)}; LED and switch",
            "    centre lines share that height.",
            f"4.  Both butt joints carry a {fmt(D.MATE_GAP)} axial gap;",
            f"    screw preload closes it. Joints {fmt(D.JOINT_A)}/"
            f"{fmt(MID_LO)} and {fmt(D.SPLIT_B)}/{fmt(BEZEL_LO)}.",
            f"5.  The plate hangs {fmt(D.PLATE_GAP)} below the case and",
            f"    its skirt wraps the lower {fmt(D.PLATE_SKIRT_TOP)}.",
            "6.  Detail positions are dimensioned on sheet 7 (MID);",
            "    the plate is sheet 5 and the BASE is sheet 6.",
        ])
    s.scale_bar(246.0, 180.0, 1.0, 50.0)
    s.title_block()
    return s


# =====================================================================
#  Sheet 3  -  assembly, side elevation (stack)
# =====================================================================

def sheet_assembly_side():
    s = Sheet(3, "ASSEMBLY  —  SIDE ELEVATION",
              "BASE / MID / BEZEL z stack and the plate, skirt and arms below z 0",
              "1:1")
    s.frame()
    v = View(s, 70.0, 220.0, 1.0)
    v.bounds(ARM_Y0, PLATE_Z0, ARM_Y1, D.OH, "side")

    # Plate slab and the two skirt walls (the skirt is not a full slab).
    v.rect(ARM_Y0, PLATE_Z0, ARM_SPAN_Y, D.PLATE_T, "outline")
    v.rect(D.PLATE_TRAY_Y0, SKIRT_Z0,
           -D.PLATE_TRAY_Y0, SKIRT_Z1 - SKIRT_Z0,
           "outline", fill="#ffffff")
    v.rect(D.OD, SKIRT_Z0, D.PLATE_TRAY_Y1 - D.OD,
           SKIRT_Z1 - SKIRT_Z0, "outline", fill="#ffffff")
    # Case body.
    v.rect(0, 0, D.OD, D.OH, "outline")
    for z in (D.JOINT_A, MID_LO, D.SPLIT_B, BEZEL_LO):
        v.line(0, z, D.OD, z, "seam")
    # The +X wall's stepped opening (ETH + removed web + USB).
    v.fill_poly(STEP_X)
    v.poly(STEP_X, "outline", closed=False)

    # ---- dimensions -----------------------------------------------------
    v.vdim(PLATE_Z0, D.OH, -34.0, fmt(D.OH - PLATE_Z0), ARM_Y0, 0.0)
    v.vdim(0.0, D.OH, -28.0, fmt(D.OH), 0.0)
    v.small_v(0.0, D.JOINT_A, -22.0, fmt(D.JOINT_A), 0.0)
    v.vdim(MID_LO, D.SPLIT_B, -16.0, fmt(D.MID_H), 0.0)
    v.vdim(BEZEL_LO, D.OH, -22.0, fmt(D.OH - BEZEL_LO), 0.0)
    v.hdim(0.0, D.OD, D.OH + 10.0, fmt(D.OD), D.OH)
    v.hdim(ARM_Y0, ARM_Y1, -14.0, fmt(ARM_EXPORT_Y), PLATE_Z0)

    # Stack annotations, aligned with the visible right edge of each part.
    v.leader_p(D.OD, D.OH - 4.0, 168.0, 175.0,
               f"BEZEL  {fmt(BEZEL_LO)} .. {fmt(D.OH)}   "
               f"({fmt(D.OH - BEZEL_LO)} SOLID)", size=2.05)
    v.leader_p(D.OD, 30.0, 168.0, 186.0,
               f"MID  {fmt(MID_LO)} .. {fmt(D.SPLIT_B)}   "
               f"({fmt(D.MID_H)}; carries every port)", size=2.05)
    v.leader_p(130.0, 24.0, 168.0, 196.0,
               f"+X STEP: ETH y {fmt(ETH['y0'])}..{fmt(ETH['y1'])} "
               f"to z {fmt(ETH['z1'])};", size=2.05)
    s.text(168.9, 199.0,
           f"USB y {fmt(USB['y0'])}..{fmt(USB['y1'])} to z "
           f"{fmt(USB['z1'])}; web removed", size=2.05, kind="note")
    v.leader_p(130.0, D.JOINT_A / 2.0, 168.0, 210.0,
               f"BASE  0.00 .. {fmt(D.JOINT_A)}   "
               f"(floor {fmt(D.FLOOR)}, rim to the Pi)", size=2.05)
    v.leader_p(D.PLATE_TRAY_Y1, 1.0, 168.0, 219.0,
               f"SKIRT  {fmt(D.PLATE_SKIRT_T)} WALL, z {fmt(SKIRT_Z0)} .. "
               f"+{fmt(SKIRT_Z1)}; {fmt(D.PLATE_SKIRT_CLR)} CLEARANCE",
               size=2.05)
    v.leader_p(ARM_Y1, PLATE_Z0 + D.PLATE_T / 2.0, 168.0, 228.0,
               f"PLATE  {fmt(PLATE_Z0)} .. {fmt(PLATE_Z1)}   "
               f"({fmt(D.PLATE_T)} slab; {fmt(D.PLATE_GAP)} gap)",
               size=2.05)
    v.leader_p(ARM_Y1, PLATE_Z0, 168.0, 236.0,
               f"ARM TIPS TO y {fmt(ARM_Y0)} / {fmt(ARM_Y1)} "
               "(SHEET 5)", size=2.05)

    v.label("SIDE ELEVATION  —  +X WALL (FROM +X, +Y TO RIGHT)",
            0.0, D.OH + 17.0, size=2.9)

    _callout_notes(
        s, 250.0, 30.0, "NOTES — SIDE ELEVATION",
        [
            "1.  Case underside is z 0.00, the bench; the plate hangs",
            "    below it and nothing else does.",
            f"2.  Case height {fmt(D.OH)}; with the plate "
            f"{fmt(D.OH - PLATE_Z0)}.",
            f"3.  Two {fmt(D.MATE_GAP)} butt-joint gaps: "
            f"{fmt(D.JOINT_A)}/{fmt(MID_LO)} and "
            f"{fmt(D.SPLIT_B)}/{fmt(BEZEL_LO)}.",
            f"4.  The BASE rim is {fmt(D.JOINT_A)}, under every plug on",
            "    the Pi, so the Pi drops straight in.",
            f"5.  Plate envelope: {fmt(ARM_EXPORT_X)} × "
            f"{fmt(ARM_EXPORT_Y)} × {fmt(PLATE_PRINT_H)} in print.",
            "6.  The hex vents and the battery-lead opening are in the",
            "    +Y wall; they read edge-on here (sheet 7).",
        ])
    s.scale_bar(250.0, 100.0, 1.0, 50.0)
    s.title_block()
    return s


# =====================================================================
#  Sheet 4  -  assembly, bottom view
# =====================================================================

def sheet_assembly_bottom():
    s = Sheet(4, "ASSEMBLY  —  BOTTOM VIEW",
              "Plate outline and arms, plate bolts, Pi counterbores, six rim bores",
              "1:1")
    s.frame()
    v = View(s, 65.0, 215.0, 1.0)
    v.bounds(ARM_X0, ARM_Y0, ARM_X1, ARM_Y1, "bottom")

    # Plate floor silhouette, with the four cut waists.
    v.trace(plate_outline_segments(0.16), "outline")
    # Skirt outer edge (coincides with the tray) and its inner clearance.
    v.rrect(D.PLATE_TRAY_X0, D.PLATE_TRAY_Y0,
            D.PLATE_TRAY_X1 - D.PLATE_TRAY_X0,
            D.PLATE_TRAY_Y1 - D.PLATE_TRAY_Y0, D.PLATE_TRAY_R, "hidden")
    v.rrect(-D.PLATE_SKIRT_CLR, -D.PLATE_SKIRT_CLR,
            D.OW + 2 * D.PLATE_SKIRT_CLR, D.OD + 2 * D.PLATE_SKIRT_CLR,
            D.PLATE_SKIRT_R, "hidden")

    # Four plate bolts: counterbore 6.20 and clearance 3.40, visible below.
    for (x, y) in PLATE_BOLTS:
        v.circle(x, y, D.PLATE_CBORE_D, "outline")
        v.circle(x, y, D.PLATE_CLR, "feature")
        v.cross(x, y, 2.2)

    # The BASE's four Pi counterbores and six rim counterbores are hidden
    # by the plate; dashed here, dimensioned here, reached through it.
    for (x, y) in PI_HOLES:
        v.circle(x, y, D.PI_CBORE_D, "hidden")
        v.circle(x, y, D.PI_SCREW_CLR, "hidden")
        v.cross(x, y, 2.0)
    for (x, y) in SCREWS:
        v.circle(x, y, D.SCREW_CSK_D, "hidden")
        v.circle(x, y, D.SCREW_CBORE_D, "hidden")
        v.cross(x, y, 2.0)

    # Skirt vent notches (upward, so hidden from below).
    for x in VENT_X:
        v.rect(x - D.VENT_W / 2, D.PLATE_TRAY_Y0, D.VENT_W,
               -D.PLATE_TRAY_Y0, "hidden")

    # Case datum, visible only as a chain line through the plate.
    v.rect(0, 0, D.OW, D.OD, "centre")

    # ---- dimensions -----------------------------------------------------
    bx = sorted({clean(x) for x, _ in PLATE_BOLTS})
    by = sorted({clean(y) for _, y in PLATE_BOLTS})
    pxs = sorted({clean(x) for x, _ in PI_HOLES})
    pys = sorted({clean(y) for _, y in PI_HOLES})
    sxs = sorted({clean(x) for x, _ in SCREWS})
    sys_ = sorted({clean(y) for _, y in SCREWS})
    # Overall plate envelope, clear of the part.
    v.hdim(ARM_X0, ARM_X1, ARM_Y1 + 8.0, fmt(ARM_EXPORT_X), ARM_Y1)
    v.vdim(ARM_Y0, ARM_Y1, ARM_X1 + 22.0, fmt(ARM_EXPORT_Y), ARM_X1)
    # Plate bolt rectangle, dimensioned on the empty face.
    v.hdim(bx[0], bx[1], D.PLATE_CY + 6.0, fmt(bx[1] - bx[0]), by[0])
    v.vdim(by[0], by[1], D.PLATE_CX - 6.0, fmt(by[1] - by[0]), bx[0])
    # Pi pattern: 8.60 from the case datum, then 58.00 / 49.00 spacing.
    v.hdim(0.0, pxs[0], D.OD + 4.0, fmt(pxs[0]), D.OD, pys[1])
    v.hdim(pxs[0], pxs[1], D.OD + 4.0, fmt(pxs[1] - pxs[0]),
           pys[1], pys[1])
    v.hdim(pxs[1], D.OW, D.OD + 4.0, fmt(D.OW - pxs[1]), pys[1], D.OD)
    v.vdim(0.0, pys[0], -4.5, fmt(pys[0]), 0.0, pxs[0])
    v.vdim(pys[0], pys[1], -4.5, fmt(pys[1] - pys[0]), pxs[0])
    v.vdim(pys[1], D.OD, -4.5, fmt(D.OD - pys[1]), pxs[0], 0.0)
    # Six rim bores, ordinates from the case datum.
    v.ord_x(sxs, ARM_Y0 - 8.0, 0.0, ARM_Y0, labels=[fmt(x) for x in sxs])
    v.ord_y(sys_, ARM_X1 + 8.0, 0.0, ARM_X1, labels=[fmt(y) for y in sys_])

    # ---- callouts -------------------------------------------------------
    v.leader_p(PLATE_BOLTS[1][0], PLATE_BOLTS[1][1], 250.0, 34.0,
               f"4× Ø{fmt(D.PLATE_CBORE_D)} × {fmt(D.PLATE_CBORE_H)} "
               f"CBORE / Ø{fmt(D.PLATE_CLR)} THRU  "
               f"(M3 × {fmt(D.PLATE_SCREW_L, 0)})", size=2.05)
    v.leader_p(PI_HOLES[1][0], PI_HOLES[1][1], 250.0, 46.0,
               f"4× Ø{fmt(D.PI_CBORE_D)} × {fmt(D.PI_CBORE_H)} CBORE / "
               f"Ø{fmt(D.PI_SCREW_CLR)} THRU  (M2.5 + NUT)", size=2.05)
    v.leader_p(SCREWS[2][0], SCREWS[2][1], 250.0, 58.0,
               f"6× Ø{fmt(D.SCREW_CSK_D)} × {fmt(D.SCREW_CSK_H)} CSK / "
               f"Ø{fmt(D.SCREW_CBORE_D)} × {fmt(D.SCREW_CBORE_H)} CBORE / "
               f"Ø{fmt(D.SCREW_CLR)} THRU", size=2.05)
    v.leader_p(VENT_X[-1], D.PLATE_TRAY_Y0 + 1.0, 250.0, 70.0,
               f"5× SKIRT NOTCH {fmt(D.VENT_W)} WIDE @ {fmt(D.VENT_P)} "
               "PITCH (FOR BASE VENTS)", size=2.05)
    v.leader_p(ARM_X1 - 4.0, D.PLATE_CY, 250.0, 82.0,
               f"4 ARMS ON {fmt(D.PLATE_ARM_ANG)}° DIAGONALS: ROOT "
               f"Ø{fmt(D.PLATE_ARM_ROOT_D)} @ r{fmt(D.PLATE_ARM_ROOT_R)},",
               size=2.05)
    s.text(250.9, 85.3,
           f"CUT WAIST {fmt(WAIST_W)} WIDE @ r{fmt(D.PLATE_ARM_NECK_R)}, TIP "
           f"Ø{fmt(D.PLATE_ARM_TIP_D)} @ r{fmt(D.PLATE_ARM_TIP_R)} "
           "(SHEET 5)", size=2.05, kind="note")

    v.label("BOTTOM VIEW  —  FROM -Z (X RIGHT, +Y UP)", 0.0,
            ARM_Y1 + 16.0, size=2.9)

    _callout_notes(
        s, 250.0, 100.0, "NOTES — BOTTOM VIEW",
        [
            "1.  The light chain rectangle is the case datum; every",
            "    position here is measured from it.",
            "2.  Dashed circles lie on the BASE's underside, above the",
            "    plate floor: remove the four plate bolts to reach them.",
            "3.  The Pi's four M2.5 screws go up from underneath through",
            "    the counterbores; each takes a nut above the PCB.",
            f"4.  The six M3 × {fmt(D.SCREW_L, 0)} case screws go up "
            "through the BASE's",
            "    rim into the MID. Their heads are covered by the plate.",
            f"5.  Plate bolts are M3 × {fmt(D.PLATE_SCREW_L, 0)} into "
            f"blind Ø{fmt(D.PLATE_PILOT_D)} ×",
            f"    {fmt(D.PLATE_PILOT_DEEP)} pilots, leaving "
            f"{fmt(D.JOINT_A - D.PLATE_PILOT_DEEP)} above z 0.",
            f"6.  Plate thickness {fmt(D.PLATE_T)}; counterbores are in "
            "the OUTER face.",
            f"7.  Arm waist is cut: two Ø{fmt(2 * WAIST_R)} cuts "
            f"{fmt(WAIST_OFF)} off each",
            f"    arm axis at r {fmt(D.PLATE_ARM_NECK_R)} leave a "
            f"{fmt(WAIST_W)} strap seat.",
        ])
    s.scale_bar(250.0, 170.0, 1.0, 50.0)
    s.title_block()
    return s


# =====================================================================
#  Sheet 7  -  MID
# =====================================================================

def sheet_mid():
    s = Sheet(7, "MID  —  SHIM",
              "Port slots, front panel, rear vent field, shelf ring, screw pilots",
              "1:1")
    s.frame()

    # ---- front (-Y) -----------------------------------------------------
    v = View(s, 55.0, 230.0, 1.0)
    v.bounds(0, MID_LO, D.OW, D.SPLIT_B, "mid front")
    v.rect(0, MID_LO, D.OW, D.MID_H, "outline")

    for tag in ("PWR", "HDMI", "AUDIO"):
        p = PORTS[tag][0]
        v.notch(p["x0"], p["x1"], MID_LO, p["z1"])
    for x in LED_X:
        v.circle(x, D.PANEL_Z, D.LED_D, "feature")
    for x in SW_X:
        v.rect(x - D.SW_POCKET / 2, SW_Z0, D.SW_POCKET, D.SW_POCKET, "hidden")
        v.circle(x, D.PANEL_Z, D.SW_BTN_D, "feature")
    v.rrect(ACC_X0, ACC_Z0, D.ACC_W, D.ACC_H, D.ACC_R, "outline")

    # ---- rear (+Y), seen from +Y: X runs left ---------------------------
    rv = View(s, 255.0, 230.0, 1.0, mirror=D.OW)
    rv.bounds(0, MID_LO, D.OW, D.SPLIT_B, "mid rear")
    rv.rect(0, MID_LO, D.OW, D.MID_H, "outline")
    for (x, z) in HEXES:
        rv.hexagon(x, z, D.HEX_R, "outline")
    rv.slot(D.LEAD_RX0, D.LEAD_RX1, D.LEAD_RZ0, D.LEAD_RZ1)
    # Header relief: cut into the inner face only, hidden from outside.
    rv.line(D.HDR_RELIEF_X0, MID_LO, D.HDR_RELIEF_X0, D.HDR_RELIEF_Z1, "hidden")
    rv.line(D.HDR_RELIEF_X1, MID_LO, D.HDR_RELIEF_X1, D.HDR_RELIEF_Z1, "hidden")
    rv.line(D.HDR_RELIEF_X0, D.HDR_RELIEF_Z1, D.HDR_RELIEF_X1,
            D.HDR_RELIEF_Z1, "hidden")

    # ---- left (-X), seen from -X: Y runs left ---------------------------
    lv = View(s, 55.0, 162.0, 1.0, mirror=D.OD)
    lv.bounds(0, MID_LO, D.OD, D.SPLIT_B, "mid left")
    lv.rect(0, MID_LO, D.OD, D.MID_H, "outline")
    sd = PORTS["SD"][0]
    lv.notch(sd["y0"], sd["y1"], MID_LO, sd["z1"])
    lv.notch(D.WITTY_BTN_Y0, D.WITTY_BTN_Y1, MID_LO, D.WITTY_BTN_Z1)

    # ---- right (+X), seen from +X: Y runs right -------------------------
    xv = View(s, 160.0, 162.0, 1.0)
    xv.bounds(0, MID_LO, D.OD, D.SPLIT_B, "mid right")
    xv.rect(0, MID_LO, D.OD, D.MID_H, "outline")
    xv.fill_poly(STEP_X)
    xv.poly(STEP_X, "outline", closed=False)

    # ---- plan from +Z ---------------------------------------------------
    pv = View(s, 300.0, 150.0, 1.0)
    pv.bounds(0, 0, D.OW, D.OD, "mid plan")
    pv.rrect(0, 0, D.OW, D.OD, 3.0, "outline")
    pv.rrect(D.WALL, D.WALL, D.IW, D.ID, 2.0, "hidden")
    pv.rrect(D.WALL + D.SHELF_W, D.WALL + D.SHELF_W,
             SHELF_OPEN_W, SHELF_OPEN_D, 2.0, "outline")
    pv.fill_poly([(D.NOTCH_X0, D.NOTCH_Y0), (D.NOTCH_X0, D.NOTCH_Y1),
                  (D.NOTCH_X1, D.NOTCH_Y1), (D.NOTCH_X1, D.NOTCH_Y0)])
    pv.poly([(D.NOTCH_X0, D.NOTCH_Y0), (D.NOTCH_X0, D.NOTCH_Y1),
             (D.NOTCH_X1, D.NOTCH_Y1), (D.NOTCH_X1, D.NOTCH_Y0)],
            "outline", closed=False)
    pv.rect(D.HDR_RELIEF_X0, D.WALL + D.ID,
            D.HDR_RELIEF_X1 - D.HDR_RELIEF_X0, D.HDR_RELIEF_D, "hidden")
    for (x, y) in SCREWS:
        pv.circle(x, y, D.SCREW_PILOT, "feature")
        pv.cross(x, y, 2.2)
    pv.cross(D.OW / 2, D.OD / 2, 6.0)

    # ---- dimensions: front ---------------------------------------------
    v.hdim(0.0, D.OW, D.SPLIT_B + 8.0, fmt(D.OW), D.SPLIT_B)
    v.vdim(MID_LO, D.SPLIT_B, -12.0, fmt(D.MID_H), 0.0)
    ports_x = []
    for tag in ("PWR", "HDMI", "AUDIO"):
        p = PORTS[tag][0]
        ports_x += [clean(p["x0"]), clean(p["x1"])]
    v.ord_x(ports_x, -6.0, 0.0, MID_LO, labels=[fmt(x) for x in ports_x])
    panel_x = LED_X + SW_X
    v.ord_x(panel_x, D.SPLIT_B + 3.0, 0.0, D.SPLIT_B,
            labels=[fmt(x) for x in panel_x])
    v.ord_y([PORTS["PWR"][0]["z1"], PORTS["HDMI"][0]["z1"],
             D.PANEL_Z, ACC_Z1, ACC_Z0],
            D.OW + 8.0, 0.0, D.OW,
            labels=[fmt(PORTS["PWR"][0]["z1"]),
                    fmt(PORTS["HDMI"][0]["z1"]),
                    f"{fmt(D.PANEL_Z)} LED / SW",
                    fmt(ACC_Z1), fmt(ACC_Z0)])
    s.view_label("FRONT ELEVATION  —  -Y (FROM -Y)", 55.0, 170.0,
                 size=2.7)

    # ---- dimensions: rear ----------------------------------------------
    rv.hdim(0.0, D.OW, D.SPLIT_B + 8.0, fmt(D.OW), D.SPLIT_B)
    rv.hdim(D.HEX_X0, D.HEX_X0 + (D.HEX_NX - 1) * D.HEX_DX,
            D.SPLIT_B + 4.0,
            fmt((D.HEX_NX - 1) * D.HEX_DX), D.SPLIT_B)
    rv.hdim(D.LEAD_RX0, D.LEAD_RX1, D.SPLIT_B + 4.0,
            fmt(D.LEAD_RX1 - D.LEAD_RX0), D.SPLIT_B)
    rv.ord_y([D.HEX_Z0, D.LEAD_RZ0, D.LEAD_RZ1,
              D.HEX_Z0 + (D.HEX_NZ - 0.5) * D.HEX_DZ],
             D.OW + 4.0, 0.0, D.OW,
             labels=[fmt(D.HEX_Z0), fmt(D.LEAD_RZ0), fmt(D.LEAD_RZ1),
                     fmt(D.HEX_Z0 + (D.HEX_NZ - 0.5) * D.HEX_DZ)],
             right=False)
    s.view_label("REAR  —  +Y (X REVERSED)", 255.0, 170.0, size=2.7)

    # ---- dimensions: left ----------------------------------------------
    lv.hdim(0.0, D.OD, D.SPLIT_B + 8.0, fmt(D.OD), D.SPLIT_B)
    lv.vdim(MID_LO, D.SPLIT_B, D.OD + 10.0, fmt(D.MID_H), D.OD)
    lv.vdim(MID_LO, sd["z1"], D.OD + 4.0, fmt(sd["z1"] - MID_LO), D.OD)
    lv.vdim(MID_LO, D.WITTY_BTN_Z1, D.OD + 4.0,
            fmt(D.WITTY_BTN_Z1 - MID_LO), D.OD)
    lv.hdim(0.0, sd["y0"], -6.0, fmt(sd["y0"]), MID_LO)
    lv.hdim(sd["y0"], sd["y1"], -10.0, fmt(sd["y1"] - sd["y0"]), MID_LO)
    lv.hdim(sd["y1"], D.WITTY_BTN_Y0, -14.0,
            fmt(D.WITTY_BTN_Y0 - sd["y1"]), MID_LO)
    lv.hdim(D.WITTY_BTN_Y0, D.WITTY_BTN_Y1, -18.0,
            fmt(D.WITTY_BTN_Y1 - D.WITTY_BTN_Y0), MID_LO)
    s.view_label("LEFT — -X (Y REVERSED)", 55.0, 116.0, size=2.7)

    # ---- dimensions: right ---------------------------------------------
    xv.hdim(0.0, D.OD, D.SPLIT_B + 8.0, fmt(D.OD), D.SPLIT_B)
    xv.vdim(MID_LO, D.SPLIT_B, -10.0, fmt(D.MID_H), 0.0)
    xv.hdim(STEP_X[0][0], STEP_X[-1][0], -6.0,
            fmt(STEP_X[-1][0] - STEP_X[0][0]), MID_LO)
    xv.hdim(STEP_X[0][0], STEP_X[2][0], -10.0,
            fmt(STEP_X[2][0] - STEP_X[0][0]), MID_LO)
    xv.hdim(STEP_X[5][0], STEP_X[-1][0], -10.0,
            fmt(STEP_X[-1][0] - STEP_X[5][0]), MID_LO)
    s.view_label("RIGHT — +X", 160.0, 116.0, size=2.7)

    # ---- dimensions: plan ----------------------------------------------
    pv.hdim(0.0, D.OW, D.OD + 8.0, fmt(D.OW), D.OD)
    pv.hdim(D.WALL + D.SHELF_W, D.OW - D.WALL - D.SHELF_W,
            D.OD + 4.0, fmt(SHELF_OPEN_W), D.OD)
    pv.vdim(D.WALL + D.SHELF_W, D.OD - D.WALL - D.SHELF_W,
            -4.0, fmt(SHELF_OPEN_D), 0.0)
    pv.hdim(0.0, D.WALL, -4.0, fmt(D.WALL), 0.0)
    pv.hdim(D.WALL, D.WALL + D.SHELF_W, -16.0, fmt(D.SHELF_W), 0.0)
    pv.hdim(D.NOTCH_X0, D.NOTCH_X1, -16.0,
            fmt(D.NOTCH_X1 - D.NOTCH_X0), 0.0)
    sx = sorted({clean(x) for x, _ in SCREWS})
    sy = sorted({clean(y) for _, y in SCREWS})
    pv.ord_x(sx, -24.0, 0.0, 0.0, labels=[fmt(x) for x in sx])
    pv.ord_y(sy, D.OW + 5.0, 0.0, D.OW, labels=[fmt(y) for y in sy])
    pv.label("PLAN  —  FROM +Z (TOP FACE AND SHELF RING)", 0.0,
             D.OD + 18.0, size=2.7)

    # ---- callouts -------------------------------------------------------
    pwr = PORTS["PWR"][0]
    hdmi = PORTS["HDMI"][0]
    audio = PORTS["AUDIO"][0]
    v.leader_p((pwr["x0"] + pwr["x1"]) / 2, 9.0, 178.0, 196.0,
               f"PWR SLOT  {fmt(pwr['x1']-pwr['x0'])} × "
               f"{fmt(pwr['z1']-MID_LO)}  TO BOTTOM", size=2.0)
    v.leader_p((hdmi["x0"] + hdmi["x1"]) / 2, 10.0, 178.0, 202.0,
               f"HDMI SLOT  {fmt(hdmi['x1']-hdmi['x0'])} × "
               f"{fmt(hdmi['z1']-MID_LO)}  TO BOTTOM", size=2.0)
    v.leader_p((audio["x0"] + audio["x1"]) / 2, 10.0, 178.0, 208.0,
               f"AUDIO SLOT  {fmt(audio['x1']-audio['x0'])} × "
               f"{fmt(audio['z1']-MID_LO)}  TO BOTTOM", size=2.0)
    v.leader_p(D.LED_X0, D.PANEL_Z, 178.0, 214.0,
               f"3× Ø{fmt(D.LED_D)} THRU  ·  P {fmt(D.LED_PITCH)}",
               size=2.0)
    v.leader_p(D.SW_X0, D.PANEL_Z, 178.0, 220.0,
               f"3× Ø{fmt(D.SW_BTN_D)} THRU LIP  ·  {fmt(D.SW_POCKET)} SQ "
               f"× {fmt(D.SW_POCKET_D)} DEEP", size=2.0)
    v.leader_p(D.ACC_CX, D.ACC_CZ, 178.0, 226.0,
               f"{fmt(D.ACC_W)} × {fmt(D.ACC_H)} R{fmt(D.ACC_R)} THRU, "
               "TO BOTTOM", size=2.0)

    rv.leader_p(D.HEX_X0, D.HEX_Z0 + D.HEX_DZ, 355.0, 198.0,
                f"18× HEX {fmt(2*D.HEX_R)} ACROSS POINTS, THRU", size=2.0)
    rv.leader_p((D.LEAD_RX0 + D.LEAD_RX1) / 2, (D.LEAD_RZ0 + D.LEAD_RZ1) / 2,
                355.0, 202.0,
                f"LEAD {fmt(D.LEAD_RX1-D.LEAD_RX0)} × "
                f"{fmt(D.LEAD_RZ1-D.LEAD_RZ0)} THRU", size=2.0)
    rv.leader_p(D.HDR_RELIEF_X1 - 6.0, D.HDR_RELIEF_Z1, 355.0, 206.0,
                f"HEADER RELIEF {fmt(D.HDR_RELIEF_D)} DEEP TO "
                f"Z {fmt(D.HDR_RELIEF_Z1)}  (HIDDEN)", size=2.0)

    lv.leader_p((sd["y0"] + sd["y1"]) / 2, 6.4, 126.0, 144.0,
                f"SD SLOT {fmt(sd['y1']-sd['y0'])} × "
                f"{fmt(sd['z1']-MID_LO)}", size=2.0)
    lv.leader_p((D.WITTY_BTN_Y0 + D.WITTY_BTN_Y1) / 2, 18.0, 126.0, 151.0,
                f"WITTY SLOT {fmt(D.WITTY_BTN_Y1-D.WITTY_BTN_Y0)} × "
                f"{fmt(D.WITTY_BTN_Z1-MID_LO)}", size=2.0)

    xv.leader_p(45.0, 20.0, 235.0, 144.0,
                "ETH + USB STEPPED OPENING, TO BOTTOM", size=2.0)
    xv.leader_p(45.0, 23.0, 235.0, 151.0,
                f"ETH TOP {fmt(PORTS['ETH'][0]['z1'])}  ·  WEB REMOVED "
                f"TO {fmt(WEB['z1'])}  ·  USB TOP "
                f"{fmt(PORTS['USB'][0]['z1'])}", size=2.0)

    pv.leader_p(D.WALL + D.SHELF_W, 30.0, 220.0, 114.0,
                f"SHELF OPENING {fmt(SHELF_OPEN_W)} × "
                f"{fmt(SHELF_OPEN_D)} R2.00", size=2.0)
    pv.leader_p((D.NOTCH_X0 + D.NOTCH_X1) / 2, D.NOTCH_Y1, 220.0, 106.0,
                f"LCD NOTCH {fmt(D.NOTCH_X1-D.NOTCH_X0)} × "
                f"{fmt(D.NOTCH_Y1-D.NOTCH_Y0)}", size=2.0)
    pv.leader_p(D.HDR_RELIEF_X0 + 20.0, D.WALL + D.ID + D.HDR_RELIEF_D / 2,
                220.0, 98.0,
                f"HDR RELIEF {fmt(D.HDR_RELIEF_D)} DEEP, Z "
                f"{fmt(D.HDR_RELIEF_Z0)}..{fmt(D.HDR_RELIEF_Z1)}", size=2.0)
    pv.leader_p(SCREWS[2][0], SCREWS[2][1], 220.0, 90.0,
                f"6 COLUMNS  ·  Ø{fmt(D.SCREW_PILOT)} × "
                f"{fmt(D.SCREW_DEEP)} FROM EACH END", size=2.0)

    # ---- feature schedule and notes ------------------------------------
    rows = [
        ("A", "-Y", "PWR slot",
         f"{fmt(pwr['x1']-pwr['x0'])} × {fmt(pwr['z1']-MID_LO)}",
         f"X {fmt(pwr['x0'])}..{fmt(pwr['x1'])}; top z {fmt(pwr['z1'])}"),
        ("B", "-Y", "HDMI slot",
         f"{fmt(hdmi['x1']-hdmi['x0'])} × {fmt(hdmi['z1']-MID_LO)}",
         f"X {fmt(hdmi['x0'])}..{fmt(hdmi['x1'])}; top z {fmt(hdmi['z1'])}"),
        ("C", "-Y", "AUDIO slot",
         f"{fmt(audio['x1']-audio['x0'])} × {fmt(audio['z1']-MID_LO)}",
         f"X {fmt(audio['x0'])}..{fmt(audio['x1'])}; top z {fmt(audio['z1'])}"),
        ("D", "-Y", "LED bores",
         f"3× Ø{fmt(D.LED_D)} THRU, P{fmt(D.LED_PITCH)}",
         f"X {fmt(LED_X[0])} / {fmt(LED_X[1])} / {fmt(LED_X[2])}; "
         f"z {fmt(D.PANEL_Z)}"),
        ("E", "-Y", "Switch seats",
         f"3× {fmt(D.SW_POCKET)} SQ × {fmt(D.SW_POCKET_D)} deep; "
         f"Ø{fmt(D.SW_BTN_D)} thru",
         f"X {fmt(SW_X[0])} / {fmt(SW_X[1])} / {fmt(SW_X[2])}; "
         f"z {fmt(D.PANEL_Z)}"),
        ("F", "-Y", "Accessory opening",
         f"{fmt(D.ACC_W)} × {fmt(D.ACC_H)} R{fmt(D.ACC_R)} THRU",
         f"X {fmt(ACC_X0)}..{fmt(ACC_X1)}; z {fmt(ACC_Z0)}..{fmt(ACC_Z1)}"),
        ("G", "+Y", "Hex vent field",
         f"18× {fmt(2*D.HEX_R)} × {fmt(D.HEX_R*math.sqrt(3))} THRU",
         f"X {fmt(D.HEX_X0)}..{fmt(D.HEX_X0+5*D.HEX_DX)}; "
         f"z {fmt(D.HEX_Z0)}..{fmt(D.HEX_Z0+2.5*D.HEX_DZ)}"),
        ("H", "+Y", "Battery lead",
         f"{fmt(D.LEAD_RX1-D.LEAD_RX0)} × {fmt(D.LEAD_RZ1-D.LEAD_RZ0)} THRU",
         f"X {fmt(D.LEAD_RX0)}..{fmt(D.LEAD_RX1)}; "
         f"z {fmt(D.LEAD_RZ0)}..{fmt(D.LEAD_RZ1)}"),
        ("I", "-X", "SD slot",
         f"{fmt(sd['y1']-sd['y0'])} × {fmt(sd['z1']-MID_LO)}",
         f"Y {fmt(sd['y0'])}..{fmt(sd['y1'])}; top z {fmt(sd['z1'])}"),
        ("J", "-X", "Witty button slot",
         f"{fmt(D.WITTY_BTN_Y1-D.WITTY_BTN_Y0)} × "
         f"{fmt(D.WITTY_BTN_Z1-MID_LO)}",
         f"Y {fmt(D.WITTY_BTN_Y0)}..{fmt(D.WITTY_BTN_Y1)}; "
         f"top z {fmt(D.WITTY_BTN_Z1)}"),
        ("K", "+X", "ETH + USB opening",
         "stepped, to bottom",
         f"Y {fmt(STEP_X[0][0])}..{fmt(STEP_X[-1][0])}; "
         f"z {fmt(MID_LO)}..{fmt(WEB['z1'])}"),
        ("L", "TOP", "Shelf opening",
         f"{fmt(SHELF_OPEN_W)} × {fmt(SHELF_OPEN_D)} R2.00",
         f"from X/Y {fmt(D.WALL+D.SHELF_W)}; z {fmt(SHELF_Z0)}.."
         f"{fmt(D.SPLIT_B)}"),
        ("M", "TOP", "LCD notch",
         f"{fmt(D.NOTCH_X1-D.NOTCH_X0)} × {fmt(D.NOTCH_Y1-D.NOTCH_Y0)}",
         f"X {fmt(D.NOTCH_X0)}..{fmt(D.NOTCH_X1)}; "
         f"Y {fmt(D.NOTCH_Y0)}..{fmt(D.NOTCH_Y1)}"),
        ("N", "+Y", "Header relief",
         f"{fmt(D.HDR_RELIEF_D)} deep, {fmt(D.HDR_RELIEF_X1-D.HDR_RELIEF_X0)} long",
         f"X {fmt(D.HDR_RELIEF_X0)}..{fmt(D.HDR_RELIEF_X1)}; "
         f"z {fmt(D.HDR_RELIEF_Z0)}..{fmt(D.HDR_RELIEF_Z1)}"),
        ("P", "ALL", "Screw pilots",
         f"12× Ø{fmt(D.SCREW_PILOT)} × {fmt(D.SCREW_DEEP)}",
         f"X {'/'.join(fmt(x) for x in sx)}; "
         f"Y {'/'.join(fmt(y) for y in sy)}"),
    ]
    _table(s, 14.0, 30.0, [7.0, 9.0, 38.0, 64.0, 82.0],
           ["TAG", "FACE", "FEATURE", "SIZE / DEPTH",
            "POSITION  (DATUM X0/Y0/Z0)"],
           rows, size=1.55, row_h=4.65)

    _callout_notes(
        s, 220.0, 30.0, "NOTES — MID",
        [
            "1.  Datum: X = -X outer face, Y = -Y outer face,",
            "    Z = case underside (z 0). MID spans z 5.70..40.60.",
            "2.  Every port slot is open to the MID's bottom edge and",
            "    is closed from below by the BASE rim on assembly.",
            "3.  Dashed: switch seats behind the 0.45 lip, the cavity",
            "    wall below the shelf, and the header relief.",
            "4.  The shelf ring is 3.00 wide; its top face at z 38.60",
            "    is the LCD seat (SPLIT_B = 40.60 at the wall).",
            f"5.  Walls {fmt(D.WALL)}; seam groove {fmt(D.SEAM_D)} × "
            f"{fmt(D.SEAM_H)} at both",
            f"    joints, patched {fmt(D.SEAM_PATCH)} long at the six columns.",
            f"6.  Pilots: {fmt(D.SCREW_DEEP)} deep from each end, leaving",
            f"    {fmt(D.MID_H - 2*D.SCREW_DEEP)} of solid between the floors.",
        ], size=2.05, spacing=2.9)
    s.scale_bar(235.0, 120.0, 1.0, 50.0)
    s.title_block()
    return s


# =====================================================================
#  Sheet 8  -  BEZEL
# =====================================================================

def sheet_bezel():
    s = Sheet(8, "BEZEL",
              "LCD pocket and window, lip, six flush counterbores, section A-A",
              "1:1  ·  SECTION 2:1")
    s.frame()

    # ---- plan from +Z ---------------------------------------------------
    v = View(s, 60.0, 216.0, 1.0)
    v.bounds(0, 0, D.OW, D.OD, "bezel plan")
    v.rrect(0, 0, D.OW, D.OD, 3.0, "outline")
    v.rrect(D.POCK_X, D.POCK_Y, D.POCK_W, D.POCK_D, 1.0, "hidden")
    v.rrect(D.WIN_X, D.WIN_Y, D.WIN_W, D.WIN_D, 0.0, "outline")
    for (x, y) in SCREWS:
        v.circle(x, y, D.SCREW_CSK_D, "outline")
        v.circle(x, y, D.SCREW_CBORE_D, "feature")
        v.circle(x, y, D.SCREW_CLR, "feature")
        v.cross(x, y, 2.2)
    v.cross(D.OW / 2, D.OD / 2, 6.0)
    # Section A-A through the window.
    ax0, ay0 = v.p(-4.0, D.OD / 2)
    ax1, ay1 = v.p(D.OW + 4.0, D.OD / 2)
    s.line(ax0, ay0, ax1, ay1, "centre")
    s.arrow(ax0, ay0, -1, 0, size=2.2, half=0.8)
    s.arrow(ax1, ay1, 1, 0, size=2.2, half=0.8)
    s.text(ax0 - 1.0, ay0 - 1.5, "A", size=2.6, anchor="end",
           weight="bold", kind="note")
    s.text(ax1 + 1.0, ay1 - 1.5, "A", size=2.6, weight="bold", kind="note")

    # ---- plan dimensions ------------------------------------------------
    v.hdim(0.0, D.OW, D.OD + 12.0, fmt(D.OW), D.OD)
    v.hdim(D.WIN_X, D.WIN_X + D.WIN_W, D.OD + 6.0, fmt(D.WIN_W), D.OD)
    v.hdim(0.0, D.WIN_X, D.OD + 2.0, fmt(D.WIN_X), D.OD)
    v.hdim(D.WIN_X + D.WIN_W, D.OW, D.OD + 2.0,
           fmt(D.OW - D.WIN_X - D.WIN_W), D.OD)
    v.vdim(0.0, D.OD, -12.0, fmt(D.OD), 0.0)
    v.vdim(D.WIN_Y, D.WIN_Y + D.WIN_D, D.OW + 12.0, fmt(D.WIN_D), D.OW)
    v.vdim(0.0, D.WIN_Y, -2.0, fmt(D.WIN_Y), 0.0)
    v.vdim(D.WIN_Y + D.WIN_D, D.OD, -2.0,
           fmt(D.OD - D.WIN_Y - D.WIN_D), 0.0)
    v.hdim(D.POCK_X, D.POCK_X + D.POCK_W, -4.0, fmt(D.POCK_W), 0.0)
    v.hdim(0.0, D.POCK_X, -8.0, fmt(D.POCK_X), 0.0)
    v.hdim(D.POCK_X + D.POCK_W, D.OW, -8.0,
           fmt(D.OW - D.POCK_X - D.POCK_W), 0.0)
    v.vdim(D.POCK_Y, D.POCK_Y + D.POCK_D, D.OW + 8.0, fmt(D.POCK_D), D.OW)
    v.vdim(0.0, D.POCK_Y, D.OW + 4.0, fmt(D.POCK_Y), D.OW)
    v.vdim(D.POCK_Y + D.POCK_D, D.OD, D.OW + 4.0,
           fmt(D.OD - D.POCK_Y - D.POCK_D), D.OW)
    sx = sorted({clean(x) for x, _ in SCREWS})
    sy = sorted({clean(y) for _, y in SCREWS})
    v.ord_x(sx, -14.0, 0.0, 0.0, labels=[fmt(x) for x in sx])
    v.ord_y(sy, -18.0, 0.0, 0.0, labels=[fmt(y) for y in sy],
            right=False)
    v.label("PLAN  —  FROM +Z (TOP FACE)", 0.0, D.OD + 20.0, size=2.9)

    # ---- section A-A, 2:1 ----------------------------------------------
    #  Absolute-z section placed so its top face sits at paper y 205.  The
    #  blank is LCD_T + BEZEL_T less the 0.20 joint gap; the pocket runs up to
    #  SPLIT_B + LCD_T, leaving the 1.60 lip that carries the window.
    ztop = D.OH
    ptop = D.SPLIT_B + D.LCD_T
    sec = View(s, 195.0, 205.0 + 2.0 * ztop, 2.0)
    sec.bounds(0, BEZEL_LO, D.OW, ztop, "bezel section")
    _section_poly(sec, [(0, BEZEL_LO), (D.POCK_X, BEZEL_LO),
                        (D.POCK_X, ptop), (0, ptop)])
    _section_poly(sec, [(D.OW - D.POCK_X, BEZEL_LO),
                        (D.OW, BEZEL_LO), (D.OW, ptop),
                        (D.OW - D.POCK_X, ptop)])
    _section_poly(sec, [(0, ptop), (D.WIN_X, ptop),
                        (D.WIN_X, ztop), (0, ztop)])
    _section_poly(sec, [(D.OW - D.WIN_X, ptop), (D.OW, ptop),
                        (D.OW, ztop), (D.OW - D.WIN_X, ztop)])
    # Dimensions stacked above the cut, where the sheet is empty.
    cz = ztop + 3.0
    sec.hdim(0.0, D.POCK_X, cz, fmt(D.POCK_X), ztop, size=1.9)
    sec.hdim(D.POCK_X, D.WIN_X, cz, fmt(D.WIN_X - D.POCK_X), ztop, size=1.9)
    sec.hdim(D.WIN_X, D.OW - D.WIN_X, cz, fmt(D.WIN_W), ztop, size=1.9)
    sec.hdim(D.OW - D.WIN_X, D.OW - D.POCK_X, cz,
             fmt(D.WIN_X - D.POCK_X), ztop, size=1.9)
    sec.hdim(D.OW - D.POCK_X, D.OW, cz, fmt(D.POCK_X), ztop, size=1.9)
    sec.hdim(0.0, D.OW, ztop + 7.0, fmt(D.OW), ztop)
    sec.vdim(BEZEL_LO, ztop, -4.0, fmt(ztop - BEZEL_LO), 0.0)
    sec.vdim(BEZEL_LO, ptop, -10.0, fmt(ptop - BEZEL_LO), 0.0)
    sec.vdim(ptop, ztop, -10.0, fmt(ztop - ptop), 0.0)
    s.text(195.0 + (D.OW / 2) * 2.0, 214.5,
           "WINDOW OPEN THROUGH THE LIP", size=2.1, anchor="middle",
           kind="note")
    s.view_label("SECTION A-A  —  THROUGH THE WINDOW  (2:1)", 195.0, 182.0,
                 size=2.7)

    # ---- feature schedule ----------------------------------------------
    rows = [
        ("W", "Window",
         f"{fmt(D.WIN_W)} × {fmt(D.WIN_D)} THRU the {fmt(D.BEZEL_T)} lip",
         f"X {fmt(D.WIN_X)}..{fmt(D.WIN_X+D.WIN_W)}; "
         f"Y {fmt(D.WIN_Y)}..{fmt(D.WIN_Y+D.WIN_D)}"),
        ("P", "LCD pocket",
         f"{fmt(D.POCK_W)} × {fmt(D.POCK_D)} R1.00 × "
         f"{fmt(ptop-BEZEL_LO)} deep from below",
         f"X {fmt(D.POCK_X)}..{fmt(D.POCK_X+D.POCK_W)}; "
         f"Y {fmt(D.POCK_Y)}..{fmt(D.POCK_Y+D.POCK_D)}; "
         f"z {fmt(BEZEL_LO)}..{fmt(ptop)}"),
        ("S", "Screw holes",
         f"6× Ø{fmt(D.SCREW_CLR)} THRU; Ø{fmt(D.SCREW_CBORE_D)} × "
         f"{fmt(D.SCREW_CBORE_H)} cbore; Ø{fmt(D.SCREW_CSK_D)} × "
         f"{fmt(D.SCREW_CSK_H)} csk",
         f"X {'/'.join(fmt(x) for x in sx)}; "
         f"Y {'/'.join(fmt(y) for y in sy)}"),
        ("L", "Walls and lip",
         f"X walls {fmt(D.POCK_X)}, Y walls {fmt(D.POCK_Y)}; lip "
         f"{fmt(D.WIN_X-D.POCK_X)} × {fmt(D.BEZEL_T)}",
         f"lip all round the window; solid {fmt(ztop-BEZEL_LO)} tall"),
    ]
    _table(s, 172.0, 28.0, [8.0, 28.0, 100.0, 94.0],
           ["TAG", "FEATURE", "SIZE / DEPTH", "POSITION  (DATUM X0/Y0/Z0)"],
           rows, size=1.6, row_h=8.0)

    _callout_notes(
        s, 172.0, 78.0, "NOTES — BEZEL",
        [
            "1.  Plan datum: X/Y from the -X/-Y outer faces.",
            f"2.  Solid z {fmt(BEZEL_LO)}..{fmt(ztop)} "
            f"({fmt(ztop - BEZEL_LO)} thick; the blank is",
            f"    LCD_T + BEZEL_T less the {fmt(D.MATE_GAP)} joint gap).",
            f"3.  Pocket is cut from underneath to z {fmt(ptop)}; the",
            f"    remaining {fmt(ztop - ptop)} lip carries the window.",
            f"4.  The X walls thin to {fmt(D.POCK_X)} for the pocket; the",
            f"    Y walls stay at {fmt(D.POCK_Y)}.",
            f"5.  Every top counterbore is Ø{fmt(D.SCREW_CBORE_D)} in a",
            f"    {fmt(D.WALL)} wall, so each breaks out "
            f"{fmt((D.SCREW_CBORE_D - D.WALL)/2)} through the",
            "    adjacent outer face. Heads still finish flush.",
            f"6.  Window {fmt(D.WIN_W)} × {fmt(D.WIN_D)} leaves a",
            f"    {fmt(D.WIN_X-D.POCK_X)} lip all round.",
            f"7.  Screw columns are shared with the MID; see sheet 7.",
        ], size=2.0, spacing=2.85)
    s.scale_bar(172.0, 128.0, 1.0, 50.0)
    s.title_block()
    return s


# =====================================================================
#  Build
# =====================================================================

SHEETS = [
    ("assembly-top", sheet_assembly_top),
    ("assembly-front", sheet_assembly_front),
    ("assembly-side", sheet_assembly_side),
    ("assembly-bottom", sheet_assembly_bottom),
    ("plate", sheet_plate),
    ("base", sheet_base),
    ("mid", sheet_mid),
    ("bezel", sheet_bezel),
]


def derived_checks():
    """Assert the numbers the sheets depend on, independently of layout."""
    bad = []
    def want(name, got, expected, tol=0.011):
        if abs(got - expected) > tol:
            bad.append(f"{name}: {got:.4f} != {expected:.4f}")
    want("MID_LO", MID_LO, 5.70)
    want("BEZEL_LO", BEZEL_LO, 40.80)
    want("MID_H", D.MID_H, 34.90)
    want("OH", D.OH, 49.20)
    want("MID top", MID_LO + D.MID_H, D.SPLIT_B)
    want("bezel solid", D.OH - BEZEL_LO, 8.40)
    want("bezel blank", D.LCD_T + D.BEZEL_T - D.MATE_GAP, 8.40)
    want("pocket depth", D.LCD_T - D.MATE_GAP, 6.80)
    want("window width", D.WIN_W, 81.80)
    want("window depth", D.WIN_D, 51.60)
    want("pocket width", D.POCK_W, 86.60)
    want("pocket depth", D.POCK_D, 57.20)
    want("shelf opening width", SHELF_OPEN_W, 80.12)
    want("shelf opening depth", SHELF_OPEN_D, 51.20)
    want("arm span X (analytic)", ARM_SPAN_X, 134.90998, 0.02)
    want("arm span Y (analytic)", ARM_SPAN_Y, 99.97310, 0.02)
    want("arm export X", ARM_EXPORT_X, 134.89, 0.02)
    want("arm export Y", ARM_EXPORT_Y, 99.95, 0.02)
    want("plate print height", PLATE_PRINT_H, 7.50)
    want("plate bolt span X", 2 * D.PLATE_BOLT_DX, 62.00)
    want("plate bolt span Y", 2 * D.PLATE_BOLT_DY, 35.00)
    want("plate waist", D.PLATE_ARM_WAIST_D, 12.00)
    want("waist offset + radius", D.PLATE_ARM_WAIST_OFF - D.PLATE_ARM_GROOVE_R, 6.00)
    if len(PI_HOLES) != 4:
        bad.append(f"Pi holes: {len(PI_HOLES)}")
    if len(SCREWS) != 6:
        bad.append(f"screw columns: {len(SCREWS)}")
    if len(HEXES) != 18:
        bad.append(f"hex vents: {len(HEXES)}")
    nsegs, baddeg, loops = outline_topology(0.16)
    if nsegs < 100:
        bad.append(f"plate outline: only {nsegs} segments")
    if baddeg:
        bad.append(f"plate outline: {len(baddeg)} open/non-manifold vertices")
    if loops != 1:
        bad.append(f"plate outline: {loops} loops, expected 1")
    for tag, (p, face) in PORTS.items():
        lo = MID_LO - 1e-6
        if p["z1"] <= lo:
            bad.append(f"{tag}: top {p['z1']:.2f} below MID underside")
        if not (0.0 <= p["x0"] and p["x1"] <= D.OW):
            bad.append(f"{tag}: X outside the case")
        if not (0.0 <= p["y0"] and p["y1"] <= D.OD):
            bad.append(f"{tag}: Y outside the case")
    if not (D.NOTCH_X0 < D.NOTCH_X1 and D.NOTCH_Y0 < D.NOTCH_Y1):
        bad.append("LCD notch has no area")
    if D.SHELF_W * 2 >= D.IW or D.SHELF_W * 2 >= D.ID:
        bad.append("shelf ring consumes the opening")
    if D.WIN_W >= D.POCK_W or D.WIN_D >= D.POCK_D:
        bad.append("window larger than pocket")
    if D.PLATE_CBORE_D <= D.PLATE_CLR:
        bad.append("plate counterbore smaller than clearance")
    return bad


def find_chromium():
    for name in ("chromium", "chromium-browser", "google-chrome",
                 "google-chrome-stable"):
        path = shutil.which(name)
        if path:
            return path
    for path in ("/snap/bin/chromium", "/usr/bin/chromium",
                 "/usr/bin/google-chrome"):
        if Path(path).exists():
            return path
    return None


def render_png(svg_path: Path, png_path: Path, chromium: str):
    """Rasterise one sheet with headless Chromium (optional preview)."""
    cmd = [
        chromium, "--headless=new", "--no-sandbox", "--disable-gpu",
        "--hide-scrollbars", "--force-device-scale-factor=1",
        "--window-size=1680,1188",
        f"--screenshot={png_path}", svg_path.as_uri(),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=120)
        return png_path.exists()
    except (OSError, subprocess.SubprocessError):
        return False


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in argv
    want_png = "--png" in argv
    failures = 0

    diffs = compare_sources()
    if diffs:
        print("SCAD / verify.py disagreements:")
        for name, a, b in diffs:
            print(f"  {name}: scad {a:.4f}  verify {b:.4f}")
        failures += len(diffs)
    else:
        print("SCAD / verify.py: no shared-constant disagreements")

    bad = derived_checks()
    for line in bad:
        print("DERIVED CHECK FAILED:", line)
    failures += len(bad)
    if not bad:
        print("derived-value checks: all passed")

    written = []
    for name, fn in SHEETS:
        sheet = fn()
        problems = sheet.run_checks()
        for ok, msg in problems:
            print(f"{name}: {msg}")
        failures += sum(1 for ok, _ in problems if not ok)
        if check_only:
            print(f"{name}: checks only ({len(sheet.texts)} texts, "
                  f"{len(problems)} problems)")
            continue
        path = OUT / f"{name}.svg"
        path.write_text(sheet.svg(), encoding="utf-8")
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            print(f"{name}: XML parse failed: {exc}")
            failures += 1
        written.append(path)
        print(f"{name}: wrote {path.name} "
              f"({len(sheet.texts)} texts, {len(problems)} problems)")

    if want_png and written:
        chromium = find_chromium()
        if not chromium:
            print("PNG previews skipped: no Chromium/Chrome found")
        else:
            for svg_path in written:
                png_path = svg_path.with_suffix(".png")
                ok = render_png(svg_path, png_path, chromium)
                print(f"{svg_path.stem}: PNG {'wrote ' + png_path.name if ok else 'FAILED'}")

    if failures:
        print(f"FAILED: {failures} problem(s)")
        return 1
    print("OK: 8 sheets, all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
