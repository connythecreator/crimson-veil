# Pi-stack case

Parametric OpenSCAD enclosure for the Raspberry Pi 3 + WittyPi + 3.5" SPI LCD
stack, with a strap plate bolted to its underside. **The LiPo is not in here** —
the battery enclosure is a separate build, and this case does not hold it. This
is the first of the three physical boxes in Project Crimson; the ESP32/analog
case and the electrode belt housing come later.

```
pi-stack-v0.7.scad     the design - single source of truth
pi-stack.scad          v0.6, three parts, no plate - kept as it was
ce07929-case.scad      the CE07929 protoboard case - a separate build
verify.py              geometry checks, run this before you print
render.sh              regenerates preview/v0.7-*.png
stl/                   exported, printable parts
  pi-stack-v0.7-*.stl  base, mid, bezel, plate
  ce07929-*.stl        protoboard case: base, lid (already in print orientation)
drawings/              dimensioned mechanical drawings (SVG), A3
  assembly-*.svg       the whole assembly, four views
  base/mid/bezel/plate.svg   one sheet per printed part
  make_drawings.py     regenerates all eight sheets from the SCAD constants
preview/               rendered views
  v0.7-parts           each part on its own
  v0.7-joints          the joint lines, part by part
  v0.7-stack           the electronics alone
  v0.7-internals       bezel off
  v0.7-assembly        everything together
  v0.7-base            the BASE alone: the tray, its bosses and the vents
  v0.7-plate           the strap plate on the bed, tray open up
  v0.7-pals            ...and the other way to hang it
  v0.7-underside       six case screws, then the plate's bolts, then the Pi's
  v0.7-section         the CUT_AWAY switch, doing its job
  v0.7-pads            the LCD's seat: the shelf, the notch, the support flanges
  v0.7-panel           the LED and switch rows, on the front of the case
  v0.7-midpanel        the same row on the MID alone, pockets and all
  v0.7-front           the front wall cut back, so every opening reads as a hole
  v0.7-fittings        the LED and switch rows as parts, case cut open behind them
  v0.6-*               the three-part predecessor, for comparison
```

Open `pi-stack-v0.7.scad` in OpenSCAD and turn on
**Design → Automatic Reload and Preview** — it rebuilds on every save.
Set `PART` at the top to `"plate"`, `"base"`, `"mid"`, `"bezel"`,
`"assembly"`, `"all"` (all four laid out for printing), `"stack"`, `"header"`
or `"boards"`. `"trailer"` is not one you would open by hand — it is driven by
OpenSCAD's animation clock; see *The demo video* below.

To export:

```sh
openscad -o stl/pi-stack-v0.7-plate.stl -D 'PART="plate"' pi-stack-v0.7.scad
openscad -o stl/pi-stack-v0.7-base.stl  -D 'PART="base"'  pi-stack-v0.7.scad
openscad -o stl/pi-stack-v0.7-mid.stl   -D 'PART="mid"'   pi-stack-v0.7.scad
openscad -o stl/pi-stack-v0.7-bezel.stl -D 'PART="bezel"' pi-stack-v0.7.scad
python3 verify.py
```

Every `PART` above exports a part sitting on the print bed at z = 0, and every
one of them is *authored* that way too: z = 0 is the underside of the BASE, and
since v0.7 that is also the bench. There used to be a set of `*_placed()`
wrappers adding a 21 mm tub's height to the parts above the BASE; the tub is
gone (see below), so stack coordinates and case coordinates are the same frame
and the wrappers went with it. The PLATE is the one part drawn below zero,
because that is where it hangs.

### Looking inside

Below `PART` there are two blocks of preview switches. They only affect what
is drawn on screen — every export above ignores them completely.

```
SHOW_PLATE / SHOW_BASE / SHOW_MID / SHOW_BEZEL                the four parts
SHOW_PI  / SHOW_WITTY / SHOW_HDR / SHOW_LCD                   the electronics
SHOW_LED / SHOW_SW                                            ...and the panel's
CUT_AWAY  = "none" | "+X" | "-X" | "+Y" | "-Y"
CUT_AT    = 0.50                               where the plane sits, 0..1 across
```

Switch anything off and it simply is not built, so it hides nothing either.
`CUT_AWAY` cuts the named half clean away, case and boards together, so you
can read the clearances straight off the cut face. `preview/v0.7-section.png`
is that switch doing its job, and `preview/v0.7-pads.png` is the same switch
on a different axis to show the LCD's seat.

One caveat, and one correction to it. The assembly contains imported meshes and
the vendor LCD model is a *surface* model rather than a closed solid, so
`CUT_AWAY` leaves coplanar faces for OpenCSG to z-fight over — the section
comes out striped wherever a board is cut. `render.sh` therefore renders the
section with the boards switched off. The v0.6 note went further and said this
stopped CGAL from converting the assembly at all, so `F6` and `openscad -o`
could not export it; **that is no longer true here** — `-D 'PART="assembly"'`
converts cleanly. It is not in the export list above because it is a preview,
not a printable part. The four printable parts are all closed solids and export
clean (`verify.py` checks exactly that, per part).

## Why four parts

The LCD window is 81.80 × 51.60 mm — the 85.80 × 55.60 panel less a 2.00 mm
retaining lip on every side — and the Pi is 84.92 × 56.00 mm. The Pi therefore
cannot pass through the top, so a one-piece shell could never be assembled
around it. It splits bottom-up:

| part  | z range (mm)   | contains |
|-------|----------------|----------|
| PLATE | −4.50 … +3.00  | the fabric interface — a bolt-on strap tray whose skirt wraps the case's lower 3.00 and whose four arms fan out on the corner diagonals; the arms lie in the same 4.00 floor, so nothing hangs below it |
| BASE  | 0 … 5.50       | floor, four Pi screw bosses (to z 7.60), four bolt bosses for the plate, four counterbored Pi screw bores, **six clearance bores through the rim**, five vents, and a rim that clears the whole board. The Pi bosses rise inside the MID's cavity; the outer rim stops at 5.50 |
| MID   | 5.70 … 40.60   | every port opening, the LCD shelf and its four support flanges, the **rear hex vent field and 10 × 6 battery-lead rectangle**, the front panel and its **12 × 7 accessory opening**, and **the twelve blind screw pilots — this part is the case's nut** |
| BEZEL | 40.80 … 49.20  | LCD pocket (86.60 × 57.20), 81.80 × 51.60 window, six flush counterbores + countersinks |

Outer envelope **95.12 × 66.20 × 49.20 mm**, interior 86.12 × 57.20 mm, wall
4.50 mm throughout. With the strap plate bolted on, the whole thing is
**53.70 mm** from the plate's outer face to the top of the BEZEL. The plate's
arms lie in its 4.00 slab, so they add to the footprint
(**134.89 × 99.95 mm**) but not to the height.

The table's z ranges are heights off the bench, and BASE + MID + BEZEL is the
case: the PLATE is drawn around z = 0, with its 4.00 floor hanging below the
case's underside and its 3.00 skirt standing up around the case's lower edge.

**Both printed butt joints carry a 0.20 mm axial clearance (`MATE_GAP`).**
FDM faces are not flat — first-layer squash and elephant's-foot put the two
surfaces somewhere other than the nominal plane — so the MID is modelled
starting **0.20 mm above the BASE's rim** and the BEZEL the same distance above
the MID's top, rather than in nominal contact. The outer seam groove is still
centred on the nominal joint plane, so it straddles each gap — **0.80 mm of
groove in the lower part, the 0.20 gap, then 0.60 mm in the upper** — and reads
as a shadow line rather than an open slit. The screws' preload closes
the joint when they are driven. `OH` is unchanged at 49.20, the MID is
**34.90 mm** tall — 36.60 less both gaps, and 1.50 less again because the
measured LCD is 7.00 thick rather than the mesh's 5.50 — and the LCD shelf
stays at `SPLIT_B` (40.60) so the LCD stack does not move with either gap.
`verify.py` asserts **139 checks**, including that both joints are open by the
gap in the exported solids and that the parts still do not interfere when
placed where the SCAD puts them.

