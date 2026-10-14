// =====================================================================
//  Crimson Veil  -  Pi stack case          v0.4  "three-part shell"
// =====================================================================
//  Holds the Raspberry Pi 3 with the WittyPi stacked on an extended header
//  and the 3.5" SPI LCD on top.  The battery lives OUTSIDE this enclosure
//  and reaches it through a service opening in the +Y wall.
//
//  In OpenSCAD:   Design > Automatic Reload and Preview   [x]
//  so this rebuilds whenever the file is edited.
//
//  All board dimensions below were MEASURED from the vendor CAD in
//  3Dmodels/base/ using a real B-rep kernel - not read off a datasheet.
//  See 3Dmodels/case/README.md.
//
//  ---------------------------------------------------------------------
//  THE THREE PARTS
//  ---------------------------------------------------------------------
//  The LCD window is 74 x 49; the Pi is 84.9 x 56.0.  The Pi therefore
//  cannot pass through the top, and a one-piece shell would be a box with
//  no way to get the electronics in.  It splits bottom-up, and the BASE /
//  MID joint sits just BELOW the lowest thing on the Pi:
//
//    BASE  z 0 .. 5.5      floor, the four Pi screw bosses, and a low rim.
//                          Low enough to clear the underside of EVERY port
//                          on the Pi, so the Pi drops straight in.  The four
//                          mounting screws go up from UNDERNEATH, through
//                          counterbored holes in the floor.
//    MID   z 5.5 .. LCD    every port opening, the LCD shelf, and the service
//                          openings for the charging cable and the battery
//                          leads.  Starts at the microSD slot, the lowest
//                          thing on the Pi.  Slides down over the port
//                          connectors and the header + WittyPi stack.  This
//                          is the SHIM - the only part that changes size if
//                          the stack height turns out different.
//    BEZEL LCD .. top      carries the LCD in a pocket, 74 x 49 window,
//                          6 counterbored screws pull the whole stack
//                          together.
//
//  Each joint is marked with a shallow SEAM groove round the outside, so
//  the split reads clearly both in the render and on the printed part.
//
//  ASSEMBLY
//    1. drop the Pi into the BASE - the rim is low enough that nothing on
//       the board fouls it, and all four mounting holes stay clear
//    2. 4 x M2 x 12 up from underneath the BASE, through the counterbored
//       floor holes and the Pi, with a nut on top of each.  These can be
//       driven from outside the box, and the whole stack can be built on the
//       bench before it ever goes near the case
//    3. extended header, then the WittyPi
//    4. slide the MID down over the stack; every port opening is in it, so
//       it has to go on before the plugs do
//    5. drop the LCD into the BEZEL pocket, from underneath - its 26-pin
//       socket faces down and lines up with the GPIO column
//    6. land the BEZEL on the MID and drive the 6 screws into the BASE
// =====================================================================

$fn = 48;

//  "base" | "mid" | "bezel"    - one part, for export
//  "stack"                     - the electronics alone, assembled
//  "assembly"                  - all three parts in place, with the boards
//  "all"                       - all three laid out for printing
PART = "assembly";

// ---------------------------------------------------------------------
//  PREVIEW TOGGLES  -  on-screen only, they never touch an exported STL
// ---------------------------------------------------------------------
//  With PART = "assembly", flip these to strip the model down until the
//  bit you want to look at is the only thing left.  Everything that is
//  switched off is simply not built, so it does not hide anything either.
SHOW_BASE  = true;     // the tray with the Pi's mounting bosses
SHOW_MID   = true;     // the shell with every port opening
SHOW_BEZEL = true;     // the LCD cover
SHOW_PI    = true;
SHOW_WITTY = true;     // the WittyPi on its extended header
SHOW_LCD   = true;

//  Half-section, for looking at the stack in situ.  CUT_AWAY names the
//  side to cut OFF - "none" | "+X" | "-X" | "+Y" | "-Y" - and CUT_AT is
//  where the plane sits, as a fraction across the case: 0.5 is the middle.
//  It applies to the case AND the boards, so you see them sectioned
//  together and can read the clearances straight off the cut.
CUT_AWAY = "none";
CUT_AT   = 0.50;

