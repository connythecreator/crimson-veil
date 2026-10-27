// =====================================================================
//  Crimson Veil  -  CE07929 protoboard case      v0.2  "two boards, one lid"
// =====================================================================
//  Holds TWO Core Electronics / Makerverse CE07929 protoboards, side by
//  side on their long edges, FLAT, on EIGHT printed PINCH CLIPS - one
//  through each board mounting hole.  The -X short end is OPEN above a
//  10 mm sill so the ESP32 and the rest of the end-of-board IO can be
//  reached with the lid on.  A separate lid closes the top and screws
//  down into the two long walls with 4 x M3.
//
//  In OpenSCAD:  Design > Automatic Reload and Preview   [x]
//  so this rebuilds whenever the file is edited.
//
//  ---------------------------------------------------------------------
//  WHERE THE BOARD NUMBERS COME FROM
//  ---------------------------------------------------------------------
//  The board is NOT sized from the catalogue.  These numbers are parsed
//  from the vendor KiCad file, PCB/PCB.kicad_pcb in
//    github.com/CoreElectronics/CE-Makerverse-Protoboard-63-Row
//
//    outline      166.000 x 52.000, square corners (four gr_lines)
//    thickness      1.600
//    mount holes    4 x o3.200 NPTH, 46.000 x 160.000 pattern, 3.000 in
//    tie pads       1.000 o, 2.540 pitch, 63 rows
//
//  The catalogue's "52 x 166 mm, M3 on a 46 x 160 mm pattern" agrees.
//  The one vendor oddity is a single mounting hole 0.26 mm out of pattern
//  (x 98.535 where the others say 98.795).  The case uses the 46 x 160
//  pattern, which the other three holes confirm.
//
//  The nearest tie-point pad is 6.5 mm from a mounting hole, and the clip
//  flange is o6.00 (radius 3.00), so the flange can support the board right
//  up to the hole and still leave every pad clear.
//
//  ---------------------------------------------------------------------
//  WHY THE CLIPS GO THROUGH THE MOUNTING HOLES
//  ---------------------------------------------------------------------
//  The board needs 2-3 mm of clear air under its whole underside, for
//  solder joints.  Edge clips would have to reach under the board, and
//  the only flat, pad-free real estate on the board is around its four
//  M3 mounting holes.  So the clip passes up THROUGH the hole:
//
//      o6.00 flange at z 4.40  <- the board rests on this
//      1.60 board, hole o3.20
//      o2.80 pin through the hole
//      4.30 x 2.90 head at z 6.90 .. 8.10, 0.55 lip over the hole
//
//  The head's flat underside is 0.10 above the board top, so the board is
//  pinched between the head and the flange.  The whole clip is split by a
//  1.20 slot down to the floor, which leaves two cantilever halves.  The
//  head is an ellipse: 4.30 along X, 2.90 along Y, and the slot runs along
//  Y.  The 2.90 already passes the o3.20 hole, so squeezing the two X
//  halves together brings 4.30 down to 3.20 and the board lifts off.  A
//  round head with one slot would not work: squeezing one diameter leaves
//  the other at 4.30, which cannot pass the hole.  Nothing unclips and
//  there are no board screws to lose.
//
//  LIFT = 2.80 is the requested 2-3 mm of clear air under the board:
//  SEAT_Z 4.40 - FLOOR 1.60 = 2.80.  At each hole the flange is the
//  support; everywhere else the underside is empty.  Thinning the floor
//  therefore does not eat into that gap - it lowers the whole stack
//  instead, and shortens the clip posts with it.
//
//  ---------------------------------------------------------------------
//  WHY THE LID IS A HONEYCOMB AND THE WALLS ARE PILASTERED
//  ---------------------------------------------------------------------
//  Airflow: the lid is a 17 mm-pitch hex field with 3 mm webs - about 56
//  cells, 14 mm across the flats.  It is a straight-through cut, so the
//  lid still prints top-face down with no support, and the solid border
//  round it carries the register lip and the four screw heads.
//
//  Room for wiring: the footprint is held at 174 x 119, so the long walls
//  are what set the channel beside the boards.  At 4.50 they leave 2.50
//  from the board edge to the wall - enough for ribbon and dupont leads
//  to pass - but 4.50 is thinner than the o6.20 lid counterbore needs to
//  sit inside the lid edge.  So the M3 pilots moved off the bare wall and
//  into six pilasters: 10 wide, 1.50 proud of the inner face, full
//  height, at the four screws and at mid-span.  The wall behind a pilot
//  is 4.50 + 1.50 = 6.00 locally, which is what the pilot needs; the lid
//  lip is notched where a pilaster passes through it.
//
//  ---------------------------------------------------------------------
//  THE NUMBERS THIS CASE IS BUILT FROM
//  ---------------------------------------------------------------------
//    BOARD_L/W/T     166.00 x 52.00 x 1.60  the board
//    SIDE_CLR          2.50  board long edge to wall, per side (derived)
//    END_CLR           1.00  board end to end wall, per end
//    BOARD_GAP         1.00  between the two boards
//    WALL_SIDE         4.50  long walls, plus six pilasters at 6.00 local;
//                            thinner walls go straight into SIDE_CLR,
//                            because the outer footprint is held
//    FLOOR             1.60  the tray's floor: 4 perimeters at a 0.4 nozzle,
//                            and the largest single slab in the part
//    LIFT              2.80  clear air under the board
//    SEAT_Z            4.40  board underside above the bench
//    BOARD_TOP         6.00  board top above the bench
//    WALL_H           24.00  wall top / lid seat; 18.00 above the board,
//                            enough for the ESP32 DevKit V1's 15.01
//
//  ---------------------------------------------------------------------
//  PARTS
//  ---------------------------------------------------------------------
//    BASE  the tray: floor, two long walls (4.5 mm, plus six 10 x 1.5
//          pilasters that carry the M3 lid pilots), a closed +X end wall,
//          the -X sill, and 8 pinch clips at the board mounting holes.
//          The clips are the only board support.
//    LID   3 mm slab with a hexagonal vent field, a 1.2 mm register lip
//          and 4 x M3 countersunk holes at x +/-45.  It prints top-face
//          down, so the lip points up and the vents need no support.
//
//  ASSEMBLY
//    1. lower each board into its bay, pad side up, and press it down over
//       its four pinch clips.  The split heads close through the holes and
//       spring open above the board; the board lands on the flanges at
//       z 4.40 with 2.80 of clear air under it.  Pinch the two halves of a
//       head together to release a board.
//    2. fit the ESP32 and any other end-of-board IO.  The -X end is one
//       full-width opening from z 10.00 to the top; the sill below it is
//       left solid, so leads leave over it rather than through it.
//    3. drop the lid on.  The register lip centres it; drive 4 x M3 x 10
//       down through the lid into the long walls.  The screws thread
//       straight into the printed plastic, as on the Pi case.
//
//  DISASSEMBLY: 4 lid screws out, lid off, pinch the four clips and lift
//  the board.  There is nothing underneath the board to remove.
// =====================================================================