**There used to be a fifth part, and it is worth saying why it went.** The
MOUNT was 21 mm of open-top tub under the BASE, and it existed to hold the LiPo
pouch. The battery came out of the design first ("we will make that
separately"), and the tub's remaining job — carrying the fabric plate and being
the hatch you reach the Pi's four screws through — was invented afterwards to
justify it. It does not hold: the plate comes off on **its own** four bolts, so
**the plate alone is the access hatch**, and the tub was a whole printed part
plus 21 mm of height for nothing. Deleting it took the case from
96.12 × 67.20 × 70.20 to **95.12 × 66.20 × 49.20** and every part above the
BASE kept its old z, so no port, no relief and no screw axis moved. The MOUNT's
five wall openings were redistributed rather than deleted, and the rear pair
have since been replaced by the hex vent field and lead rectangle — see *The
rear wall* below.

The stack is **40.00 mm** from the Pi's PCB underside to the LCD's top face,
and that one figure is what the case is sized from — see the section on it
below. Adding the parts up instead is what made an earlier version 10.21 mm
too tall.

### The plate, and why the interface is on the underside

Hanging the case by its −Z face is what puts the **LCD parallel to the
mounting plane**: the screen faces straight out from the belt instead of up the
body's side, which is the only orientation you can read while wearing it. The
case never touches fabric — it touches the plate, and the plate touches the
fabric. That also makes the mount **swappable**: any plate on this bolt
rectangle fits, and the case does not change when you find a better way to hang
it.

It bolts rather than clips because it is the first thing off and the last thing
on (see above), and four M3 bolts into printed plastic is the least that
survives being taken off and put back any number of times.

```
plate        102.12 x 73.20 x 4.00 r6.50   tray: the case + 0.50 clearance
                                           + a 3.00 skirt, all round
arms         4, on the corner diagonals at 34.85 deg to X
             root o16.00 at r 46.00 -> cut waist o12.00 at r 64.00
             -> tip paddle o20.00 at r 70.00
envelope     134.89 x 99.95 x 7.50         arms included; z -4.50..+3.00
                                           (4.00 floor + 3.50 skirt above it)
skirt        3.00 wall, 0.50 off the case, top at +3.00 above its underside
gap          0.50   to the case's underside - both are printed, and neither
                    first layer is flat, so a gap is what stops the case rocking
bolts        4 x M3 x 6, on a 62.00 x 35.00 rectangle, into blind Ø2.75 pilots
```

The tray is the **case's outline**, not a belt dimension: its inner face is
`PLATE_SKIRT_CLR` (0.50) off the case on every side, and its wall is 3.00
thick, so the case sits down into a shallow tray. That is what "hug" means
here — the skirt locates the case in X and Y and takes the side load, while the
0.50 gap under the floor keeps both printed faces from rocking on each other.

The four arms are the fabric interface, and they grow out of the same 4.00
slab. Each is a hull chain: a 16.00 root at r 46.00, a **12.00 waist at
r 64.00**, and a 20.00 tip paddle at r 70.00. The waist is the strap's seat,
and it is **cut, not implied by a neck circle**: the tip's rear arc reaches
back to r 60.00, so a hull alone measures 16.00 wide there and the groove
disappears into the paddle. Two Ø8.00 circles per arm, 10.00 off the axis, cut
a concave 12.00 seat about 6.00 long along the arm. An elastic loop stretches
over the 20.00 paddle, settles into the 12.00 waist, and the 4.00 shoulder at
the tip stops it walking off. The arms sit on the **corner diagonals** — the
longest lever the case has — and there are four rather than two because a
continuous loop can cross the back in an X and share the load between them.
`PLATE_ARM_ANG = atan(OD / OW)` is the real diagonal, 34.85°, not a
drawn-by-eye 45°.

The skirt's top is at +3.00, deliberately below the MID's ports at 5.70, so it
is a hug and not a sleeve. It is **crenellated at the BASE's five −Y vents**:
the same five 6.00 × 2.50 columns are cut through it from z 1.50 to 4.00, which
is 1.00 above the skirt's top, so each notch opens through the top edge. That
is a crenellation, not a tunnel — it prints without a bridge, and the vents
still breathe into the 0.50 gap rather than into the skirt.

The bosses stand on the **inside** of the BASE's floor, as four
Ø7.00 × **2.90** pillars, so the case's own underside stays flat and the plate's
case face has nothing to sit on but the case. Each carries one **blind Ø2.75
pilot, 5.30 deep**, running up from the case's underside through the floor's
2.60 skin and into the pillar, and stopping 0.20 below the pillar's top. The
screw comes up from under the plate and threads into that plastic — there are no
inserts in this build, and this is the only hole in the whole case that is
threaded in the BASE. The plate's own counterbores open to the **outer** face,
so nothing stands proud against the fabric.

**The bosses are 2.90 tall, and that number is set by the Pi, not by the
screw.** On the MOUNT they were 3.40, standing in a tub whose floor was 21 mm
below the Pi. Moved up into the BASE they share airspace with the board's
underside, where the Ethernet shell hangs 5.93 above the BASE's floor and the
microSD socket 6.01 — the same two figures that put `JOINT_A` at 5.50. So the
bosses stop **exactly at the rim**: `PLATE_BOSS_H` is written as
`JOINT_A − FLOOR`, and the +X pair sits under the Ethernet shell with the same
0.43 mm the rim already lives with. A 3.40 boss at this height would have driven
0.07 mm into it. `verify.py` ray-casts the imported Pi mesh over each boss's
footprint for exactly this, which is the one thing here a bounding box cannot
see — and it is measured to a mesh, not to the board in hand, so if your real
Ethernet shell hangs lower, shorten the bosses and that check is where it shows
up.

`PLATE_STYLE` picks the interface:

- **`"strap"`** (the default) — the tray and four arms above. The plate prints
  **outer face down**: the floor is on the bed, the skirt stands up around it
  and the tray is open. No support, and the only overhang is the four
  Ø6.20 × 1.65 counterbores, which bridge a 6.20 circle. The print is 7.50 tall
  — 4.00 of floor and 3.50 of skirt above it. Turning it over instead would put
  the skirt's 3.00 rim on the bed and ask the floor to bridge the whole tray,
  so `plate_placed()` lifts it rather than flipping it.
- **`"hook"`** — the older belt-edge interface: two prongs that hook the belt's
  lower edge, as a J in the Y-Z plane: a 2.00 web leaves the plate and runs out
  8.00, a 2.00 lip turns back along +Y for 6.00, and the channel between them is
  6.00 deep. The web carries the case and the lip keeps it on. The hook body is
  still 76.20 × 57.20, and it prints case-face-down with the hooks standing up;
  the only overhang then is the lip's underside, a 6.00 cantilever 2.00 thick.
- **`"pals"`** — a slot field on the webbing module: 25.40 × 6.00 slots on a
  38.10 row pitch, for threading standard PALS/MOLLE webbing. It prints
  case-face-down like the hook. All three styles bolt on the same four holes.

The three are deliberately isolated in the plate. The strap's fit is the one
thing here no measurement can settle, so a wrong guess costs a plate, not the
case.

### The BASE is a low tray on purpose

The joint sits at 5.50 mm, just under the lowest thing on the Pi — the microSD
socket at 6.01 and the Ethernet shell at 5.93. That 0.43 mm is the whole point:
the rim passes under the entire board, so the Pi drops straight in and nothing
has to be threaded past a connector. **That is also why the rim holds no
thread**: 5.50 is not enough wall to pilot a screw into, so the six screws that
clamp the BASE to the MID pass *through* it as Ø3.40 clearance bores and bite in
the MID above — see *The MID is the nut* below. Raising the joint to buy thread
here would cost the drop-in assembly and 3 mm of case height for nothing.

Because the rim is below everything, **the BASE cuts no ports at all**. It
carries five things: the Pi's four screw bosses, the plate's four bolt bosses,
the six clearance bores through the rim, the five vents in its −Y wall, and the
rim itself. Its underside is the face the plate's floor lies under, so it is the
one part whose flatness matters — there is no seam groove in it (`seam(0)` was
removed with the MOUNT) and `verify.py` ray-casts the case's whole underside to
prove the lowest surface is 0.00 everywhere.

### Every port opening is a three-sided notch

All six openings live in the MID, and each is taken right down through the
MID's bottom edge, so it is a slot open at the bottom rather than a closed
rectangle. That is a hard assembly requirement, not a style choice: at step 3
the MID slides **down** over a stack that already has its connectors plugged
in and sticking out through the walls. A closed rectangle comes down onto the
top of the Ethernet shell at z 22.43 and stops dead, 17 mm short of seating.

Nothing is given up in service. Once assembled, the BASE's rim closes the
bottom of every slot from below, so a plugged connector still sees a closed
opening — see `preview/v0.7-internals.png`.

The **rear (+Y) wall** is the exception. It carries no Pi port at all, so
nothing there has to pass a connector mid-assembly. Its old charging slot, Ø9
battery-lead grommet and two Ø3.20 cable-tie holes have been **removed at the
user's request** and replaced by a **hexagonal vent field** and a **10 × 6 mm
battery-lead rectangle** at the field's left. Both are closed holes, not slots;
the lead is therefore threaded during assembly rather than dropped in
afterwards. See the assembly order.

The **accessory opening** below the switch row is a closed rectangle for the same
reason, and it is worth being explicit that this is safe: the MID descends over
everything that stands proud of the wall, and at this opening's height (stack z
19.13 … 26.33) **nothing does**. The nearest board material in its footprint is
25.65 behind the wall's inner face, and the highest thing on this face below it
is the audio jack, which tops out at 14.73 (its opening's edge at 15.48, with
`PORT_G`) — 3.65 under the opening's floor. It is the one opening in the case
that is free to be a plain closed rectangle, because there is no connector to
pass.

### Clearance round the ports

`PORT_G = 0.75 mm` per side, so 1.5 mm of slack around a plug body. This is a
hand-assembled prototype and a USB lead's overmould has to clear the wall as
it goes in.

The one place that forced a decision is the dual USB deck. Its two USB-A
shells measure 2.52 mm apart, so cutting them as two openings with `PORT_G`
round each would leave a **1.0 mm post** between them — far too thin to
survive a plug. They are cut as a single opening, as the real dual-deck
connector and every commercial Pi case does it.

**The Ethernet and USB openings are now one stepped opening.** Cut separately,
their clearance boxes left a **1.57 mm free-standing web** between the
Ethernet's +Y edge at 24.13 and the USB's −Y edge at 25.70. At the user's
request that web is gone: the cutter overlaps 1.00 mm into each opening and
runs 0.50 mm above the USB opening's top, so the two read as a single stepped
opening in the +X wall. The merged opening still clears both connectors by
`PORT_G` on every remaining edge, and the wall closes it fore and aft
(`verify.py` probes 12 points across the old web band and both solid ends).

### The rear wall: a hex vent field and the battery lead

The **+Y wall** is the one face the Pi puts no ports on. It used to carry a
15 × 8 mm charging slot, a Ø9 battery-lead grommet and two Ø3.20 cable-tie
holes. At the user's request those are gone. In their place:

- a **hexagonal vent field**: 18 holes, each **7.00 mm across the points and
  6.06 mm across the flats**, on a **9.00 × 9.00 mm stagger**. Columns run at
  x 17.00, 26.00 … 62.00 and odd columns sit half a row up, which is what makes
  the pattern read as a honeycomb; the webs are 2.00 mm along X and 2.94 mm
  between flats. The field spans **x 13.50 … 65.50, z 8.97 … 37.53**.
- a **10.00 × 6.00 mm rectangle** at **x 70.00 … 80.00, z 17.00 … 23.00**,
  on the field's left as seen from behind the case. The pack's lead goes
  through this instead of the old round grommet.

The field keeps **1.60 mm** from the case screw column at x 9.00 and **4.50 mm**
from the lead rectangle; the rectangle keeps **3.22 mm** from the column at
x 86.12. Both stop well clear of the joint at 5.50 and the LCD shelf at 38.60.
Every cut starts 1.00 mm inside the wall's inner face and runs outward, so
nothing can break through the opposite (−Y) wall.

### The front panel

Three 5 mm indicator LEDs and three 6 × 6 mm tactile momentary switches, in the
MID's **−Y** wall — the same face the power, HDMI and audio ports are on, so
everything you touch or look at is on one side. Under the switch row, and on the
same wall, there is also a **12 × 7 mm accessory opening**.

```
   x  26   33   40       50    59    68
        o    o    o       [ ]   [ ]   [ ]
      LED  LED  LED       SW    SW    SW
                         +-------------+
                         |  12 x 7 R1.5 |   <- the accessory opening
                         +-------------+
```

**Where it can go is a narrow band, and that is worth stating.** The −Y wall is
only free between stack z **15.56** and **38.60**:

- below, the HDMI opening tops out at 15.56 — the highest of the three ports on
  this wall;
- above, the LCD shelf begins at `SPLIT_B − SHELF_T` = 38.60.

Nothing can go higher than that. Above the shelf is the BEZEL, whose rim is only
4.26 wide at the pocket, with the LCD slab 0.40 mm behind it, so the bezel can
never take a hole. The row sits at stack z **33.00** (54.00 off the bench, 77% of
the height), and the switch bodies span 30.00 … 36.00, clearing the ports by
14.4 mm and the shelf by 2.60 mm.

It is also clear of the LCD socket (x 11.81 … 46.10, y 54.50 … 59.58) and of the
two `M3` bores in this wall, at x 9.00 and 86.12 — the leftmost LED bore is
17.0 mm off the nearest one, and there is nothing between them at all.

**The LEDs** are 5 mm through-hole parts: a Ø5.20 plain bore at 7.00 pitch,
Ø5.00 body, Ø5.90 flange 0.50 thick, 8.60 overall. They push in from the cavity
and the **flange is what stops them** against the inner face — the 8.10 barrel
then fills the 4.50 wall and stands **3.60 mm proud** of the outer face. There
is no counterbore, deliberately: an LED's flange is at its **base**, so sinking
it into a recess moves the lens *out*, not in. The plain bore is what sets the
proud figure, and a flangeless LED would push straight through.

**The switches need a pocket**, because a 6 × 6 tactile has no flange to stop it.
Each gets a Ø3.60 button hole through a **0.45 mm lip** left in front of the
body, and a 6.20 × 6.20 pocket sunk 4.05 into the 4.50 wall behind it.

Two details there are load-bearing:

- **Two crush ribs, 0.20 mm proud**, on the pocket's ±X faces, narrowing it to
  5.80 for a 6.00 body. A plain interference fit would let the printer's
  tolerance decide whether the switch falls out or will not go in; ribs deform
  and grip either way. They are cut by subtracting the rib *volume from the
  cut*, which leaves material standing where the rib is and the pocket 6.20
  everywhere else.
- At `SW_H` = 5.00 the pocket reaches the wall's inner face and leaves **no
  floor** behind the body — which is the point, not an oversight. The four
  terminals of a 6 × 6 tactile are strips that hang *outside* the body and splay
  to 7.20 across, wider than the 6.20 pocket, so they have to clear the wall
  altogether and run free in the cavity. The body spans y 0.45 … 5.45 and its
  terminals run 5.45 → 8.96 at stack z 29.10 … 36.90, where the nearest board is
  a long way off.

  **Four terminal notches make that clearance real.** With the 4.50 wall the
  drawn 5.00-tall body's strip tops sit at y 4.55 — only **0.05** outside the
  inner face, which is less than printed tolerance. Each strip therefore gets a
  **1.40 mm deep notch** behind it, lapped 0.20 into the pocket and the cavity.
  That gives **1.45 mm** of clearance at the drawn seat, and still **0.31 mm**
  for the measured 3.86-tall 1825910-6, whose strip tops sit deeper at y 3.41.
  The notches are 1.11 wide in X and span the strips' ±Z reach; the lip, the
  ribs and the rest of the wall are untouched. `verify.py` proves both cases
  with a point lattice and checks the wall below and between the notches.