// =====================================================================
//  MEASURED
// =====================================================================
// Raspberry Pi 3 / "Raspberry Pi 3 Light Version.STEP"
PI_PCB_W   = 84.92;    // X, long side
PI_PCB_D   = 56.00;    // Y
PI_PCB_T   =  1.33;
PI_OUT_X   = -48.44;   // model X of the PCB -X edge
PI_OUT_Y   = -25.59;   // model Y of the PCB -Y edge
PI_OUT_Z   =  -0.33;   // model Z of the PCB underside
PI_HOLE_DX = 58.00;    // mounting hole pattern
PI_HOLE_DY = 49.00;
PI_HOLE_D  =  2.75;    // hole diameter
PI_HOLE_IN =  3.50;    // hole centre inset from the board edge

// +X wall: Ethernet and the dual USB deck
ETH   = [ 17.53, 38.93, -23.19,  -7.31,  -2.00, 14.50];  // X0 X1 Y0 Y1 Z0 Z1
USB   = [ 21.01, 38.93,  -4.24,  29.24,  -0.75, 16.39];
//  The two USB-A ports measure as one part with a 2.52 mm gap between the
//  shells (y 11.24 and 13.76).  Cut separately with PORT_G round each they
//  would leave a 1.0 mm post between the two openings - far too thin to
//  survive a plug going in.  Cut as one opening, as the real dual-deck
//  connector and every commercial Pi case does it.
// -Y wall: power, HDMI, audio  (in that order along the edge)
PWR   = [-41.89,-33.91, -26.90, -20.38,   0.76,  3.53];
HDMI  = [-24.00, -9.00, -26.90, -15.33,  -0.75,  6.88];
AUDIO = [  1.60,  8.60, -26.90, -11.90,   0.00,  6.80];
// -X wall: the microSD card slot, on the underside
SD    = [-50.71,-35.71,  -2.77,   8.23,  -1.92, -0.95];

// Raspberry Pi 3 GPIO header, model coords - where the WittyPi's socket lands
PI_GPIO_X0 = -41.34;   PI_GPIO_X1 =  9.46;   // 50.8 long
PI_GPIO_Y0 =  24.41;   PI_GPIO_Y1 = 29.41;   // 5.0 wide, flush to the PCB edge

// WittyPi 4 L3V7 / "WittyPi4L3V7.step"
WP_SOCK_X0 =   6.90;   WP_SOCK_X1 = 58.10;   // the 40-pin socket, 51.2 x 5.0
WP_SOCK_Y0 =   1.20;   WP_SOCK_Y1 =  6.20;
WP_PCB_BOT =  -1.58;                        // PCB underside
WP_H       =   7.08;                        // overall height above that

// 3.5" SPI LCD / "3.5inch RPi LCD.stp"
LCD_W     = 85.00;     // slab outline = the HAT footprint
LCD_D     = 55.50;
LCD_T     =  5.50;     // panel+PCB slab
LCD_ACT_W = 74.00;     // visible area -> the bezel window
LCD_ACT_D = 49.00;
LCD_SLAB_LO = -0.80;   // model Z of the slab underside (top face is +4.75)
LCD_DROP  = 12.75;     // model Z -13.55, so this much of socket/header hangs
                       // below the slab - and it is what sets the case height
LCD_OUT_X =  0.00;     // this model is centred on its own origin
LCD_OUT_Y =  0.00;

// =====================================================================
//  TUNE THESE
// =====================================================================
// A screwed joint needs the wall to swallow both the clearance hole and the
// screw head.  At 4.5 mm an M2.5 head counterbore (o5.6) punches out through
// both faces of the wall.  At 5.0 mm an M2 pan head (o4.0 into a o2.2 hole)
// fits with ~0.5 mm to spare on each side, so: M2 for the case, M2.5 for the
// Pi's own mounting holes.
WALL        = 5.00;    // wall thickness - houses the vertical joint screws
CLR         = 0.35;    // board-to-wall clearance, per side
FLOOR       = 2.60;    // floor slab thickness
FLOOR_CLEAR = 5.00;    // PCB underside above the interior floor

