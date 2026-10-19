# Pi-stack case

Parametric OpenSCAD enclosure for the Raspberry Pi 3 + WittyPi + 3.5" SPI LCD
stack. This is the first of the three physical boxes in Project Crimson; the
ESP32/analog case and the electrode belt housing come later.

```
pi-stack.scad          the design - single source of truth
stl/                   exported, printable parts
preview/               rendered views (v0.6-*.png)
  v0.6-parts           each part on its own
  v0.6-joints          the two joint lines, part by part
  v0.6-stack           the electronics alone
  v0.6-internals       bezel off
  v0.6-assembly        everything together
  v0.6-underside       the counterbored holes the Pi screws go up through
  v0.6-section         the CUT_AWAY switch, doing its job
```

Open `pi-stack.scad` in OpenSCAD and turn on
**Design → Automatic Reload and Preview** — it rebuilds on every save.
Set `PART` at the top to `"base"`, `"mid"`, `"bezel"`, `"assembly"`,
`"all"` (all three laid out for printing), `"stack"` or `"boards"`.

To export:

```sh
openscad -o stl/pi-stack-base.stl  -D 'PART="base"'  pi-stack.scad
openscad -o stl/pi-stack-mid.stl   -D 'PART="mid"'   pi-stack.scad
openscad -o stl/pi-stack-bezel.stl -D 'PART="bezel"' pi-stack.scad
```

### Looking inside

Below `PART` there are two blocks of preview switches. They only affect what
is drawn on screen — every export above ignores them completely.

```
SHOW_BASE / SHOW_MID / SHOW_BEZEL      the three case parts
SHOW_PI  / SHOW_WITTY / SHOW_LCD       the electronics
CUT_AWAY  = "none" | "+X" | "-X" | "+Y" | "-Y"
CUT_AT    = 0.50                       where the plane sits, 0..1 across
```

Switch anything off and it simply is not built, so it hides nothing either.
`CUT_AWAY` cuts the named half clean away, case and boards together, so you
can read the clearances straight off the cut face. `preview/v0.6-section.png`
is that switch doing its job.

One caveat: the assembly preview contains imported meshes, and the vendor LCD
model is a surface model rather than a closed solid. That has always stopped
OpenSCAD's CGAL path (`F6`, and `openscad -o`) from converting the assembly, so
**section it in the interactive preview (`F5`), which uses OpenCSG and handles
it fine.** The three printable parts are all closed solids and export clean.

## Why three parts

The LCD window is 74 × 49 mm; the Pi is 84.92 × 56.00 mm. The Pi therefore
cannot pass through the top, so a one-piece shell could never be assembled
around it. It splits bottom-up:

| part  | z range (mm)  | contains |
|-------|---------------|----------|
| BASE  | 0 … 5.50      | floor, four counterbored Pi screw bores, and a rim that clears the whole board |
| MID   | 5.50 … 39.76  | every port opening, the LCD shelf, the service openings — **the shim that sets the stack height** |
| BEZEL | 39.76 … 46.86 | LCD pocket, 74 × 49 window, six counterbored screws |

Outer envelope **95.62 × 66.70 × 46.86 mm**, interior 85.62 × 56.70 mm,
wall 5.00 mm.

### The BASE is a low tray on purpose

The joint sits at 5.50 mm, just under the lowest thing on the Pi — the
microSD socket at 6.01 and the Ethernet shell at 5.93. That 0.43 mm is the
whole point: the rim passes under the entire board, so the Pi drops straight
in and nothing has to be threaded past a connector. Lowering it further buys
nothing and costs thread depth in the screw pilots.

Because the rim is below everything, **the BASE cuts no ports at all**.

### Every port opening is a three-sided notch

All six openings live in the MID, and each is taken right down through the
MID's bottom edge, so it is a slot open at the bottom rather than a closed
rectangle. That is a hard assembly requirement, not a style choice: at step 4
the MID slides **down** over a stack that already has its connectors plugged
in and sticking out through the walls. A closed rectangle comes down onto the
top of the Ethernet shell at z 22.43 and stops dead, 17 mm short of seating.

Nothing is given up in service. Once assembled, the BASE's rim closes the
bottom of every slot from below, so a plugged connector still sees a closed
opening — see `preview/v0.6-internals.png`, front and side2.

### Clearance round the ports