$fn = 48;

//  "base" | "lid" | "lid-local" | "assembly" | "boards" | "all"
//  "lid" is the print orientation; "lid-local" is the same part in the
//  fitted orientation, kept for fit checks against the base.
PART = "assembly";

// ---------------------------------------------------------------------
//  PREVIEW TOGGLES  -  on-screen only, they never touch an exported STL
// ---------------------------------------------------------------------
SHOW_BASE   = true;
SHOW_LID    = true;
SHOW_BOARDS = true;
SHOW_ESP    = true;
SHOW_PADS   = true;    // the board stand-in's 1250 holes; false is faster

//  Half-section, for reading the fits off the cut.  "none" | "+X" | "-X"
//  | "+Y" | "-Y" names the side to cut OFF; CUT_AT is the fraction across
//  the case, 0.5 the middle.
CUT_AWAY = "none";
CUT_AT   = 0.50;

// =====================================================================
//  BOARD  -  vendor KiCad, 3Dmodels/case/README.md "What to measure"
// =====================================================================
BOARD_L      = 166.00;   // X, the long edge
BOARD_W      =  52.00;   // Y
BOARD_T      =   1.60;
BOARD_HOLE_D =   3.20;   // NPTH
BOARD_PAT_X  = 160.00;   // mounting pattern along the long edge
BOARD_PAT_Y  =  46.00;   // ...and across it
BOARD_PAD_D  =   1.00;   // tie-point drill
BOARD_PAD_P  =   2.540;  // 0.1 in
BOARD_ROWS   =  63;
BOARD_ROW_0  =   1.905;  // first row centre in from the -X board edge
BOARD_COL_0  =   3.810;  // innermost tie column, from the centreline