// The BASE / MID joint, set just under the lowest thing on the Pi - the
// microSD socket, whose underside is at z 6.01, and the Ethernet shell, whose
// underside is at 5.93.  At 5.50 the BASE is a low tray whose rim clears the
// whole board, so the Pi drops straight in and a driver reaches all four
// mounting holes square on instead of down the inside of a deep well.  Every
// port opening then lands in the MID, and the BASE cuts no ports at all.
JOINT_A     = 5.50;

// Clearance cut round every port.  This is a hand-assembled prototype, not a
// sealed unit, so the openings are generous: 0.75 a side is 1.5 mm of slack
// around a plug body, which is what you actually want when a USB lead's
// overmould has to clear the wall as it goes in.  It also sets the narrowest
// web left in the shell - see the USB note below.
PORT_G      = 0.75;

BEZEL_T     = 1.60;    // bezel lip above the LCD slab, around the window
SHELF_W     = 3.00;    // MID's inner ledge that the LCD rests on
SHELF_T     = 2.00;

//  The visible joint line.  A shallow groove round the outside, cut by both
//  parts, which reads as a clear divide in the render and on the printed
//  case.  Kept to 0.6 deep: the screws sit on the wall centreline 2.50 from
//  each face, so the groove floor is 2.50 - 1.10 (screw radius) - 0.60 =
//  0.80 mm clear of every screw bore.  At 0.90 deep that ligament is only
//  0.5 mm and the grooves start breaking into the bores at all six corners.
SEAM_H      = 1.60;
SEAM_D      = 0.60;

//  The Pi's four mounting screws go in from UNDERNEATH, so the whole stack can
//  be built on the bench and dropped in, and the screws driven from outside
//  the box rather than down the inside of a well.  That decides the boss: it
//  is a clearance sleeve with a counterbore in the case's underside, not a
//  blind self-tapping pilot.  A screw driven from below has its head on the
//  far side of the Pi from the boss's shoulder, so it cannot clamp the board
//  on its own - each one needs a nut above the PCB.  The screws are M2, the
//  same as the case hardware, so there is one screw size in the build.
BOSS_D      = 6.50;    // Pi screw boss diameter
PI_SCREW_CLR = 2.20;   // M2 clearance, bored right through the boss and floor
PI_CBORE_D  = 4.30;    // counterbore for an M2 pan head (dk 4.0)
PI_CBORE_H  = 1.35;    // head height 1.3, so the head sits just under flush
//  -> leaves 1.25 mm of floor under each counterbore (FLOOR - PI_CBORE_H) and
//     1.10 mm of boss wall round it, which is what caps the head at M2.
//  -> 4 x M2 x 12 mm pan head, up from underneath, + 4 x M2 nuts on the PCB.
//     Head seat at 1.35, boss top at 7.60, PCB top at 8.93, nut 1.6 tall, so
//     the tip lands at 13.35 - 2.8 mm proud, into the 11 mm header gap.

SCREW_CLR   = 2.20;    // M2 clearance, through MID + BEZEL
SCREW_PILOT = 1.60;    // M2 self-tap pilot, in the BASE
SCREW_DEEP  = 5.50;    // pilot depth below the BASE's top face - runs out the
                      // bottom on purpose, see below
CBORE_D     = 4.00;    // M2 pan head counterbore in the BEZEL's top face
CBORE_DEEP  = 1.60;
//  -> 6 x M2 x 45 mm pan head screws hold the whole stack together.
//  The length falls out of the stack and there is no slack in it: the head
//  sits at OH - CBORE_DEEP = 45.26 and the screw has to clear the joint at
//  5.50, so anything under 40 mm grips nothing at all and 45 mm lands its tip
//  at z 0.26.  Rather than cut a blind pilot that a slightly long screw would
//  bottom out in and lift the BEZEL by a fraction of a millimetre, the pilots
//  are cut clean through the BASE's floor.  A screw then cannot jack the
//  joint apart; at worst its tip shows a few tenths below the case, where
//  nothing sits.  It also drains, and it prints without a trapped void.

