#!/usr/bin/env python3
"""
Geometry check for pi-stack-v0.7.scad.

    python3 verify.py

Exports the five printable parts with OpenSCAD, then answers geometric
questions about them by ray-casting the exported triangles - not by eye.  Exit
status is 0 only if every check passes.

Standard library only.  OpenSCAD 2021.01 writes ASCII STL and there is no numpy
in this repo's venv or on the system python, so everything here is hand-rolled
on text parsing and plain lists.

WHY THIS FILE EXISTS
The v0.6 README credits its verification to /tmp/cv_models/wallcheck4.py and
cam_test.py.  Both lived only in /tmp, were never committed, and are gone, so
that claim is not reproducible from the repo.  This is a replacement for the
part of it that matters: the assertions about the fits, which is where a
mistake is invisible in a render.  Two parts touch at a plane, so "no
interference" and "no gap" look identical until you print it; a wall 0.40 too
thin for the header looks like every other wall.

TWO WAYS TO GET A FALSE PASS, BOTH OF WHICH THIS FILE HAS ALREADY FALLEN FOR
  1. An OpenSCAD `intersection()` that comes out EMPTY is only evidence if both
     operands are closed manifolds.  The imported Pi and WittyPi meshes are
     not: mesh_health reports 4470 and 2100 edges not shared by exactly two
     triangles, 185 and 158 shells.  CGAL cannot resolve them, OpenSCAD returns
     an empty intersection for ANYTHING you intersect with them, and it prints
     nothing but a warning.  The LCD's mesh IS closed (2 shells, 0 bad edges),
     so booleans against that one mean something.  Everything asserted here
     about the Pi and the WittyPi is a RAY CAST of the imported mesh, which
     works pointwise regardless of manifoldness.
  2. A probe that lands exactly on a facet plane returns noise in either
     direction.  Every probe below is inset, overshot or jittered for that
     reason; see surf_points and JITTER.

MIRRORED CONSTANTS
OpenSCAD's `use <>` imports modules but NOT top-level variables, so these
cannot be read out of the .scad.  They are mirrored here, and the bounding-box
checks below fail loudly if the exported envelope stops matching - which is the
drift that actually matters.  If you change a parameter in the .scad and this
script complains about a bounding box, update the mirror.
"""

import math
import os
import subprocess
import sys
import tempfile
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SCAD = os.path.join(HERE, "pi-stack-v0.7.scad")

# ---- mirrored from pi-stack-v0.7.scad ------------------------------------
OW, OD = 95.12, 66.20  # derived envelope
WALL = 4.50
CLR = 0.60
FLOOR = 2.60
JOINT_A = 5.50         # BASE height, in STACK coordinates
MATE_GAP = 0.20        # axial clearance at each printed butt joint
IW, ID = 86.12, 57.20  # interior, = the Pi's PCB + 2 * CLR
SHELF_T, SHELF_W = 2.00, 3.00
LCD_T, BEZEL_T = 7.00, 1.60
LCD_W, LCD_D = 85.80, 55.60     # measured off the part, not the 85.00 x 55.50 mesh
LCD_ACT_W, LCD_ACT_D = 74.00, 49.00   # the visible area - what the window must show
LCD_FIT, LCD_LIP, WIN_CLR = 0.40, 2.00, 0.40   # pocket, bezel lip, min window margin
PCB_X = PCB_Y = 5.10   # the Pi's PCB corner, = WALL + CLR
PCB_Z = 7.60           # the Pi's PCB underside, stack coords
PI_PCB_T = 1.33        # the Pi's PCB thickness
PI_PCB_W, PI_PCB_D = 84.92, 56.00
BOSS_D = 7.00          # Pi screw boss
PI_HOLE_IN = 3.50
PI_HOLE_DX, PI_HOLE_DY = 58.00, 49.00
PI_SCREW_CLR = 2.80    # M2.5: the Pi's own holes are o2.75, so M3 will not pass
PI_CBORE_D, PI_CBORE_H = 5.00, 1.40
SCREW_CLR, SCREW_PILOT, SCREW_DEEP = 3.40, 2.75, 15.00
SCREW_CBORE_D, SCREW_CBORE_H = 5.80, 1.65
SCREW_CSK_D, SCREW_CSK_H = 6.20, 0.20
SEAM_H, SEAM_D = 1.60, 0.60
SEAM_CLEAR = SCREW_CLR / 2 + 0.20       # = 1.90, in from the outer face
SEAM_PATCH = 7.00                       # ...and how far along the wall it runs
SCREW_L = 14.00        # 12 x M3 x 14, flush heads at OH and z 0, tip in the MID
#  The six columns, on the wall centreline 9 mm in from each corner.  EACH ONE
#  NOW CARRIES TWO SCREWS: a BEZEL one down from the top face into the MID's
#  upper pilot, and a BASE one up from the case's underside into the MID's
#  lower one.  They are separate from the Pi's four and the plate's four.
BASE_SCREWS = [(WALL / 2, 9.00), (WALL / 2, OD - 9.00), (9.00, WALL / 2),
               (OW - 9.00, WALL / 2), (9.00, OD - WALL / 2),
               (OW - 9.00, OD - WALL / 2)]
SCREWS = BASE_SCREWS

#  THE STACK, top-down from one measurement.  See the .scad's DERIVED block:
#  everything between PCB_Z and LCD_TOP_Z falls out of STACK_MEASURED, and the
#  checks in "the measured stack" below are what hold that derivation honest.
STACK_MEASURED = 40.00     # Pi PCB underside -> LCD top face, +/-0.2, MEASURED
LCD_TOP_Z = PCB_Z + STACK_MEASURED                 # = 47.60
LCD_UNDER = LCD_TOP_Z - LCD_T                      # = 40.60
SPLIT_B = LCD_UNDER        # MID / BEZEL joint = the LCD's underside
LCD_DROP = 12.80           # how far the LCD's socket hangs below its slab
WP_H = 7.08                # the WittyPi, above WITTY_Z (its tallest part)
WITTY_Z = LCD_UNDER - LCD_DROP - WP_H              # = 20.72
EXT_HEADER = 23.50         # CE09547 above the Pi's PCB top face (PUBLISHED)
HDR_BODY = 5.08            # the insulator's height - NOT published, derived
HDR_BODY_W, HDR_BODY_D = 51.50, 8.50
HDR_PIN_L, HDR_PIN, HDR_PITCH = 14.50, 0.64, 2.54
HDR_STANDOFF = EXT_HEADER - HDR_BODY - HDR_PIN_L   # = 3.92, the body's lift
HDR_TIP_Z = PCB_Z + PI_PCB_T + EXT_HEADER          # = 32.43, the pin tips
HDR_BODY_UNDER = PCB_Z + PI_PCB_T + HDR_STANDOFF   # = 12.85
HDR_BODY_TOP = PCB_Z + PI_PCB_T + EXT_HEADER - HDR_PIN_L   # = 17.93
WP_SOCK_D = HDR_TIP_Z - WITTY_Z    # = 11.71, how much socket swallows a pin
HDR_PIN_UP = WP_SOCK_D - WP_H      # = 4.63, pins proud of the WittyPi's top
MID_H = SPLIT_B - JOINT_A - MATE_GAP               # = 34.90, less the BASE gap
OH = SPLIT_B + LCD_T + BEZEL_T                     # = 49.20, the whole shell
PI_GPIO_CX, PI_GPIO_CY = 37.60, 57.60              # the GPIO field's centre

#  The case screws, which have to come after OH.  Each of the six columns is
#  drilled TWICE, from opposite ends, and the two drills are blind:
PILOT_UP = (SPLIT_B - SCREW_DEEP, SPLIT_B)         # 25.60 .. 40.60, from the top
PILOT_LO = (JOINT_A + MATE_GAP,
            JOINT_A + MATE_GAP + SCREW_DEEP)       #  5.70 .. 20.70, from below
#  Where the head of a SCREW_L screw seats in each group, and so where its tip
#  lands.  Both heads now seat FLUSH at OH and at z 0: the counterbore is
#  1.65 deep at both faces.
TIP_UP = OH - SCREW_CBORE_H - SCREW_L              # = 33.55, head flush
TIP_LO = SCREW_CBORE_H + SCREW_L                   # = 15.65, head flush

#  The header wall relief.  It now reaches the full pin height, not just the
#  body, so no MID material stands over any of the 40 pins.
HDR_RELIEF_D, HDR_RELIEF_X0, HDR_RELIEF_X1 = 1.30, 11.70, 66.00
HDR_RELIEF_Z0, HDR_RELIEF_Z1 = JOINT_A - 1.00, HDR_TIP_Z + 1.50
#  The WittyPi button's through-slot in the -X wall, measured off the mesh and
#  expressed in case coordinates.
WITTY_BTN_X0, WITTY_BTN_X1 = -1.00, WALL + 1.50
WITTY_BTN_Y0, WITTY_BTN_Y1 = 44.30, 47.90
WITTY_BTN_Z0, WITTY_BTN_Z1 = JOINT_A - 1.00, 25.80
#  The button itself, measured: local x 65.00..66.10, y 13.93..16.47,
#  z 0..1.00 -> case x 4.00..5.10, y 44.83..47.37, z 22.30..23.30.
WITTY_BTN = (4.00, 5.10, 44.83, 47.37, 22.30, 23.30)
ASSEMBLY_TOL = 0.25
SWEEP_SPAN = 80.0       # the MID's descent, mirrored from SWEEP_SPAN in the .scad
SWEEP_STEP = 0.50       # probe every half millimetre: finer than ASSEMBLY_TOL

#  The LCD's own geometry, measured off its mesh (see the "LCD seat" section).
#  The 0.50 wall reduction carries the whole board stack -0.50 in X and Y.
LCD_SOCK_X0, LCD_SOCK_X1 = 11.81, 46.10    # the 2x13 socket, case coords
LCD_SOCK_Y0, LCD_SOCK_Y1 = 54.50, 59.58
NOTCH_X0 = PI_GPIO_CX - HDR_BODY_W / 2 - 1.00
NOTCH_X1 = PI_GPIO_CX + HDR_BODY_W / 2 + 1.00
NOTCH_Y0, NOTCH_Y1 = WALL + ID - SHELF_W, WALL + ID     # 58.70, 61.70
LCD_PADS = [                               # the four support flanges
    [WALL,               30.00, WALL + 8.00,  42.00],   # -X wall
    [OW - WALL - 8.00,   30.00, OW - WALL,    42.00],   # +X wall
    [60.00,              WALL,  72.00,        WALL + 8.00],   # -Y wall
    [70.00,              WALL + ID - 8.00, 82.00, WALL + ID],  # +Y wall
]

#  The rear (+Y) wall's airflow and battery-lead openings.  The old charge
#  slot, round lead grommet and tie holes were replaced at the user's request
#  by a hexagonal vent field plus one lead rectangle.
HEX_R = 3.50                                 # circumradius, $fn=6 cylinder
HEX_DX, HEX_DZ = 9.00, 9.00                  # column / row pitch
HEX_X0, HEX_NX = 17.00, 6                    # first column, count
HEX_Z0, HEX_NZ = 12.00, 3                    # first even-column row, count
HEX_HW = HEX_R                               # half-width along X
HEX_HH = HEX_R * math.sqrt(3) / 2            # half-height across the flats
LEAD_RX0, LEAD_RX1 = 70.00, 80.00            # battery-lead rectangle, 10 x 6
LEAD_RZ0, LEAD_RZ1 = 17.00, 23.00
VENT_N, VENT_W, VENT_H = 5, 6.00, 2.50
VENT_P, VENT_Z = 9.00, 2.75

#  The belt plate, and the four bolts that hold it to the BASE's floor.
PLATE_CX, PLATE_CY = OW / 2, OD / 2
PLATE_BOLT_DX, PLATE_BOLT_DY = 31.00, 17.50
PLATE_BOLTS = [[PLATE_CX - PLATE_BOLT_DX, PLATE_CY - PLATE_BOLT_DY],
               [PLATE_CX + PLATE_BOLT_DX, PLATE_CY - PLATE_BOLT_DY],
               [PLATE_CX - PLATE_BOLT_DX, PLATE_CY + PLATE_BOLT_DY],
               [PLATE_CX + PLATE_BOLT_DX, PLATE_CY + PLATE_BOLT_DY]]
PLATE_GAP, PLATE_T = 0.50, 4.00
PLATE_W, PLATE_D = 76.20, OD - 2 * WALL            # 76.20 x 57.20
PLATE_R = 3.20                              # corner radius; sets the heads' gap
PLATE_CLR = 3.40                            # through the plate only
PLATE_CBORE_D, PLATE_CBORE_H = 6.20, 1.65   # M3 button head, buried flush
PLATE_PILOT_D = SCREW_PILOT                 # = 2.75, threaded in the BASE
PLATE_PILOT_DEEP = JOINT_A - 0.20           # = 5.30, blind, 0.20 cap at JOINT_A
PLATE_BOSS_D, PLATE_BOSS_H = 7.00, JOINT_A - FLOOR  # = 2.90, stops at the rim
PLATE_SCREW_L = 6.00                               # 4 x M3 x 6
PLATE_X0, PLATE_X1 = PLATE_CX - PLATE_W / 2, PLATE_CX + PLATE_W / 2
PLATE_Y0, PLATE_Y1 = PLATE_CY - PLATE_D / 2, PLATE_CY + PLATE_D / 2
PLATE_Z0, PLATE_Z1 = -(PLATE_GAP + PLATE_T), -PLATE_GAP   # -4.50 .. -0.50
BELT_W = 50.00
PLATE_HOOK_Y = PLATE_CY - BELT_W / 2                       # = 8.35
PLATE_HOOK_PROJ, PLATE_HOOK_T = 8.00, 2.00
PLATE_HOOK_LIP, PLATE_HOOK_W = 6.00, 12.00
PLATE_HOOK_N, PLATE_MOD = 2, 25.40

#  Front panel, in the -Y wall.  PANEL_Z and the band around it are STACK z.
PANEL_Z = 33.00
PANEL_BAND_LO, PANEL_BAND_HI = 15.56, SPLIT_B - SHELF_T   # 15.56 .. 38.60
LED_N, LED_D = 3, 5.20
LED_PITCH, LED_X0 = 7.00, 26.00
SW_N, SW_BODY, SW_H = 3, 6.00, 5.00
SW_POCKET, SW_LIP, SW_BTN_D = 6.20, 0.45, 3.60
SW_PITCH, SW_X0, SW_RIB = 9.00, 50.00, 0.20
SW_TERM_NOTCH, SW_TERM_MARGIN = 1.40, 0.20

#  ---- the reference hardware ------------------------------------------
#  The LEDs and the switches as PARTS, not as the space they need.  Mirrored
#  by hand from the .scad for the same reason as everything above: an
#  assertion driven by these numbers has to fail when the .scad's copy of
#  them drifts, which a shared import would quietly prevent.
#
#  Provenance, because it is not the same for the two:
#   - the SWITCH is measured.  `base/te-tactile-momentary-switches-1.snapshot
#     .1/1825910-6.step` reads out per-solid vertex boxes by walking
#     MANIFOLD_SOLID_BREP -> CLOSED_SHELL -> ... -> VERTEX_POINT ->
#     CARTESIAN_POINT, with the LENGTH_UNIT's SI prefix applied - these files
#     are in METRES.  No B-rep kernel is needed for extents, which is what
#     the README used to say was the blocker.
#   - the LED is NOT.  The vendor CAD is a 3 mm part, but the fitted LED is a
#     5 mm through-hole part; the .stp has only construction geometry, the
#     .igs is in INCHES, and the datasheet is an outline-only AutoCAD plot.
#     So these are the published figures for a 5 mm flanged LED.
LED_BODY_D, LED_FLANGE_D = 5.00, 5.90
LED_FLANGE_T, LED_LEN = 0.50, 8.60          # flange back to tip
LED_LEAD, LED_LEAD_DX, LED_LEAD_L = 0.45, 1.27, 2.50
SW_BODY_R, SW_LID_T = 0.25, 0.25
SW_TOP, SW_TOP_H, SW_ACT_D = 4.99, 0.50, 3.50
SW_ACT_UP, SW_ACT_L = 0.75, 2.50
SW_LEG_W, SW_LEG_D = 0.71, 0.60
SW_LEG_X0, SW_LEG_X1 = 1.90, 2.61           # the strip, measured, in case X
SW_LEG_Y0, SW_LEG_Y1 = 3.00, 3.60           # ...and in the SPLAY axis, which
                                            #  the placement turns into case Z
SW_LEG_L, SW_LEG_UP = 3.51, 0.90            # below the seat / the side exit
SW_LEG_IN = 0.10                            # pulled in, so the leg laps the
                                            #  body instead of touching it