// =====================================================================
//  TUNE THESE
// =====================================================================
END_CLR   = 1.00;   // board end to end wall, per end
BOARD_GAP = 1.00;   // between the two boards, along the centreline
WALL_SIDE = 4.50;   // long walls.  The outer envelope is held fixed, so
                    // thinning this is what widens the wire channel beside
                    // the boards.  The M3 pilots no longer have to live in
                    // this number: they sit in the pilasters below.
WALL_END  = 3.00;   // short walls
PILASTER_W = 10.00; // pilaster width along the wall
PILASTER_T =  1.50; // how far it stands proud of the wall's inner face
FLOOR     = 1.60;   // 4 perimeters at a 0.4 nozzle.  The floor is the biggest
                    // flat area in the part, so every 0.2 mm of it costs a
                    // full 174 x 119 layer; it is also the one dimension with
                    // nothing behind it.  LIFT is measured above it, so
                    // thinning the floor lowers the whole stack rather than
                    // eating into the air under the board.
LIFT      = 2.80;   // clear air under the board, for solder joints
WALL_H    = 24.00;  // wall top, and the lid's seat
SILL_H    = 10.00;  // the open -X end is solid only up to here
LID_T     = 3.00;
LID_OVH   = 2.00;   // lid overhang at the open end: the finger lift
LID_LIP   = 1.20;   // register lip below the lid
LID_LIP_W = 2.00;
LID_EMBED = 0.50;   // lip buried into the slab, so no coplanar union face
LID_FIT   = 0.40;   // lip clearance to the inner walls, per side

//  Lid vents.  Hexagons are laid out on a triangular lattice at HEX_PITCH
//  centre to centre; HEX_WEB is the plastic left between neighbouring
//  cells.  The field is trimmed square to the border, which is solid for
//  the register lip and the four screws.
HEX_PITCH = 17.00;
HEX_WEB   =  3.00;
VENT_X    = 79.00;   // vent field half-width  (lip inner face at 81.60)
VENT_Y    = 50.50;   // vent field half-depth  (lip inner face at 52.60)

//  Pinch clips, one per board mounting hole (8 total).  The lower post and
//  flange are BELOW the board; only the pin and head go through the hole.
//  The board is pinched between the flange and the head.  The 1.20 slot is
//  cut down to the floor, so the two halves are cantilevers you pinch.  The
//  head's Y axis is 2.90, under the 3.20 hole, so only X has to be pinched.
PINCH_POST_D   = 4.00;   // lower post, floor to flange
PINCH_FLANGE_D = 6.00;   // support flange at the board underside
PINCH_FLANGE_H = 1.00;
PINCH_PIN_D    = 2.80;   // through the o3.20 hole; 0.20 clearance per side
PINCH_HEAD_DX  = 4.30;   // head across X; 0.55 lip over the hole
PINCH_HEAD_DY  = 2.90;   // head across Y; 0.15 clear per side in the hole
PINCH_HEAD_H   = 1.20;
PINCH_HEAD_CLR = 0.10;   // head underside above the board top
PINCH_SLOT_W   = 1.20;   // slot along Y; halves pinch along X