// ---- service openings in the +Y wall --------------------------------
//  The one wall the Pi puts no ports on.  The battery is NOT in this
//  enclosure, so it and the charger both come in through here.  Measured
//  in case coordinates: X along the wall, Z up from the case floor.
CHARGE_X    = 30.00;   // charging cable slot, centred
CHARGE_W    = 15.00;   // along X
CHARGE_Z    = 21.00;
CHARGE_H    =  8.00;   // tall enough for a USB-C or micro-USB plug body

BATT_X      = 66.00;   // battery leads, round grommet
BATT_Z      = 20.00;
BATT_D      =  9.00;

// >>>  THE TWO NUMBERS STILL TO MEASURE  <<<
//  EXT_HEADER - how far the top of the extended header stands above the
//  Pi's PCB top face, where the WittyPi's socket lands.
EXT_HEADER  = 11.00;

//  LCD_UNDER  - underside of the LCD slab above the interior floor.
//  Leave at -1 and it is DERIVED from the stack: the LCD's socket is
//  LCD_DROP long, so the slab has to sit at least that far above the top of
//  the WittyPi or the two collide.  Set a positive number to override it
//  with a real caliper reading instead.
LCD_UNDER_MEASURED = -1;

// =====================================================================
//  DERIVED
// =====================================================================
IW = PI_PCB_W + 2 * CLR;                    // interior width  X
ID = PI_PCB_D + 2 * CLR;                    // interior depth  Y
OW = IW + 2 * WALL;                         // outer width
OD = ID + 2 * WALL;                         // outer depth

PCB_X = WALL + CLR;                         // the cavity is inset by WALL
PCB_Y = WALL + CLR;
PCB_Z = FLOOR + FLOOR_CLEAR;                // PCB underside

OFF = [PCB_X - PI_OUT_X, PCB_Y - PI_OUT_Y, PCB_Z - PI_OUT_Z];  // model -> case

WITTY_Z    = PCB_Z + PI_PCB_T + EXT_HEADER;         // WittyPi PCB underside
PI_GPIO_CX = (PI_GPIO_X0 + PI_GPIO_X1) / 2 + OFF[0];
PI_GPIO_CY = (PI_GPIO_Y0 + PI_GPIO_Y1) / 2 + OFF[1];
WP_SOCK_CX = (WP_SOCK_X0 + WP_SOCK_X1) / 2;
WP_SOCK_CY = (WP_SOCK_Y0 + WP_SOCK_Y1) / 2;

LCD_UNDER = (LCD_UNDER_MEASURED > 0) ? LCD_UNDER_MEASURED
                                     : WITTY_Z + WP_H + LCD_DROP;
SPLIT_B   = LCD_UNDER;                     // MID / BEZEL joint = LCD underside
MID_H     = SPLIT_B - JOINT_A;             // the shim
OH        = SPLIT_B + LCD_T + BEZEL_T;     // outer height

LCD_X = PCB_X + (PI_PCB_W - LCD_W) / 2;    // the LCD sits centred on the Pi
LCD_Y = PCB_Y + (PI_PCB_D - LCD_D) / 2;
LCD_Z = SPLIT_B;                           // LCD slab underside
LCD_CX = PCB_X + PI_PCB_W / 2;
LCD_CY = PCB_Y + PI_PCB_D / 2;

WIN_X = LCD_X + (LCD_W - LCD_ACT_W) / 2;
WIN_Y = LCD_Y + (LCD_D - LCD_ACT_D) / 2;

//  The vertical stack screws.  On the wall centreline so the clearance hole
//  and the head counterbore both stay buried in the wall, and 9 mm in from
//  each outer face, which keeps all six clear of every port opening and of
//  the two service openings - the +X wall in particular is solid port all
//  the way along and gets none.
SCREWS = [
    [WALL / 2,     9.00],
    [WALL / 2,     OD - 9.00],
    [9.00,         OD - WALL / 2],
    [OW - 9.00,    OD - WALL / 2],
    [9.00,         WALL / 2],
    [OW - 9.00,    WALL / 2],
];