`PORT_G = 0.75 mm` per side, so 1.5 mm of slack around a plug body. This is a
hand-assembled prototype and a USB lead's overmould has to clear the wall as
it goes in.

The one place that forced a decision is the dual USB deck. Its two USB-A
shells measure 2.52 mm apart, so cutting them as two openings with `PORT_G`
round each would leave a **1.0 mm post** between them — far too thin to
survive a plug. They are cut as a single opening, as the real dual-deck
connector and every commercial Pi case does it.

### The seam

Each joint carries a shallow groove round the outside — 1.60 mm tall, 0.60 mm
deep — cut by both neighbours, so together they leave one clean division line
that reads on the printed part and in the render. The renders also colour the
three parts differently (`v0.6-joints.png`).

The inner cut of the groove is the part's own outline offset inwards by
`SEAM_D`, corners included: same corner centres, radius reduced to
`3.0 − SEAM_D`. Reusing the part's own radius leaves a groove only 0.58 mm
deep at the four corners, and the ligament to the screw bores drops to
0.59 mm — which is how that was found.

## Hardware

- 4 × **M2 × 12 mm** pan head, **up from underneath**, + 4 × M2 nuts.
- 6 × **M2 × 45 mm** pan head, down through the BEZEL and the MID into the
  BASE. The length is tight and falls out of the stack: the head sits at
  `OH − CBORE_DEEP` = 45.26 and must clear the joint at 5.50, so anything
  under 40 mm grips nothing at all. The pilots are cut **clean through the
  BASE's floor**, so a slightly long screw cannot bottom out and jack the
  joint open — at worst its tip shows a few tenths below the case, where
  nothing sits. They also drain, and they print without a trapped void.

### The Pi is screwed in from the underside

The four mounting holes in the BASE are **clearance bores with a counterbore
in the case's underside**, not blind self-tapping pilots, so all four screws
go in from outside the box. The whole stack can be built on the bench and
dropped in.

That decides the mechanics, and it is worth being explicit about why the nuts
are there. A screw driven from below has its head on the *far* side of the PCB
from the boss's shoulder, and the boss is part of the same solid the head is
pressing on — so tightening it is self-reacting and clamps nothing. The board
has to be pinched between something below and something above, and with the
head underneath that something has to be a **nut on top of the PCB**.

The nuts cost nothing in height: the PCB top is at 8.93 and the WittyPi sits
at 19.93, so there is an 11 mm gap up there. Two of the four sit under the
WittyPi, which is fitted after.

Sizing: `PI_CBORE_D` 4.30 for an M2 pan head (dk 4.0), leaving 1.10 mm of boss
wall and 1.25 mm of floor under each counterbore. That is what caps the head
at M2 — an M2.5 head is Ø5.0 and would leave 0.75 mm of wall. The screw seat
is at 1.35, the PCB top at 8.93 and a nut is 1.6 tall, so a 12 mm screw lands
its tip 2.8 mm proud, well inside the header gap.

## Assembly

1. Drop the Pi into the BASE; the rim clears the whole board and the four
   bosses take it at the corners.
2. Four M2 × 12 up from **underneath** the BASE, through the counterbored
   floor holes and the Pi, with a nut on each. Access is from outside the box
   the whole way.
3. Extended header, then the WittyPi. (The WittyPi is on a Pi Zero footprint;
   only the two holes that line up need populating.)
4. Slide the MID down over the stack. Every port opening is in it, so it has
   to go on before the plugs do.
5. Drop the LCD into the BEZEL pocket, from underneath.
6. Land the BEZEL on the MID and drive the six screws down into the BASE.

## What to measure

Everything below was read off the vendor CAD in `../base/` with a real B-rep
kernel (`build123d`/OCP), not off a datasheet — STEP files are not in
consistent units (the LCD model is in metres) and their bounding boxes are
routinely inflated by construction geometry, so a kernel is the only way to
get these numbers.

| part | true size (mm) | notes |
|------|----------------|-------|
| Raspberry Pi 3 | 89.64 × 57.31 × 18.59 | PCB 84.92 × 56.00 × 1.33; holes 58 × 49 Ø2.75, inset 3.5 |
| 3.5" SPI LCD | 85.00 × 55.50 × 18.30 | surface model, 0 solids. Slab only 5.5 thick; 12.75 mm of socket hangs below it |
| WittyPi 4 L3V7 | 66.11 × 30.91 × 7.08 | PCB 65.02 × 30.22; holes 58 × 23 → Pi Zero footprint |
| ESP32 DevKit V1 | 28.15 × 51.50 × 15.01 | for the second box |