The pocket is sized straight off `SW_H`: the cut is the body's own height,
started at the lip. Set `SW_H` to your switch and everything else follows — a
taller body runs out the far side of the wall on its own, a shorter one stops
inside it and leaves a floor. See the known gaps.

**The accessory opening** is the fourth thing on this wall and the only opening
in the whole case that **no component asked for**. It is sized to the request —
**at least 12.00 × 7.00** — and cut at **12.20 × 7.20** so the *printed* hole
still clears the minimum after the slicer's usual hole undersize, using the same
`+0.20` the switch pockets take for the same reason. Its corners are filleted at
**R1.50**, because a 90° internal corner is where a printed wall starts a crack
when it is flexed or levered off the bed. It is a plain bore: no lip, no
counterbore and no chamfer, so there is nothing here to take strain off a cable.

It sits centred under the switch row at **x 59.00** (x 52.90 … 65.10) and
centred in the free band above the ports, stack z **19.13 … 26.33**. The band
between the HDMI opening's top edge (**15.56** — the highest port on this wall,
and the number the whole panel is measured from) and the switch pockets' floor
(**29.90**) is 14.34 tall, so the opening leaves **3.57 mm of wall above it and
3.57 below**. It is 12.90 clear of the LED row's right-hand bore and 43.90 /
21.52 clear of the two `M3` columns that run this wall's full height.

**There is nothing behind it.** A pass-through opening that emptied into the
back of a board would be useless, so this is measured rather than assumed. In
the opening's whole x/z footprint the nearest material of any of the three
boards is the WittyPi's, at case y 30.65 — **25.65 mm behind the wall's inner
face**. The Pi's tall parts are its Ethernet and USB shells at 22.43 and its
GPIO header, none of which is in this x/z window, and its PCB is *below* the
opening altogether (top face 8.93, so 10.20 under the opening's floor). What the
opening passes is 25 mm of free space at every depth — enough for a plug body
and a bend radius.

That check has to be done differently from every other board check in
`verify.py`, and the difference is worth knowing: the imported Pi and WittyPi
meshes are open **surfaces**, so a point-in-solid ray cast through them returns
nonsense. A triangle-level overlap test needs no closed surface at all, so the
suite carries a separating-axis test and asks that instead — *no triangle of the
Pi, the WittyPi or the LCD crosses the corridor*, which is a statement that holds
for a surface mesh.

### The reference hardware

The panel was designed *around* three LEDs and three switches, and until v0.7
it contained only their **negative** space — three bores and three pockets.
Both parts are now geometry: `led()` and `switch()` in the `.scad`, placed on
the panel's own constants, drawn wherever `electronics()` is and switchable
with `SHOW_LED` / `SHOW_SW`. `v0.7-panel` shows them seated in the front face and
`v0.7-fittings` shows them standing off the wall's inner face with the case cut
open behind them.

That matters for two reasons. The obvious one is that the assembly now reads.
The other is that `verify.py` used to confirm the panel by probing a synthetic
6 × 6 × `SW_H` box it built in Python — the last thing in the suite measuring a
guess. Those probes are now asked of the exported part meshes, which fail when
the `.scad`'s geometry drifts even though its arithmetic has not. **That is how
the terminal conflict below was found.**

**The switch is measured.** `base/te-tactile-momentary-switches-1.snapshot.1/
1825910-6.step`, by walking `MANIFOLD_SOLID_BREP → CLOSED_SHELL → … →
VERTEX_POINT → CARTESIAN_POINT` and taking extents, origin at the body's
underside and centre. The README used to call these files unusable because
there is no B-rep kernel here — that was wrong for extents, which need no kernel
at all, only the unit prefix read (`SI_UNIT(.MILLI.,.METRE.)` vs the bare metre
form these use). In millimetres:

| `1825910-6.step` | measured | drawn as |
|---|---|---|
| body | 5.99 × 5.99, R0.25 corners, z 0 … 3.86 | 6.00 × 6.00 × `SW_H` |
| pressed metal lid | 5.99 square × 0.25, z 3.36 … 3.61 | inside the body |
| raised centre | 4.99 square on R0.375, z 3.36 … 3.86 | tops out at `SW_H` |
| actuator | Ø3.50, z 2.11 … **4.61** — 0.75 proud | `SW_ACT_D`, `SW_ACT_UP` |
| terminal strip ×4 | 0.71 wide × 0.60 thick, at x ±(1.91 … 2.62) | `SW_LEG_W`, `SW_LEG_D` |
| …its splay | **flush with the body's side and 0.60 beyond it** | `SW_LEG_Y0/Y1` |
| …its height | **0.90 above the body's underside to 3.51 below** | `SW_LEG_UP`, `SW_LEG_L` |

Two of those need a word.

The **terminal splay** is what the old prose called a "6.5 × 4.5 footprint".
Measured, the pattern is **6.60 × 4.535** — the prose was right to 0.10 on the
long axis — but a pattern is centres, not extents, and extents are what a pocket
has to clear. The strips are **7.20 × 5.22** overall: 5.22 fits the 6.20 pocket
with room to spare, and 7.20 does not.

The **vertex bounding boxes are traps** in two places, and both are in the
table above. A filleted square's extreme *vertices* are its tangent points, not
its corners, so the lid reads 5.49 across when it is really 5.99, and the raised
centre reads 4.24 when it is 4.99 — which is why `SW_TOP` is 4.99 and not 4.24.
And the terminal solid's box is 0.905 deep where the flat strip is 0.60: the
extra 0.305 is a retention barb that pokes out at one height only, 2.48 below
the seat plane — deep in the cavity at case y 7.93, where nothing cares. Reading
the box as the strip would have made the overhang below 0.80 instead of 0.50.

**The LED is not measured, because there is nothing to measure.**
`base/3mm-led/3mm_LED.stp` is three solids of pure construction geometry — a
6.13 × 0 × 3.64 plane and two 13 mm slivers — the `.igs` beside it is in inches,
and the datasheet is an outline-only AutoCAD plot that `pdftotext` reads as one
byte. The fitted part is a 5 mm through-hole LED, so its figures are the
published ones: **Ø5.00 body, Ø5.90 flange 0.50 thick, 8.60 overall**, with
0.45 square leads on 2.54 centres, drawn 2.50 long because nothing here knows
how much of them you will cut off.

**The drawn switch is a stretch, and it is the honest kind.** `SW_H` is 5.00
where the vendor part is 3.86. The model draws the measured part with its
one full-section tier extended to `SW_H − SW_TOP_H` — everything else stays as
measured, the actuator included — so the drawing follows `SW_H` if it is ever
set to a real measurement, exactly as `SW_POCKET_CUT` already did. The real
3.86 body seats at y 4.31 instead of 5.45, which puts its strip tops at 3.41 —
deeper into the wall than the drawn part, and the reason the notches below are
1.40 deep rather than the 0.60 the drawn part alone would need. At `SW_H` =
3.86 the pocket would also leave a **0.19 mm floor** behind the body; at the
drawn 5.00 it breaks through and leaves none.

**And the one number that came out of all this as a defect — now closed.** Two
axes were in play and they are not the same number. In the **splay** axis each
strip's outer face sits at ±3.60 against the pocket's wall at ±3.10 — it pokes
**0.50** out past it. In **y** the strip's top is `SW_LEG_UP` = 0.90 above the
body's underside. On the old 5.00 wall the drawn body seated at 5.45, putting
that top at 4.55 — **0.45** past the wall's inner face, overlapping over
0.50 × 0.45.

That understated the problem, because 0.45 is the overlap **at the drawn
position**, not the depth the switch can reach. The strip is 4.41 long in y —
0.90 up into the body plus 3.51 out the back of it — and the overhanging 0.50 of
each flank runs the *whole* of that length, while the wall it had to cross was
solid from the outer face to the inner one. The flanks cleared at exactly two
depths: body front at y ≥ 0.90, which is 0.45 deeper than the lip lets the body
go, or body front at y ≤ −8.51, which is the switch held outside the case.
Everywhere between, the terminals were in wall — and there was no way to get
from outside to either. **The switch did not fit.**

The fix, now taken, is **four clearance notches per switch**: 1.11 wide in x
(the 0.71 strip plus a 0.20 lap each side), 1.40 deep from the wall's inner
face, lapped 0.20 into the pocket and the cavity, and spanning the strips' ±Z
reach. At the drawn 5.00 body that is **1.45 mm** of clearance; the measured
3.86 body seats deeper and still has **0.31 mm**, against `ASSEMBLY_TOL` = 0.25.
`verify.py` probes a lattice over every notch — 0/768 points left in MID
material — and checks that the wall below the notches and between each pair is
still solid, so the relief cannot quietly cut the wall through.

**One more fit, and it is tight on purpose.** `SW_BTN_D` = 3.60 was chosen before
the actuator was measurable. The measured actuator is Ø3.50, so the button hole
leaves **0.05 mm radially** — the tightest fit in the panel, and the reason the
crush ribs have to locate the body at all rather than letting it float.

### The CE09547 header, and the three numbers it brings

The Pi gets a Core Electronics **CE09547 2×20 ultra-long stacking header**, and
its height is what the whole case grew around. Published: **23.50 mm total,
14.50 mm pins**. That is 12.50 more than the `EXT_HEADER = 11.00` the case was
built on, and every height above the Pi's PCB moved with it.

The one thing to know is that **the header's CAD in this repo is not this
part.** `../base/2x20-stacking-header-1.snapshot.1/` is a shorter header (a
5.08 × 51.5 × 8.5 insulator on ~11.3 pins, an Adafruit 2223-alike, 16.4
overall) and its solids sit in rotated local frames, so even parsing it
measures the part's own frame rather than its assembled size. So the two
published figures above are *authoritative over that model*, and the case is
built on them:

```
total   23.50   above the Pi's PCB top face, where the WittyPi's socket lands
pins    14.50   standing above the body's top face
body     5.08   <- the one number here that is NOT published.  See below.
```

`23.50 − 14.50 = 9.00` is where the body's top face sits, and the body is
**5.08** because its underside has to sit high enough above the Pi's own GPIO
header to swallow it. Measured off the Pi's mesh, that header's insulator tops
out 2.50 above the PCB top and its pins at 8.00, so a 5.08 socket on a 3.92
standoff clears those pin tips by 1.00 while engaging them 4.08 deep.
`3.92 + 5.08 + 14.50 = 23.50` exactly — which is why 5.08 is the value and not
a guess. It is also 5.08 on the reference CAD.

What that leaves, in stack coordinates (z 0 = the BASE's underside):

```
Pi PCB top        8.93
Pi GPIO insulator 11.45 top, its pins to 16.95
CE09547 body      12.85 .. 17.93        pins 17.93 .. 32.43
WittyPi PCB      20.72 .. 27.80         its socket swallows 11.71 of the pins
LCD socket       27.80 .. 40.60         the top 4.63 of the pins are inside it
```

**`WP_SOCK_D = 11.71` is derived, not published.** It is the depth the WittyPi's
socket swallows, and it falls out of the measured stack: the LCD's 12.80 socket
lands on the WittyPi's top face, so the WittyPi's PCB sits 19.88 below the LCD
slab — and the pins, which stand 32.43 above the BASE's floor, therefore reach
11.71 into it. Nothing in this repo states how deep that socket really is, so
`verify.py` asserts the consequences instead: that all 40 pins pass through it,
that it is solid between the holes (so the socket is aligned), and that what
stands proud above it is less than the LCD's own socket can cover. 11.71 is
deep for a 2×20 socket — check it against the real part.

### The LCD seats, and the four flanges that stop it being pushed in

This was a real defect, not a missing feature. The LCD's 26-pin socket hangs
**12.80 mm** below its slab (measured off the mesh: x 12.31 … 46.60,
y 55.00 … 60.08). The MID's shelf ring — the feature whose top face *is* the
LCD's seat plane — had its inner edge at y 59.20, so 0.88 mm of socket was
inside the +Y ledge and **the LCD jammed 12.8 mm high, standing on its own
socket**. That is precisely the path that puts a finger's worth of force into
the GPIO header pins.

Three things fix it:

1. **The ledge is notched** for the socket, x 11.06 … 47.35 (the socket's
   footprint plus 1.00 all round), full ring width. The cut stops on the wall's
   inner face, so the wall itself is untouched, and it overshoots 1.00 past the
   ledge above and below — a cut landing exactly on an existing face is the one
   thing CGAL will not forgive (see the verification notes). What survives of
   the +Y ledge is x 5.00 … 11.06 and 47.35 … 90.62; the LCD keeps 594 of the
   681 mm² of ring bearing it had, and most of what it loses was under a socket
   that was never going to touch it anyway. **The ledge was never the problem.
   The notch is what makes it work.**
2. **Four support flanges** stand on the ring, one per wall — the ring bears on
   the LCD's *edges*, and the flanges are what stops a thumb in the middle of
   the screen from being the thing that takes the load. Each reaches 8.00 in
   from the wall, 12.00 along it, and is `SHELF_T` = 2.00 thick with its top
   coplanar with the ring, so the LCD sees one continuous seat rather than a
   ring with four lumps on it. Four, because the load case is a fingertip
   anywhere on the glass and one flange leaves three quadrants with nothing
   behind them. They are cantilevered off the wall with no web beneath —
   sound at this size, since 5 N on one of them at a 20 N press bends it under
   0.05 mm — and deliberately not a closed frame, because the LCD's edge has
   only `LCD_FIT` = 0.40 mm of fit in X and 0.80 in Y and a frame would eat it.
3. **The BEZEL's pocket corners came in**, from r2.00 to r1.00, and the pocket
   itself is cut to the **measured** panel (85.80 × 55.60) plus 0.40 per side:
   86.60 × 57.20, which is 0.24 wider than the cavity on each X side and leaves
   a 4.26 rim. The LCD's PCB is a rectangle and the pocket is a rounded one, so
   at r2.00 the four corners fouled by **0.195 mm each** — enough to hold the
   LCD proud of its shelf and load the pins, which is exactly the failure this
   case exists to prevent. At r1.00 the corners have 0.37 mm of clearance and
   `lcd ∩ bezel` is empty.

**The case is cut to the measured panel, not to the reference mesh.** The part
in hand measures **85.80 × 55.60 × 7.00**; the mesh in `../derived/` is
85.00 × 55.50 × 5.50 and is only good for the socket footprint and the screen
top. So the pocket is **86.60 × 57.20** (`LCD_W + 2 × LCD_FIT`; 0.40 per side in
X, and 0.80 in Y because the cavity depth is already 57.20), the window is
**81.80 × 51.60** — the panel less `LCD_LIP` = 2.00 per side, which is the
bezel material that holds the LCD down without creeping over the screen — and
`LCD_T` is 7.00. The window still clears the 74 × 49 visible area by 3.90 in X
and 1.30 in Y (`WIN_CLR` = 0.40 is the floor it is checked against), and it
keeps 1.31 mm from the nearest countersink. The extra 1.50 is all above
the PCB, so the shelf still meets the PCB's underside: `SPLIT_B` moves from
42.10 to **40.60** and `OH` stays at 49.20. `verify.py` re-checks all of this as
boxes against the measured size, because the imported mesh cannot prove a panel
it does not model.

Where the flanges may sit is fixed by the LCD's own underside: the socket box
above, and three shallow components. All four rectangles are clear of both by
construction, and `verify.py` re-checks them **against the mesh rather than
against the numbers** — each flange must bear on bare PCB (no mesh vertex below
the slab over its footprint) and be at least 60% inside the panel's outline.

The load path is: finger → glass → LCD PCB → flange and ring → MID wall → the
**twelve M3 × 14** clamped into that wall, six from each end → BASE floor →
plate → fabric. **The LCD's socket is never load-bearing**, and neither is the
BEZEL: a press on the glass reaches the MID's wall directly, and the MID is the
one part every screw in the case bites into.

### The MID's two relief cuts

Two places where a *component's* outline ends up inside a wall. Both are 1.00
of a 4.50 wall, in a patch nothing else is in, and both start below the MID's
own bottom edge so the MID can still be slid down over the stack.

- **The +Y wall, for the header's body.** The body is 8.50 in Y (a borrowed
  number — see above) and centres on the Pi's GPIO, whose centre is 3.50 in from
  the Pi's PCB edge, so the body overhangs that edge by 0.75 — as every stacking
  header does — and the case leaves only `CLR` = 0.60 there. The body's +Y face
  therefore lands at 62.35 and the wall's inner face is at 62.20: 0.15 mm of
  header inside the wall, and the MID could not be slid down over it. The relief
  runs x 11.70 … 66.00, z 4.50 … 19.43, and stops 1.00 clear of the M3 clearance
  bore's own edge at x 10.70. It would be tempting to start it at 10.70, which
  is exactly *on* that bore over the relief's whole height — a knife-edge of
  wall between two holes, which is a breakage waiting to happen and buys
  nothing.
- **The −X wall, for the WittyPi's board edge.** The WittyPi's mesh is 66.10
  wide with its −X edge at case x 4.25, and the wall's inner face is at 5.00:
  0.75 inside. The relief covers y 33.85 … 59.05 and the board's whole 7.08 of
  standoff in z (21.22 … 30.30), not just the bare PCB — so no cut face lands on
  a face of anything, and nothing on the board's far side can be the thing that
  fouled.

Both are measured against the *imported meshes*, which is worth a caveat of its
own: see the gaps.

### The seam

Each of the **two** real joints carries a shallow groove round the outside —
1.60 mm tall, 0.60 mm deep — cut by both neighbours, so together they leave one
clean division line that reads on the printed part and in the render. The
0.20 mm `MATE_GAP` sits in the middle of that groove: the lower part receives
0.80 mm of it, the upper part 0.60 mm, and the gap between them is only 0.60 mm
deep, so it reads as the shadow at the centre of the line rather than as a slit
you can see through. The renders also colour the four parts differently
(`v0.7-joints.png`).

Two, not three: the plate is bolted on and stands 0.50 mm clear, so it shares no
face with anything and has no seam. And the **BASE's bottom edge has no groove
either** — `seam(0)` was cut there to mark the MOUNT/BASE joint, and with the
MOUNT gone that edge is the face the plate lies on. A 0.60 mm groove in it would
leave the plate rocking on four ridges. `verify.py` asserts both facts: the
groove is gone from the BASE's underside, and it is still there at the BASE/MID
joint.

The inner cut of the groove is the part's own outline offset inwards by
`SEAM_D`, corners included: same corner centres, radius reduced to
`3.0 − SEAM_D`. Reusing the part's own radius leaves a groove only 0.58 mm
deep at the four corners, and the ligament to the screw bores drops to
0.59 mm — which is how that was found.

**...and the groove now stops at every screw.** The bores are Ø3.40 and sit on
the wall's centreline, so a bore's edge is only **0.80 mm** in from the outer
face; a 0.60 groove cut straight across it would leave a **0.20 mm ligament**,
and the screw's own expansion is what splits that. (At M2 the same arithmetic
left 0.80 mm, which is why this never came up before.) So the cutter has a
`SEAM_PATCH` × `SEAM_CLEAR` patch taken out of it at each of the six columns —
7.00 mm along the wall, 1.90 mm in from the face, which is 1.10 mm past the bore
it is protecting. All six columns sit on straight runs well inside the 3.00
corners, so the patches are plain boxes, and every one of them lands behind a
screw head: nothing extra to look at. In the renders the two groove rings
therefore read as **six dashes each**, not as unbroken rings.
`verify.py` probes both halves of that claim at both joints — solid at each
column, groove 4.20 mm along from it.