//  Lid screws, M3 x 10 into the long walls.
SCREW_X      =  45.00;
SCREW_CLEAR  =   3.40;
SCREW_HEAD_D =   6.20;
SCREW_HEAD_H =   1.80;

// =====================================================================
//  DERIVED
// =====================================================================
IX    = BOARD_L/2 + END_CLR;                        // 84.00 inner half-X
OX    = IX + WALL_END;                              // 87.00 outer half-X
OY    = 59.50;                                      // outer half-Y, HELD:
                                                    // it sets the footprint,
                                                    // so WALL_SIDE is what
                                                    // moves the inner face
IY    = OY - WALL_SIDE;                             // 55.00 inner half-Y
BAY_Y = BOARD_GAP/2 + BOARD_W/2;                    // 26.50 bay centre
SIDE_CLR = IY - (BOARD_GAP/2 + BOARD_W);            // 2.50 board edge to wall
SEAT_Z     = FLOOR + LIFT;                          // 4.40 board underside
BOARD_TOP  = SEAT_Z + BOARD_T;                      // 6.00 board top
//  Measured off the OUTER face: the o6.20 lid counterbore then stays
//  inside the lid whatever WALL_SIDE is.  The o2.50 pilot is carried by
//  the pilasters on the inner face, not by the bare wall.
SCREW_Y    = OY - SCREW_HEAD_D/2 - 0.20;            // 56.20

//  Pilasters: a rib on the inner face at each screw, plus one at
//  mid-span.  Each screw pilaster is 4.50 + 1.50 = 6.00 of local wall.
PILASTER_X = [-SCREW_X, 0, SCREW_X];

//  Vent lattice, derived from HEX_PITCH and HEX_WEB.  OpenSCAD's 6-gon
//  has vertices at 0, 60, ... so its flats face 30, 90, ...: neighbours
//  sit across flats, and the lattice is 1.5R across by 0.866R down with
//  alternating rows offset.
HEX_R      = HEX_PITCH/1.7320508;                  // 9.815 lattice radius
HEX_DX     = 1.5*HEX_R;                            // 14.723
HEX_DY     = 0.8660254*HEX_R;                      //  8.500
HEX_HOLE_D = (HEX_PITCH - HEX_WEB)/0.8660254;      // 16.166 across corners

//  The ESP32 DevKit V1 stand-in, from 3Dmodels/case/README.md.
ESP_W = 28.15;   // X, short edge
ESP_L = 51.50;   // Y, the pin rows run along here
ESP_H = 15.01;
ESP_X = -60.00;  // centre, near the open end
ESP_Y = BAY_Y;   // on the +Y board

// =====================================================================
//  HELPERS
// =====================================================================
module box(x0, x1, y0, y1, z0, z1) {
    translate([x0, y0, z0]) cube([x1 - x0, y1 - y0, z1 - z0]);
}

//  Cutaway for preview only.  CUT_AT is a fraction of the case's outer
//  envelope, measured from the -X / -Y face of that axis.
module cutaway() {
    if (CUT_AWAY == "none") {
        children();
    } else {
        difference() {
            children();
            if (CUT_AWAY == "+X")
                box(-OX - LID_OVH + CUT_AT*(2*OX + LID_OVH) - 1, OX + 1,
                    -OY - 1, OY + 1, -1, WALL_H + LID_T + 2);
            if (CUT_AWAY == "-X")
                box(-OX - LID_OVH - 1, -OX - LID_OVH + CUT_AT*(2*OX + LID_OVH) + 1,
                    -OY - 1, OY + 1, -1, WALL_H + LID_T + 2);
            if (CUT_AWAY == "+Y")
                box(-OX - LID_OVH - 1, OX + 1,
                    -OY + CUT_AT*2*OY - 1, OY + 1, -1, WALL_H + LID_T + 2);
            if (CUT_AWAY == "-Y")
                box(-OX - LID_OVH - 1, OX + 1,
                    -OY - 1, -OY + CUT_AT*2*OY + 1, -1, WALL_H + LID_T + 2);
        }
    }
}