Port extents, in Pi model coordinates, as cut into the walls
(X0 X1 Y0 Y1 Z0 Z1, mm):

```
ETH   [ 17.53, 38.93, -23.19,  -7.31,  -2.00, 14.50]   +X
USB   [ 21.01, 38.93,  -4.24,  29.24,  -0.75, 16.39]   +X, both decks as one
PWR   [-41.89,-33.91, -26.90, -20.38,   0.76,  3.53]   -Y
HDMI  [-24.00, -9.00, -26.90, -15.33,  -0.75,  6.88]   -Y
AUDIO [  1.60,  8.60, -26.90, -11.90,   0.00,  6.80]   -Y
SD    [-50.71,-35.71,  -2.77,   8.23,  -1.92, -0.95]   -X, on the underside
```

### Board placement

- **The LCD must be turned 180°.** Its 26-pin socket hangs off its −Y edge at
  x +1.5…+35.8, the opposite corner of the board from the Pi's GPIO header,
  which is on the +Y edge at board-relative x −35.4…+15.4. Turned 180° about
  the panel centre the socket lands at −35.8…−1.5 / +21.4…+26.5, which is the
  header's first 13 columns to within 0.4 mm in X and 0.6 mm in Y — the way it
  actually plugs on.
- **The WittyPi is also turned 180°**, so it lies back across the Pi rather
  than hanging off the far edge. With that rotation it lands at case
  x 4.25…70.36, y 30.65…61.56.

### The numbers still needed

`EXT_HEADER = 11.00` is how far the top of the extended header stands above
the Pi's PCB top face, where the WittyPi's socket lands. It is a guess.

`LCD_UNDER_MEASURED = -1` leaves `LCD_UNDER` **derived** from the stack: the
LCD's socket is `LCD_DROP` = 12.75 long, so the slab has to sit at least that
far above the top of the WittyPi or the two collide. That gives 39.76 and the
46.86 mm case height. Assemble the stack, sit it next to a rule and read
floor → underside of the panel, then set it:

```scad
LCD_UNDER_MEASURED = 39.76;   // <- your measurement
```

`SPLIT_B`, the case height and the MID's height all follow. **Only the MID
changes size**, so a wrong guess costs one small reprint, not the whole case.

## Verification

Geometry is checked by ray-casting the exported STLs, not by eye —
`/tmp/cv_models/wallcheck4.py`. Every opening must be open at the MID's
bottom edge, open at its middle, solid above its top, and uncut in the BASE;
the BASE's rim must clear every port; the seam grooves must be 0.60 mm deep at
all four joints and absent elsewhere; the counterbores must stay buried in the
5.00 mm wall; the seam must not break into the screw bores; all four Pi bosses
must be open from the underside right through to the PCB face, with their
counterbores at the right depth and their shoulders still stopping at the
PCB; the LCD socket must land on the GPIO column; and the three parts must
stack with zero interference. All of it currently passes.

The renders in `preview/` are software-rasterised (no GPU needed) with depth
fog, which is required — without it every wall facing the same way renders as
the same flat grey and the openings are invisible. The camera basis is checked
by `cam_test.py` against a physical expectation, because a mirrored render
puts the Ethernet and USB openings on the wall opposite the one they are
really on, and that is easy to mistake for a modelling error.

## Known gaps

- `EXT_HEADER` and `LCD_UNDER` are unmeasured (above), so the case height is
  provisional. The MID is the only part that changes.
- The LCD is carried by the BEZEL's pocket and bears on the header stack below
  it. The MID's inner ledge takes its outer edge, 2.69 mm per side in X.
- The two service openings in the +Y wall are sized for a USB-C/micro-USB plug
  body (15 × 8 mm) and a Ø9 mm battery-lead grommet. Their heights put them in
  the MID, but the WittyPi's own charging input faces the **+X** wall once
  rotated, about 20 mm in, so the charging cable has to route internally from
  there to the +Y opening. If the real connector turns out to be somewhere
  else, they are two lines of parameters.
- No vents, no strain relief, no belt or carry attachment yet.
- The Pi's microSD slot exits the −X wall; the MID's notch lets the card out,
  but reaching it means pulling the case apart or using a long card.