echo(str("outer    : ", OW, " x ", OD, " x ", OH, " mm"));
echo(str("interior : ", IW, " x ", ID, " mm"));
echo(str("splits   : base 0..", JOINT_A, "  mid ..", SPLIT_B,
         "  bezel ..", OH, "   (mid is ", MID_H, " tall)"));
echo(str("PCB under z=", PCB_Z, "  WittyPi ", WITTY_Z, "..", WITTY_Z + WP_H,
         "  LCD slab ", LCD_Z, "..", LCD_Z + LCD_T));
echo(str("LCD socket hangs down to z=", LCD_Z - LCD_DROP));
echo(str("service openings: charge x ", CHARGE_X - CHARGE_W / 2, "..",
         CHARGE_X + CHARGE_W / 2, " z ", CHARGE_Z - CHARGE_H / 2, "..",
         CHARGE_Z + CHARGE_H / 2, "   battery x ", BATT_X, " z ", BATT_Z));
echo(str("model->case offset : ", OFF));

// =====================================================================
//  helpers   (all coordinates below are ABSOLUTE case coordinates)
// =====================================================================
module rbox(w, d, h, r) {
    hull() for (x = [r, w - r], y = [r, d - r])
        translate([x, y, 0]) cylinder(r = r, h = h, $fn = $fn);
}

// Cut a measured opening out through a wall.  The opening is given in MODEL
// coordinates and converted with OFF.  `wall` names which wall it passes
// through.  `zb` overrides the opening's bottom edge, in ABSOLUTE case height.
module wall_cut(box, wall, out = 8, g = PORT_G, zb = undef) {
    x0 = box[0] + OFF[0] - g;   x1 = box[1] + OFF[0] + g;
    y0 = box[2] + OFF[1] - g;   y1 = box[3] + OFF[1] + g;
    z0 = is_undef(zb) ? box[4] + OFF[2] - g : zb;
    z1 = box[5] + OFF[2] + g;
    if      (wall == "+X") translate([WALL + IW - 1, y0, z0])
                               cube([WALL + out + 1, y1 - y0, z1 - z0]);
    else if (wall == "-X") translate([-out, y0, z0])
                               cube([WALL + out + 1, y1 - y0, z1 - z0]);
    else if (wall == "-Y") translate([x0, -out, z0])
                               cube([x1 - x0, WALL + out + 1, z1 - z0]);
    else                   translate([x0, WALL + ID - 1, z0])
                               cube([x1 - x0, WALL + out + 1, z1 - z0]);
}

// Every port opening is taken right down through the MID's bottom edge, so
// each is a three-sided notch - a slot - rather than a closed rectangle.
// That is not cosmetic.  The MID slides DOWN over the stack at step 4 of the
// assembly, and the Pi's connectors are already plugged in and sticking out
// through the walls.  A closed rectangle would come down onto the top of the
// Ethernet shell at z 22.43 and stop dead, 17 mm short of seating.  Open at
// the bottom, the openings act as slots and the MID drops straight on.
// Nothing is lost in service: the BASE's rim closes the bottom of each slot
// from below, so a plugged connector still sees a closed opening.
module ports() {
    zb = JOINT_A - 2.0;
    wall_cut(ETH,   "+X", zb = zb);
    wall_cut(USB,   "+X", zb = zb);
    wall_cut(PWR,   "-Y", zb = zb);
    wall_cut(HDMI,  "-Y", zb = zb);
    wall_cut(AUDIO, "-Y", zb = zb);
    wall_cut(SD,    "-X", zb = zb);
}

// The charging cable and the battery leads, through the +Y wall.
module service_holes() {
    translate([CHARGE_X - CHARGE_W / 2, WALL + ID - 1, CHARGE_Z - CHARGE_H / 2])
        rbox(CHARGE_W, WALL + 2, CHARGE_H, 2.0);
    translate([BATT_X, WALL + ID - 1, BATT_Z]) rotate([-90, 0, 0])
        cylinder(d = BATT_D, h = WALL + 2, $fn = $fn);
}

module screw_holes() {
    for (s = SCREWS) translate([s[0], s[1], -1])
        cylinder(d = SCREW_CLR, h = OH + 2, $fn = $fn);
}