// =====================================================================
//  STAND-INS  -  the boards and the ESP, for the preview and the fits
// =====================================================================
//  The board is centred on its own origin: X is the long edge, Y across,
//  z = 0 at the PCB underside.  The pad grid is the vendor one: 63 rows
//  from 1.905 in from the -X edge, 6 + 6 columns either side of the
//  7.62 centre channel, and the power rails outboard of them.  It is a
//  stand-in, so the two extra 7th pads per row that give the 1250 count
//  are left out - they would sit in the same clip-free margin.
module board() {
    difference() {
        translate([-BOARD_L/2, -BOARD_W/2, 0])
            cube([BOARD_L, BOARD_W, BOARD_T]);

        // 4 x o3.2 mounting holes, 46 x 160, centred on the board
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx*BOARD_PAT_X/2, sy*BOARD_PAT_Y/2, -1])
                cylinder(d = BOARD_HOLE_D, h = BOARD_T + 2, $fn = 24);

        if (SHOW_PADS) {
            // 63 rows x (6 + 6) tie pads
            for (r = [0 : BOARD_ROWS - 1])
                for (sy = [-1, 1], c = [0 : 5])
                    translate([-BOARD_L/2 + BOARD_ROW_0 + r*BOARD_PAD_P,
                               sy*(BOARD_COL_0 + c*BOARD_PAD_P), -1])
                        cylinder(d = BOARD_PAD_D, h = BOARD_T + 2, $fn = 12);

            // outer power rails: two columns each side
            for (sy = [-1, 1], c = [0 : 1], r = [0 : 58])
                translate([-BOARD_L/2 + 9.53 + r*BOARD_PAD_P,
                           sy*(21.275 + c*BOARD_PAD_P), -1])
                    cylinder(d = BOARD_PAD_D, h = BOARD_T + 2, $fn = 12);

            // centre-channel rails: one column each side of the centreline
            for (sy = [-1, 1], r = [0 : 62])
                translate([-BOARD_L/2 + 1.91 + r*BOARD_PAD_P, sy*1.27, -1])
                    cylinder(d = BOARD_PAD_D, h = BOARD_T + 2, $fn = 12);
        }
    }
}

//  ESP32 DevKit V1: 28.15 x 51.50 x 15.01, the two pin rows 22.86 apart.
//  Local origin at the board top, centre of the footprint; USB faces -X.
module esp32() {
    // the two header strips, standing on the protoboard
    for (sx = [-1, 1])
        translate([sx*11.43 - 1.27, -ESP_L/2 + 2.0, 0])
            cube([2.54, ESP_L - 4.0, 10.0]);

    // PCB
    translate([-ESP_W/2, -ESP_L/2, 10.0]) cube([ESP_W, ESP_L, 1.6]);

    // shield can
    translate([-9.0, -9.0, 11.6]) cube([18.0, 18.0, 3.4]);

    // USB socket on the open-end edge
    translate([-ESP_W/2 - 1.0, -4.0, 10.0]) cube([1.0, 8.0, 3.0]);
}