## Hardware

**There are no heat-set inserts anywhere in this build.** Every screw threads
into printed plastic — see *Threading directly into plastic* below, which is
where the costs of that are set out.

- 12 × **M3 × 14 mm button head** — the case screws, in **two groups of six**
  that share the same six columns. Six go **down through the BEZEL's top face**
  into the MID, and six come **up from underneath the BASE** into the same six
  pilots from the other end. Both heads seat **flush**: each face carries a
  Ø5.80 × 1.65 counterbore for the Ø5.70 head, lapped by a Ø6.20 × 0.20
  countersink so the edge never stands proud of the surface. The counterbore is
  wider than the 4.50 wall, so it **breaks out through the outer side face by
  0.65 at every column** — a shallow scallop at the seam, visible on both the
  bezel's top and the case's underside. The head still lands flush and bears on
  the inboard half of the counterbore floor; the alternatives are a proud head
  or a 5.80 wall. The length window is **6.95 … 19.05 mm**, so M3 × 8 through
  M3 × 19 all fit either group; 14 is specified, giving 7.05 of bite at the top
  and 9.95 at the bottom. The lower pilot starts at `JOINT_A + MATE_GAP` but
  is still 15.00 deep, so the joint clearance moves that group's whole window
  up by 0.20 (to 4.05 … 19.05) instead of shortening the thread; the overlap
  with the BEZEL group is the 6.95 … 19.05 quoted above.
- 4 × **M3 × 6 mm button head**, **up from underneath the plate**, into the four
  blind Ø2.75 pilots in the BASE's floor bosses. The plate's counterbores bury
  these heads flush, so nothing stands proud against the fabric. Not M3 × 8 — its
  tip lands 0.15 mm above the pilot's floor, which is inside the printer's own
  hole-depth tolerance, and a screw that bottoms stands the plate off its seat.
- 4 × **M2.5 × 14 mm** pan head, **up from underneath** the BASE, through the
  counterbored floor holes and the Pi, + **4 × M2.5 nuts**. These are the only
  M2.5 in the build — the case used to be all-M2, on the grounds that one screw
  size is worth something, and M3 spent that. M2.5 is what the Pi's own mounting
  holes are for: they are Ø2.75, so an M3 will not pass through them.
- 3 × **5 mm indicator LED**, **flanged** — Ø5.00 body, **Ø5.90 flange** 0.50
  thick, 8.60 overall. The bore is a plain Ø5.20, so the flange is what stops it
  against the wall's inner face — and a flangeless LED pushes straight through.
  Those are the published figures for a 5 mm through-hole part, not a
  measurement: the vendor CAD in `base/3mm-led/` is construction geometry and
  its datasheet plots as vectors. See the known gaps.
- 3 × **6 × 6 mm tactile momentary switch**, the **TE 1825910-6** by its
  measured CAD — body 5.99 square, actuator Ø3.50 standing 0.75 proud, four
  0.71 × 0.60 terminals on a **6.60 × 4.535** pattern. **The model draws it
  5.00 deep (`SW_H`) where the real part is 3.86**, so that the drawn part
  follows the pocket rather than the other way round; set `SW_H` to whatever
  yours actually is and the pocket, the seat and the drawing all move with it.
  At 3.86 the body still fits: the four terminal notches are cut 1.40 deep,
  which leaves the measured body's strips 0.31 clear of the wall.

Ten case screws became six when the MOUNT went: the four that held the tub to
the BASE, and the pylons and pilots they needed, went with it. The six then
became twelve in the other direction, because the six that clamp the BASE to the
MID are a *separate* group from the six that clamp the BEZEL to the MID — and
all twelve still sit on the same six columns, so the case got no wider and no
taller for it. The plate's four are separate again, and so are the Pi's four:
nothing shares a fastener.

### The Pi is screwed in from the underside

The four mounting holes in the BASE are **clearance bores with a counterbore
in the case's underside**, not blind self-tapping pilots, so all four screws
go in from outside the box. The whole stack can be built on the bench and
dropped in — and because the plate comes off on its own four bolts, **the
plate alone is the hatch**: four out, plate off, and the Pi's four are looking
at you, flush in the case's underside.