#  Where the drawn leg actually lands, in case z about PANEL_Z.  The strip's
#  inner face is pulled SW_LEG_IN into the body; its outer face is the
#  measured SW_LEG_D beyond that.  These two, not SW_LEG_D on its own, are
#  what the terminal-clearance measurement below compares against the pocket.
SW_LEG_S0 = SW_LEG_Y0 - SW_LEG_IN               # = 2.90
SW_LEG_S1 = SW_LEG_S0 + SW_LEG_D + SW_LEG_IN    # = 3.60
LED_BARREL = LED_LEN - LED_FLANGE_T             # = 4.80, flange face to tip
#  The seat, as the .scad derives it: whatever of the wall is left after the
#  lip, or SW_H if the body is shorter than that - which is the branch that
#  decides whether there is a floor behind the body.  At the common 6 x 6 x 5
#  and WALL 4.50 the two are 4.05 and 5.00, so the cut breaks through and
#  there is none.
SW_POCKET_D = min(SW_H, WALL - SW_LIP)          # = 4.05, the seat
SW_POCKET_CUT = SW_H                            # = 5.00, the cut through it
#  The seat plane: the body's back face, and so the plane the legs hang from.
#  0.95 PAST the wall's inner face, because the body is SW_H tall and only
#  WALL - SW_LIP of wall is available to it.  The strip tops sit SW_LEG_UP
#  forward of that, so without the notches they would clear by only 0.05.
SW_SEAT = SW_LIP + SW_H                         # = 5.45
#  ...and the rib's own span, because two tests need to probe AROUND it.  The
#  .scad insets the rib's cut sub-box 0.60 from the seat end and 0.80 from
#  each side, and takes that sub-box OUT of the pocket cut - so the material
#  that stays is the sub-box's footprint, not its size.  Its far edge is the
#  inset PLUS the size, which is how a thickness of 3.35 becomes a span
#  ending at 3.95, and getting that wrong is exactly how a probe ends up
#  inside a rib it was told to avoid.
RIB_Y0 = SW_LIP + 0.60                          # = 1.05
RIB_Y1 = SW_LIP + SW_POCKET_D - 0.60           # = 4.40
RIB_Z = SW_POCKET / 2 - 0.80                   # = 2.30, symmetric about PANEL_Z

#  The accessory opening, directly under the switch row.  Sized to the request
#  (at least 12 x 7) rather than to a component, and cut 0.20 larger so the
#  finished opening still clears the minimum after hole undersize.
ACC_MIN_W, ACC_MIN_H = 12.00, 7.00
ACC_W, ACC_H, ACC_R = ACC_MIN_W + 0.20, ACC_MIN_H + 0.20, 1.50
ACC_CX = SW_X0 + (SW_N - 1) * SW_PITCH / 2      # = 59.00, under the buttons
ACC_LO = PANEL_BAND_LO                          # = 15.56, the HDMI top edge
ACC_HI = PANEL_Z - SW_POCKET / 2                # = 29.90, the pocket floors
ACC_CZ = (ACC_LO + ACC_HI) / 2                  # = 22.73, centred in the band
PORT_TOP = PANEL_BAND_LO                        # the highest port on this wall
ACC_DEPTH = 25.00                               # the clear corridor asked for
#  The audio jack's opening in this same wall: its top edge is the lowest thing
#  the accessory opening has to clear, and the strip of wall between the two is
#  the thinnest cross-section in the front face.  Model z1 6.80 + OFF[2] 7.93 +
#  PORT_G 0.75 = 15.48; the audio jack itself tops out at 14.73.
AUDIO_TOP = 15.48

#  The two +X port openings, in ABSOLUTE case coordinates.  The web the user
#  asked to remove is the strip left between their clearance cuts.
PORT_G = 0.75
OFF = (PCB_X + 48.44, PCB_Y + 25.59, PCB_Z + 0.33)   # model -> case
ETH_BOX = [17.53, 38.93, -23.19, -7.31, -2.00, 14.50]  # X0 X1 Y0 Y1 Z0 Z1
USB_BOX = [21.01, 38.93, -4.24, 29.24, -0.75, 16.39]
ETH_Y0 = ETH_BOX[2] + OFF[1] - PORT_G       # = 6.75, opening's -Y edge
ETH_Y1 = ETH_BOX[3] + OFF[1] + PORT_G       # = 24.13, opening's +Y edge
USB_Y0 = USB_BOX[2] + OFF[1] - PORT_G       # = 25.70, opening's -Y edge
USB_Y1 = USB_BOX[3] + OFF[1] + PORT_G       # = 60.68, opening's +Y edge
USB_Z1 = USB_BOX[5] + OFF[2] + PORT_G       # = 25.07, opening's top edge

EPS = 0.01   # probe separation where two parts legitimately bear on each
             # other (the LCD's seat), so CGAL's contact facets are not read
             # as interference.  The case's own butt joints now carry
             # MATE_GAP and need no lift at all.

#  Probe jitter, applied inside every ray cast.
#  Every coordinate in the .scad is a round number, so a probe placed on a
#  round number lands exactly on facet EDGES and vertices - and the inclusive
#  point-in-triangle test counts a point on a shared edge once for EACH of the
#  two triangles that share it.  That silently turns an even crossing count
#  odd and reports solid material where there is none; it is what made the
#  first run of this script blame the vent slots, the grommet and a good
#  chunk of the BASE's wall.  A few microns of deterministic skew is the
#  cheapest reliable cure, and it is orders of magnitude below anything this
#  model cares about.
JITTER = (0.00137, 0.00271, 0.00353)

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))


def note(name, detail=""):
    """Something worth printing that is not a pass/fail: an imported mesh's
    health, or a number measured off one."""
    print(f"  ----  {name}" + (f"   {detail}" if detail else ""))


# =====================================================================
#  OpenSCAD side
# =====================================================================
def run_openscad(out, driver, defines=()):
    """Run openscad on `driver`.  Returns its log.

    An EMPTY intersection is the answer we want for every interference probe,
    and openscad reports it as a non-zero exit with no output file - so that
    one case is success, not failure.  It is NOT proof: see the module
    docstring.  Only intersect closed manifolds with it.
    """
    cmd = ["openscad", "-o", out]
    for d in defines:
        cmd += ["-D", d]
    cmd.append(driver)
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    log = p.stdout + p.stderr
    if p.returncode != 0 and "top level object is empty" not in log:
        raise RuntimeError(f"openscad failed on {driver}:\n{log}")
    return log


def export(tmp, tag, expr, z=0.0):
    """Export one module EXPRESSION, translated up by z.  Returns the path.

    It takes an expression rather than a name because plate() has to be
    exported raw to be checked against the BASE where it really sits - while
    print_ok()'s plate_placed() is the flipped copy that lies on the bed.
    `-D Z=...` cannot reach through `use <>`, so the offset goes in the
    driver.

    z is 0.00 for every call now that the whole file is in one frame; it stays
    because probe_intersection's EPS still comes through it, and because a
    future frame change should not have to rediscover this.
    """
    driver = os.path.join(tmp, f"d_{tag}.scad")
    with open(driver, "w") as f:
        f.write(f"use <{SCAD}>\ntranslate([0, 0, Z]) {expr};\n")
    out = os.path.join(tmp, f"{tag}.stl")
    run_openscad(out, driver, [f"Z={z}"])
    return out


def probe_intersection(tmp, a, a_z, b, b_z, tag):
    """Facet count of the intersection of two placed parts.

    The parts are modelled MATE_GAP apart at every butt joint, so a plain
    intersection at their real positions is a usable interference test: any
    triangle at all is a genuine volumetric overlap.  (Before the mating
    clearance was added, a shared face made CGAL report contact triangles and
    the caller had to lift one part by EPS to filter them out.)

    Only for the case parts and the LCD.  Against the Pi or the WittyPi this
    returns 0 whatever you do, because those meshes are not closed.
    """
    driver = os.path.join(tmp, f"i_{tag}.scad")
    with open(driver, "w") as f:
        f.write(f"use <{SCAD}>\n"
                f"intersection() {{\n"
                f"    translate([0, 0, AZ]) {a};\n"
                f"    translate([0, 0, BZ]) {b};\n"
                f"}}\n")
    out = os.path.join(tmp, f"i_{tag}.stl")
    run_openscad(out, driver, [f"AZ={a_z}", f"BZ={b_z}"])
    if not os.path.exists(out):
        return 0
    return len(read_stl(out))


# =====================================================================
#  STL
# =====================================================================
def read_stl(path):
    """ASCII STL -> list of triangles, each 3 (x, y, z) tuples."""
    verts = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("vertex"):
                verts.append(tuple(float(t) for t in s.split()[1:4]))
    if not verts:
        return []
    return [tuple(verts[k:k + 3]) for k in range(0, len(verts), 3)]


def bbox(tris):
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def vertices(tris):
    """The unique vertices, rounded - a set to measure features off."""
    return sorted({tuple(round(c, 3) for c in v) for t in tris for v in t})


def mesh_health(tris):
    """(shells, bad_edges) for an exported mesh.

    A printable part has to be ONE closed shell.  Both halves of that are
    worth testing and they catch different things:

      - every edge must be shared by exactly two triangles, or the surface has
        a hole in it;
      - and every triangle must be reachable from every other by edge
        adjacency, or the "part" is really several pieces.

    A solid with an ENCLOSED VOID passes the first test and fails the second.
    That is not a hypothetical: it is what this model did, silently, wherever a
    cut landed exactly on an existing face or two pieces of the same cut met
    face-to-face.  CGAL kept each switch pocket as its own closed shell inside
    the wall, the mesh stayed closed, manifold and arithmetically the right
    volume, and the part read as one piece in every render - with a
    zero-thickness membrane where the pocket should have been open.

    It is also the test that says whether an intersection() means anything.
    The three imported boards do not pass it; see the docstring.
    """
    edges = defaultdict(list)
    for i, tri in enumerate(tris):
        a, b, c = (tuple(round(x, 6) for x in v) for v in tri)
        for p, q in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((p, q)))].append(i)
    bad = sum(1 for e in edges.values() if len(e) != 2)

    parent = list(range(len(tris)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges.values():
        for k in e[1:]:
            ra, rb = find(e[0]), find(k)
            if ra != rb:
                parent[ra] = rb
    return len({find(i) for i in range(len(tris))}), bad


def tri_box_hit(tri, lo, hi):
    """Does TRIANGLE cross the axis-aligned box [lo, hi]?

    Separating-axis test (Akenine-Moller).  This is the ONE kind of question
    the imported board meshes can be asked, and the reason it is here: they
    are open SURFACES, so a point-in-solid ray cast through one is
    meaningless - but a triangle-level overlap test needs no closure at all.
    Every axis either separates the two or it does not, so a single axis that
    does is proof of no overlap; finding none is proof of overlap.
    """
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    e = [(hi[i] - lo[i]) / 2 for i in range(3)]
    v = [[p[i] - c[i] for i in range(3)] for p in tri]

    for i in range(3):                       # the box's own three axes
        if min(p[i] for p in v) > e[i] or max(p[i] for p in v) < -e[i]:
            return False

    a = [v[1][i] - v[0][i] for i in range(3)]     # the triangle's normal
    b = [v[2][i] - v[1][i] for i in range(3)]
    n = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
         a[0] * b[1] - a[1] * b[0]]
    r = sum(e[i] * abs(n[i]) for i in range(3))
    if abs(sum(n[i] * v[0][i] for i in range(3))) > r:
        return False

    # ...and the nine cross products of the triangle's edges with them.  A
    # zero axis (a degenerate triangle) cannot separate anything, which is the
    # safe direction: it can only ever report an overlap, never hide one.
    for ed in (a, b, [v[0][i] - v[2][i] for i in range(3)]):
        for ax in ((0.0, ed[2], -ed[1]), (-ed[2], 0.0, ed[0]),
                   (ed[1], -ed[0], 0.0)):
            r = sum(e[i] * abs(ax[i]) for i in range(3))
            d = [sum(ax[i] * p[i] for i in range(3)) for p in v]
            if min(d) > r or max(d) < -r:
                return False
    return True


def tris_in_box(tris, lo, hi):
    return [t for t in tris if tri_box_hit(t, lo, hi)]


def facet_z(a, b, c, x, y):
    """The z at which the +Z ray through (x, y) crosses triangle a-b-c, or
    None if it misses.  Barycentric, with the same inclusive sign test the
    crossing count uses."""
    d1 = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
    d2 = (c[0] - b[0]) * (y - b[1]) - (c[1] - b[1]) * (x - b[0])
    d3 = (a[0] - c[0]) * (y - c[1]) - (a[1] - c[1]) * (x - c[0])
    if not ((d1 >= 0 and d2 >= 0 and d3 >= 0)
            or (d1 <= 0 and d2 <= 0 and d3 <= 0)):
        return None
    den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(den) < 1e-12:              # facet parallel to the ray
        return None
    l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
    l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
    l3 = 1.0 - l1 - l2
    return l1 * a[2] + l2 * b[2] + l3 * c[2]


class Solid:
    """A placed part, with an XY bucket index so ray casts stay cheap."""

    CELL = 10.0

    def __init__(self, tris, dz=0.0):
        self.tris = [tuple((v[0], v[1], v[2] + dz) for v in t) for t in tris]
        self.buckets = {}
        for t in self.tris:
            xs = [v[0] for v in t]
            ys = [v[1] for v in t]
            for i in range(int(math.floor(min(xs) / self.CELL)),
                           int(math.floor(max(xs) / self.CELL)) + 1):
                for j in range(int(math.floor(min(ys) / self.CELL)),
                               int(math.floor(max(ys) / self.CELL)) + 1):
                    self.buckets.setdefault((i, j), []).append(t)

    def inside(self, p):
        return self.crossings_above(*p) % 2 == 1

    def crossings_above(self, x, y, z):
        x, y, z = x + JITTER[0], y + JITTER[1], z + JITTER[2]
        n = 0
        cell = (int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL)))
        for a, b, c in self.buckets.get(cell, ()):
            zc = facet_z(a, b, c, x, y)
            if zc is not None and zc > z:
                n += 1
        return n

    def first_above(self, x, y, z0):
        """The lowest facet above z0 along +Z, or None above everything.

        This is what "is the underside flat" needs: a count answers inside or
        outside, but a standing-off screw head is a *lowest* surface below the
        one everything else shares.
        """
        x, y, z0 = x + JITTER[0], y + JITTER[1], z0 + JITTER[2]
        best = None
        cell = (int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL)))
        for a, b, c in self.buckets.get(cell, ()):
            zc = facet_z(a, b, c, x, y)
            if zc is not None and zc > z0 and (best is None or zc < best):
                best = zc
        return best


class Union:
    """Several placed parts, tested as one body."""

    def __init__(self, *solids):
        self.solids = solids

    def inside(self, p):
        return sum(s.crossings_above(*p) for s in self.solids) % 2 == 1


def spans(solid, x, y, z0, z1, step=0.1):
    """The solid z-runs along the +Z ray through (x, y), as (lo, hi) pairs."""
    out, cur, z = [], None, z0
    while z <= z1 + 1e-9:
        if solid.inside((x, y, z)):
            if cur is None:
                cur = z
        elif cur is not None:
            out.append((round(cur, 2), round(z, 2)))
            cur = None
        z += step
    if cur is not None:
        out.append((round(cur, 2), round(z1, 2)))
    return out


def surf_points(x0, x1, y0, y1, z0, z1, step=3.0, inset=0.4):
    """Sample the SURFACE of a box, strictly inside it.

    Every probe is inset from the true boundary, and that is not fussiness.
    A probe at exactly a face's z lands on a facet plane, where a ray cast
    along +Z is genuinely ambiguous and returns noise - the first run of this
    script reported 13 "collisions" that were all exactly that.  Inset probes
    also keep every sample inside the volume being claimed free, which is the
    conservative direction.
    """
    X0, X1 = x0 + inset, x1 - inset
    Y0, Y1 = y0 + inset, y1 - inset
    Z0, Z1 = z0 + inset, z1 - inset
    n = lambda a, b: max(1, int(math.ceil((b - a) / step)))
    nx, ny, nz = n(X0, X1), n(Y0, Y1), n(Z0, Z1)
    pts = []
    for i in range(nx + 1):
        x = X0 + (X1 - X0) * i / nx
        for j in range(ny + 1):
            y = Y0 + (Y1 - Y0) * j / ny
            pts += [(x, y, Z0), (x, y, Z1)]          # bottom and top faces
    for i in range(nx + 1):
        x = X0 + (X1 - X0) * i / nx
        for k in range(nz + 1):
            z = Z0 + (Z1 - Z0) * k / nz
            pts += [(x, Y0, z), (x, Y1, z)]          # the two Y walls
    for j in range(ny + 1):
        y = Y0 + (Y1 - Y0) * j / ny
        for k in range(nz + 1):
            z = Z0 + (Z1 - Z0) * k / nz
            pts += [(X0, y, z), (X1, y, z)]          # the two X walls
    return pts


def pin_centres():
    """The 40 GPIO pin centres, case coordinates."""
    return [(PI_GPIO_CX + (i - 9.5) * HDR_PITCH,
             PI_GPIO_CY + (j - 0.5) * HDR_PITCH)
            for i in range(20) for j in (0, 1)]