// A shallow groove round the outside at height z.  Both parts either side of
// a joint cut the whole groove; each only has material on its own side, so
// together they leave one clean seam line.
//
// The inner cut is the part's own outline offset inwards by SEAM_D, corners
// included: same corner centres (3.0, 3.0), radius reduced to 3.0 - SEAM_D.
// Reusing the part's own radius instead would leave the groove only 0.4 deep
// at the four corners, and the ligament to the screw bores down at 0.59 mm.
module seam(z) {
    translate([0, 0, z - SEAM_H / 2]) difference() {
        rbox(OW + 4, OD + 4, SEAM_H, 3.0);
        translate([SEAM_D, SEAM_D, -1])
            rbox(OW - 2 * SEAM_D, OD - 2 * SEAM_D, SEAM_H + 2, 3.0 - SEAM_D);
    }
}

// =====================================================================
//  PART 1  -  BASE     z 0 .. JOINT_A     the Pi's mounting
// =====================================================================
module pi_hole(i, j) {
    translate([PCB_X + PI_HOLE_IN + i * PI_HOLE_DX,
               PCB_Y + PI_HOLE_IN + j * PI_HOLE_DY, 0]) children();
}

module base() {
    difference() {
        union() {
            difference() {
                rbox(OW, OD, JOINT_A, 3.0);

                translate([WALL, WALL, FLOOR])
                    rbox(IW, ID, JOINT_A - FLOOR + 1, 2.0);

                // no port cuts here at all - the rim is below the whole board
                seam(JOINT_A);          // the joint line

                for (s = SCREWS) translate([s[0], s[1], JOINT_A - SCREW_DEEP])
                    cylinder(d = SCREW_PILOT, h = SCREW_DEEP + 1, $fn = $fn);
            }

            // Pi screw bosses, printed up to the PCB underside.  Added after
            // the cavity is cut, or the cavity would take them with it.
            for (i = [0, 1], j = [0, 1])
                pi_hole(i, j) cylinder(d = BOSS_D, h = PCB_Z, $fn = $fn);
        }

        // ...and only now bored through, so the holes clear the floor slab too.
        // Each is a clearance hole from the PCB underside down out of the
        // case, with a counterbore in the underside to bury the screw head.
        for (i = [0, 1], j = [0, 1]) {
            pi_hole(i, j) translate([0, 0, -1])
                cylinder(d = PI_SCREW_CLR, h = PCB_Z + 2, $fn = $fn);
            pi_hole(i, j) translate([0, 0, -0.01])
                cylinder(d = PI_CBORE_D, h = PI_CBORE_H + 0.01, $fn = $fn);
        }
    }
}

// =====================================================================
//  PART 2  -  MID      z JOINT_A .. SPLIT_B      the shim
// =====================================================================
module mid() {
    difference() {
        translate([0, 0, JOINT_A]) rbox(OW, OD, MID_H, 3.0);

        // full-height cavity, except a ledge at the very top that the
        // LCD slab rests on
        translate([WALL, WALL, JOINT_A - 1])
            rbox(IW, ID, MID_H - SHELF_T + 1, 2.0);
        translate([WALL + SHELF_W, WALL + SHELF_W, SPLIT_B - SHELF_T])
            rbox(IW - 2 * SHELF_W, ID - 2 * SHELF_W, SHELF_T + 1, 2.0);

        ports();                        // upper half of every port
        service_holes();
        screw_holes();
        seam(JOINT_A);
        seam(SPLIT_B);
    }
}

// =====================================================================
//  PART 3  -  BEZEL    z SPLIT_B .. OH   (carries the LCD)
// =====================================================================
module bezel() {
    difference() {
        translate([0, 0, SPLIT_B]) rbox(OW, OD, LCD_T + BEZEL_T, 3.0);

        // LCD pocket - dropped in from underneath, so the pocket is the
        // continuation of the cavity and the LCD finds its own level
        translate([WALL, WALL, SPLIT_B - 1]) rbox(IW, ID, LCD_T + 1, 2.0);

        // the window through the bezel lip.  Only as deep as the lip, so
        // the pocket floor stays solid and the LCD cannot be pushed through.
        translate([WIN_X, WIN_Y, SPLIT_B + LCD_T - 0.1])
            cube([LCD_ACT_W, LCD_ACT_D, BEZEL_T + 1.1]);

        screw_holes();
        for (s = SCREWS)
            translate([s[0], s[1], SPLIT_B + LCD_T + BEZEL_T - CBORE_DEEP])
                cylinder(d = CBORE_D, h = CBORE_DEEP + 1, $fn = $fn);
        seam(SPLIT_B);
    }
}