None of them is reachable with the strap plate on: its tray is larger than the
case and its floor spans the whole underside, so all four heads sit behind it.
That is the deliberate trade for the skirt and the four arms — the plate is the
hatch, and it comes off first. Under the older hook plate two heads sat just
outside its 76.20 width; the tray has no such edge. The clearance is the same
either way: the plate's inner face is 0.50 mm below the case, so a flush head
never touches it.

That decides the mechanics, and it is worth being explicit about why the nuts
are there. A screw driven from below has its head on the *far* side of the PCB
from the boss's shoulder, and the boss is part of the same solid the head is
pressing on — so tightening it is self-reacting and clamps nothing. The board
has to be pinched between something below and something above, and with the
head underneath that something has to be a **nut on top of the PCB**.

The nuts cost nothing in height: the PCB top is at 8.93 and the WittyPi sits
at 20.72, so there is a 12 mm gap up there. Two of the four sit under the
WittyPi, which is fitted after.

Sizing: `PI_CBORE_D` 5.00 for an M2.5 pan head (dk 4.7), leaving **1.00 mm of
boss wall** and **1.20 mm of floor** under each counterbore, in a Ø7.00 boss
whose clearance bore is Ø2.80. That 1.00 of wall is what caps the head at M2.5
— an M3 head would need the boss out past Ø8.00, and no M3 will pass the Pi's
Ø2.75 holes in any case. The screw seat is at 1.40, the PCB top at 8.93 and a
nut is 2.0 tall, so a 14 mm screw lands its tip at 15.40, 4.45 mm proud — well
inside the 23.50 the header stands across, and none of the four is under the
header's body anyway: they sit at x 8.85 and 66.85, and the body spans
x 12.10 … 63.60.

### The MID is the nut

All **twelve** case screws thread into the MID. That is not a stylistic choice;
it is what the geometry allows:

| joint | screws | enter from | head seats | threads into |
|-------|--------|------------|------------|--------------|
| BASE ↔ MID  | 6 × M3 × 14 | the case's **underside** | flush, in a 1.65 counterbore | MID's lower pilot, z 5.70 … 20.70 |
| MID ↔ BEZEL | 6 × M3 × 14 | the BEZEL's **top face** | flush, in a 1.65 counterbore | MID's upper pilot, z 25.60 … 40.60 |

Both groups use the **same six columns** — so each column carries two blind
pilots, **15.00 deep**, drilled from opposite ends, with **4.90 mm of solid wall**
between them. Only the threads are shared; each group is a separate set of
screws, and the BASE and the BEZEL are each clamped to the MID independently,
in one action each.

The lower pilot starts at 5.70, not 5.50: it opens through the MID's underside,
which the `MATE_GAP` clearance holds 0.20 above the BASE's rim, and is drilled
15.00 from there. So the joint clearance costs bite (9.95 mm for the 14 mm
screw, still ample) but **not thread depth**.

The BASE's rim is only 5.50 tall. It stops there because that is where the Pi's
Ethernet shell (5.93) and microSD socket (6.01) are — so it holds no thread at
all, and the six screws pass through it as Ø3.40 clearance bores. The MID's wall
is 34.90 tall and can hold a pilot deep enough to matter, which the BASE's
cannot. Putting the thread in the MID is therefore what keeps the case at
**49.20 mm**; the earlier version of this design put it in the BASE and had to
grow the whole electronics stack by 3 mm to buy 7.00 mm of thread.

**15.00 mm is the depth that matters**, and it is a minimum with 0.20–0.30 of
drift allowance built into the Ø2.75 pilot. It is well past the 10 mm first
asked for, and it is the stock a stripped hole is re-driven into — there is no
insert to replace, so the extra depth *is* the repair. `verify.py` asserts the
depth, the **4.90 mm gap**, the **0.20 mm clearance at each butt joint**, and
the wall all round both pilots, from the constants and from the exported
solids, so a later edit cannot quietly take any of them away.

### Threading directly into plastic

This case has no heat-set inserts and no captive nuts anywhere. Every screw
forms its own thread in FDM plastic, and the consequences are real:

- **The failure axis is layer adhesion, not the plastic.** The BASE and the MID
  both print **open-side-up**, so their walls' layers are horizontal and the
  pilots run *along* the layers. A screw's radial load therefore pulls the wall
  apart *between* layers, not through them — and interlayer strength is a
  fraction of the filament's. The 15.00 pilot is the mitigation: it spreads the
  load over more layers and moves the failure away from the mouth.
- **The pilot diameter is the one number to test-print.** Ø2.75 is a starting
  point, not a measurement: it leaves 0.25 over an M3's shank for printing
  drift, but PLA, PETG and ASA each want a different one, and 0.1 mm either way
  is the difference between a split boss and a hole a screw turns in forever.
  Print one BASE, drive one screw, and adjust `SCREW_PILOT`
  (`PLATE_PILOT_D` follows it) before printing anything else.
- **Every cycle wears the thread, and nothing can be replaced.** An insert can be
  swapped; plastic cannot. Count on a handful of full teardowns before the holes
  loosen, and remember that the extra depth is the repair: drive the same screw
  deeper, or step up one gauge.
- **Plastic creeps under sustained load.** The plate hangs a ~400 g case
  from four M3 × 6 with only **3.15 mm of bite**, into the thinnest and most
  cycled joint in the case. Under a belt or strap, that load is permanent and
  warm, which
  is exactly the condition creep needs. Those four want re-checking after the
  first few weeks of wear; they are also the ones a stripped hole hurts most.
- **A long thread means high driving torque**, and the first few turns take all
  of it, because that is where the screw is cutting its way in. Go in slowly and
  straight, and back a screw out and start again rather than forcing it.
- **A blind pilot traps air and chips**, and a screw that bottoms out jacks the
  joint open instead of clamping it. That is why every depth here is published
  and why the four plate screws are M3 × 6 and not M3 × 8: the tip lands 2.15 mm
  short of the pilot's floor at the top and every length in the 5.45 … 19.05
  window lands clear inside the MID's.
- **A button head bears on plastic with no washer**, so the twelve will mark the
  counterbores they seat in the first time they are snugged down. That is
  cosmetic and hidden below the flush face; a washer under each is the fix if
  it matters, at the cost of the heads standing 1.0 mm proud of the case.
- **Cross-threading is the one outright assembly risk.** The BEZEL's six cross
  8.60 mm of clearance bore before they reach any thread, so there is nothing to
  guide them for the first five turns. Start every one of them by hand.

## Assembly

The order below is forced, not preferred. Two things drive it: the battery-lead
rectangle is a **closed 10 × 6 mm hole**, unlike the six port openings which are
bottom-open slots, so the lead has to be threaded as the MID goes on; and the
two groups of case screws are driven from **opposite ends**, so the BASE's six
have to go in before the BEZEL lands on top.

1. Drop the Pi into the BASE — the rim is low enough that nothing on the board
   fouls it, and all four mounting holes stay clear.
2. Four M2.5 × 14 up from **underneath** the BASE, through the counterbored
   floor holes and the Pi, with a nut on each. Access is from outside the box
   the whole way, and the plate is not on yet.
3. Extended header, then the WittyPi. (The WittyPi is on a Pi Zero footprint;
   only the two holes that line up need populating.)
4. Thread the battery lead up the **outside** of the case and in through the
   MID's **10 × 6 battery rectangle**, and plug it into the WittyPi. Do it now
   — once the MID and BASE are together there is nothing to reach through.
5. Slide the MID down over the stack, dressing the lead out through the
   rectangle as it comes. Every port opening is in the MID, so it has to go on
   before the plugs do.
6. Drive the **six M3 × 14 up from underneath**, through the BASE's rim into the
   MID's lower pilots. Do these now: the BEZEL's six thread into the same
   columns from the top, and while it is off you can still see into them. Each
   head sinks into its 1.65 counterbore until it is flush with the case's
   underside. The strap plate is not on yet — and once it is, its floor covers
   all six, so this is the only chance.
7. Fit the panel, **from inside** with the top still open: press the three
   switches into their pockets, and drop the three LEDs into their bores lens
   first until the flange lands on the wall's inner face, then wire them to the
   GPIO header. Nothing printed holds the switch pins or the wires — tie or
   heat-shrink them now, while you can still reach. Once the BEZEL is on, the
   only way back to the panel is by taking the whole stack out again.
8. Drop the LCD into the BEZEL pocket, from underneath. Its socket faces down,
   clears the notch, and lands on the ring and the four flanges.
9. Land the BEZEL on the MID and drive the other **six M3 × 14 down into the
   MID's upper pilots**. Thread them by hand for the first few turns — there is
   8.60 mm of clearance bore to cross before the thread starts, and that is the
   one place this design can be cross-threaded.
10. Secure the lead's outside run with a stick-on tie mount or tape — the old
    Ø3.2 tie holes went with the round grommet. An external pack's lead is the
    one wire here that gets yanked every time the case comes off the fabric.
11. Fit the strap plate. Stand the case on its BEZEL (on a cloth, so the window
    does not take the weight), lower the plate tray-down over the BASE, and
    drive the **four M3 × 6 down through the plate** into the BASE's bosses.
    Then turn the case over and thread the elastic over the four arm paddles,
    settling each loop into its waist. This is the last step because it is the
    first one undone: the plate comes off on its own four bolts, and that is
    what exposes the Pi's four screws.

    If you would rather keep the plate on the bench, set it outer-face down and
    lower the case into the tray to locate it, then tip the pair up to reach the
    counterbores. Either way the four bolts go in from the **outer** face, into
    the bosses.

**The lower six are behind the plate.** The tray's floor spans the whole
underside, so none of the six BASE-to-MID screws is reachable once step 11 is
done. They have to be driven at step 6, before the plate lands — and taking the
plate off is the first move in any teardown.

Disassembly is the reverse, and it is short: **plate off (4 bolts), Pi screws
out (4)**, and the board lifts out of the BASE with everything above it still
assembled.

## What to measure

Everything below was read off the vendor CAD in `../base/` with a real B-rep
kernel (`build123d`/`OCP`), not off a datasheet — STEP files are not in
consistent units (the LCD model is in metres) and their bounding boxes are
routinely inflated by construction geometry, so a kernel is the only way to
get these numbers. The CE09547 row is the exception, and it says so.

| part | true size (mm) | notes |
|------|----------------|-------|
| Raspberry Pi 3 | 89.64 × 57.31 × 18.59 | PCB 84.92 × 56.00 × 1.33; holes 58 × 49 Ø2.75, inset 3.5 |
| 3.5" SPI LCD | **85.80 × 55.60 × 7.00** (measured) | the vendor mesh is 85.00 × 55.50 × **5.50** and is what `lcd()` imports; the case is cut to the measured part, with **0.40 mm per side** in the pocket and window. **12.80** mm of socket hangs below the slab |
| WittyPi 4 L3V7 | 66.11 × 30.91 × 7.08 | PCB 65.02 × 30.22; holes 58 × 23 → Pi Zero footprint |
| ESP32 DevKit V1 | 28.15 × 51.50 × 15.01 | for the second box |
| CE09547 header | 23.50 total, 14.50 pins | **Core Electronics' published figures** — the CAD in `../base/` is a different part |

### The one measurement the height comes from

**40.00 ± 0.20 mm, from the Pi's PCB underside to the LCD's top face.** It is
`STACK_MEASURED` in the .scad, and it is spent once: `LCD_TOP_Z` from the PCB,
the slab's underside a slab-thickness below that, then the WittyPi hung
`LCD_DROP + WP_H` under the slab, because the LCD's socket is 12.80 long and
lands on the WittyPi's top face. Everything else is a measured length and the
sum is what closes the assembly.

**Do not add the parts up instead.** That is what made an earlier version
10.21 mm too tall: a sum has to assume how deep the WittyPi's socket is, and
nothing states it. The published header figure, the socket depth and the
standoff cannot all be entered by hand without contradicting each other — so
the case hangs *down* from your measurement and derives the rest. If the
measurement changes, `SPLIT_B`, the case height and the MID's height follow,
and **only the MID changes size** — a wrong number costs one small reprint,
not the whole case.

### Board placement