// =====================================================================
//  PINCH CLIP  -  one per board mounting hole
// =====================================================================
//  Absolute z throughout, because the clip's heights are the fits:
//    z FLOOR .. SEAT_Z-FLANGE_H   o4.00 post, below the board
//    z .. SEAT_Z                  o4.00 -> o6.00 flange, flat top
//    z .. BOARD_TOP+CLR           o2.80 pin through the o3.20 hole
//    z .. +HEAD_H                 4.30 x 2.90 elliptical head
//
//  The head is deliberately NOT round.  Its 2.90 Y axis already clears the
//  o3.20 hole, so only the 4.30 X axis has to move.  The slot runs along Y,
//  which leaves the two halves free to be pinched together along X: a board
//  coming down cams them in, and squeezing the two top halves together
//  brings 4.30 down to 3.20 so the board lifts off.  A single slot in a
//  round head would not work - squeezing one diameter leaves the other at
//  4.30, which cannot pass the hole.
module pinch_clip() {
    head_z = BOARD_TOP + PINCH_HEAD_CLR;
    top_z  = head_z + PINCH_HEAD_H;

    difference() {
        union() {
            // lower post, floor to the flange
            translate([0, 0, FLOOR])
                cylinder(d = PINCH_POST_D,
                         h = SEAT_Z - PINCH_FLANGE_H - FLOOR);

            // support flange: conical underside, flat top for the board
            translate([0, 0, SEAT_Z - PINCH_FLANGE_H])
                cylinder(d1 = PINCH_POST_D, d2 = PINCH_FLANGE_D,
                         h = PINCH_FLANGE_H);

            // pin through the board hole
            translate([0, 0, SEAT_Z])
                cylinder(d = PINCH_PIN_D, h = head_z - SEAT_Z);

            // elliptical split head: 4.30 across X, 2.90 across Y
            hull() {
                translate([0, 0, head_z])
                    scale([PINCH_HEAD_DX/PINCH_PIN_D,
                           PINCH_HEAD_DY/PINCH_PIN_D, 1])
                        cylinder(d = PINCH_PIN_D, h = 0.01);
                translate([0, 0, top_z - 0.01])
                    cylinder(d = PINCH_PIN_D, h = 0.01);
            }
        }

        // full-depth slot along Y: two cantilever halves, joined by the floor
        translate([-PINCH_SLOT_W/2, -(PINCH_FLANGE_D/2 + 1), FLOOR])
            cube([PINCH_SLOT_W, PINCH_FLANGE_D + 2, top_z - FLOOR + 1]);
    }
}

// =====================================================================
//  BASE
// =====================================================================
module base() {
    difference() {
        union() {
            // floor
            box(-OX, OX, -OY, OY, 0, FLOOR);

            // two long walls, the closed +X end, and the -X sill
            box(-OX, OX,  IY,  OY, 0, WALL_H);
            box(-OX, OX, -OY, -IY, 0, WALL_H);
            box( IX, OX, -OY,  OY, 0, WALL_H);
            box(-OX, -IX, -OY, OY, 0, SILL_H);

            //  pilasters: a thicker pillar on the inner face at each screw
            //  and at mid-span.  These are what carry the M3 pilots now
            //  that the wall behind them is only 4.50 thick.
            for (px = PILASTER_X, sy = [-1, 1])
                translate([px, sy*(IY - PILASTER_T/2), 0])
                    box(-PILASTER_W/2, PILASTER_W/2,
                        -PILASTER_T/2, PILASTER_T/2,
                        FLOOR, WALL_H);

            // no rib between the boards: the 1.00 gap is all they get
            // 8 pinch clips, one in each board mounting hole
            for (sx = [-1, 1], sy = [-1, 1], by = [-1, 1])
                translate([sx*BOARD_PAT_X/2,
                           by*BAY_Y + sy*BOARD_PAT_Y/2, 0])
                    pinch_clip();
        }

        // M3 pilots down into the long walls
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx*SCREW_X, sy*SCREW_Y, WALL_H - 10])
                cylinder(d = 2.50, h = 10.20, $fn = 24);
    }
}