// =====================================================================
//  the real boards, imported - for eyeballing the fit
// =====================================================================
module pi() {
    translate(OFF) import("../derived/Raspberry_Pi_3_Light_Version.stl");
}

module wittypi() {
    // Turned 180 deg so the board lies back across the Pi rather than
    // hanging off the far edge, with its 40-pin socket centred on the Pi's
    // GPIO header - which is what its mounting holes assume.
    translate([PI_GPIO_CX, PI_GPIO_CY, WITTY_Z])
        rotate([0, 0, 180])
            translate([-WP_SOCK_CX, -WP_SOCK_CY, -WP_PCB_BOT])
                import("../derived/WittyPi4L3V7.stl");
}

module lcd() {
    // The panel's 26-pin socket hangs off its -Y edge, x +1.5..+35.8 - the
    // opposite corner of the board from the Pi's GPIO header, which is on the
    // +Y edge at x -35.4..+15.4 (board-relative).  Turned 180 deg about the
    // panel centre the socket lands at board-relative x -35.8..-1.5,
    // y +21.4..+26.5, which is the header's first 13 columns to within
    // 0.4 mm in X and 0.6 mm in Y - the way it actually plugs on.
    translate([LCD_CX, LCD_CY, LCD_Z - LCD_SLAB_LO])
        rotate([0, 0, 180])
            import("../derived/3.5inch_RPi_LCD.stl");
}

module boards() {
    color("DarkGreen")      pi();
    color("DarkOliveGreen") wittypi();
    color("SlateGray")      lcd();
}

module shell() {
    if (SHOW_BASE)  color("SteelBlue")      base();
    if (SHOW_MID)   color("CornflowerBlue") mid();
    if (SHOW_BEZEL) color("BurlyWood")      bezel();
}

module electronics() {
    if (SHOW_PI)    color("DarkGreen")      pi();
    if (SHOW_WITTY) color("DarkOliveGreen") wittypi();
    if (SHOW_LCD)   color("SlateGray")      lcd();
}

// The half-section.  A big cube over the side named by CUT_AWAY, sized off
// the case so it always clears it whatever the parameters are set to.
module cutaway() {
    s = 4 * (OW + OD + OH);
    if      (CUT_AWAY == "+X") translate([CUT_AT * OW, -s, -s])  cube([s, 2 * s, 2 * s]);
    else if (CUT_AWAY == "-X") translate([CUT_AT * OW - s, -s, -s]) cube([s, 2 * s, 2 * s]);
    else if (CUT_AWAY == "+Y") translate([-s, CUT_AT * OD, -s])  cube([2 * s, s, 2 * s]);
    else if (CUT_AWAY == "-Y") translate([-s, CUT_AT * OD - s, -s]) cube([2 * s, s, 2 * s]);
}

module preview() {
    difference() { shell();       cutaway(); }
    difference() { electronics(); cutaway(); }
}

// =====================================================================
//  output
// =====================================================================
if      (PART == "base")     { color("SteelBlue") base(); }
else if (PART == "mid")      { color("SteelBlue") mid(); }
else if (PART == "bezel")    { color("SteelBlue") bezel(); }
else if (PART == "boards")   { electronics(); }
else if (PART == "stack")    { electronics(); }   // the electronics alone
else if (PART == "assembly") { preview(); }
else {  // "all" - laid out along X for printing
    color("SteelBlue") base();
    translate([OW + 10, 0, 0])          color("CornflowerBlue") mid();
    translate([2 * (OW + 10), 0, 0])    color("BurlyWood")      bezel();
}