- **The LCD must be turned 180°.** Its 26-pin socket hangs off its −Y edge at
  x +1.5…+35.8, the opposite corner of the board from the Pi's GPIO header,
  which is on the +Y edge at board-relative x −35.4…+15.4. Turned 180° about
  the panel centre the socket lands at −35.8…−1.5 / +21.4…+26.5, which is the
  header's first 13 columns to within 0.4 mm in X and 0.6 mm in Y — the way it
  actually plugs on. **The socket is 2×13, not 2×20**: it swallows the first
  13 columns' pins and the remaining 7 columns' 14 pins stand in the clear
  pocket below the slab, which `verify.py` checks span by span.
- **The WittyPi is also turned 180°**, so it lies back across the Pi rather
  than hanging off the far edge. With that rotation it lands at case
  x 4.25…70.36, y 30.65…61.56.

## Verification

```sh
python3 verify.py
```

Exports the four parts and then answers geometric questions about them by
ray-casting the triangles — not by eye. Standard library only; there is no
numpy here, so the STL parser, the point-in-triangle tests and the XY bucket
index are all hand-rolled. Exit status is 0 only if every check passes.

**This replaces the v0.6 claim.** That README credited its verification to
`/tmp/cv_models/wallcheck4.py` and `cam_test.py`, both of which lived only in
`/tmp`, were never committed, and are gone — so "All of it currently passes"
was not reproducible from this repo. `verify.py` covers the assertions that
still matter. What it checks, in the order it runs:

- **every export is one closed shell** — every edge shared by exactly two
  triangles, and every triangle reachable from every other by edge adjacency.
  Both halves matter and they catch different things: a hole in the surface
  fails the first, and a part that has quietly become several pieces fails the
  second. See the last note below for why this one earns its keep.
- the **envelope** of each part, its position in the stack, and the two
  arithmetic invariants of the height: `LCD_TOP_Z − PCB_Z = 40.00` and
  `OH = 49.20` with **nothing at all under the BASE** (the check that would
  catch a stray part still hanging below z 0).
- the **measured stack**: the LCD's socket lands on the WittyPi's top face, the
  header's body clears the WittyPi's PCB, the pins stand proud by less than the
  LCD's socket is deep, and the **12 × M3 × 14 reach their pilots at both ends**
  — tip at 33.55 for the BEZEL group (7.05 of bite) and at 15.65 for the BASE
  group (9.95) — plus the window any M3 must sit in to fit both: 6.95 … 19.05.
- the **CE09547**, in the case: its body sits on its standoff and clears the
  Pi's GPIO insulator; it is solid through the body and empty in the standoff
  below it; it is empty between the pins and solid on one; nothing is above the
  pin tips; and **the whole body fits inside the MID** — the check a 51.50 ×
  8.50 body in an 8.50 gap fails. Plus the WittyPi's socket swallowing all 40
  pins with 18/20 between-pin probes solid (so the socket is aligned), and the
  LCD's 2×13 socket covering the 13 columns under it with no LCD material over
  the other 7.
- the **two wall reliefs**: each is cut, the wall behind it is not, neither has
  reached a screw bore, both span the outline that needs them, and each starts
  below the MID's bottom edge so the MID can still slide on.
- the **+X port band**: the Ethernet and USB openings are one stepped opening
  now — 12 probes across the old 1.57 mm web band find no MID material, and
  the wall is still solid fore and aft of the merged opening.
- the **LCD's seat**: `mid ∩ lcd` empty and `lcd ∩ bezel` empty (the first
  *failed* before the ledge was notched, the second before the pocket's corners
  came in); the notch is open and the ledge survives either side of it; the
  +Y wall behind the notch is untouched; the socket's whole 12.80 descent is
  clear over 452 probes; each of the four flanges bears on **bare PCB** with no
  mesh vertex hanging below the slab over it, and is at least 60% inside the
  panel's outline as measured off the mesh. Plus the box checks the mesh cannot
  make: the **measured 85.80 × 55.60** panel fits the 86.60 × 57.20 pocket with
  `LCD_FIT` all round; the 81.80 × 51.60 window sits inside the panel and still
  clears the **74 × 49** visible area by `WIN_CLR`; and the enlarged window
  stays clear of all six top-face counterbores.
- the **BASE**: the tray is open above at its perimeter; its **six rim bores are
  open through the rim with wall all round them** — the opposite of the blind
  pilot the M2 version was checked for, and the assertion that would catch one
  blocked or reopened into the cavity — and the plate interface on its floor:
  the four Ø7.00 bosses present, each with a **blind Ø2.75 × 5.30 pilot** open
  down through the skin, capped at the top, and no wider than Ø2.75 anywhere.
  **Every plate-boss top stops at the rim, not past it** (`JOINT_A` = 5.50), and
  the one check a bounding box cannot make — a grid over each boss's footprint
  ray-cast against the **imported Pi mesh** — finds the closest approach is
  **2.10 mm** at (15.76, 15.60).