// =====================================================================
//  LID
// =====================================================================
//  Honeycomb vent field.  6-gons with their flats facing +/-Y, on a
//  lattice HEX_DX across and 2*HEX_DY down, alternate columns dropped by
//  HEX_DY.  Trimmed square to the solid border, so the cells at the edge
//  come out as part hexagons.
module lid_vents() {
    translate([0, 0, WALL_H - 1])
        intersection() {
            union()
                for (i = [-9 : 9], j = [-9 : 9])
                    translate([i*HEX_DX,
                               HEX_DY*((i % 2 == 0) ? 0 : 1) + 2*HEX_DY*j,
                               0])
                        cylinder(d = HEX_HOLE_D, h = LID_T + 2, $fn = 6);
            box(-VENT_X, VENT_X, -VENT_Y, VENT_Y, -1, LID_T + 3);
        }
}

module lid_local() {
    difference() {
        union() {
            // slab
            box(-OX - LID_OVH, OX, -OY, OY, WALL_H, WALL_H + LID_T);

            // register lip: a 2 mm ring down the inside of the walls,
            // buried 0.50 into the slab so the union has no coplanar face
            difference() {
                box(-IX + LID_FIT, IX - LID_FIT,
                    -IY + LID_FIT, IY - LID_FIT,
                    WALL_H - LID_LIP, WALL_H + LID_EMBED);
                box(-IX + LID_FIT + LID_LIP_W,
                     IX - LID_FIT - LID_LIP_W,
                    -IY + LID_FIT + LID_LIP_W,
                     IY - LID_FIT - LID_LIP_W,
                    WALL_H - LID_LIP - 1, WALL_H + LID_EMBED);
            }
        }

        //  the lip is interrupted where a base pilaster comes up through
        //  it.  The cut stops at the slab's underside, so it leaves no
        //  mark on the outside.
        for (px = PILASTER_X, sy = [-1, 1])
            translate([px, sy*(IY - LID_FIT - LID_LIP_W/2), 0])
                box(-PILASTER_W/2 - 0.30, PILASTER_W/2 + 0.30,
                    -LID_LIP_W/2 - 0.30, LID_LIP_W/2 + 0.30,
                    WALL_H - LID_LIP - 1, WALL_H);

        //  hexagonal vent field, cut straight through the slab
        lid_vents();

        // M3 clearance through the slab
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx*SCREW_X, sy*SCREW_Y, WALL_H - 0.10])
                cylinder(d = SCREW_CLEAR, h = LID_T + 1.10, $fn = 24);

        // counterbore for the head, open at the top face
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx*SCREW_X, sy*SCREW_Y,
                       WALL_H + LID_T - SCREW_HEAD_H])
                cylinder(d = SCREW_HEAD_D, h = SCREW_HEAD_H + 1, $fn = 32);
    }
}

//  Print orientation: top face down, so the lip points up and needs no
//  support.  The counterbores are then recesses in the bed face.
module lid_print() {
    translate([0, 0, WALL_H + LID_T]) rotate([180, 0, 0]) lid_local();
}

// =====================================================================
//  SCENE
// =====================================================================
module boards_in_place() {
    for (by = [-1, 1])
        translate([0, by*BAY_Y, SEAT_Z]) board();
}

module assembly() {
    cutaway() {
        //  Colours are for reading the preview only; exporting a part
        //  (PART = "base" / "lid") bypasses this module entirely.
        if (SHOW_BASE)   color("#d8b64a") base();
        if (SHOW_BOARDS) color("#2f7d4f") boards_in_place();
        if (SHOW_ESP)    color("#3a3a3a")
                             translate([ESP_X, ESP_Y, BOARD_TOP]) esp32();
        if (SHOW_LID)    color([0.86, 0.86, 0.80, 0.55]) lid_local();
    }
}

// =====================================================================
//  PART SWITCH
// =====================================================================
if (PART == "base") {
    base();
} else if (PART == "lid") {
    lid_print();
} else if (PART == "lid-local") {
    lid_local();
} else if (PART == "boards") {
    boards_in_place();
} else {                // "assembly" or "all"
    assembly();
}