# =====================================================================
def main():
    if not os.path.exists(SCAD):
        sys.exit(f"missing {SCAD}")
    tmp = tempfile.mkdtemp(prefix="cv07-")
    print(f"pi-stack v0.7 geometry check   (scratch {tmp})\n")

    #  FRAMES.  There is only one now.  The .scad used to draw base/mid/bezel
    #  and the boards in STACK coordinates (z 0 = the BASE's underside) and the
    #  mount and the plate in ABSOLUTE ones (z 0 = the bench), crossing
    #  between them with an S() offset.  With the 21 mm tub gone, stack
    #  coordinates ARE absolute, every part is exported already placed, and
    #  S() is the identity - so it is deleted rather than left as `+ 0.00`.
    #  Only the plate is still drawn below z 0, and that is where it belongs.
    print("exporting")
    parts = {                       # tag -> module expression
        "base":   "base()",
        "mid":    "mid()",
        "bezel":  "bezel()",
        "plate":  "plate()",        # raw: below the case, negative z
        "header": "header()",
    }
    stl = {p: read_stl(export(tmp, p, e)) for p, e in parts.items()}
    base = Solid(stl["base"])
    mid = Solid(stl["mid"])
    bezel = Solid(stl["bezel"])
    plate = Solid(stl["plate"])
    header = Solid(stl["header"])
    shell = Union(base, mid, bezel)
    for p, t in stl.items():
        print(f"  {p:<6} {len(t):>5} triangles")

    #  The three imported boards, and the plate as it PRINTS.  The boards are
    #  exported already placed too, so nothing here needs a dz - and they are
    #  here as meshes to be ray-cast, not as operands for a boolean.
    stl_lcd = read_stl(export(tmp, "lcd", "lcd()"))
    stl_wit = read_stl(export(tmp, "wittypi", "wittypi()"))
    stl_rpi = read_stl(export(tmp, "pi", "pi()"))
    stl_bed = read_stl(export(tmp, "plate_bed", "plate_placed()"))
    lcd = Solid(stl_lcd, 0.0)
    witty = Solid(stl_wit, 0.0)
    rpi = Solid(stl_rpi, 0.0)

    #  The two reference parts, exported as the PLACED groups so every
    #  assertion below measures where the parts actually are rather than
    #  re-deriving the placement in Python and hoping it agrees.  Three shells
    #  each - one per part - and unlike the imported boards these ARE closed
    #  CSG solids, so `Solid.inside` is sound against them.  That is the whole
    #  reason the panel tests can ask the part a question now instead of
    #  asking a box that stands in for it.
    stl_leds = read_stl(export(tmp, "leds", "leds()"))
    stl_sws = read_stl(export(tmp, "switches", "switches()"))
    leds, sws = Solid(stl_leds), Solid(stl_sws)

    # ---- the exported meshes --------------------------------------------
    #  Nothing else here would notice a part that had quietly become several
    #  shells; see mesh_health.
    print("\nexported meshes")
    for p in ("base", "mid", "bezel", "plate", "header"):
        shells, bad = mesh_health(stl[p])
        check(f"{p} is one closed shell",
              shells == 1 and bad == 0,
              f"{shells} shell(s), {bad} edges not shared by two")

    #  ...and the two reference groups, which are three parts each.  Three
    #  shells is the assertion, not an accident of the export: it is what
    #  makes SW_N = 0 / LED_N = 0 deletable, and a union that had silently
    #  fused a leg into the part next door would show up here as fewer.
    for p, n in (("leds", LED_N), ("switches", SW_N)):
        shells, bad = mesh_health({"leds": stl_leds, "switches": stl_sws}[p])
        check(f"{p} is {n} closed shell(s)",
              shells == n and bad == 0,
              f"{shells} shell(s), {bad} edges not shared by two")

    # ---- envelope, which is also the drift guard on the mirrored numbers --
    print("\nenvelope")
    for name, part, lo, hi, why in (
            ("base", "base", 0, PCB_Z, "to the Pi bosses"),
            ("mid", "mid", JOINT_A + MATE_GAP, SPLIT_B, ""),
            ("bezel", "bezel", SPLIT_B + MATE_GAP, OH, "")):
        bx, by, z = bbox(stl[part])
        check(f"{name} z {lo}..{hi} {why}".strip(),
              abs(z[0] - lo) < 1e-6 and abs(z[1] - hi) < 1e-6,
              f"z {z[0]:.2f}..{z[1]:.2f}")
        check(f"{name} x/y = OW x OD",
              abs(bx[1] - bx[0] - OW) < 1e-6 and abs(by[1] - by[0] - OD) < 1e-6,
              f"{bx[1]-bx[0]:.2f} x {by[1]-by[0]:.2f}")
    #  The case's height is now just OH: the BASE sits on the bench.  This is
    #  the number the delete-the-MOUNT change is FOR, so it is asserted twice -
    #  once as the derived identity and once as a literal, so that a mirrored
    #  constant that drifted with the .scad cannot carry it.
    check("stack height = OH", abs(bbox(stl["bezel"])[2][1] - OH) < 1e-6,
          f"{OH:.2f}")
    check("case height = OH = 49.20, nothing under the BASE",
          abs(OH - 49.20) < 1e-9 and abs(bbox(stl["base"])[2][0]) < 1e-6,
          f"OH {OH:.2f}, BASE underside at {bbox(stl['base'])[2][0]:.2f}")
    _, _, hz = bbox(stl["header"])
    check("header stack z HDR_BODY_UNDER..HDR_TIP_Z",
          abs(hz[0] - HDR_BODY_UNDER) < 1e-6 and abs(hz[1] - HDR_TIP_Z) < 1e-6,
          f"z {hz[0]:.2f}..{hz[1]:.2f}")
    hx, hy, _ = bbox(stl["header"])
    check("header x/y = the body's 51.50 x 8.50 on the GPIO centre",
          abs(hx[1] - hx[0] - HDR_BODY_W) < 1e-6
          and abs(hy[1] - hy[0] - HDR_BODY_D) < 1e-6,
          f"{hx[1]-hx[0]:.2f} x {hy[1]-hy[0]:.2f} at "
          f"{(hx[0]+hx[1])/2:.2f},{(hy[0]+hy[1])/2:.2f}")

    # ---- the measured stack ---------------------------------------------
    #  Every height above the Pi falls out of ONE measurement.  These are the
    #  identities that make that true; if any of them drifts, the case is
    #  being sized twice, from two numbers that can disagree.
    print("\nthe measured stack (ONE measurement, everything else derived)")
    check("LCD_TOP_Z - PCB_Z = STACK_MEASURED",
          abs((LCD_TOP_Z - PCB_Z) - STACK_MEASURED) < 1e-9,
          f"{LCD_TOP_Z - PCB_Z:.2f} = the measured {STACK_MEASURED:.2f}")
    check("the LCD's socket lands on the WittyPi's top face",
          abs(WITTY_Z + WP_H + LCD_DROP - SPLIT_B) < 1e-9,
          f"{WITTY_Z:.2f} + {WP_H:.2f} + {LCD_DROP:.2f} = {SPLIT_B:.2f}")
    check("the header's body sits clear above the WittyPi's PCB",
          WITTY_Z > HDR_BODY_TOP,
          f"WittyPi at {WITTY_Z:.2f}, body top {HDR_BODY_TOP:.2f}, "
          f"gap {WITTY_Z - HDR_BODY_TOP:.2f}")
    check("the WittyPi's socket swallows a sane length of pin",
          0 < WP_SOCK_D < HDR_PIN_L,
          f"WP_SOCK_D {WP_SOCK_D:.2f} of the {HDR_PIN_L:.2f} long pins "
          f"(- DERIVED, not published: check it against the real socket)")
    check("the pins stand proud of the WittyPi into the LCD's socket",
          0 < HDR_PIN_UP < LCD_DROP,
          f"{HDR_PIN_UP:.2f} proud, LCD socket {LCD_DROP:.2f} deep")
    #  The twelve case screws only fit because of the stack height, and now
    #  there are TWO windows to satisfy with one length.  Both heads seat
    #  FLUSH in their counterbores - at OH above and at z 0 below - so each
    #  tip lands at OH - SCREW_L / SCREW_L.  Each has to fall inside its own
    #  blind pilot, and the check that matters is the LAST one below: the
    #  window any M3 must sit in to fit both joints, which is what the README
    #  publishes.
    check(f"the {SCREW_L:.0f} mm BEZEL screws land in the MID's upper pilot",
          PILOT_UP[0] <= TIP_UP <= PILOT_UP[1],
          f"head flush at {OH:.2f}, tip at {TIP_UP:.2f} in pilot "
          f"{PILOT_UP[0]:.2f}..{PILOT_UP[1]:.2f}; bite "
          f"{PILOT_UP[1] - TIP_UP:.2f}, {TIP_UP - PILOT_UP[0]:.2f} above its floor")
    check(f"the {SCREW_L:.0f} mm BASE screws land in the MID's lower pilot",
          PILOT_LO[0] <= TIP_LO <= PILOT_LO[1],
          f"head flush at 0.00, tip at {TIP_LO:.2f} in pilot "
          f"{PILOT_LO[0]:.2f}..{PILOT_LO[1]:.2f}; bite "
          f"{TIP_LO - PILOT_LO[0]:.2f}, {PILOT_LO[1] - TIP_LO:.2f} below its "
          f"ceiling")
    win_lo = max(OH - SCREW_CBORE_H - SPLIT_B,
                 PILOT_LO[0] - SCREW_CBORE_H)
    win_hi = min(OH - SCREW_CBORE_H - SPLIT_B + SCREW_DEEP,
                 PILOT_LO[1] - SCREW_CBORE_H)
    check("any M3 from 8 to 19 fits BOTH joints",
          win_lo <= 8.00 and 19.00 <= win_hi,
          f"window {win_lo:.2f}..{win_hi:.2f} mm; {SCREW_L:.0f} is the "
          f"specified length")

    # ---- the CE09547, in the case and in the stack -----------------------
    print("\nthe CE09547 (published 23.5 total / 14.5 pins)")
    check("body underside sits on the standoff, clear of the PCB",
          abs(HDR_BODY_UNDER - (PCB_Z + PI_PCB_T + HDR_STANDOFF)) < 1e-9,
          f"{HDR_BODY_UNDER:.2f} = {PCB_Z + PI_PCB_T:.2f} + {HDR_STANDOFF:.2f}")
    check("solid through the body, empty in the standoff below it",
          header.inside((PI_GPIO_CX, PI_GPIO_CY, (HDR_BODY_UNDER + 2.00)))
          and not header.inside((PI_GPIO_CX, PI_GPIO_CY,
                                 (HDR_BODY_UNDER - 0.50))),
          f"probed stack {HDR_BODY_UNDER + 2.00:.2f} and "
          f"{HDR_BODY_UNDER - 0.50:.2f}")
    #  Between the two pin rows and between columns: the body is only as wide
    #  as the 2x20 field there, so this is the gap that proves the pins are
    #  drawn as pins and not as a block.
    gapx = PI_GPIO_CX + 0.5 * HDR_PITCH
    check("empty between the pins, solid on one",
          not header.inside((gapx, PI_GPIO_CY, (20.00)))
          and header.inside((PI_GPIO_CX - 0.5 * HDR_PITCH,
                             PI_GPIO_CY - 0.5 * HDR_PITCH, (20.00))),
          f"probed {gapx:.2f},{PI_GPIO_CY:.2f} and "
          f"{PI_GPIO_CX - 0.5 * HDR_PITCH:.2f},{PI_GPIO_CY - 0.5 * HDR_PITCH:.2f}")
    check("nothing above the pin tips",
          not header.inside((PI_GPIO_CX - 0.5 * HDR_PITCH,
                             PI_GPIO_CY - 0.5 * HDR_PITCH,
                             (HDR_TIP_Z + 0.50))),
          f"probed stack {HDR_TIP_Z + 0.50:.2f}")
    n = probe_intersection(tmp, "mid()", 0.0, "header()", EPS, "midhdr")
    check("the CE09547 fits inside the MID", n == 0,
          "this is the check that a 51.50 x 8.50 body in an 8.50 gap fails")

    #  The Pi's own GPIO header, RAY-CAST rather than intersected (the Pi's
    #  mesh is open).  It is solid 7.60..11.45 between the pins and 8.95..16.95
    #  on them, so the CE09547's body has to be a RECEPTACLE: its underside
    #  lands above the insulator and its pins swallow the stock ones.
    ins_spans = spans(rpi, PI_GPIO_CX + 0.5 * HDR_PITCH, PI_GPIO_CY,
                      8.00, 20.00)
    pin_tips = [spans(rpi, x, y, 8.00, 20.00) for x, y in pin_centres()]
    ins_top = round(ins_spans[-1][1], 2) if ins_spans else None
    pin_tip = max((round(s[-1][1], 2) for s in pin_tips if s),
                  default=None)
    check("the body's underside clears the Pi's GPIO insulator",
          ins_top is not None and HDR_BODY_UNDER > ins_top + 0.50,
          f"insulator tops out at stack {ins_top}, body underside "
          f"{HDR_BODY_UNDER:.2f}")
    check("the Pi's stock pins reach up INTO the body (as a socket must)",
          pin_tip is not None and pin_tip > HDR_BODY_UNDER,
          f"stock pins to stack {pin_tip}, body {HDR_BODY_UNDER:.2f}.."
          f"{HDR_BODY_TOP:.2f}, tips {HDR_TIP_Z:.2f} - the drawn body is solid,"
          f" so this is a RECEPTACLE and the repo cannot prove it")

    #  ...and the other end of the same chain: the WittyPi's socket has to let
    #  the pins through, and the LCD's socket has to cover them.  Both are ray
    #  casts, and both would move together if WITTY_Z were wrong - which is
    #  exactly how the case came out 10.21 mm too tall before.
    blocked = [(round(x, 2), round(y, 2), z)
               for x, y in pin_centres() for z in (21.10, 21.50, 21.90)
               if witty.inside((x, y, (z)))]
    check("the WittyPi's socket lets all 40 pins through",
          not blocked,
          f"{len(pin_centres()) * 3} probes through the socket, "
          f"{len(blocked)} blocked" + (f" e.g. {blocked[0]}" if blocked else ""))
    ctl = [witty.inside((PI_GPIO_CX + (i - 9.5) * HDR_PITCH + 1.27,
                         PI_GPIO_CY, (21.50))) for i in range(20)]
    check("...and is solid between the holes, so the socket is aligned",
          sum(ctl) >= 16, f"{sum(ctl)}/20 between-pin probes are material")
    #  The LCD's socket is 2x13, NOT 2x20: it covers the header's first 13
    #  columns and the other 7 columns' 14 pins stand in the open pocket under
    #  the slab.  So this is not "every pin ends inside the socket" - that is
    #  false by design and reads as 14 failures if you word it that way.  It is:
    #  every pin the socket DOES cover ends inside it, every covered pin is
    #  inside the socket's own x range (i.e. nothing else of the LCD is sitting
    #  on pins), and the 14 pins that are not covered have clear air from the
    #  WittyPi's top face up to the slab.
    pins = pin_centres()
    tip_z = (HDR_TIP_Z + 0.50)
    covered = [(x, y) for x, y in pins if lcd.inside((x, y, tip_z))]
    stray = [p for p in covered if not (LCD_SOCK_X0 <= p[0] <= LCD_SOCK_X1)]
    check("the LCD's 2x13 socket swallows the 13 columns of pins under it",
          len(covered) == 26 and not stray,
          f"{len(covered)}/40 pin centres have LCD material at stack "
          f"{HDR_TIP_Z + 0.50:.2f}, {len(stray)} of them outside the socket x "
          f"{LCD_SOCK_X0}..{LCD_SOCK_X1}")
    #  The 14 uncovered pins, up the whole 12.80 of pocket.  This is the span
    #  that would bend them if the slab came down on them.
    open_pins = [p for p in pins if p not in covered]
    hits = [p for p in open_pins
            for z in ((WITTY_Z + WP_H + 0.50 + 0.50 * i) for i in range(23))
            if lcd.inside((p[0], p[1], z))]
    check("...and the other 7 columns stand in clear pocket, tips under the slab",
          not hits and HDR_TIP_Z < LCD_UNDER - 1.00,
          f"{len(open_pins)} pins outside the socket, probed "
          f"{len(open_pins) * 23} points up the pocket, {len(hits)} inside the "
          f"LCD; tips {HDR_TIP_Z:.2f}, slab underside {LCD_UNDER:.2f}")
    check("...and is empty below the WittyPi's top face",
          not lcd.inside((PI_GPIO_CX, PI_GPIO_CY, (WITTY_Z - 0.50))),
          f"probed stack {WITTY_Z - 0.50:.2f}")

    # ---- the two wall reliefs -------------------------------------------
    #  Both are 1.00 of a 5.00 wall, in a patch nothing else is in.  What has
    #  to hold is: the relieved face is now empty, the wall beyond it is still
    #  wall, and neither cut has reached a screw bore.
    print("\nthe wall reliefs (the two places a part's outline is in a wall)")
    ry = WALL + ID - 0.50                      # inside the +Y relief
    check("the +Y relief is cut and the wall behind it is not",
          not mid.inside((20.00, ry, (HDR_BODY_TOP - 1.00)))
          and mid.inside((20.00, WALL + ID + 1.50, (HDR_BODY_TOP - 1.00))),
          f"probed y {ry:.2f} and {WALL + ID + 1.50:.2f} at stack z "
          f"{HDR_BODY_TOP - 1.00:.2f}")
    check("the +Y relief covers the WHOLE 40-pin column, not just the body",
          HDR_RELIEF_Z0 <= HDR_BODY_UNDER and HDR_RELIEF_Z1 >= HDR_TIP_Z
          and PI_GPIO_CY + HDR_BODY_D / 2 <= WALL + ID + HDR_RELIEF_D,
          f"body to y {PI_GPIO_CY + HDR_BODY_D / 2:.2f}, wall face "
          f"{WALL + ID:.2f}, relief takes it to "
          f"{WALL + ID + HDR_RELIEF_D:.2f}; z to {HDR_RELIEF_Z1:.2f} "
          f"past the {HDR_TIP_Z:.2f} pin tips")
    check("the MID can be slid down over the +Y relief (it starts below the joint)",
          HDR_RELIEF_Z0 < JOINT_A,
          f"relief from stack z {HDR_RELIEF_Z0:.2f}, MID's own bottom "
          f"{JOINT_A:.2f}")
    check("the +Y relief stops clear of the M3 bore at x 9.00",
          HDR_RELIEF_X0 - (9.00 + SCREW_CLR / 2) >= 1.00,
          f"relief starts at x {HDR_RELIEF_X0:.2f}, bore edge "
          f"{9.00 + SCREW_CLR / 2:.2f}")
    #  The whole 40-pin envelope, body and pins, is sampled as a volume and no
    #  probe may be MID.  This is the assertion the request asks for: the
    #  support structure does not enter the GPIO anywhere over its full
    #  vertical run.
    gx0, gx1 = PI_GPIO_CX - HDR_BODY_W / 2, PI_GPIO_CX + HDR_BODY_W / 2
    gy0, gy1 = PI_GPIO_CY - HDR_BODY_D / 2, PI_GPIO_CY + HDR_BODY_D / 2
    gpio = [(x, y, z)
            for x in [gx0 + 0.10 + i * (gx1 - gx0 - 0.20) / 8 for i in range(9)]
            for y in [gy0 + 0.10, PI_GPIO_CY,
                      gy1 - 0.10]
            for z in [HDR_BODY_UNDER + 0.10, HDR_BODY_TOP - 0.10,
                      (HDR_BODY_TOP + HDR_TIP_Z) / 2, HDR_TIP_Z - 0.10]]
    in_gpio = [p for p in gpio if mid.inside(p)]
    check("no MID material anywhere in the full 40-pin GPIO envelope",
          not in_gpio,
          f"{len(gpio)} probes over x {gx0:.2f}..{gx1:.2f}, "
          f"y {gy0:.2f}..{gy1:.2f}, z {HDR_BODY_UNDER:.2f}..{HDR_TIP_Z:.2f}"
          + (f"; first hit {in_gpio[0]}" if in_gpio else ""))
    fy0 = LCD_PADS[3][0]
    check("the +Y LCD support flange is outboard of the 40-pin span",
          fy0 >= gx1 + ASSEMBLY_TOL,
          f"flange starts x {fy0:.2f}, header ends {gx1:.2f}, "
          f"{fy0 - gx1:.2f} clear")
    #  The -X wall.  At the 4.50 wall the WittyPi's BOARD edge is at case
    #  x 5.09, so it no longer enters the wall at all; what still enters is
    #  the button boss at x 4.00..5.10.  `wit_v` is the EXPORTED mesh, which
    #  is already in case coordinates, so the board edge is the smallest x
    #  outside the measured button box - not a model-coordinate cutoff that
    #  would need mapping a second time.
    def in_button(v):
        return (WITTY_BTN[0] - 0.05 <= v[0] <= WITTY_BTN[1] + 0.05
                and WITTY_BTN[2] - 0.05 <= v[1] <= WITTY_BTN[3] + 0.05
                and WITTY_BTN[4] - 0.05 <= v[2] <= WITTY_BTN[5] + 0.05)

    wit_v = vertices(stl_wit)
    board_x_case = min(v[0] for v in wit_v if not in_button(v))
    check("the WittyPi's board edge clears the 4.50 wall by the assembly tolerance",
          board_x_case - WALL >= ASSEMBLY_TOL,
          f"board edge x {board_x_case:.2f}, wall face {WALL:.2f}, "
          f"{board_x_case - WALL:.2f} clear")
    check("...so the wall is solid where the board runs but the button does not",
          mid.inside((WALL - 0.25, 38.00, 22.80))
          and mid.inside((WALL - 0.25, 52.00, 22.80)),
          "probed x 4.25 at y 38 and y 52, both outside the button slot")
    #  The button slot.  Its whole cut has to be empty through the wall, open
    #  at the MID's bottom edge, and leave wall above and either side.
    bx0, bx1, by0, by1, bz0, bz1 = WITTY_BTN
    slot_pts = [(x, y, z) for x in (0.50, 2.25, 4.25)
                for y in (44.80, 46.10, 47.40)
                for z in (JOINT_A + MATE_GAP + 0.20, 22.80)]
    check("the WittyPi button slot is open through the wall and into the cavity",
          not [p for p in slot_pts if mid.inside(p)],
          f"{len(slot_pts)} probes at x 0.50..4.25")
    check("the slot encloses the measured button with >= 0.25 all round",
          WITTY_BTN_X0 + ASSEMBLY_TOL <= bx0
          and bx1 <= WITTY_BTN_X1 - ASSEMBLY_TOL
          and WITTY_BTN_Y0 + ASSEMBLY_TOL <= by0
          and by1 <= WITTY_BTN_Y1 - ASSEMBLY_TOL
          and WITTY_BTN_Z0 + ASSEMBLY_TOL <= bz0
          and bz1 <= WITTY_BTN_Z1 - ASSEMBLY_TOL,
          f"button x {bx0:.2f}..{bx1:.2f} y {by0:.2f}..{by1:.2f} "
          f"z {bz0:.2f}..{bz1:.2f} in slot x {WITTY_BTN_X0:.2f}.."
          f"{WITTY_BTN_X1:.2f} y {WITTY_BTN_Y0:.2f}..{WITTY_BTN_Y1:.2f} "
          f"z {WITTY_BTN_Z0:.2f}..{WITTY_BTN_Z1:.2f}")
    check("...the slot opens to the MID's bottom edge, so the shell drops over it",
          WITTY_BTN_Z0 < JOINT_A + MATE_GAP,
          f"slot starts at z {WITTY_BTN_Z0:.2f}, MID bottom "
          f"{JOINT_A + MATE_GAP:.2f}")
    check("...and the wall survives above the slot",
          mid.inside((2.25, 46.10, WITTY_BTN_Z1 + 0.60)),
          f"probed x 2.25 y 46.10 z {WITTY_BTN_Z1 + 0.60:.2f}")

    # ---- the +X port band ------------------------------------------------
    #  The Ethernet and USB openings were cut separately, which left a
    #  1.57 mm free-standing web between them.  It is removed now, so the
    #  pair is one stepped opening.  Probe the old web band right across the
    #  wall: no MID material may remain anywhere in it, and the wall must
    #  still close the merged opening fore and aft.
    print("\nthe +X port band (Ethernet and USB share one opening)")
    web_pts = [(OW - 0.30, y, z)
               for y in (ETH_Y1 + 0.30, (ETH_Y1 + USB_Y0) / 2, USB_Y0 - 0.30)
               for z in (JOINT_A + MATE_GAP + 0.50, 12.00, 20.00,
                         USB_Z1 - 0.30)]
    check("the web between the Ethernet and USB openings is gone",
          not [p for p in web_pts if mid.inside(p)],
          f"{len(web_pts)} probes in y {ETH_Y1:.2f}..{USB_Y0:.2f}, "
          f"z {JOINT_A + MATE_GAP + 0.50:.2f}..{USB_Z1 - 0.30:.2f}")
    check("...and the wall still closes the merged opening fore and aft",
          mid.inside((OW - 0.30, ETH_Y0 - 0.50, 12.00))
          and mid.inside((OW - 0.30, USB_Y1 + 0.50, 12.00)),
          f"solid at y {ETH_Y0 - 0.50:.2f} and {USB_Y1 + 0.50:.2f}")

    # ---- the LCD's seat --------------------------------------------------
    #  The defect this whole rework exists to fix: the socket hangs 12.80 below
    #  the slab and the +Y ledge's inner edge is at y 58.70, so 1.13 of socket
    #  was inside the ledge and the LCD jammed 12.8 mm high on its own socket.
    print("\nthe LCD's seat (socket, ledge, flanges)")
    n = probe_intersection(tmp, "mid()", 0.0, "lcd()", EPS, "midlcd")
    check("the LCD seats in the MID - no interference", n == 0,
          "this one FAILED before the ledge was notched")
    n = probe_intersection(tmp, "lcd()", 0.0, "bezel()", EPS, "lcdbez")
    check("the LCD's slab sits in the BEZEL's pocket - no interference", n == 0,
          "the pocket's corner radius was 2.00 and the PCB is a rectangle: "
          "0.195 of jam at each of the four corners")
    #  The mesh is the old 85.00 x 55.50 x 5.50 part, so the interference above
    #  cannot prove the MEASURED panel fits.  These do it as boxes, from the
    #  same formulas the .scad uses: the pocket is the panel plus LCD_FIT, and
    #  the window is the panel less the retaining lip LCD_LIP.
    LCD_X, LCD_Y = (OW - LCD_W) / 2, (OD - LCD_D) / 2
    pock_w = max(IW, LCD_W + 2 * LCD_FIT)
    pock_d = max(ID, LCD_D + 2 * LCD_FIT)
    pock_x, pock_y = (OW - pock_w) / 2, (OD - pock_d) / 2
    win_w, win_d = LCD_W - 2 * LCD_LIP, LCD_D - 2 * LCD_LIP
    win_x = LCD_X + LCD_LIP
    win_y = LCD_Y + LCD_LIP
    check("the measured 85.80 x 55.60 panel drops in with its tolerance",
          pock_x <= LCD_X - LCD_FIT + 1e-9
          and pock_x + pock_w >= LCD_X + LCD_W + LCD_FIT - 1e-9
          and pock_y <= LCD_Y - LCD_FIT + 1e-9
          and pock_y + pock_d >= LCD_Y + LCD_D + LCD_FIT - 1e-9
          and win_x > pock_x and win_x + win_w < pock_x + pock_w
          and win_y > pock_y and win_y + win_d < pock_y + pock_d,
          f"pocket {pock_w:.2f} x {pock_d:.2f} at x {pock_x:.2f} y {pock_y:.2f} "
          f"around the panel at x {LCD_X:.2f} y {LCD_Y:.2f}; the bezel rim "
          f"overlaps it by {min(LCD_X - win_x, LCD_Y - win_y):.2f}")
    check("the window shows the whole 74.00 x 49.00 visible area + tolerance",
          win_w >= LCD_ACT_W + 2 * WIN_CLR - 1e-9
          and win_d >= LCD_ACT_D + 2 * WIN_CLR - 1e-9
          and win_x >= LCD_X and win_x + win_w <= LCD_X + LCD_W
          and win_y >= LCD_Y and win_y + win_d <= LCD_Y + LCD_D,
          f"window {win_w:.2f} x {win_d:.2f} at x {win_x:.2f} y {win_y:.2f}, "
          f"active {LCD_ACT_W:.2f} x {LCD_ACT_D:.2f}")
    #  The window is wider now, so it has to stay clear of the six top-face
    #  counterbores - their rims are all the material the bezel screws bear on.
    rim = SCREW_CSK_D / 2 + 0.50
    hit = [(sx, sy) for sx, sy in SCREWS
           if win_x - rim < sx < win_x + win_w + rim
           and win_y - rim < sy < win_y + win_d + rim]
    check("the enlarged window clears the six counterbores", not hit,
          f"window {win_w:.2f} x {win_d:.2f} at x {win_x:.2f} y {win_y:.2f}, "
          f"{len(SCREWS)} columns, {len(hit)} too close")
    notch_z = ((SPLIT_B - SHELF_T + 0.50), (SPLIT_B - 0.30))
    open_pts = [(x, y, z) for x in (12.10, 30.00, 46.30)
                for y in (NOTCH_Y0 + 0.20, NOTCH_Y1 - 0.20) for z in notch_z]
    blocked = [p for p in open_pts if mid.inside(p)]
    check("the notch the socket drops through is open", not blocked,
          f"{len(open_pts)} probes through the ledge, {len(blocked)} blocked"
          + (f" e.g. {blocked[0]}" if blocked else ""))
    ledge = [(NOTCH_X0 - 0.50, 60.00, (SPLIT_B - 0.60)),
             (NOTCH_X1 + 0.50, 60.00, (SPLIT_B - 0.60))]
    check("the ledge survives either side of the notch",
          not [p for p in ledge if not mid.inside(p)], f"{len(ledge)} probes")
    check("the +Y wall behind the notch is untouched",
          mid.inside((30.00, OD - WALL, (SPLIT_B - 0.60))),
          "the cut stops on the wall's inner face, not through it")
    #  The socket box itself, measured off the LCD mesh, has to be clear of the
    #  finished MID everywhere it hangs - not just at the probe heights above.
    sock = surf_points(LCD_SOCK_X0, LCD_SOCK_X1, LCD_SOCK_Y0, LCD_SOCK_Y1,
                       (SPLIT_B - LCD_DROP + 0.20), (SPLIT_B - 0.20), 2.00)
    bad = [p for p in sock if mid.inside(p)]
    check("the socket's whole 12.80 descent is clear of the MID",
          not bad, f"{len(sock)} probes" + (f" e.g. {bad[0]}" if bad else ""))

    #  The four flanges.  Two things about each: it bears on BARE PCB (nothing
    #  hangs below the slab over its footprint) and enough of it is actually
    #  under the panel.  Both are measured off the imported mesh rather than
    #  from remembered boxes.
    lcd_v = vertices(stl_lcd)
    slab_under = LCD_UNDER
    #  The PCB layer's own two faces: the slab's underside at slab_under, and
    #  the board's top face 1.50 above it.  BOTH, because the outline's extreme
    #  vertices lie ON those faces - a band strictly inside them selects nothing
    #  and this read as a min() over an empty sequence.  It is also the reason
    #  the empty case is a FAIL here rather than a traceback: a selection that
    #  finds nothing is a mesh or a frame that moved, not a geometry error.
    pcb = [v for v in lcd_v if slab_under - 0.05 < v[2] < slab_under + 1.60]
    if pcb:
        px0 = min(v[0] for v in pcb)
        px1 = max(v[0] for v in pcb)
        py0 = min(v[1] for v in pcb)
        py1 = max(v[1] for v in pcb)
    else:
        px0 = px1 = py0 = py1 = 0.0        # the FAIL on the next line says why
    check("the LCD's PCB layer is in the mesh, so the flanges have a target",
          bool(pcb), f"{len(pcb)} vertices in the slab's 1.60 layer")
    note("the LCD's PCB layer, off its mesh",
         f"x {px0:.2f}..{px1:.2f} y {py0:.2f}..{py1:.2f} "
         f"({px1-px0:.2f} x {py1-py0:.2f})")
    hangs = [v for v in lcd_v if v[2] < slab_under - 0.10]
    note("what the LCD hangs below its slab",
         f"{len(hangs)} vertices, socket x {LCD_SOCK_X0}..{LCD_SOCK_X1} "
         f"y {LCD_SOCK_Y0}..{LCD_SOCK_Y1} down {LCD_DROP:.2f}, "
         f"plus shallow bumps of 1.20 and 2.80")

    fouled, thin = [], []
    for p in LCD_PADS:
        rect = (p[0], p[2], p[1], p[3])
        deep = [v for v in hangs
                if rect[0] <= v[0] <= rect[1] and rect[2] <= v[1] <= rect[3]]
        if deep:
            fouled.append((rect, round(max(slab_under - v[2] for v in deep), 2)))
        pts = surf_points(p[0], p[2], p[1], p[3],
                          (SPLIT_B - SHELF_T + 0.10), (SPLIT_B - 0.10), 2.00)
        #  The band's topmost samples, taken as the max rather than as a
        #  literal z: surf_points insets EVERY face by 0.4, so these sit at
        #  z1 - 0.4 and a test against z1 selects nothing at all.
        ztop = max(q[2] for q in pts)
        top = [q for q in pts if abs(q[2] - ztop) < 1e-9]
        covered = sum(1 for q in top
                      if px0 <= q[0] <= px1 and py0 <= q[1] <= py1)
        frac = covered / len(top)
        if frac < 0.60:
            thin.append((rect, frac))
    check("all four flanges bear on bare PCB (nothing hangs over them)",
          not fouled, f"{len(LCD_PADS)} flanges"
          + (f", fouled: {fouled}" if fouled else ""))
    check("all four flanges are at least 60% under the panel",
          not thin, f"{len(LCD_PADS)} flanges"
          + (f", thin: {thin}" if thin else ""))
    #  ...and they are 2.00 thick with their tops coplanar with the ledge.
    fpad = LCD_PADS[0]
    check("each flange is SHELF_T thick, its top at SPLIT_B",
          mid.inside((fpad[0] + 0.60, 36.00, (SPLIT_B - 0.30)))
          and mid.inside((fpad[0] + 0.60, 36.00, (SPLIT_B - 1.70)))
          and not mid.inside((fpad[0] + 0.60, 36.00, (SPLIT_B - 2.30))),
          f"probed SPLIT_B - 0.30 / -1.70 / -2.30 at x {fpad[0] + 0.60:.2f}")
    #  The flanges are ADDED after the cavity cuts, so they are the one place
    #  where a subtraction could have eaten them.  Probed away from the wall.
    tips = [(p[0] + 0.60 if p[0] < OW / 2 else p[2] - 0.60, 36.00,
             (SPLIT_B - 1.00)) for p in LCD_PADS[:2]]
    check("the flanges stand inside the cavity, not just at the wall",
          not [p for p in tips if not mid.inside(p)], f"{len(tips)} probes")

    # ---- the BASE's plate interface --------------------------------------
    #  This section used to be "the mount": a whole printed tub, and the four
    #  M2 x 25 that held it under the BASE.  Both have gone.  The tub's walls
    #  were its own vents and grommet and its own screw pylons, and none of
    #  that is needed now the belt plate bolts straight to the BASE's floor.
    #  What is left to check is the interface on that floor.
    print("\nthe BASE (an open tray, and the plate's seat on its floor)")
    check("the BASE is an open tray at IW x ID x JOINT_A - FLOOR",
          not base.inside((OW / 2, OD / 2, (FLOOR + JOINT_A) / 2))
          and base.inside((WALL / 2, OD / 2, (FLOOR + JOINT_A) / 2)),
          f"cavity {IW:.2f} x {ID:.2f} x {JOINT_A - FLOOR:.2f}")

    #  The six bores in the rim - one per column, and they are CLEARANCE
    #  bores, o3.40 right through, because the BASE holds no thread any more:
    #  the MID is the nut, so a screw passes through this wall and bites in the
    #  one above it.  So this is the opposite of what used to be asserted here.
    #  The hole is open at both ends, solid wall stands all round it, and there
    #  is no counterbore at the bottom face - an M3 button head is wider than
    #  this wall, so the head has to stand proud of the case's underside.
    ok, det = True, []
    for sx, sy in SCREWS:
        for z in (0.50, JOINT_A / 2, JOINT_A - 0.50):
            if base.inside((sx, sy, z)):
                ok, det = False, f"bore blocked at x{sx} y{sy} z{z:.2f}"
        r = SCREW_CLR / 2 + 0.30
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if not base.inside((sx + dx * r, sy + dy * r, JOINT_A / 2)):
                ok, det = False, f"wall eaten beside the bore at x{sx} y{sy}"
        if base.inside((sx, sy, JOINT_A + 0.50)):
            ok, det = False, f"the BASE runs on past the joint at x{sx}"
    check("the 6 BASE bores are open through the rim, wall all round", ok, det)

    #  The four plate-bolt bosses.  They stand on the INSIDE of the floor, so
    #  the case's underside stays one flat face for the plate to lie on.
    check("the bosses stop at the rim, not past it",
          abs((FLOOR + PLATE_BOSS_H) - JOINT_A) < 1e-9,
          f"top at {FLOOR + PLATE_BOSS_H:.2f}, rim at {JOINT_A:.2f} - so the "
          f"Pi drops in over them")
    #  ...and the pilot through each one.  This is the ONLY hole in the build
    #  that is threaded in the BASE, and it is BLIND: a o2.50 pilot from the
    #  case's underside all the way up through the floor and into the boss,
    #  stopping PLATE_PILOT_DEEP with a cap over it.  It is the pilot's
    #  diameter the whole way, too - a clearance bore through the floor would
    #  leave the screw only the boss's 2.70 to bite in.
    ok, det = True, []
    for bx_, by_ in PLATE_BOLTS:
        if base.inside((bx_, by_, FLOOR / 2)):
            ok, det = False, f"floor not bored at {bx_:.2f},{by_:.2f}"
        if base.inside((bx_, by_, PLATE_PILOT_DEEP - 0.60)):
            ok, det = False, f"pilot blocked up in the boss at {bx_:.2f}"
        if not base.inside((bx_, by_, PLATE_PILOT_DEEP + 0.10)):
            ok, det = False, f"no cap over the pilot at {bx_:.2f}"
        if not base.inside((bx_ + PLATE_BOSS_D / 2 - 0.40, by_,
                            FLOOR + PLATE_BOSS_H - 0.50)):
            ok, det = False, f"no boss beside {bx_:.2f}"
        if not base.inside((bx_ + PLATE_PILOT_D / 2 + 0.30, by_,
                            PLATE_PILOT_DEEP - 0.60)):
            ok, det = False, f"the pilot is wider than o{PLATE_PILOT_D} at {bx_:.2f}"
    check(f"4 plate bosses: a blind o{PLATE_PILOT_D:.2f} pilot {PLATE_PILOT_DEEP:.2f} "
          f"deep, capped, in the boss's plastic", ok, det)

    #  ...and the check no bounding box can do.  The bosses share airspace with
    #  the Pi, which hangs the Ethernet shell and the microSD socket off the
    #  underside of its PCB - 5.93 and 6.01 above the BASE's underside, which
    #  is why JOINT_A is 5.50.  So a boss is free to rise to the rim and no
    #  further, and this is what says so.  RAY-CAST, because the imported Pi
    #  mesh is open and intersecting it reads 0 whatever you do.
    clear, det, worst = True, [], None
    for k, (bx_, by_) in enumerate(PLATE_BOLTS):
        for i in range(-4, 5):
            for j in range(-4, 5):
                u, v = i * 0.80, j * 0.80
                if math.hypot(u, v) > PLATE_BOSS_D / 2 - 0.40:
                    continue
                fa = rpi.first_above(bx_ + u, by_ + v, FLOOR + PLATE_BOSS_H)
                if fa is None:
                    continue
                gap = fa - (FLOOR + PLATE_BOSS_H)
                if worst is None or gap < worst[0]:
                    worst = (gap, bx_ + u, by_ + v, fa)
                if gap < 0.40:
                    clear = False
                    det.append(f"boss {k} at {bx_+u:.2f},{by_+v:.2f}: "
                               f"{fa:.2f}, only {gap:.2f} above the top")
    check("every boss clears the Pi's lowest underside features by >= 0.40",
          clear,
          (f"closest {worst[0]:.2f} at {worst[1]:.2f},{worst[2]:.2f} "
           f"(first Pi surface at {worst[3]:.2f}); the +X pair is the one "
           f"under the Ethernet shell, with the rim's 0.43 clearance"
           if worst else "no Pi geometry over a boss")
          + (f"; tight: {det}" if det else ""))

    # ---- the plate -------------------------------------------------------
    #  A separate part, bolted to the BASE's flat underside, threading into the
    #  four bosses with M3 x 6 - no inserts, and the SHORTEST bite in the case.
    #  Everything here is about it coming off again.
    print("\nthe belt plate")
    shells, bad = mesh_health(stl["plate"])
    check("plate is one closed shell", shells == 1 and bad == 0,
          f"{shells} shell(s), {bad} edges not shared by two")
    bx, by, bz = bbox(stl["plate"])
    check("plate is PLATE_W x PLATE_D x PLATE_T, on the case's centre",
          abs(bx[1] - bx[0] - PLATE_W) < 1e-6
          and abs(by[1] - by[0] - PLATE_D) < 1e-6
          and abs(bz[1] - PLATE_Z1) < 1e-6,
          f"{bx[1]-bx[0]:.2f} x {by[1]-by[0]:.2f} x "
          f"{bz[1]-PLATE_Z1 + PLATE_T:.2f}, body z {PLATE_Z0:.2f}..{PLATE_Z1:.2f}")
    check("plate outline sits inside the case's OW x OD",
          PLATE_X0 > 0 and PLATE_X1 < OW and PLATE_Y0 > 0 and PLATE_Y1 < OD,
          f"x {PLATE_X0:.2f}..{PLATE_X1:.2f}, y {PLATE_Y0:.2f}..{PLATE_Y1:.2f}")
    n = probe_intersection(tmp, "plate()", 0.0, "base()", 0.0, "platebase")
    check("plate n base, as placed", n == 0,
          f"{n} facets - the plate lies PLATE_GAP below the case, not on it")
    #  The plate prints flipped, case face down.  This is that copy: it has to
    #  start on the bed, or it is not printable as drawn.
    pbx, pby, pbz = bbox(stl_bed)
    check("plate_placed() lies on the bed, hooks up",
          abs(pbz[0]) < 1e-6
          and abs(pbz[1] - (PLATE_T + PLATE_HOOK_PROJ)) < 1e-6,
          f"z {pbz[0]:.2f}..{pbz[1]:.2f}")
    #  The four bolts: hole open, counterbore in the OUTER face, material
    #  beside both.
    ok, det = True, []
    for bx_, by_ in PLATE_BOLTS:
        if plate.inside((bx_, by_, (PLATE_Z0 + PLATE_Z1) / 2)):
            ok, det = False, f"bolt hole closed at {bx_:.2f},{by_:.2f}"
        if plate.inside((bx_, by_, PLATE_Z0 + PLATE_CBORE_H / 2)):
            ok, det = False, f"no counterbore at {bx_:.2f},{by_:.2f}"
        if not plate.inside((bx_ + PLATE_CBORE_D / 2 + 0.40, by_ + 1.00,
                             PLATE_Z0 + PLATE_CBORE_H / 2)):
            ok, det = False, f"no material beside the head at {bx_:.2f}"
        #  ...and the same axis in the BASE, checked at length in the section
        #  above; repeated here because THIS is the claim that matters - that
        #  the four bolts really do land in the BASE's own plastic and not in
        #  some part that is not there.
        if base.inside((bx_, by_, FLOOR / 2)):
            ok, det = False, f"BASE floor not bored at {bx_:.2f}"
        if not base.inside((bx_ + PLATE_BOSS_D / 2 - 0.40, by_,
                            FLOOR + PLATE_BOSS_H - 0.50)):
            ok, det = False, f"no boss beside {bx_:.2f}"
        if not base.inside((bx_, by_, PLATE_PILOT_DEEP + 0.10)):
            ok, det = False, f"no cap over the pilot at {bx_:.2f}"
    check("4 plate bolts: hole and counterbore in the plate, blind pilot in "
          "the BASE's boss", ok, det)
    #  The screw's length, against the pilot it has to land in.  The pilot is
    #  cut UP from the case's underside - z 0.00 .. PLATE_PILOT_DEEP - so the
    #  screw has to be long enough to reach past the plate and the 0.50 gap
    #  and still bite, and short enough not to bottom on the cap at the top.
    pk_lo, pk_hi = 0.00, PLATE_PILOT_DEEP
    tip = PLATE_Z0 + PLATE_CBORE_H + PLATE_SCREW_L
    check(f"the {PLATE_SCREW_L:.0f} mm plate screws land in the plastic",
          pk_lo < tip < pk_hi and tip - pk_lo > 2.00,
          f"head seats at z {PLATE_Z0 + PLATE_CBORE_H:.2f} in the plate, tip "
          f"at z {tip:.2f}; pilot {pk_lo:.2f}..{pk_hi:.2f} - "
          f"{tip - pk_lo:.2f} of thread and {pk_hi - tip:.2f} short of the "
          f"pilot's floor")
    #  The hooks: the web takes the belt's lower edge, the lip keeps the case
    #  on it.  Probed on one hook, and in the channel on the belt's side.
    hx_ = PLATE_CX - PLATE_MOD / 2
    check("the hook's web and lip are where the belt needs them",
          plate.inside((hx_, PLATE_HOOK_Y - PLATE_HOOK_T / 2, -8.00))
          and plate.inside((hx_, PLATE_HOOK_Y + PLATE_HOOK_LIP / 2, -11.50))
          and not plate.inside((hx_, PLATE_HOOK_Y + PLATE_HOOK_LIP / 2, -7.00))
          and not plate.inside((hx_, PLATE_HOOK_Y - PLATE_HOOK_T - 1.00,
                                -8.00)),
          f"web at y {PLATE_HOOK_Y - PLATE_HOOK_T:.2f}..{PLATE_HOOK_Y:.2f}, "
          f"lip to y {PLATE_HOOK_Y + PLATE_HOOK_LIP:.2f}, channel "
          f"{PLATE_HOOK_PROJ - PLATE_HOOK_T:.2f} deep")
    check("the two hooks are clear of each other on the 25.4 module",
          not plate.inside((PLATE_CX, PLATE_HOOK_Y - PLATE_HOOK_T / 2, -8.00)),
          f"probed the middle at x {PLATE_CX:.2f}")
    check("no case bore mouth is hidden behind the plate",
          all(sx < PLATE_X0 or sx > PLATE_X1 or sy < PLATE_Y0 or sy > PLATE_Y1
              for sx, sy in SCREWS),
          f"plate x {PLATE_X0:.2f}..{PLATE_X1:.2f} y {PLATE_Y0:.2f}.."
          f"{PLATE_Y1:.2f}, bores at "
          f"{sorted({(round(s[0], 2), round(s[1], 2)) for s in SCREWS})}")
    #  ...and the twelve heads have to clear it too, not just the bores.  An M3
    #  button head is o5.70, so its rim is 2.85 from each column's centre, and
    #  the plate's footprint has rounded corners - so the four CORNER columns
    #  are the tight ones and they are what this measures.  (The plate has to
    #  come off before a bit driver will reach those four; a hex key will.)
    def plate_gap(px, py):
        """Distance from a point to the plate's rounded-rectangle footprint."""
        r = PLATE_R
        cx = min(max(px, PLATE_X0 + r), PLATE_X1 - r)
        cy = min(max(py, PLATE_Y0 + r), PLATE_Y1 - r)
        if (px, py) == (cx, cy):
            return -min(px - PLATE_X0, PLATE_X1 - px,
                        py - PLATE_Y0, PLATE_Y1 - py)
        return math.hypot(px - cx, py - cy) - r
    gaps = [(plate_gap(sx, sy) - 5.70 / 2, sx, sy) for sx, sy in SCREWS]
    worst = min(gaps)
    check("all twelve case heads clear the plate by >= 0.50",
          worst[0] >= 0.50,
          f"tightest {worst[0]:.2f} at the corner column "
          f"{worst[1]:.2f},{worst[2]:.2f}; the long-wall ones clear by "
          f"{max(gaps)[0]:.2f}")
    #  ...and the reason all of this works: the BASE's underside is FLAT
    #  everywhere the plate bears on it, from the plate's own edge in.  A
    #  screw head 0.5 proud, or a stray seam, would show up here and nowhere
    #  else.  This is the check that moved with the interface when the MOUNT
    #  went - it used to run over the MOUNT's underside.
    grid, worst = [], None
    x = PLATE_X0 + 0.50
    while x < PLATE_X1:
        y = PLATE_Y0 + 0.50
        while y < PLATE_Y1:
            z = base.first_above(x, y, -2.00)
            if z is not None and (worst is None or z < worst[0]):
                worst = (z, x, y)
            grid.append((x, y))
            y += 5.00
        x += 5.00
    check("the BASE's underside is flat under the whole plate",
          worst is not None and worst[0] >= -1e-6,
          f"{len(grid)} probes, lowest surface "
          f"{worst[0]:.2f} at {worst[1]:.2f},{worst[2]:.2f}")

    # ---- joints ---------------------------------------------------------
    #  The parts are modelled MATE_GAP apart at each butt joint, so here the
    #  check is the one that matters as printed: place them exactly where the
    #  SCAD puts them and demand no overlap at all.  No EPS lift - there is no
    #  shared face left to filter out.
    print("\njoints (a real clearance at each butt joint)")
    n = probe_intersection(tmp, "base()", 0.0, "mid()", 0.0, "basemid")
    check("base n mid, as placed", n == 0, f"{n} facets")
    n = probe_intersection(tmp, "mid()", 0.0, "bezel()", 0.0, "midbezel")
    check("mid n bezel, as placed", n == 0, f"{n} facets")
    #  ...and prove the gap is really there in the exported solid, not just in
    #  the constants: empty at the seam, solid on both sides of it.  x 1.20 is
    #  past the 0.60 seam groove; y 20.00 is plain -X wall, clear of the SD
    #  port (y 29.58..42.08), the WittyPi button slot (y 44.30..47.90) and
    #  every screw patch.
    gap_y = 20.00
    lower_gap = [z for z in (JOINT_A + 0.05, JOINT_A + MATE_GAP - 0.05)
                 if base.inside((1.20, gap_y, z))
                 or mid.inside((1.20, gap_y, z))]
    check(f"the BASE/MID joint is open by {MATE_GAP:.2f}",
          MATE_GAP >= 0.20 and not lower_gap
          and base.inside((1.20, gap_y, JOINT_A - 0.10))
          and mid.inside((1.20, gap_y, JOINT_A + MATE_GAP + 0.10)),
          f"{MATE_GAP:.2f} clear between the BASE's rim at {JOINT_A:.2f} and "
          f"the MID's underside at {JOINT_A + MATE_GAP:.2f}")
    upper_gap = [z for z in (SPLIT_B + 0.05, SPLIT_B + MATE_GAP - 0.05)
                 if mid.inside((1.20, gap_y, z))
                 or bezel.inside((1.20, gap_y, z))]
    check(f"the MID/BEZEL joint is open by {MATE_GAP:.2f}",
          MATE_GAP >= 0.20 and not upper_gap
          and mid.inside((1.20, gap_y, SPLIT_B - 0.10))
          and bezel.inside((1.20, gap_y, SPLIT_B + MATE_GAP + 0.10)),
          f"{MATE_GAP:.2f} clear between the MID's top at {SPLIT_B:.2f} and "
          f"the BEZEL's underside at {SPLIT_B + MATE_GAP:.2f}")

    # ---- seams ----------------------------------------------------------
    #  THREE joints, not four: the plate is bolted on and stands PLATE_GAP
    #  clear, so it shares no face with anything.  The BASE's own bottom edge
    #  is the new thing to protect - it is the plate's seat.
    print("\nseams")
    check("the BASE's bottom edge is solid where the plate seats",
          base.inside((0.3, OD / 2, 0.40)) and base.inside((0.3, OD / 2, 1.40))
          and base.inside((OW - 0.3, OD / 2, 0.40)),
          "no seam groove in the face the plate lies on")
    check("...and the BASE/MID joint still has its groove",
          not mid.inside((0.30, 41.50, JOINT_A + MATE_GAP + 0.30))
          and mid.inside((0.30, 41.50, JOINT_A + MATE_GAP + 1.20))
          and not mid.inside((OW / 2, OD - 0.30, JOINT_A + MATE_GAP + 0.30))
          and mid.inside((OW / 2, OD - 0.30, JOINT_A + MATE_GAP + 1.20)),
          "groove open at the outer face on two opposite walls, solid 1.20 "
          "above it - note the -X probe is at y 41.50, between the microSD "
          "opening (to y 39.35) and the WittyPi button slot (from y 44.30)")

    # ---- the MID is the nut ---------------------------------------------
    #  Both groups of case screws thread into the MID, which is the whole point
    #  of the joint: the BASE's rim is only 5.50 tall - it stops under the Pi's
    #  Ethernet shell - so it cannot hold a deep pilot, and the MID's 34.90 of
    #  wall can.  Each of the six columns is therefore drilled TWICE, from
    #  opposite ends, and left blind both ways.
    print("\nthe MID is the nut (two blind pilots per column)")
    ok, det = True, []
    for sx, sy in SCREWS:
        for z in (PILOT_UP[0] + 0.50, PILOT_UP[1] - 0.50,
                  PILOT_LO[0] + 0.50, PILOT_LO[1] - 0.50):
            if mid.inside((sx, sy, z)):
                ok, det = False, f"pilot blocked at x{sx} y{sy} z{z:.2f}"
        #  solid wall between the two drills, and round each one - so neither
        #  is a slot that opens into the cavity or out through the outer face
        between = (PILOT_UP[0] + PILOT_LO[1]) / 2
        if not mid.inside((sx, sy, between)):
            ok, det = False, f"the two pilots meet at x{sx} y{sy}"
        for z in ((PILOT_UP[0] + PILOT_UP[1]) / 2, (PILOT_LO[0] + PILOT_LO[1]) / 2):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                r = SCREW_PILOT / 2 + 0.55
                if not mid.inside((sx + dx * r, sy + dy * r, z)):
                    ok, det = False, f"pilot breaks out at x{sx} y{sy} z{z:.2f}"
    check("6 columns: two blind pilots each, wall all round both", ok, det)
    #  Two 15 mm blind drills from opposite ends now leave 4.90 of solid wall
    #  in a 34.90 MID - still more than a diameter and a half of o2.75, and
    #  the 15.00 depth is what the user asked for, so it is the shorter MID
    #  that gives up the margin, not the drills.
    check(f"the solid wall between the two pilots is >= 4.50 mm",
          PILOT_UP[0] - PILOT_LO[1] >= 4.50,
          f"{PILOT_UP[0] - PILOT_LO[1]:.2f} between {PILOT_LO[1]:.2f} and "
          f"{PILOT_UP[0]:.2f} - two 15 mm drills in a {MID_H:.2f} MID")
    check("every receptacle is at least the 15 mm asked for",
          SCREW_DEEP >= 15.00,
          f"{SCREW_DEEP:.2f} of thread per screw per column - this is the "
          f"stock a stripped hole is re-driven into, since there is no insert "
          f"to replace")
    check(f"the pilot is the requested 0.20..0.30 over an M3's 2.50 core",
          0.20 <= SCREW_PILOT - 2.50 <= 0.30,
          f"o{SCREW_PILOT:.2f}, {SCREW_PILOT - 2.50:.2f} over 2.50")

    #  ...and the heads sit FLUSH.  An M3 button head is 1.65 tall, so each
    #  joint gets a o5.80 counterbore exactly that deep, with a 0.20 x o6.20
    #  countersink lapping the top edge.  Both faces are probed: the bore has
    #  to be open at the screw's axis, and material has to remain inboard of
    #  it - a counterbore that ate through into the cavity would show here.
    print("\nflush counterbores at both case faces")
    ok, det = True, []
    for sx, sy in SCREWS:
        vx, vy = OW / 2 - sx, OD / 2 - sy
        vn = math.hypot(vx, vy)
        ix, iy = sx + (SCREW_CBORE_D / 2 + 0.45) * vx / vn, \
                  sy + (SCREW_CBORE_D / 2 + 0.45) * vy / vn
        if bezel.inside((sx, sy, OH - SCREW_CBORE_H / 2)):
            ok, det = False, f"BEZEL counterbore blocked at x{sx} y{sy}"
        if base.inside((sx, sy, SCREW_CBORE_H / 2)):
            ok, det = False, f"BASE counterbore blocked at x{sx} y{sy}"
        if not bezel.inside((ix, iy, OH - SCREW_CBORE_H / 2)):
            ok, det = False, f"BEZEL counterbore breaks inward at x{sx} y{sy}"
        if not base.inside((ix, iy, SCREW_CBORE_H / 2)):
            ok, det = False, f"BASE counterbore breaks inward at x{sx} y{sy}"
    check("all twelve heads have a flush 1.65 counterbore at the face",
          ok, det)
    check("...with the requested countersink lapping each one",
          SCREW_CSK_D > SCREW_CBORE_D and 0.0 < SCREW_CSK_H <= 0.30,
          f"o{SCREW_CSK_D:.2f} x {SCREW_CSK_H:.2f} over the o"
          f"{SCREW_CBORE_D:.2f} counterbore")
    #  ...and the SEAM KEEP-OUT, which is the one thing an M3 bore forced.  A
    #  o3.40 clearance bore leaves its edge only 0.80 from the outer face, so a
    #  0.60 groove cut straight across it would leave a 0.20 ligament - and the
    #  screw's own expansion is what splits that.  So the cutter is interrupted
    #  over SEAM_PATCH at every column: at the column the wall is FULL
    #  thickness at the groove's own height, and 4.20 along from it the groove
    #  is there as usual.  All six sit on straight runs, so a plain cube does
    #  it.  The directions below stay clear of the port openings.
    print("\nthe seam keep-out (the groove stops at every screw)")
    probes = []
    for sx, sy in SCREWS:
        if sx < WALL:
            probes.append(((0.30, sy + 2.00), (0.30, sy + 4.20)))
        elif sy < WALL:
            probes.append(((sx - 2.00, 0.30), (sx - 4.20, 0.30)))
        else:
            probes.append(((sx + 2.00, OD - 0.30), (sx + 4.20, OD - 0.30)))
    ok, det = True, []
    for at, beside in probes:
        for z, tag in ((JOINT_A + MATE_GAP + 0.20, "BASE"),
                       (SPLIT_B - 0.20, "BEZEL")):
            if not mid.inside((at[0], at[1], z)):
                ok, det = False, f"{tag}: keep-out missing at {at} z{z:.2f}"
            if mid.inside((beside[0], beside[1], z)):
                ok, det = False, f"{tag}: no groove cut at {beside} z{z:.2f}"
    check("the seam keep-out holds the full wall at all six columns", ok, det)
    bore_edge = WALL / 2 - SCREW_CLR / 2        # = 0.55 from the outer face
    check("...so the 0.55 ligament at every bore is never grooved",
          bore_edge > 0 and SEAM_CLEAR > bore_edge,
          f"the bore's centre is on the wall centreline, so its edge is "
          f"{bore_edge:.2f} in from the face - a straight {SEAM_D:.2f} groove "
          f"would cut through it. The keep-out reaches {SEAM_CLEAR:.2f} in, "
          f"{SEAM_CLEAR - bore_edge:.2f} past the bore, so the groove stops "
          f"short at all six columns")

    # ---- rear-wall airflow and the battery lead --------------------------
    #  The +Y wall used to carry a charging-cable slot, a round lead grommet
    #  and two tie holes.  At the user's request those are gone: the wall is
    #  now a hexagonal vent field, with one 10 x 6 rectangle at its left for
    #  the pack's lead.  Every cut starts 1.00 inside the wall's inner face and
    #  runs outward, so none can reach the opposite (-Y) wall.
    print("\nthe rear (+Y) wall: hex vent field and the battery-lead rectangle")
    #  Probe in the OUTER half of the wall.  The +Y wall's inner 1.30 is cut
    #  back by the header relief (x 11.70..66.00, z ..33.93), so a probe just
    #  past the inner face would read "empty" there whether or not a vent hole
    #  had been cut.  y = OD - 1.00 is solid wall unless this module cut it.
    probe_y = OD - 1.00
    hex_centres = [(HEX_X0 + i * HEX_DX,
                    HEX_Z0 + j * HEX_DZ + (i % 2) * HEX_DZ / 2)
                   for i in range(HEX_NX) for j in range(HEX_NZ)]
    hex_x0 = HEX_X0 - HEX_HW
    hex_x1 = HEX_X0 + (HEX_NX - 1) * HEX_DX + HEX_HW
    hex_z0 = HEX_Z0 - HEX_HH
    hex_z1 = HEX_Z0 + (HEX_NZ - 1) * HEX_DZ + HEX_DZ / 2 + HEX_HH
    check("every hex vent hole is open through the +Y wall",
          not [p for p in hex_centres if mid.inside((p[0], probe_y, p[1]))],
          f"{len(hex_centres)} holes, {2 * HEX_R:.2f} x {2 * HEX_HH:.2f}, "
          f"on a {HEX_DX:.2f} x {HEX_DZ:.2f} stagger")
    check("...and wall survives between the holes and round the field",
          mid.inside((HEX_X0 + HEX_DX / 2, probe_y, HEX_Z0))
          and mid.inside((HEX_X0, probe_y, HEX_Z0 + HEX_DZ / 2))
          and mid.inside((hex_x0 - 0.50, probe_y, HEX_Z0))
          and mid.inside((hex_x1 + 0.50, probe_y, HEX_Z0)),
          f"webs probed at the column and row midpoints; field x "
          f"{hex_x0:.2f}..{hex_x1:.2f}, z {hex_z0:.2f}..{hex_z1:.2f}")
    check("...and the field clears the lead rectangle and both screw columns",
          hex_x0 > 9.00 + 2.90 and hex_x1 < LEAD_RX0
          and hex_z0 > JOINT_A + 0.50 and hex_z1 < SPLIT_B - 1.00,
          f"left margin {hex_x0 - (9.00 + 2.90):.2f} to the screw column, "
          f"right margin {LEAD_RX0 - hex_x1:.2f} to the lead rectangle")
    check("the battery-lead rectangle is open through the +Y wall",
          not mid.inside(((LEAD_RX0 + LEAD_RX1) / 2, probe_y,
                          (LEAD_RZ0 + LEAD_RZ1) / 2))
          and not [p for p in ((LEAD_RX0 + 0.50, LEAD_RZ0 + 0.50),
                               (LEAD_RX1 - 0.50, LEAD_RZ0 + 0.50),
                               (LEAD_RX0 + 0.50, LEAD_RZ1 - 0.50),
                               (LEAD_RX1 - 0.50, LEAD_RZ1 - 0.50))
                  if mid.inside((p[0], probe_y, p[1]))],
          f"{LEAD_RX1 - LEAD_RX0:.2f} x {LEAD_RZ1 - LEAD_RZ0:.2f} at "
          f"x {LEAD_RX0:.2f}..{LEAD_RX1:.2f}, z {LEAD_RZ0:.2f}..{LEAD_RZ1:.2f}")
    check("...and it is a through-cut in this wall only",
          mid.inside((LEAD_RX0 - 1.00, probe_y, (LEAD_RZ0 + LEAD_RZ1) / 2))
          and mid.inside((LEAD_RX1 + 1.00, probe_y, (LEAD_RZ0 + LEAD_RZ1) / 2))
          and mid.inside(((LEAD_RX0 + LEAD_RX1) / 2, WALL / 2,
                          (LEAD_RZ0 + LEAD_RZ1) / 2)),
          "solid at both flanks, and the -Y wall behind it is untouched")
    check("...and it clears the field, the screws and the wall's ends",
          LEAD_RX0 > hex_x1 + 1.00
          and LEAD_RX1 < OW - 9.00 - 2.90 - 1.00
          and LEAD_RZ0 > JOINT_A + 0.50 and LEAD_RZ1 < SPLIT_B - 1.00,
          f"field ends at {hex_x1:.2f}, rectangle x {LEAD_RX0:.2f}.."
          f"{LEAD_RX1:.2f}, next screw at {OW - 9.00:.2f}")
    check("the vents are open through the BASE's -Y wall",
          not base.inside((OW / 2, WALL / 2, VENT_Z)))
    check("the vent row is inside the wall span and clear of both screws",
          OW / 2 + (VENT_N - 1) / 2 * VENT_P + VENT_W / 2 < OW - WALL - 9.00
          and VENT_Z - VENT_H / 2 > 0 and VENT_Z + VENT_H / 2 < JOINT_A,
          f"row spans x {OW / 2 - (VENT_N - 1) / 2 * VENT_P - VENT_W / 2:.2f}"
          f"..{OW / 2 + (VENT_N - 1) / 2 * VENT_P + VENT_W / 2:.2f}, "
          f"z {VENT_Z - VENT_H / 2:.2f}..{VENT_Z + VENT_H / 2:.2f}")

    # ---- the regression that matters most ------------------------------
    #  The plate is the access hatch now, so this is a statement about the
    #  DISASSEMBLY ORDER: four bolts out, plate off, and the Pi's four are
    #  there in the BASE's underside, counterbored flush, looking at you.
    print("\nthe Pi's screws, reachable from underneath with the plate off")
    ok, det = True, []
    for i in (0, 1):
        for j in (0, 1):
            hx = PCB_X + PI_HOLE_IN + i * PI_HOLE_DX
            hy = PCB_Y + PI_HOLE_IN + j * PI_HOLE_DY
            #  The counterbore and the bore must be EMPTY along the screw's
            #  axis, from the BASE's floor face up to the PCB's underside.  If
            #  anything closed these the Pi could never be unscrewed.
            for z in (PI_CBORE_H / 2, PI_CBORE_H + 0.5, PCB_Z - 0.5):
                if base.inside((hx, hy, z)):
                    ok, det = False, f"blocked at {hx:.2f},{hy:.2f} z {z:.2f}"
            # and there is floor beside the counterbore for the head to seat on
            if not base.inside((hx, hy + PI_CBORE_D / 2 + 0.6, PI_CBORE_H / 2)):
                ok, det = False, f"no head seat beside {hx:.2f},{hy:.2f}"
    check("4 Pi counterbores reachable from below, flush in the BASE", ok, det)
    #  ...and the three figures that make an M2.5 safe in a o7.00 boss.  It is
    #  the only M2.5 in the build; the case used to be all-M2 on the "one screw
    #  size" argument, which the move to M3 spent.  M2.5 is what the Pi's own
    #  mounting holes are for - they are o2.75, so an M3 cannot pass them.
    check("the Pi's boss, bore and head seat all stay sound at M2.5",
          abs((BOSS_D - PI_CBORE_D) / 2 - 1.00) < 1e-9
          and abs(FLOOR - PI_CBORE_H - 1.20) < 1e-9
          and PI_SCREW_CLR - 2.70 >= 0.10 - 1e-9,
          f"o{PI_SCREW_CLR:.2f} clearance for an M2.5's 2.70 shank, "
          f"{PI_CBORE_H:.2f} of counterbore for its 1.40 head, leaving "
          f"{FLOOR - PI_CBORE_H:.2f} of floor under it and "
          f"{(BOSS_D - PI_CBORE_D) / 2:.2f} of boss wall round it")
    #  And the plate passes over them, which is why the 0.50 gap is not
    #  decoration: the heads seat into the BASE's underside with their bearing
    #  faces at z 0.00, so a proud head would stand the plate off the case.
    #
    #  Worth stating rather than rounding away: the plate is 76.20 wide and the
    #  Pi's hole pattern starts at x 8.85, so only the +X pair is well inside
    #  the plate's footprint.  The -X pair sits 0.86 OUTBOARD of its edge, with
    #  the edge cutting across the outer rim of those two heads - harmless, and
    #  it means those two can be reached with the plate still on.
    heads_x = [PCB_X + PI_HOLE_IN + i * PI_HOLE_DX for i in (0, 1)]
    heads_y = [PCB_Y + PI_HOLE_IN + j * PI_HOLE_DY for j in (0, 1)]
    check("...and the plate clears the four seated heads by PLATE_GAP",
          abs(PLATE_Z1 - (-PLATE_GAP)) < 1e-9
          and all(PLATE_Y0 < hy < PLATE_Y1 for hy in heads_y),
          f"heads flush at z 0.00 in the BASE's underside; the plate's inner "
          f"face is z {PLATE_Z1:.2f} - {PLATE_GAP:.2f} clear. All four sit "
          f"inside the plate's y span {PLATE_Y0:.2f}..{PLATE_Y1:.2f}; the "
          f"x {heads_x[0]:.2f} pair lies {PLATE_X0 - heads_x[0]:.2f} outside "
          f"its x edge and the x {heads_x[1]:.2f} pair "
          f"{PLATE_X1 - heads_x[1]:.2f} inside it")

    # ---- the front panel -------------------------------------------------
    #  LEDs and switches in the -Y wall.  Everything here is a NEGATIVE
    #  assertion about the MID, so every probe is a place that must be empty
    #  (or, for the lip, the one place that must not be).
    print("\nfront panel (3 LEDs + 3 switches, -Y wall)")
    PZ = PANEL_Z                      # the row's z, = the height above the
                                      #  case's underside and the bench alike
    led_x = [LED_X0 + i * LED_PITCH for i in range(LED_N)]
    sw_x = [SW_X0 + i * SW_PITCH for i in range(SW_N)]

    holes = [(x, y, PZ) for x in led_x for y in (0.4, 2.25, 4.1)]
    check(f"{LED_N} LED bores open through the wall",
          not [p for p in holes if mid.inside(p)], f"{len(holes)} probes")

    #  The bore is deliberately plain rather than counterbored: the LED's flange
    #  has to stop against the wall's inner face for the lens to finish INSIDE
    #  the outer face.  A counterbore defeats that, because the flange is at the
    #  LED's base - sinking it in carries the lens out with it.  Probe just
    #  outside the Ø3.20 bore at both faces: solid the whole way means plain.
    r = LED_D / 2 + 0.20                      # outside the bore, inside a Ø5.60 one
    plain = [(x, y, PZ + s * r) for x in led_x for y in (0.30, 4.20)
             for s in (-1, 1)]
    check("the LED bore is plain - no counterbore to carry the lens out",
          not [p for p in plain if not mid.inside(p)],
          f"{len(plain)} probes beside the bores")

    check("LED row is plain wall between the holes",
          not [p for p in [(LED_X0 + LED_PITCH / 2, 2.5, PZ)]
               if not mid.inside(p)])

    buttons = [(x, y, PZ) for x in sw_x for y in (0.05, 0.22, 0.40)]
    check(f"{SW_N} button holes open through the lip",
          not [p for p in buttons if mid.inside(p)], f"{len(buttons)} probes")

    pockets = [(x, y, PZ) for x in sw_x
               for y in (SW_LIP + 0.2, 2.7, WALL - 0.1)]
    check("pockets are hollow to the inner face",
          not [p for p in pockets if mid.inside(p)], f"{len(pockets)} probes")

    # The lip is 0.45 of wall left in FRONT of the body and is the only thing
    # holding the switch in.  If the pocket had been cut deeper than the wall
    # the button hole would run straight through and the switch would fall into
    # the case on the first press.
    lip = [(x + s * (SW_BTN_D / 2 + 0.35), 0.22, PZ)
           for x in sw_x for s in (-1, 1)]
    behind = [(x + s * (SW_BTN_D / 2 + 0.35), 0.60, PZ)
              for x in sw_x for s in (-1, 1)]
    check("the 0.45 lip holds the switch in",
          not [p for p in lip if not mid.inside(p)]
          and not [p for p in behind if mid.inside(p)],
          f"{len(lip)} probes")

    # The crush ribs are cut by subtracting their volume FROM the cut, so the
    # material stays where the rib is.  Probed at the rib and just beside it.
    ribbed = [(x + s * (SW_POCKET / 2 - SW_RIB / 2), 2.5, PZ)
              for x in sw_x for s in (-1, 1)]
    beside = [(x + s * (SW_POCKET / 2 - SW_RIB - 0.3), 2.5, PZ)
              for x in sw_x for s in (-1, 1)]
    check("crush ribs stand proud of the pocket walls",
          not [p for p in ribbed if not mid.inside(p)]
          and not [p for p in beside if mid.inside(p)],
          f"rib {SW_RIB} proud, pocket {SW_POCKET}")

    # The band.  A panel that drifted out of it would eat a port below or the
    # LCD shelf above, and both are invisible in a render.  The row is what
    # keeps its absolute height when the stack above it moves: the switch is
    # 6.00 tall on a 33.00 centre, and 15.56..38.60 is where it fits.
    #
    # The x probes are the LED row's first bore and the switch row's first, so
    # they stay clear of the ACCESSORY OPENING at x 52.90..65.10 - that opening
    # is the one piece of wall under this panel that is cut on purpose, and its
    # own section below probes it.
    below = [(x, 2.5, z) for x in (LED_X0, SW_X0)
             for z in (PANEL_BAND_LO + 1.0, 20.0, 24.0, 28.0)]
    above = [(x, 2.5, z) for x in (LED_X0, LED_X0 + LED_PITCH, SW_X0)
             for z in (PANEL_BAND_HI - 1.2, PANEL_BAND_HI - 0.6)]
    check("wall below the panel untouched either side of the opening",
          not [p for p in below if not mid.inside(p)], f"{len(below)} probes "
          f"at x {LED_X0:.2f} and {SW_X0:.2f}, ports stop at "
          f"{PANEL_BAND_LO:.2f}")
    check("wall above the panel untouched (the shelf starts at 38.60)",
          not [p for p in above if not mid.inside(p)], f"{len(above)} probes")
    #  The shelf's underside is now at 38.60, so the body (top 36.00) keeps
    #  2.60 of plain wall above it rather than the old 4.10.  The pocket needs
    #  the body plus a margin at either end, not a second body height.
    check("the switch body fits the band with wall either side",
          PANEL_Z - SW_BODY / 2 >= PANEL_BAND_LO + 2.00
          and PANEL_Z + SW_BODY / 2 + 2.00 <= PANEL_BAND_HI,
          f"body {PANEL_Z - SW_BODY / 2:.2f}..{PANEL_Z + SW_BODY / 2:.2f} in "
          f"{PANEL_BAND_LO:.2f}..{PANEL_BAND_HI:.2f}")

    # ---- the accessory opening ------------------------------------------
    #  A 12 x 7 slot under the switch row, cut at 12.20 x 7.20 so the PRINTED
    #  opening still clears the 12 x 7 that was asked for (FDM holes come out
    #  undersize; the +0.20 is the same allowance the switch pockets take).
    #  The request is a MINIMUM, so this measures the real thing: the probes
    #  below are the corners of a 12.00 x 7.00 rectangle, at three depths
    #  through the 4.50 wall, and every one of them has to be empty.
    #
    #  Placement is deliberate, not incidental.  The x pair is taken at the
    #  opening's MID-height and the z pair inside the fillets' straight run,
    #  so no probe lands in a corner the R1.50 has rounded away - and the
    #  wall round it is probed in the four directions it could have eaten.
    open_at = [(ACC_CX + dx, y, ACC_CZ) for dx in (-6.00, 6.00)
               for y in (0.05, 2.25, 4.40)]
    open_at += [(ACC_CX + dx, y, ACC_CZ + dz)
                for dx in (-4.50, 4.50) for dz in (-3.50, 3.50)
                for y in (0.05, 2.25, 4.40)]
    check(f"the opening is at least {ACC_MIN_W:.2f} x {ACC_MIN_H:.2f}, "
          "open right through",
          not [p for p in open_at if mid.inside(p)],
          f"{len(open_at)} probes through the {ACC_W} x {ACC_H} cut")

    keep = [(ACC_CX + s * (ACC_W / 2 + 0.30), y, ACC_CZ)
            for s in (-1, 1) for y in (0.30, 4.40)]
    keep += [(ACC_CX, y, ACC_CZ + s * (ACC_H / 2 + 0.30))
             for s in (-1, 1) for y in (0.30, 4.40)]
    check("the wall round the opening is intact at both faces",
          not [p for p in keep if not mid.inside(p)], f"{len(keep)} probes")

    #  The strip between this opening and the audio jack's is the THINNEST
    #  cross-section in the whole front face - 3.65 of wall bridging a 12.20
    #  window, with a slot open at the bottom below it and a 12.20 hole above.
    #  So it is probed along its length rather than assumed, and the figure is
    #  printed rather than described.
    band = [(ACC_CX + dx, y, z) for dx in (-5.00, 0.0, 5.00)
            for z in (16.20, 17.50, 18.70) for y in (0.30, 4.40)]
    check("the 3.65 band of wall above the audio opening is solid",
          not [p for p in band if not mid.inside(p)],
          f"{len(band)} probes in z 16.20..18.70, the strip between the audio "
          f"opening's edge at {AUDIO_TOP:.2f} and the opening's floor at "
          f"{ACC_CZ - ACC_H / 2:.2f}")

    #  The fillet, measured rather than taken on trust.  R1.50 rounds the
    #  corner off, so the square corner point itself has to be MATERIAL and a
    #  point inside the arc has to be hole.  A plain rectangular cut fails the
    #  first of those; a cut that had lost its corners altogether would fail
    #  the second.
    def in_hole(px, pz):
        r = ACC_R
        dx = abs(px - ACC_CX) - (ACC_W / 2 - r)
        dz = abs(pz - ACC_CZ) - (ACC_H / 2 - r)
        inside = (dx <= 0 or dz <= 0 or dx * dx + dz * dz <= r * r)
        return (inside and abs(px - ACC_CX) < ACC_W / 2
                and abs(pz - ACC_CZ) < ACC_H / 2)

    corner = (ACC_CX + ACC_W / 2 - 0.20, 2.5, ACC_CZ + ACC_H / 2 - 0.20)
    arc_in = (ACC_CX + (ACC_W / 2 - ACC_R) + 0.40, 2.5,
              ACC_CZ + (ACC_H / 2 - ACC_R) + 0.40)
    check(f"the corners are filleted at R{ACC_R}, not left square",
          mid.inside(corner) and not mid.inside(arc_in)
          and not in_hole(corner[0], corner[2])
          and in_hole(arc_in[0], arc_in[2]),
          f"({corner[0]:.2f}, {corner[2]:.2f}) is plastic with nothing cut "
          f"there, ({arc_in[0]:.2f}, {arc_in[2]:.2f}) is inside the arc")

    #  The margins that make the placement true.  Below, the highest port on
    #  this wall (the HDMI opening, whose top edge is what the whole panel
    #  band is measured from); above, the switch pockets' floor; sideways, the
    #  LED row's last bore and the two M3 columns that run the wall's full
    #  height.  The AUDIO opening is directly below the new hole in x and
    #  lower than the HDMI's edge in z, so the HDMI figure bounds it too.
    acc_lo = (ACC_CZ - ACC_H / 2) - PORT_TOP
    acc_audio = (ACC_CZ - ACC_H / 2) - AUDIO_TOP
    acc_hi = ACC_HI - (ACC_CZ + ACC_H / 2)
    acc_led = (ACC_CX - ACC_W / 2) - (LED_X0 + (LED_N - 1) * LED_PITCH)
    acc_mx0 = ACC_CX - ACC_W / 2 - 9.00
    acc_mx1 = (OW - 9.00) - (ACC_CX + ACC_W / 2)
    check("the opening clears the ports, the pockets, the LEDs and both M3 columns",
          min(acc_lo, acc_hi, acc_led, acc_mx0, acc_mx1) >= 3.00,
          f"HDMI below {acc_lo:.2f} (audio {acc_audio:.2f}), pocket floors "
          f"above {acc_hi:.2f}, LED row {acc_led:.2f}, M3 columns "
          f"{acc_mx0:.2f} / {acc_mx1:.2f}")

    check("the opening sits wholly in the MID, clear of the BASE and the shelf",
          ACC_CZ - ACC_H / 2 > JOINT_A
          and ACC_CZ + ACC_H / 2 < SPLIT_B - SHELF_T,
          f"z {ACC_CZ - ACC_H / 2:.2f}..{ACC_CZ + ACC_H / 2:.2f} inside "
          f"{JOINT_A:.2f}..{SPLIT_B - SHELF_T:.2f}")

    #  The corridor behind it has to be clear, or the opening leads into the
    #  back of a board.  This is the one question the imported meshes can be
    #  asked soundly - a triangle-level overlap test, which needs no closed
    #  surface - and it is asked of all three.  The corridor is the opening's
    #  own x/z footprint swept ACC_DEPTH back from the wall's inner face.
    cor_lo = [ACC_CX - ACC_W / 2, WALL, ACC_CZ - ACC_H / 2]
    cor_hi = [ACC_CX + ACC_W / 2, WALL + ACC_DEPTH, ACC_CZ + ACC_H / 2]

    def nearest_behind(tris):
        """The nearest triangle's lowest y, over everything in the footprint."""
        near = [min(p[1] for p in t) for t in tris
                if min(p[0] for p in t) < cor_hi[0] and max(p[0] for p in t) > cor_lo[0]
                and min(p[2] for p in t) < cor_hi[2] and max(p[2] for p in t) > cor_lo[2]]
        return min(near) if near else None

    boarded = [(n, tris_in_box(t, cor_lo, cor_hi))
               for n, t in (("pi", stl_rpi), ("wittypi", stl_wit), ("lcd", stl_lcd))]
    nearest = min((y for y in (nearest_behind(t) for _, t in
                               (("pi", stl_rpi), ("wittypi", stl_wit),
                                ("lcd", stl_lcd))) if y is not None),
                  default=None)
    check(f"nothing on the boards sits within {ACC_DEPTH:.2f} behind the opening",
          not [t for _, t in boarded if t],
          "no triangle of the Pi, WittyPi or LCD crosses the corridor"
          + (f"; nearest board material at y {nearest:.2f}, "
             f"{nearest - WALL:.2f} clear" if nearest is not None else ""))

    #  ---- the parts themselves -------------------------------------------
    #  Everything above is the CASE - where a hole is, what it clears.  From
    #  here on the questions are asked of the exported PART meshes, so they
    #  fail if the .scad's geometry drifts even when its arithmetic does not.
    #
    #  This block replaces a probe over a synthetic 6 x 6 x SW_H box that
    #  stood in for the switch.  It was the last thing in this suite measuring
    #  a guess, and it could not have caught the one thing that is actually
    #  wrong here - see the terminal check at the end.
    rest = Union(base, bezel)

    #  1. The body sits in its own pocket with 0.10 all round.  Probed 0.05 in
    #  from the pocket's walls, which is where the gap is - and clear of the
    #  ribs in y, because AT a rib the same point is plastic on purpose and
    #  this test would read the crush fit as a collision.  The ribs get their
    #  own check next, from the other side.
    gaps = []
    for cx in sw_x:
        for s in (-1, 1):
            gaps += [(cx + s * (SW_POCKET / 2 - 0.05), y, PZ)
                     for y in (RIB_Y0 - 0.30, RIB_Y1 + 0.30, RIB_Y1 + 0.55)]
            gaps += [(cx, y, PZ + s * (SW_POCKET / 2 - 0.05))
                     for y in (RIB_Y0 - 0.30, 2.40, RIB_Y1 + 0.30, RIB_Y1 + 0.55)]
    bad = [p for p in gaps if mid.inside(p)]
    check("each switch body sits in its pocket with 0.10 all round",
          not bad,
          f"{len(gaps)} probes 0.05 inside the pocket walls, clear of the ribs"
          + (f" e.g. {bad[0]}" if bad else ""))

    #  2. ...and the ribs grip it.  The positive half, which nothing has ever
    #  asserted: a probe INSIDE the rib has to be inside case material AND
    #  inside the exported switch at once, or the "interference fit" is a
    #  claim about two numbers rather than about two solids.
    #
    #  The rib stands SW_RIB proud of the pocket wall, so its inner face is at
    #  SW_POCKET/2 - SW_RIB = 2.90, and the body reaches SW_BODY/2 = 3.00.  The
    #  two overlap over that 0.10, and the probe goes at its MIDPOINT - the
    #  only x in the whole panel where a point is inside both parts and on
    #  neither of their faces.
    grip_d = (SW_BODY / 2 - (SW_POCKET / 2 - SW_RIB)) / 2
    grip_x = SW_POCKET / 2 - SW_RIB + grip_d
    grip = [(cx + s * grip_x, y, PZ + t)
            for cx in sw_x for s in (-1, 1)
            for y in (1.50, 2.70, 3.60) for t in (-RIB_Z / 2, 0.0, RIB_Z / 2)]
    held = [p for p in grip if mid.inside(p) and sws.inside(p)]
    check("the crush ribs grip the body - the only place the two touch",
          len(held) == len(grip),
          f"{len(held)}/{len(grip)} probes in both the MID and the exported "
          f"switch at |x - centre| {grip_x:.2f}, {grip_d:.2f} into each")

    #  3. The four legs stand in free cavity behind the seat plane.  Probed
    #  down the strips between the inner face and their tips, against the
    #  whole shell - this is the part of the leg that has to be free for the
    #  switch to go in at all.  x and z are the two different axes the legs
    #  have different numbers in: SW_LEG_X0..X1 across, SW_LEG_S0..S1 in the
    #  splay, which the placement turns into z.
    legs = [(cx + s * (SW_LEG_X0 + SW_LEG_W / 2), y,
             PZ + u * (SW_LEG_S0 + (SW_LEG_D + SW_LEG_IN) / 2))
            for cx in sw_x for s in (-1, 1) for u in (-1, 1)
            for y in (5.10, 5.60, 6.50, 7.50, 8.40)]
    stuck = [p for p in legs if shell.inside(p) or not sws.inside(p)]
    check("every switch's four legs clear the case and stand in free cavity",
          not stuck,
          f"{len(legs)} probes down the strips, from y 5.10 past the seat "
          f"plane at {SW_SEAT:.2f}"
          + (f" e.g. {stuck[0]}" if stuck else ""))

    #  4. The LED seats: the flange bears on the wall's inner face and the
    #  barrel stops short of the outer one, which is the whole reason the bore
    #  is plain and not counterbored.  Both halves are read off the exported
    #  mesh rather than re-derived - the tip from its own y minimum, the
    #  bearing face by asking the MID at the flange's own radius.  A LED
    #  dropped in at the wrong y fails here with every number above unchanged.
    led_tip = min(p[1] for t in stl_leds for p in t)
    flange_r = (LED_BODY_D / 2 + LED_FLANGE_D / 2) / 2      # 1.90, on the annulus
    bearing = [(cx + s * flange_r, y, PZ) for cx in led_x for s in (-1, 1)
               for y in (WALL - 0.05, WALL + 0.05)]
    on_wall = [p for p in bearing if p[1] < WALL and mid.inside(p)]
    in_cavity = [p for p in bearing if p[1] > WALL
                 and not mid.inside(p) and leds.inside(p)]
    check("the LED flange bears on the inner face; the 5 mm lens stands proud",
          abs(led_tip - (WALL - LED_BARREL)) < 0.02
          and len(on_wall) == LED_N * 2 and len(in_cavity) == LED_N * 2,
          f"tip at y {led_tip:.2f} = {-led_tip:.2f} proud of the outer "
          f"face ({LED_BARREL:.2f} of barrel from the flange on {WALL:.2f}); "
          f"{len(on_wall)}/{LED_N * 2} probes on the annulus are MID, "
          f"{len(in_cavity)}/{LED_N * 2} are LED and not MID")

    #  5. Nothing on the boards is within reach of a LED lead or a switch
    #  leg.  The README used to assert this in prose ("nothing is within
    #  45 mm of them"); this is the same claim as a measurement, and it is
    #  the one question the open board meshes can be asked soundly.
    corridors = []
    for cx in sw_x:
        for s in (-1, 1):
            c = SW_LEG_S0 + SW_LEG_D / 2
            corridors.append(("leg", cx + s * c, PZ + c))
            corridors.append(("leg", cx + s * c, PZ - c))
    for cx in led_x:
        for s in (-1, 1):
            corridors.append(("lead", cx + s * LED_LEAD_DX, PZ))
    reach = []
    for kind, x, z in corridors:
        lo = [x - LED_LEAD / 2 - 0.1 if kind == "lead" else x - SW_LEG_W / 2 - 0.1,
              WALL, z - (LED_LEAD / 2 + 0.1 if kind == "lead" else SW_LEG_D / 2 + 0.1)]
        hi = [lo[0] + (LED_LEAD + 0.2 if kind == "lead" else SW_LEG_W + 0.2),
              WALL + LED_LEAD_L + SW_LEG_L,
              lo[2] + (LED_LEAD + 0.2 if kind == "lead" else SW_LEG_D + 0.2)]
        for n, t in (("pi", stl_rpi), ("wittypi", stl_wit), ("lcd", stl_lcd)):
            hit = tris_in_box(t, lo, hi)
            if hit:
                reach.append((kind, n, x, z, len(hit)))
    check("no board is within reach of a LED lead or a switch leg",
          not reach,
          f"{len(corridors)} corridors swept behind the panel"
          + (f"; {reach[0][1]} crosses the {reach[0][0]} at x {reach[0][2]:.2f}"
             if reach else " - no triangle of the Pi, WittyPi or LCD in any"))

    #  6. The button hole clears the measured actuator.  SW_BTN_D was set
    #  before the actuator was measurable, so this is the number that says
    #  the two agree: 0.05 radially, the tightest fit in the panel.
    check("the button hole clears the measured actuator",
          SW_BTN_D > SW_ACT_D,
          f"hole {SW_BTN_D:.2f}, actuator {SW_ACT_D:.2f}, "
          f"{(SW_BTN_D - SW_ACT_D) / 2:.2f} radially")

    #  7. THE TERMINALS CLEAR THE POCKET.  This check used to be a KNOWN GAP:
    #  at WALL 5.00 the seat plane was 0.45 past the inner face, so the tops
    #  of the four strips sat inside solid wall and the switch could not be
    #  seated.  The wall is now 4.50, which leaves the drawn 5.00-tall part's
    #  strips 0.05 clear of the inner face - still less than printed
    #  tolerance - and the MID cuts a SW_TERM_NOTCH notch behind each strip.
    #  The depth is set by the MEASURED 3.86-tall part, whose strip tops reach
    #  3.41 and need 0.25 of clearance from the notch floor.
    #
    #  The strips splay SW_LEG_S1 (3.60) from the switch centre while the
    #  pocket half-width is only 3.10, so only their z reach crosses into the
    #  wall; the notches are placed on that reach and over the strip's x.
    #  The probes sit strictly inside both cut and wall so a ray cast cannot
    #  land on a face, where it is genuinely ambiguous.
    def notch_box(cx, sy, sz):
        a = (cx + sy * (SW_LEG_X0 + 0.05), WALL - SW_TERM_NOTCH + 0.10,
             PZ + sz * (SW_POCKET / 2 + 0.05))
        b = (cx + sy * (SW_LEG_X1 - 0.05), WALL - 0.10,
             PZ + sz * (SW_LEG_Y1 + SW_TERM_MARGIN - 0.05))
        return ([min(a[i], b[i]) for i in range(3)],
                [max(a[i], b[i]) for i in range(3)])

    def spread(lo, hi, n=4):
        return [lo + i * (hi - lo) / (n - 1) for i in range(n)]

    notch = []
    for cx in sw_x:
        for sy in (-1, 1):
            for sz in (-1, 1):
                lo, hi = notch_box(cx, sy, sz)
                notch += [(x, y, z)
                          for x in spread(lo[0], hi[0])
                          for y in spread(lo[1], hi[1])
                          for z in spread(lo[2], hi[2])]
    left = [p for p in notch if mid.inside(p)]
    clear = SW_SEAT - SW_LEG_UP - WALL          # 0.05 at the drawn seat
    gain = SW_TERM_NOTCH + clear                # 1.45 with the notch
    check("the switch terminals clear the MID wall behind them",
          not left and gain >= ASSEMBLY_TOL,
          f"the strip tops sit {clear:.2f} off the inner face and each notch "
          f"is {SW_TERM_NOTCH:.2f} deep, so clearance is {gain:.2f} "
          f"(assembly tolerance {ASSEMBLY_TOL:.2f}); "
          f"{len(left)}/{len(notch)} notch probes still in MID material"
          + (f" e.g. {left[0]}" if left else ""))
    #  The measured 1825910-6 is only 3.86 tall, which puts its seat at 4.31
    #  and its strip tops at 3.41 - deeper into the wall than the drawn part.
    #  The notch depth has to cover that case too, or fitting the real switch
    #  would undo the fix.
    real_top = SW_LIP + 3.86 - SW_LEG_UP       # = 3.41
    real_clear = real_top - (WALL - SW_TERM_NOTCH)
    check("...and the notch clears the measured 3.86-tall switch as well",
          real_clear >= ASSEMBLY_TOL,
          f"real strip top {real_top:.2f}, notch floor "
          f"{WALL - SW_TERM_NOTCH:.2f}, {real_clear:.2f} clear")

    #  ...and the notch did not eat the wall around it.  One probe below the
    #  notch floor and one between adjacent notches must still be solid.
    notch_floor = [(cx, WALL - SW_TERM_NOTCH - 0.15, PZ + sz * 3.45)
                   for cx in sw_x for sz in (-1, 1)]
    notch_web = [(cx, WALL - 0.25, PZ + sz * 3.45)
                 for cx in sw_x for sz in (-1, 1)]
    check("the terminal notches leave the wall solid around them",
          not [p for p in notch_floor if not mid.inside(p)],
          f"{len(notch_floor)} probes below the notch floors")
    check("the wall between each pair of terminal notches is solid",
          not [p for p in notch_web if not mid.inside(p)],
          f"{len(notch_web)} probes at the switch centre line, z +/-3.45")

    #  ...and nothing ELSE does.  The pair is the point: that check says where
    #  the parts DO meet, this one says where they must not - the ribs are the
    #  only intended interference, and everything else has to be clear.  The
    #  x step is 0.10 for a reason: the rib's grip is only 0.10 deep, so a
    #  coarser sweep would walk straight past the one contact it is meant to
    #  find and the check would pass for the wrong reason.
    #
    #  One region is allowed: the rib, where case material is inside the
    #  BODY - |dx| between the rib's tip and the pocket wall, over the rib's
    #  own inset span.  The terminal shoulders are no longer a contact at all
    #  now that each strip has its own notch.
    def allowed(p, cx):
        dx, dz = abs(p[0] - cx), abs(p[2] - PZ)
        rib = (SW_POCKET / 2 - SW_RIB - 0.02 <= dx <= SW_POCKET / 2 + 0.02
               and RIB_Y0 - 0.02 <= p[1] <= RIB_Y1 + 0.02
               and abs(p[2] - PZ) <= RIB_Z + 0.02)
        return rib

    contacts, loose = 0, []
    for cx in sw_x:
        for x in [cx - 3.15 + i * 0.10 for i in range(64)]:
            for y in [0.50 + j * 0.25 for j in range(33)]:
                for z in (PZ - 3.30, PZ - 1.50, PZ, PZ + 1.50, PZ + 3.30):
                    if sws.inside((x, y, z)) and shell.inside((x, y, z)):
                        contacts += 1
                        if not allowed((x, y, z), cx):
                            loose.append((round(x, 2), round(y, 2), round(z, 2)))
    check("...and the ribs are the only place the parts meet",
          not loose,
          f"{contacts} contact samples over the whole switch envelope, all in "
          f"the ribs"
          + (f"; {len(loose)} outside them e.g. {loose[0]}" if loose else ""))

    # ---- the assembly sweep ---------------------------------------------
    #  The .scad has a `sweep` view that lowers the MID over the stack: BASE,
    #  Pi, header and WittyPi are present, while the LCD and the panel
    #  hardware go on afterwards.  This is the same motion in numbers.  A
    #  world point p collides at lift L when it lies inside the MID's own
    #  frame at p - (0, 0, L); sampling every 0.50 mm is finer than the
    #  0.25 assembly tolerance, so a feature cannot slip between probes.
    print("\nassembly sweep (the MID descending over the stack)")
    lift_n = int(round(SWEEP_SPAN / SWEEP_STEP))
    lifts = [i * SWEEP_STEP for i in range(lift_n + 1)]

    def sweep_hits(points):
        hits = []
        for L in lifts:
            for p in points:
                if mid.inside((p[0], p[1], p[2] - L)):
                    hits.append((L, p))
                    break
        return hits

    #  The button, sampled through its measured box rather than its mesh.
    bpoints = [(bx0 + (i + 0.5) * (bx1 - bx0) / 3,
                by0 + (j + 0.5) * (by1 - by0) / 3,
                bz0 + (k + 0.5) * (bz1 - bz0) / 3)
               for i in range(3) for j in range(3) for k in range(3)]
    bhits = sweep_hits(bpoints)
    check("the MID slides down over the WittyPi button without touching it",
          not bhits,
          f"{len(bpoints)} points through the button box, {len(lifts)} lifts "
          f"0..{SWEEP_SPAN:.0f}"
          + (f"; first contact at lift {bhits[0][0]:.2f} {bhits[0][1]}"
             if bhits else ""))

    #  The full 40-pin envelope, the same probes as the static check above,
    #  now carried through every lift.  The MID's notch and +Y relief have to
    #  be open all the way down, not just at the seat.
    ghits = sweep_hits(gpio)
    check("the MID slides down over the full 40-pin header without touching it",
          not ghits,
          f"{len(gpio)} envelope probes x {gx0:.2f}..{gx1:.2f}, "
          f"{len(lifts)} lifts"
          + (f"; first contact at lift {ghits[0][0]:.2f} {ghits[0][1]}"
             if ghits else ""))

    #  The Pi's PCB is the largest thing the cavity has to swallow.  Sampled
    #  on a 5 mm grid inside the board, so a wall or a boss that reached in
    #  would be caught well before the 0.60 edge clearance.
    pcb = [(x, y, z)
           for x in [5.30 + i * 5.00 for i in range(17)]
           for y in [5.30 + j * 5.00 for j in range(11)]
           for z in (PCB_Z + 0.30, PCB_Z + PI_PCB_T - 0.30)
           if x < 90.02 and y < 61.10]
    phits = sweep_hits(pcb)
    check("the MID slides down over the Pi's PCB without touching it",
          not phits,
          f"{len(pcb)} probes through the board, {len(lifts)} lifts"
          + (f"; first contact at lift {phits[0][0]:.2f} {phits[0][1]}"
             if phits else ""))

    # ---- the loops really do switch off ---------------------------------
    #  `for (i = [0 : N - 1])` does NOT do nothing at N = 0.  OpenSCAD
    #  normalises a range whose end is below its start into a REVERSED one:
    #  [0 : -1] becomes [-1 : 1 : 0] and the body runs TWICE, at i = -1 and
    #  i = 0.  Without the guards in panel(), LED_N = 0 would hang two phantom
    #  LEDs off the left end of the row instead of deleting them.  Exported
    #  straight from the .scad, because `use <>` would not carry -D through.
    off = os.path.join(tmp, "mid_off.stl")
    run_openscad(off, SCAD, ['PART="mid"', "LED_N=0", "SW_N=0"])
    moff = Solid(read_stl(off))
    phantom = [(LED_X0 - LED_PITCH, 2.5, PZ), (LED_X0, 2.5, PZ),
               (SW_X0 - SW_PITCH, 2.5, PZ), (SW_X0, 2.5, PZ)]
    check("LED_N=0 / SW_N=0 remove the panel outright",
          not [p for p in phantom if not moff.inside(p)],
          f"{len(phantom)} probes where phantoms would land")

    #  The imported boards, for the record: none of them is a solid this
    #  script's booleans can be trusted against, and saying so here is the
    #  point - the LCD is the exception, which is why its two intersections
    #  above are real checks.
    print("\nthe imported meshes (informational)")
    for name, tris in (("pi", stl_rpi), ("wittypi", stl_wit),
                       ("lcd", stl_lcd)):
        sh, bd = mesh_health(tris)
        note(f"{name}: {len(tris)} triangles, {sh} shells, {bd} unshared edges",
             "closed - booleans are meaningful" if bd == 0
             else "NOT closed - an intersection with it returns 0 regardless")

    # ---- report ---------------------------------------------------------
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} passed")
    if bad:
        for name, _, detail in bad:
            print(f"  FAILED: {name}  {detail}")
        return 1
    print("all geometry checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