- **the MID is the nut**: per column, both pilots open at the heights the
  screws land on, **solid wall all round both of them**, **≥ 4.50 mm of solid
  between them** (4.90), and **no receptacle shallower than the 15 mm
  requested** (15.00, with the Ø2.75 pilot giving 0.25 over an M3's core) — all
  computed from the constants, so a later edit cannot quietly trim the depth.
- **the seam keep-out**: at each of the six columns the groove is *not* cut at
  either joint, and 4.20 mm along the wall from each it *is* — both probed, at
  both joints, with the probes placed to stay clear of the port openings. Plus
  the arithmetic that forced it: the bore's edge is 0.80 mm in from the face,
  so a straight 0.60 groove would have left 0.20.
- the **plate**: one closed shell; the envelope set by the four arm tips; the
  skirt probed all round — **solid at 2.00 out, empty in the 0.50 gap, floor
  solid under the case**; zero intersection with the BASE; `plate_placed()`
  lying on the bed with the tray open up (z 0.00..7.50); the four bolts with
  their holes, counterbores, bosses and **blind pilots**; the 6 mm screw
  landing in the plastic with 3.15 of bite and its tip 2.15 short of the
  pilot's floor; **all four arms** with a root, a waist that is empty just
  outside it, a tip paddle that is solid at the same offset, and a rim that
  stops at r 80.00 — plus the four mid-edges empty, which is the X measured
  rather than drawn; the **five vent crenellations** open through the skirt
  with material beside and below them; and that the floor covers **all six
  lower case-screw mouths**, so the plate is the hatch. The check that matters
  most is the last one — **the BASE's underside is flat under the whole
  plate**, **266 probes** on a 5 mm grid over the case's own footprint, lowest
  reading 0.00. That is what would have caught a screw tip standing below the
  case.
- **joints and seams**: both parts-to-parts joints stack with **zero
  interference as placed** (no `EPS` lift — the 0.20 `MATE_GAP` means they are
  not in contact at all), each joint is probed **open at the seam and solid on
  both sides of it**, and the check the plate's seat needs — **the BASE's
  bottom edge is solid**, because `seam(0)` used to cut a groove into precisely
  the face the plate now lies on. The BASE/MID joint still has its groove,
  probed at mid-Y on two opposite walls (at `OD / 2` the probe sits inside the
  microSD port opening; the gap probes use y 20 for the same reason).
- the **rear-wall openings**: all **18 hex vent holes** open through the +Y
  wall, wall still solid on the webs between them and round the field, and the
  field clear of both screw columns; the **10 × 6 battery rectangle** open
  through +Y but **not** through −Y, solid at both flanks, and 4.50 from the
  field; plus the five vents open through the BASE's −Y wall, with the row
  inside the wall's span and clear of both screws in it.
- **the four Pi counterbores are reachable as soon as the plate is off** — the
  regression that matters most, because the strap plate is the only thing
  between you and them: the counterbore and bore are empty along each screw's
  axis from the BASE's floor face up to the PCB's underside, there is floor
  beside each counterbore for the head to seat on, and the plate's inner face
  clears the four seated heads by `PLATE_GAP`. Plus the M2.5 figures in a
  Ø7.00 boss: Ø2.80 of clearance for a 2.70 shank, 1.40 of counterbore for a
  1.40 head, leaving 1.20 of floor under it and 1.00 of boss wall round it.
- the **front panel**, which is all *negative* assertions — places that must be
  empty, plus one that must not be: the three LED bores open through the wall
  and the bore is **plain** (probing just outside Ø5.20 at *both* faces finds
  material, so there is no counterbore to carry the lens forward); the three
  button holes open through the lip and **the 0.45 lip is still solid beside
  each one** (if the pocket were cut deeper than the wall the button hole would
  run straight through and the switch would drop into the case on the first
  press); the crush ribs stand proud while the pocket either side of them is
  clear; the wall below the panel is untouched (the ports stop at 15.56) and
  the wall above it is untouched (the shelf starts at 38.60) — the check that
  catches a panel drifted out of its band, which no render would show; and
  **`LED_N = 0` / `SW_N = 0` remove the panel outright**.
- **the panel hardware**, which is the section that used to be the suite's one
  guess. There is geometry for the LEDs and the switches now, so the questions
  are asked of the exported part meshes rather than of a 6 × 6 × `SW_H` box
  Python built for itself:

  - each **switch body** sits in its pocket with 0.10 all round — probes just
    off each of the body's four faces, in cut space;
  - **the crush ribs are touching it** — the rib tips are inside case *material*
    and inside the switch solid at the same time, which is the assertion that
    the 0.10 grip is real and is the only place the case and the part meet;
  - every switch's **four terminal strips sit in their notches** and stand in
    free cavity, at the measured splay: 60 probes down the strips plus **768
    probes through every notch**, none of which lands in MID material, for both
    the drawn 5.00 body and the measured 3.86 one;
  - the **terminal notches leave the wall solid** below them and between each
    pair, so the relief cannot cut the wall through;
  - the **LED flange** bears on the inner face and the Ø5.00 lens runs 3.60
    **proud** of the outer face — read off the mesh's own y extents *and* the
    arithmetic, so a bad placement fails the same test as bad maths;
  - **nothing on any board is within reach of a terminal or a lead** — the
    documented "nothing is within 45 mm of them" turned into a measurement, with
    the same separating-axis test the accessory opening uses, against the Pi,
    the WittyPi and the LCD;
  - the **button hole clears the measured actuator**, printed as what it is:
    3.60 against 3.50, **0.05 radially**;
  - both parts are **closed shells, three each** — which the imported boards are
    not, and which is why point-in-solid is sound here and is not there.
- **the assembly sweep**, which is the answer to "can the MID actually go on
  without hitting anything?": the exported MID is lifted through **161
  positions over 80 mm** and at every one a point lattice is tested against the
  obstacles it has to pass. Three obstacle sets are used — **27 points in the
  WittyPi button's measured box**, **108 points across the full 40-pin
  header's envelope** (x 11.85 … 63.35, not just the 13 LCD pin columns) and
  **374 points through the Pi's PCB** — and the MID never once contains a point
  at any lift. It is a swept check rather than a single assembled pose, which
  is what catches a relief that is deep enough when seated but not on the way
  down.
- **the accessory opening** below that row, which is measured rather than
  described: eighteen probes at the corners of a **12.00 × 7.00** rectangle
  through the wall prove the finished opening really is that big (the cut is
  12.20 × 7.20, so a 12 × 7 probe set has to pass), the wall round it is intact
  at both faces, the **R1.50 fillets are measured** — the square corner point
  must be *material* while a point inside the arc must be *hole*, which a plain
  rectangular cut fails and a cut that had lost its corners fails the other way
  — the margins to the ports below, the pockets above, the LED row and both M3
  columns are all re-derived from the constants, and the **25.00 mm corridor
  behind it is proven clear** against the imported meshes with a separating-axis
  test. That last one is the only sound question to ask an open surface mesh,
  and it is the check that makes "there is nothing behind it" true rather than
  hopeful.
- and an informational report on the **imported meshes**, because two of the
  three are not closed solids and that changes what the checks above can mean.

### Two ways to get a false pass

Both of these were live in this suite and both are worth knowing about.

- **An empty `intersection()` is only evidence if both operands are closed
  manifolds.** The imported Pi and WittyPi meshes are **not** — 4470 and 2100
  edges are not shared by exactly two triangles, and they arrive as 185 and 158
  shells — so OpenSCAD returns empty for *any* boolean with them. Every
  assertion about the Pi and the WittyPi is therefore a ray cast against their
  triangles, and `verify.py` prints their health as a note so the next person
  can see why. The LCD's mesh *is* closed (2 shells, 0 bad edges), so booleans
  against it are meaningful and are used.
- **A probe placed on a face plane is a coin toss.** Every coordinate in the
  .scad is a round number, and a ray starting exactly on a facet plane — or a
  facet *edge*, where an inclusive point-in-triangle test counts it once per
  triangle that shares the edge — silently flips an even crossing count to odd.
  That reported 13 "collisions" that were not there, and it made the MOUNT's
  −X pylons (since deleted with the tub) read as missing, because the probe
  landed exactly on the pylon's inner face at x 5.00. `crossings_above` applies
  a few microns of deterministic jitter to every ray, and every probe is placed
  off round numbers.

### Three .scad habits this suite exists to protect

- **`for (i = [0 : N − 1])` does not do nothing at `N = 0`.** OpenSCAD
  normalises a range whose end is below its start into a *reversed* one: `[0 :
  −1]` becomes `[-1 : 1 : 0]` and the body runs **twice**, at `i = −1` and
  `i = 0`. Every loop in `panel()` is therefore wrapped in `if (N > 0)`, and the
  last check above exists to keep it that way. This is also why "disable the
  panel with `-D LED_N=0`" is *not* a valid way to diff the MID against v0.6
  without those guards — it cuts two phantom LEDs off the left end of the row
  instead. Measured, the panel removes 648.90 mm³; predicted from the
  parameters it is 649.31, the 0.41 difference being exactly the shortfall of
  inscribing a 48-gon in each bore.
- **A cut that lands exactly on an existing face does not make a hole.** It
  made a *sealed* one. Where the switch pocket's back face was sized to land on
  the wall's inner face, CGAL did not subtract it from the surface — it kept
  the pocket as a **separate closed shell inside the wall**, with a
  zero-thickness membrane across the opening. The mesh stayed closed, manifold
  and arithmetically the right volume, the render looked right, and every probe
  in this suite still said "open", because a ray cast through a zero-thickness
  membrane does cross a surface. What gave it away was `openscad` reporting
  `Volumes: 5` where the panel-less MID reports 2, and the fix is the file's own
  existing habit: **overshoot**. Every cut in the file now laps past its target
  rather than landing on it — the pocket is `SW_H` deep starting at the lip, the
  button hole laps into the pocket, the notch laps past the ledge. Neither
  overshoot removes anything, because the space it reaches into is already being
  cut. `mesh_health` in `verify.py` is what makes this class of bug visible;
  before it, nothing here could see it.
- **CGAL reports a shared face as real facets**, so `intersection()` alone
  cannot tell "touching" from "overlapping". That is one more reason the butt
  joints carry the 0.20 mm `MATE_GAP`: the parts are no longer in contact, so
  an intersection at their real positions is unambiguous. (Before the gap, the
  probes had to lift the upper part by 0.01 mm to filter out contact facets.)

The mirrored constants at the top of `verify.py` are a snapshot, because
OpenSCAD's `use <>` imports modules but **not** top-level variables — they
cannot be read out of the .scad. The bounding-box checks fail loudly if they
drift from the model, so a mismatch means "update the mirror", not "the model
is broken".

### Renders

`./render.sh` regenerates `preview/v0.7-*.png` with OpenSCAD's own renderer.
It needs a real X display — 2021.01 has no `--headless` — and it is committed
for the same reason `verify.py` is: the v0.6 images came from a software
rasteriser in `/tmp` and cannot be regenerated at all now.

OpenSCAD shades by face normal, so two walls facing the same way come out the
same tone and an opening reads as a flat patch. Per-part colour is what makes
the joints legible; `v0.7-section` is what makes the walls legible. It is cut
with the boards left out on purpose, because the imported LCD is a *surface*
model and cutting it leaves coplanar faces for OpenCSG to fight over.

`v0.7-base` replaces what used to be `v0.7-mount`: the BASE on its own, open
side up, which is where the four plate bosses and the five vents now live — look
for the blind Ø2.75 pilots down the middle of those bosses, the only holes in
the case that take a thread. `v0.7-underside` is shot from below and reads as
the disassembly order — **six M3 button heads sunk flush in their
counterbores**, inside their ring the plate's four bolts, and behind those the
Pi's four counterbored screws, which is exactly the order they come out in. The
heads sit flush because the 4.50 wall now takes a Ø5.80 counterbore with a
Ø6.20 countersink lapped over it, so no head stands outside the silhouette.
`v0.7-joints` shows the seam grooves reading as **six dashes** at each joint
rather than unbroken rings.

`v0.7-panel`, `v0.7-midpanel` and `v0.7-pads` are shot tilted a few degrees off
horizontal on purpose. Shot dead face-on, you look straight down a through-hole
and see the far wall's inner face in the same tone — the three LED holes
disappear entirely, and the render looks like a solid wall. The tilt is what
makes a bore read as a bore. In `v0.7-midpanel` the switch pockets show as
crescents, because what you are seeing through is the Ø3.60 button hole in the
0.45 lip.

`v0.7-front` is the exception and the fix for that same problem: it is the front
wall shot square on with the case cut back to just behind it (`CUT_AWAY = "+Y"`,
`CUT_AT = 0.20`), so every opening, the **accessory opening** included, looks
out at the background instead of at the far wall. That is the view where the
opening's **R1.50 corners** are visible as corners — in `v0.7-panel` it is the
flat patch the paragraph above warns about.

`v0.7-fittings` is the panel hardware — the three switches and the three red
LEDs — and it is the one view this file could not produce before v0.7, because
those parts were arithmetic and not geometry. The cut has to come from
**behind** them rather than in front: the switch body's front face is 0.45
behind the case's outer face, so any plane that removes the wall removes the
bodies with it. The LED does not have that problem — it stands 3.60 proud — but
it is cut from the same side for consistency. `CUT_AWAY = "+Y"` at 0.20 takes
the far wall, the shelf and the boards instead, and leaves the panel whole with
its hardware standing off it — the bodies clear of the pocket walls with the
ribs pinching them, the four terminals splaying into their notches, the flanges
flat on the inner face. The camera is 25° off straight-on rather than
`v0.7-front`'s 12, because the point of this view is depth: at a shallower
angle the bodies standing off the wall flatten away and it looks like the panel
view again.

A render is a sanity check, not evidence. The measurements above are evidence.

### The demo video

The rendered video, its `.ass` title file and the render script were removed
from the repo — they were build artefacts of the marketing pass, not part of
the case. The `PART="trailer"` animation that produced them is still in
`pi-stack-v0.7.scad`, so the video can be rebuilt from the design alone.

It came out as 1280 × 720 H.264, 40 s, silent, with the titles burned in. Those
titles lived in a plain text `.ass` file rather than being baked into a binary,
so a caption could be corrected with an editor and a re-encode, which took
about ten seconds.

It is **two shots**, not one. The first is a card: a single frame of the
*finished* case, held 4.6 s with the title over it. Then a dip to the paper —
`#FFFFE5`, which is OpenSCAD's own background, so the cut reads as a breath
rather than the two dark flashes you get by fading to ffmpeg's default black —
and then the build. Opening on the finished object is the better hook, and it
is also what keeps the build honest: parts that have not arrived yet are
standing in the top of the build's frame, in plain sight, where they belong,
and no text has to be legible over them.

**It is its own `PART`, and that is the whole safety argument.** `trailer()`
decides only *where* each already-built part is drawn and *how far along* it
is; every part is the same module the assembly view draws, in the same place,
at offset zero. Nothing above the block is touched, and no other `PART`
evaluates one line of it, so the four exports and `verify.py` cannot see it —
the same discipline the `SHOW_*` toggles follow.

The frames come from `--animate 840`, which is **one** openscad process for
the whole sequence. That is not a detail: the three imported board meshes are
around 295k triangles between them, and one process parses them once instead
of 840 times. Five minutes, against roughly an hour the other way.

The camera is pinned, and it has to be: `--viewall` recomputes the bounding box
on every frame, so as parts fly in the case would zoom and drift under a
camera that was trying to keep it framed. So the model is composed to fit a
fixed camera instead. OpenSCAD's orthographic scale is `view_height ≈
dist / 3.8`, so the `dist 450` the video was rendered at gives a frame about 118 mm tall,
the 67 mm case silhouette fills a little over half of it, and there is clear
cream above for the title and below for the captions.

`TRAILER_BEATS` is the score: nine `[start, end]` windows on a clock that
`TRAILER_SPAN` compresses into the first 86% of the frame count, leaving the
last 4.9 s as a held shot of the finished case under the end card. Each part
falls (or, for the plate, rises) in on a smoothstep, so it starts and stops at
rest — a part that snaps to a halt reads as a bug rather than as a part
settling.

The rule the offsets follow is worth stating, because getting it wrong is
invisible until you watch the video: **a part must start above everything it
has to pass on the way down.** The MID starts clear of the LCD's top and the
BEZEL clear of the MID's. A shell sliding down over a board is right — that is
the lid closing — but a board sliding up through a shell's top plate is not.
The beats also run in build order, header before WittyPi, because the WittyPi
plugs onto the header and not the other way round — that one was wrong in the
first cut and read as the WittyPi mounting itself on thin air.

`TRAILER_LIFT` scales the whole queue at once, and it is one number because
how high the queue has to stand is a fact about the *camera*, not the case:
raise it to about 2.8 at this camera and the waiting parts climb out of frame
and every one of them enters from off-screen instead. It is 1.0 here — they
are meant to be seen waiting. Re-sweep it by rendering one frame at
`TRAILER_AT=0` if the camera or the aspect ever moves.

Two things it does not have. There is **no score** — there is no music to clear
here, so the encoded file is silent; an audio track can be muxed on afterwards
with one ffmpeg copy, without re-encoding the video. And it is
**not a rendering of the real hardware**: the boards are the imported vendor
meshes and the LEDs and switches are the reference geometry from `### The
reference hardware`, so the video shows the three 5 mm LEDs and the three
switches dropping neatly into their pockets. That is now true of the measured
1825910-6 as well: the four terminal notches give its strips **0.31 mm** of
clearance, and `verify.py` probes it. The animation cannot show a thing the
model does not contain, and it is not allowed to imply the opposite.

## Known gaps

- **The CE09547 must be a receptacle, and this repo cannot prove it.** The
  drawn body is solid, and the Pi's own stock pins reach 4.08 up into it —
  which is only correct if the part presses *onto* the Pi's 2×20 header rather
  than being soldered flush into its holes. Soldered flush instead, the total
  above the PCB is 19.58, not 23.50, and every height above the Pi moves with
  it. 4.08 of engagement on a 2×20 is on the short side. **Measure the part
  before committing filament**, and if it is the flush kind, `EXT_HEADER` is
  the single constant to change.
- **`WP_SOCK_D = 11.71` is derived, not measured** (above). It is the depth the
  WittyPi's socket must swallow. Nothing in this repo has that dimension — the
  WittyPi mesh has no socket cavity at all — so the checks assert the
  consequences rather than the number. Measure the socket's depth if you can
  reach it.
- **`HDR_BODY = 5.08` and `HDR_BODY_D = 8.50` are borrowed** from the reference
  header CAD in `../base/`, because the vendor publishes no body dimensions.
  5.08 is fixed by the total (it is the only value that closes 3.92 + 5.08 +
  14.50 = 23.50), but **8.50 in Y is a real guess**, and it is the number the
  +Y wall's relief is cut for. It is also why the relief exists at all: at 8.50
  the body overhangs the Pi's PCB edge by 0.75 into a 0.60 gap. If the real
  body is narrower than 8.50 the relief is merely redundant — it is 1.00 into a
  4.50 wall, in a patch nothing else is in — but if it is *wider*, the relief
  needs to be deeper. **Measure the body's Y before printing.**
- **Both reliefs are measured against open meshes.** The 0.40 of header body in
  the +Y wall comes from `HDR_BODY_D` above; the 0.75 of WittyPi board edge in
  the −X wall comes from the WittyPi mesh, whose outline is 66.10 against a
  vendor figure of 65. The mesh is not a closed solid (see the verification
  notes), so those two outlines are the best evidence available rather than
  proof. Both reliefs are cheap to widen.
- **The LCD seat has a mesh residue.** `LCD_SLAB_LO` is −0.75 against a true
  mesh value of −0.751, so up to 0.001 mm of the slab's underside is inside the
  ring's top face. That is inside first-layer squish and is stated rather than
  chased.
- **The four flanges bear on the LCD's PCB, and the PCB is carried by nothing
  else.** There is no adhesive, no gasket and no pad preload in the model: the
  LCD sits in the pocket and the six screws hold the case closed around it.
  Print, assemble, then decide whether the flanges want a 0.2 mm shim of tape
  under the panel.
- **The strap's grip is a guess.** The 12.00 cut waist and 20.00 paddle are
  sized for a 4–5 mm elastic loop; a wider or narrower elastic, or a different
  stretch, changes how hard it seats in the waist and whether the tip shoulder
  holds it. Elastic fatigue, abrasion against the printed paddle and the
  tension actually needed to carry ~400 g are not modelled at all. This is the
  part to iterate on, which is why it is isolated in a plate; the older
  `PLATE_STYLE = "hook"` is still there for comparison.
- **The plate's structural adequacy as a fabric carrier is not analysed.** It
  is a 4.00 tray with four arms, and it carries a ~400 g case on **four
  M3 × 6 into printed plastic, with 3.15 mm of bite** — the shortest thread and
  the most cycled joint in the case, into a Ø2.75 pilot only 5.30 deep. The
  arms are loaded in bending at the 12.00 waist, and the skirt is only 3.00
  tall, so a sideways knock can peel the case out of the tray. Geometry cannot
  answer whether that is enough; a swing test can. If it is not, the bosses, the
  floor skin and the pilot's depth are where to thicken — remembering that the
  +X/−Y boss is capped at 5.30 by the Pi's Ethernet shell above it.
- **The plate's durability is the weakest thing in this design, and it is worth
  saying twice.** Those four screws are the ones that come out every time the
  plate does, which is every teardown; they are the only screws in the case with
  less than 3.15 mm of thread; and the load they carry never comes off while the
  case is worn. If anything strips, it will be these.
- **The twelve case screws are flush now, and the counterbores are the new
  print-tolerance item.** Each head sinks into a Ø5.80 × 1.65 counterbore with a
  Ø6.20 × 0.20 countersink lapped over it, in the BEZEL's top face and the
  case's underside. Because 5.80 is wider than the 4.50 wall, every counterbore
  **opens through the outer side face** as a shallow 0.65 scallop — the head is
  flush, but it bears on roughly the inboard half of its floor rather than a
  full ring. That is the cost of a flush button head in this wall; a contained
  counterbore needs a 5.80 wall, and a proud head needs no counterbore at all.
  A printer that over-extrudes or leaves a first-layer lip can also make the
  counterbore tight enough that the head will not seat the last fraction; ream
  it with the screw or a 5.8 bit if it happens. A washer under each still fixes
  any marking, at the cost of the heads standing 1.0 mm proud.
- **The strap plate is the largest print in the project.** Its footprint is
  **134.89 × 99.95 mm**, arms included, so the bed has to be at least that; the
  tray alone is 102.12 × 73.20. The tip paddles are 4.00 thick and carry the
  elastic at their waist, which is fine in PLA or PETG but is where a brittle
  filament will crack first if the loop is too tight.
- **The Ø2.75 pilot is a starting point, not a measurement.** It leaves 0.25
  over an M3's core so printing drift does not close the hole, but PLA, PETG and
  ASA each want their own, and the right one is found by printing a BASE and
  driving a screw into it. `SCREW_PILOT` is the one number to change
  (`PLATE_PILOT_D` follows it), and the failure modes either side are a split
  boss and a hole that never tightens.
- **Nothing here has been cycled.** Every screw in this case forms its own
  thread, and the whole assembly/disassembly count in this document is design
  intent, not test data. The first teardown is the experiment.
- **The bosses' clearance to the Pi's Ethernet shell is measured to a mesh, not
  to the board in hand.** The bosses stop at `JOINT_A` = 5.50, i.e. at the
  BASE's rim, and the closest approach anywhere on their footprints is 2.10 mm
  against the imported mesh. If the real shell hangs lower than the mesh says,
  shorten `PLATE_BOSS_H` — the check above is where that shows up.
- **The BASE's underside is the tray's seat now, and it is the case's whole
  bottom face.** Nothing bears on it but the plate's floor, and `verify.py`
  samples it on a 5 mm grid over the case's own footprint — but a warped first
  layer is a real seat with a real gap in it, and no geometry check sees a warp.
  If the plate rocks, the fix is the print, not the model.
- **The rear (+Y) wall is now a hex vent field and a 10 × 6 mm lead
  rectangle.** The old charging slot (15 × 8 mm), Ø9 grommet and two Ø3.20 tie
  holes are gone, so the WittyPi's charging input, which faces the **+X** wall
  about 20 mm in, no longer has a dedicated route out. If charging in place is
  wanted again, add an opening to the +Y wall — the field's parameters
  (`HEX_*`, `LEAD_R*`) are a few lines and the checks follow them.

### Known gaps in the front panel

- **The switch-terminal defect is fixed, and the fix is in the printed MID.**
  The terminals hang outside the 6.00 body and splay to **7.20 across**, against
  a 6.20 pocket. Measured from the **TE 1825910-6**'s own CAD: 0.71 wide × 0.60
  thick, on a **6.60 × 4.535** pattern, tops **0.90 above the body's underside**
  and running 3.51 back — **4.41 of strip**, with the overhanging 0.50 running
  all of it. Before the fix the wall was solid across its whole depth and the
  flanks cleared at no insertable depth; the switches could not be fitted at
  all. Four **1.40-deep notches per switch**, lapped 0.20 into the pocket and
  the cavity and spanning the strips' ±Z reach, now give **1.45 mm** of clearance
  at the drawn seat and **0.31 mm** for the measured 3.86 body. `verify.py`
  proves it with **768 notch probes plus 60 strip probes** and checks that the
  wall below and between the notches is still solid.

  The old prose before v0.7 said these pins "splay to a 6.5 × 4.5 footprint" —
  the pattern is 6.60 × 4.535 — but a *pattern* is centres and a pocket has to
  clear *extents*. The extents are what bite, and they are what the notches are
  cut for.
- **`SW_H` is 5.00, and the switch it is drawn from is 3.86 tall.** The drawn
  part is the measured 1825910-6 with its body stretched to `SW_H`, the actuator
  and terminals left as measured — the honest option, and the one that makes the
  drawing follow `SW_H` if it is ever set to a real number. The 3.86 body is the
  tighter case in y: it seats 1.14 deeper, so its terminal tops end at 3.41
  rather than 4.55, which is why the notches are cut to 1.40 and not 0.60. At
  `SW_H` = 3.86 the pocket also leaves a **0.19 mm floor** behind the body,
  against none at 5.00; that floor sits behind the body, not across the
  terminals, so it does not block insertion — but it does mean the body's back
  face bears on plastic instead of the pocket breaking through. Set `SW_H` to
  whatever yours measures and everything follows.
- **The LED's CAD is unreadable and its figures are the published ones.**
  `base/3mm-led/3mm_LED.stp` is construction geometry — a 6.13 × 0 × 3.64 plane
  and two 13 mm slivers — the `.igs` beside it is in inches, and the datasheet is
  an outline-only AutoCAD plot. So the drawn LED is Ø5.00 body, Ø5.90 flange,
  0.50 thick, 8.60 overall, from the published figures for a 5 mm through-hole
  part. Its leads are **drawn 2.50 long and never cut to length**, because
  nothing here knows how much of them you will snip off.
- **The crush ribs are a guess at 0.20 — but the grip they give is now
  measured.** They stand 0.20 proud of the pocket and 0.10 into the body, and
  `verify.py` asserts both halves: material at the rib tips *and* switch solid at
  the same points, so the ribs are provably the one place the case touches the
  part. Whether 0.10 of interference is the right amount for your printer is
  still the guess. If the switches will not go in, drop `SW_RIB`; if they fall
  out, raise it — and widen `SW_POCKET` with it. This is the one feature here
  that wants a test print before the real one.
- **Nothing holds the switches against being pushed in.** With no floor behind
  them, the only thing resisting a press is the ribs' friction and whatever the
  wiring does. Solder, then tie or heat-shrink the leads — that is the
  retention, not the print. It is why the assembly puts the panel in with the
  top still open.
- **There is no board behind the switches.** The pins float in the cavity at
  stack z 29.90 … 36.10, clear of every other part, and are meant to be
  hand-wired to the GPIO header. That "clear of every other part" used to be an
  assertion about a box; it is now a separating-axis test of the real terminal
  and lead geometry against the Pi, the WittyPi and the LCD, and it passes with
  room to spare.
- **The LEDs are retained by their flange or a drop of adhesive.** A flangeless
  5 mm LED pushes straight through the Ø5.20 bore.
- **The lens stands 3.60 proud of the outer face, and the plain bore is why.**
  The published 5 mm part is 8.60 overall with a 0.50 flange; seated on the
  inner face its 8.10 barrel crosses the 4.50 wall and leaves 3.60 outside. A
  longer body sits deeper (dimmer but still visible); a shorter one stands out
  more. There is nothing to set: the bore cannot be mis-sized for the LED, it
  just changes how much lens is exposed. The 3.60 is the drawn part's own tip
  against the case's outer face, read off the mesh, so it is a property of the
  model rather than a claim about it — but it is still only as good as the
  published figures above.
- **A flange counterbore would make the protrusion worse, so there is none.**
  The flange is at the LED's base, so sinking it carries the lens *out* with it:
  every 0.20 of recess adds 0.20 to the 3.60 already proud. The bore centres
  the LED well enough on its own (a Ø5.00 body has 0.10 mm of play in a Ø5.20
  bore). If a near-flush lens matters, use a bezel or a different holder — the
  printed wall cannot do it without capturing the flange from the front.
- **The accessory opening leaves the thinnest wall section in the front face.**
  The 12.20 × 7.20 window sits centred in a 14.34 band, which is the arithmetic
  of the request: 3.57 of wall survives above it and 3.57 below, and the strip
  below is only 3.65 because the audio jack's opening (edge at 15.48) is what
  it clears. It is a 12.20-wide bridge with a slot open at the bottom under it
  — nothing in the model loads it (the MID's wall carries no tension; the twelve
  M3s do), but a knock on the front face bends that band and it is the place a
  crack would start. Every one of those figures is a probe in `verify.py`, not
  a sketch. If it wants more, the opening is the thing to change: **the request
  is a 7.00 minimum and the cut is 7.20**, so 6.00 would buy 1.20 of wall at
  each end.
- **The accessory opening is sized to a request, not to a part.** 12.20 × 7.20
  finished (R1.50) is "at least 12 × 7" and nothing more — no connector, gland
  or grommet was measured into it. It is a plain bore through the 4.50 wall:
  **no lip, no counterbore, no chamfer and no strain relief**, so a cable
  leaving through it is held by whatever you add (a knot, a tie, a gland, or
  nothing). If it is for a named part, tell me the part and the opening can be
  sized to its cutout drawing; if it is for a lead, the 25 mm of clear corridor
  behind it is the number that matters and that is already checked.
- **The panel is not sealed.** The switch pockets open into the cavity and the
  button holes open to outside, so this face is no longer splash-resistant — for
  whatever that was worth before.
