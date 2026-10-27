// =====================================================================
//  Crimson Veil  -  Pi stack case          v0.7  "four-part shell"
// =====================================================================
//  Holds the Raspberry Pi 3 with the WittyPi stacked on a Core Electronics
//  CE09547 ultra-long header, and the 3.5" SPI LCD on top, and rides a
//  50 mm belt on a separate hook plate bolted to its underside.  The LiPo
//  is NOT in here: the battery enclosure is its own build, and the tub
//  that carried it - the MOUNT - is gone with it.  The plate bolts
//  straight to the BASE now, and the plate alone is the hatch you reach
//  the Pi's four screws through.
//
//  In OpenSCAD:   Design > Automatic Reload and Preview   [x]
//  so this rebuilds whenever the file is edited.
//
//  All board dimensions below were MEASURED from the vendor CAD in
//  3Dmodels/base/.  The one exception is the CE09547 header: the CAD for
//  it in that directory is a DIFFERENT part, so its numbers are the
//  vendor's published ones - read the header block in the stack section
//  for which of the three is published, which is derived, and why.  See
//  3Dmodels/case/README.md for the rest.
//
//  THE HEIGHT IS A MEASUREMENT, NOT A SUM.  The assembled electronics
//  measure 40.0 +/-0.2 from the Pi's PCB UNDERSIDE to the LCD's TOP FACE,
//  and that single figure - STACK_MEASURED, in the stack section - is what
//  the whole case is sized from.  Adding the parts up instead is what put
//  the case 10.2 mm too tall before: the sum has to assume how deep the
//  WittyPi's socket is, and nothing states it.
//
//  This file is pi-stack.scad (the three-part shell: BASE, MID, BEZEL) plus
//  the PLATE that hangs it on a belt.  The three case parts are drawn in
//  stack coordinates whose z 0 is the BASE's underside - and that IS the
//  bench, because nothing sits below the BASE any more.  One frame, no
//  wrappers: PART = "base" exports a part flat on the bed, and
//  PART = "assembly" stands it exactly where it exported.
//
//  ---------------------------------------------------------------------
//  THE FOUR PARTS
//  ---------------------------------------------------------------------
//  The LCD window is 81.80 x 51.60 - the 85.80 x 55.60 panel less a 2.00
//  retaining lip - and the Pi is 84.9 x 56.0.  The Pi therefore
//  cannot pass through the top, and a one-piece shell would be a box with
//  no way to get the electronics in.  It splits bottom-up, and the BASE /
//  MID joint sits just BELOW the lowest thing on the Pi:
//
//    PLATE z -4.5 .. -0.5  the belt interface: a plate that bolts to the
//                          BASE's underside and hooks the belt, so the
//                          case hangs with the LCD parallel to the belt -
//                          which is what wearing it wants.  A separate
//                          print because the hook's fit is the one thing
//                          here no measurement can settle, so a wrong
//                          guess costs a plate and not the case.
//                          4 x M3 x 6 up into the BASE's printed plastic.
//    BASE  z  0.0 ..  5.5  floor, the four Pi screw bosses, the four bolt
//                          bosses the plate threads into, six clearance
//                          bores, and a low rim.
//                          Low enough to clear the underside of EVERY port
//                          on the Pi, so the Pi drops straight in.  The four
//                          mounting screws go up from UNDERNEATH, through
//                          counterbored holes in the floor - and the plate
//                          is what you reach them through.
//    MID   5.5 .. 40.6     every port opening, the LCD shelf, the panel row
//                          of LEDs and switches, the 12 x 7 accessory
//                          opening under that row, and the service openings
//                          for the charging cable and the battery lead.
//                          Starts at the microSD slot, the lowest thing on
//                          the Pi.  Slides down over the port connectors and
//                          the header + WittyPi stack.  This is the SHIM -
//                          the only part that changes size if the stack
//                          height turns out different.
//                          IT IS ALSO THE NUT.  Both groups of case screws
//                          thread into its wall - see the screw block.
//    BEZEL 40.6 .. 49.2    carries the LCD in a pocket, 81.80 x 51.60 window,
//                          6 x M3 x 14 pass through it into the MID.
//
//  Each joint is marked with a shallow SEAM groove round the outside, so
//  the split reads clearly both in the render and on the printed part.  The
//  BASE has only the one, at the top of its rim: the plate seats on its
//  underside, so the groove that used to mark the joint down there would be
//  a groove under the plate.
//
//  ---------------------------------------------------------------------
//  WHY THE PLATE IS A BOLT-ON AND NOT PART OF THE BASE
//  ---------------------------------------------------------------------
//  The four Pi mounting screws go in from UNDERNEATH the BASE, so anything
//  fixed under the BASE blocks the one joint the Pi is held by.  The plate
//  is therefore the first thing off and the last thing on, and that order -
//  plate, then the Pi - is the whole service path into this case.  Two
//  consequences, and they set everything about the plate:
//    - the BASE's underside is FLAT, because it is the face the plate seats
//      on.  That is why the six case bores are outside the plate's footprint
//      (see the plate block) and why the four plate-bolt bosses stand INSIDE
//      the BASE's floor rather than proud of its underside.
//    - the plate is swappable.  Any plate on this bolt rectangle fits, and
//      the case does not change when you find a better way to hang it.
//
//  It also decides the lead route.  The Pi's PCB fills its cavity to within
//  CLR = 0.60 mm of every wall, so there is no internal path from the floor
//  up to the WittyPi's JST.  The pack's lead comes in through the o9 grommet
//  in the MID's +Y wall, the one face the Pi puts no ports on, and the pack
//  itself hangs off the belt beside the case - so the run from the belt up
//  that face is nearly straight.  The two tie holes flanking the grommet are
//  what stop that lead being yanked reaching the cell's solder joints.
//
//  ASSEMBLY
//    0. drop the Pi into the BASE - the rim is low enough that nothing on
//       the board fouls it, and all four mounting holes stay clear
//    1. 4 x M2.5 x 14 up from underneath the BASE, through the counterbored
//       floor holes and the Pi, with a nut on top of each.  These can be
//       driven from outside the box, and the whole stack can be built on the
//       bench before it ever goes near the case
//    2. the CE09547 header, then the WittyPi
//    3. slide the MID down over the stack; every port opening is in it, so
//       it has to go on before the plugs do
//    4. drop the LCD into the BEZEL pocket, from underneath - its 26-pin
//       socket faces down and lines up with the GPIO column, and lands on
//       the MID's shelf, which is what stops a press on the glass from
//       reaching the header's pins
//    5. drive the 6 x M3 x 14 up from underneath, through the BASE's rim
//       into the MID's lower pilots, then land the BEZEL on top and drive
//       the other 6 x M3 x 14 down into the MID's upper ones
//    6. the belt plate onto the BASE's underside - 4 x M3 x 6 up into the
//       BASE's printed plastic, driven from under the belt face
//
//  Step 0 comes first and step 6 last for a reason: once the Pi is in, the
//  BASE's four counterbored floor holes are underneath it, and the plate is
//  what you reach them through.  With the whole case standing on the belt
//  plate, the plate comes off first - four screws - and then the Pi's four.
//  That is the whole point of the plate being a separate part.
// =====================================================================

$fn = 48;

//  "plate" | "base" | "mid" | "bezel"   - one part, for export
//  "stack"                     - the electronics alone, assembled
//  "header"                    - the CE09547 header on its own, for checking
//  "assembly"                  - all four parts in place, with the boards
//  "sweep"                     - the MID lowered over the assembled stack
//  "trailer"                   - the animated build, for the demo video
//  "all"                       - all four laid out for printing
PART = "assembly";

//  PART = "sweep" is the clearance view: BASE and the four boards fixed, the
//  MID translated up by SWEEP_LIFT.  Set SWEEP_LIFT to a number for one
//  frame, or leave it at -1 and use --animate to watch the shell descend.
//  The range covers the MID's whole travel: at 0 it is seated, at 80 it is
//  clear of the LCD's top.
SWEEP_LIFT = -1;
SWEEP_SPAN = 80;

// ---------------------------------------------------------------------
//  PREVIEW TOGGLES  -  on-screen only, they never touch an exported STL
// ---------------------------------------------------------------------
//  With PART = "assembly", flip these to strip the model down until the
//  bit you want to look at is the only thing left.  Everything that is
//  switched off is simply not built, so it does not hide anything either.
SHOW_PLATE = true;     // the belt plate under everything, hooks down
SHOW_BASE  = true;     // the tray with the Pi's mounting bosses
SHOW_MID   = true;     // the shell with every port opening
SHOW_BEZEL = true;     // the LCD cover
SHOW_PI    = true;
SHOW_WITTY = true;     // the WittyPi on its extended header
SHOW_HDR   = true;     // the CE09547 header itself, between the two
SHOW_LCD   = true;
SHOW_LED   = true;     // the three indicator LEDs, in the panel's bores
SHOW_SW    = true;     // the three tactiles, in the pockets under them

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
//  MEASURED OFF THE PART, not the mesh.  The imported mesh is an older 5.50
//  slab (85.00 x 55.50) with a 5.00 screen stack; the real module is 85.80 x
//  55.60 and 7.00 from the PCB's underside to the screen's top face.  The
//  extra 1.50 is all above the PCB, so the case's shelf still meets the PCB
//  underside and only the screen sits higher in the pocket.
LCD_W     = 85.80;     // slab outline, measured
LCD_D     = 55.60;
LCD_T     =  7.00;     // panel+PCB slab, measured
LCD_ACT_W = 74.00;     // visible area -> the bezel window
LCD_ACT_D = 49.00;
//  TOLERANCE, because the printed pocket is not the CAD.  Each side of the
//  BEZEL pocket gets LCD_FIT over the measured outline.  The window is cut
//  from the panel outline less LCD_LIP, which is the material that holds the
//  LCD down - enough to retain it, little enough that the bezel does not
//  cover the screen.  WIN_CLR is the floor under that: the opening must still
//  clear the visible area by at least this much on every side.
LCD_FIT   =  0.40;     // per side: pocket clearance
LCD_LIP   =  2.00;     // per side: bezel left over the panel's edge
WIN_CLR   =  0.40;     // per side: MINIMUM opening beyond the visible area
//  The imported mesh, for the stand-in in lcd(): its slab is 5.50 thick and
//  its screen's top face measures 84.51 x 55.00.  Those three numbers are the
//  only ones the mesh still gets to state.
LCD_MESH_T     = 5.50;   // its slab
LCD_MESH_TOP_W = 84.51;  // its screen top
LCD_MESH_TOP_D = 55.00;
//  Measured off the mesh: the slab spans model z -0.75 .. +4.75, and its
//  26-pin socket reaches down to -13.55.  So the socket hangs 12.80 below its
//  underside, which is the one number the mesh and the real part share.
//
//  These two read -0.80 and 12.75 until now, which is one part described
//  inconsistently: 12.75 is the hang measured from -0.80, but the slab's real
//  underside is at -0.75.  Left alone it put the socket 0.05 mm INTO the
//  WittyPi and the slab 0.05 mm ABOVE the shelf it is meant to seat on.  Both
//  come off the mesh now, and SPLIT_B moves 0.05 with them - the three are one
//  change, never one alone.
LCD_SLAB_LO = -0.75;   // model Z of the slab underside (top face is +4.75)
LCD_DROP  = 12.80;     // model Z -13.55, so this much of socket/header hangs
                       // below the slab - and it is what sets the case height
LCD_OUT_X =  0.00;     // this model is centred on its own origin
LCD_OUT_Y =  0.00;

// 2x20 ultra-long stacking header / Core Electronics CE09547
//  The one part here whose CAD in this repo is NOT the part.  ../base/
//  2x20-stacking-header-1.snapshot.1/ is a shorter header (a 5.08 x 51.5 x
//  8.5 insulator on ~11.3 pins - an Adafruit 2223-alike, 16.4 overall), and
//  its solids sit in rotated local frames, so even parsing it measures the
//  part's own frame rather than its assembled size.  So the numbers below are
//  the vendor's PUBLISHED figures, and they are authoritative over that model:
//
//    total  23.50   above the Pi's PCB top face - where the WittyPi's socket
//                   lands.  This is the number the case is built on.
//    pins   14.50   standing above the body's top face
//    body    5.08   <- THE ONE NUMBER HERE NOT PUBLISHED.  See below.
//
//  23.50 - 14.50 = 9.00 is the height of the body's TOP face, and that is what
//  fixes the body at 5.08: its underside has to sit high enough above the Pi's
//  own GPIO header to swallow it.  Measured off the Pi's mesh, that header's
//  insulator tops out 2.50 above the PCB top and its pins at 8.00, so a 5.08
//  socket on a 3.92 standoff clears the pin tips by 1.00 while engaging them
//  4.08 deep.  3.92 + 5.08 + 14.50 = 23.50 exactly, which is why 5.08 is the
//  value and not a guess.  It is also 5.08 on the reference CAD above.
//
//  HDR_BODY_D is a second borrowed number, and a more dangerous one: an 8.50
//  body centred on the Pi's GPIO overhangs the Pi's own PCB edge by 0.75, and
//  the case only leaves 0.60 there - so the +Y wall is RELIEVED to take it.
//  See HDR_RELIEF_D, which also says why that is better than trusting 8.50.
HDR_BODY   =  5.08;    // Z, the insulator
HDR_BODY_W = 51.50;    // X, the 2x20 in plan - matches the Pi's 50.8 field
HDR_BODY_D =  8.50;    // Y - wider than a plain header: it swallows one
HDR_PIN_L  = 14.50;    // Z, the pins above the body's top face
HDR_PIN    =  0.64;    // square
HDR_PITCH  =  2.54;

// =====================================================================
//  TUNE THESE
// =====================================================================
// A screwed joint needs the wall to swallow the clearance hole.  At 4.50 an
// M3 clearance bore (o3.40) sits on the wall centreline with 0.55 either side,
// which is still enough for the pilot and leaves the seam keep-out its full
// ligament.  M3 button heads throughout, threading straight into the printed
// plastic, no inserts anywhere.
//
// THE HEAD IS WIDER THAN THE WALL.  A o5.70 button head needs a o5.80
// counterbore, and 5.80 > 4.50, so every counterbore opens through the outer
// side face.  It is cut anyway, because the request is a FLUSH face: the head
// lands at OH / z 0 with the case's face instead of standing 1.65 proud.  The
// recess breaks out for 0.65 on the outboard side, at both the BEZEL's top
// and the BASE's underside; that is the unavoidable consequence of a 4.50
// wall and a button head, and it is visible in the render rather than hidden.
// The head still bears on the inboard half of the counterbore floor.  A
// contained counterbore needs a 5.80 wall; the only other option is a proud
// head.
WALL        = 4.50;    // wall thickness - houses the vertical joint screws
CLR         = 0.60;    // board-to-wall clearance, per side - the MID has to
                       // drop over the whole stack, so this is the fit that
                       // matters; it also carries through the BASE and BEZEL
FLOOR       = 2.60;    // floor slab thickness
FLOOR_CLEAR = 5.00;    // PCB underside above the interior floor

// The BASE / MID joint, set just under the lowest thing on the Pi - the
// microSD socket, whose underside is at z 6.01, and the Ethernet shell, whose
// underside is at 5.93.  At 5.50 the BASE is a low tray whose rim clears the
// whole board, so the Pi drops straight in and a driver reaches all four
// mounting holes square on instead of down the inside of a deep well.  Every
// port opening then lands in the MID, and the BASE cuts no ports at all.
JOINT_A     = 5.50;

//  Axial clearance at each printed butt joint.  Both faces are flat prints
//  with their own first-layer variation, so they are not modelled in contact:
//  the MID starts MATE_GAP above the BASE's rim and the BEZEL starts the same
//  distance above the MID's top.  The outer seam groove straddles each gap, so
//  the 0.20 reads as a shadow line rather than an open slit, and the screws'
//  preload closes it on assembly.  The LCD shelf stays at SPLIT_B, so the LCD
//  stack does not move with either gap.
MATE_GAP    = 0.20;

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
//  parts, which reads as a clear divide in the render and on the printed case.
//  Kept to 0.60 deep - no deeper, because the screws sit on the wall centreline
//  2.50 from each face.
//
//  AT M2 THAT WAS THE WHOLE STORY: a o2.20 bore put its edge 1.40 out, and a
//  0.60 groove under it still left 0.80 of wall.  An M3 clearance bore is
//  o3.40, so its edge is only 0.80 out, and the same groove would leave 0.20 -
//  a strip the screw's own expansion is going to split.  Shallowing the groove
//  to 0.30 is all the room there is and would barely read as a line, so
//  instead THE GROOVE STOPS SHORT OF EVERY SCREW: seam() cuts a
//  SEAM_PATCH x SEAM_CLEAR patch out of its cutter at each of the six columns,
//  which restores the full wall there and keeps the ligament at 0.80.  All six
//  columns are on straight runs well inside the corners, so the patches are
//  plain cubes, and every one of them lands behind a screw head - nothing
//  extra to look at.  In the render the two groove rings read as six dashes
//  each rather than unbroken rings.
//
//  SEAM_CLEAR and SEAM_PATCH themselves live down in the screw block, because
//  SEAM_CLEAR is written off SCREW_CLR - see there.
SEAM_H      = 1.60;
SEAM_D      = 0.60;

//  The Pi's four mounting screws go in from UNDERNEATH, so the whole stack can
//  be built on the bench and dropped in, and the screws driven from outside
//  the box rather than down the inside of a well.  That decides the boss: it
//  is a clearance sleeve with a counterbore in the case's underside, not a
//  blind self-tapping pilot.  A screw driven from below has its head on the
//  far side of the Pi from the boss's shoulder, so it cannot clamp the board
//  on its own - each one needs a nut above the PCB.
//
//  These are M2.5, and they are the only M2.5 in the build.  They used to be
//  M2 to match the case's own six, on the grounds that one screw size is worth
//  something; the case screws are M3 now, so that is spent, and M2.5 is what
//  the Pi's own mounting holes are for - they are o2.75, which is why an M3
//  cannot go through them.
BOSS_D      = 7.00;    // Pi screw boss diameter
PI_SCREW_CLR = 2.80;   // M2.5 clearance, bored right through the boss and floor
PI_CBORE_D  = 5.00;    // counterbore for an M2.5 pan head (dk 4.7)
PI_CBORE_H  = 1.40;    // head height 1.4, so the head sits just flush
//  -> leaves 1.20 mm of floor under each counterbore (FLOOR - PI_CBORE_H) and
//     1.00 mm of boss wall round it, the same trade the M2 version made at
//     1.25 and 1.10.  That 1.00 is what caps the Pi's screws at M2.5.
//  -> 4 x M2.5 x 14 mm pan head, up from underneath, + 4 x M2.5 nuts on the
//     PCB.  Head seat at 1.40, boss top at 7.60, PCB top at 8.93, nut 2.0
//     tall, so the tip lands at 15.40 - 4.5 mm proud of the nut, into the gap
//     the header now stands across.  That gap went from 11.00 to 23.50 with
//     the CE09547, and none of the four screws is under the header's body
//     anyway: they sit at x 8.85 / 66.85 and the body spans x 12.10 .. 63.60.

SCREW_CLR   = 3.40;    // M3 clearance, through the BEZEL and through the BASE
SCREW_PILOT = 2.75;    // M3 thread-forming pilot, in the MID - 0.25 over the
                       // old 2.50 for the printer's hole shrink and drill drift
SCREW_DEEP  = 15.00;   // pilot depth, MINIMUM - TWO per column, see below.
                       // At MID_H = 34.90 two 15 mm drills leave 4.90 of solid
                       // wall between their floors.
//  A flush button head.  o5.70 head, 1.65 tall, so o5.80 x 1.65 recess plus a
//  0.20 x 45 deg lead-in.  See the WALL note for why it opens through the
//  outer side face at the six top columns.
SCREW_CBORE_D = 5.80;
SCREW_CBORE_H = 1.65;
SCREW_CSK_D   = 6.20;
SCREW_CSK_H   = 0.20;
SEAM_CLEAR  = SCREW_CLR / 2 + 0.20;  // = 1.90, in from the face - as far as
                                     // the seam keep-out has to reach to clear
                                     // the bore's own edge at 0.80
SEAM_PATCH  = 7.00;                  // ...and how far along the wall it runs
SCREW_L     = 14.00;   // the case screws, and the longest that fits either
                       // group with room to spare - see the window below
//  -> 12 x M3 x 14 mm button head screws hold the case together, in TWO
//  groups of six that share the same six columns.
//
//  THE MID IS THE NUT.  Both groups thread into the MID's wall, and neither
//  reaches the BASE's - which is the whole point, because the BASE's rim is
//  only 5.50 tall (it stops under the Pi's Ethernet shell) and cannot hold a
//  deep pilot.  The MID's wall is 34.90 tall, so it can:
//
//    BEZEL  -> MID   head flush on the BEZEL's top face at OH = 49.20, its
//                    shank down through the BEZEL's 8.60, into a blind o2.75
//                    pilot in the MID from SPLIT_B down to SPLIT_B - 15.00.
//    BASE   -> MID   head flush under the BASE's underside at z 0, its shank
//                    up through the BASE's 5.50 wall, across the MATE_GAP
//                    joint clearance, into a blind o2.75 pilot in the MID from
//                    JOINT_A + MATE_GAP up to JOINT_A + MATE_GAP + 15.00.
//
//  So each column carries two blind pilots 15.00 deep, 4.90 apart, drilled
//  from opposite ends - the same hole positions, which is what the user meant
//  by reusing them.  Heads are flush in 1.65 counterbores, so the usable screw
//  length is where the two windows overlap: the BEZEL side takes 5.45 .. 20.45
//  and the BASE side 4.05 .. 19.05 (the lower pilot starts MATE_GAP higher),
//  so ANY M3 from 8 to 19 fits both.  14 is specified: 8.55 of bite on the
//  BEZEL side (tip at 33.55, 6.45 above the pilot's floor) and 9.95 on the
//  BASE side (tip at 15.65, 5.05 below the pilot's ceiling).  The extra depth
//  is the margin a stripped hole is re-driven into, not extra bite for the
//  screw.
//
//  15.00 IS THE DEPTH THAT MATTERS.  It is past the 10 mm first asked for with
//  5 mm to spare, and it is the stock a stripped hole is re-driven into -
//  there is no insert to replace, so the extra depth IS the repair.  See the
//  README's "threading directly into plastic" before changing it.
//
//  THE HEADS ARE COUNTERBORED FLUSH.  A button head is o5.70, so the recess is
//  o5.80 x 1.65 with a 0.20 x 45 deg lead-in.  At OH it is cut into the
//  BEZEL's solid lip; at z 0 it is buried in the BASE's 2.60 floor.  The top
//  recess is 0.65 wider than the 4.50 wall, so its outer side opens through
//  the case's side face - that is geometry, not a mistake, and the head is
//  still flush with the top.  Both ends stay reachable, the BEZEL's from the
//  top and the BASE's from underneath (the plate does not cover them).


// ---- airflow and the battery lead, in the +Y wall --------------------
//  The one wall the Pi puts no ports on.  The battery is NOT in this
//  enclosure, and stays out of it.  The two service openings that used to be
//  here - the charging-cable slot and the o9 battery-lead grommet - are gone
//  at the user's request.  What is left is a hexagonal vent field through the
//  wall, and one small rectangle at its left for the pack's lead.  Measured in
//  case coordinates: X along the wall, Z up from the case floor.
//
//  The hexagons are cut with $fn = 6 cylinders.  A vertex sits on +X, so each
//  hole is 2 * HEX_R wide and sqrt(3) * HEX_R tall.  Odd columns rise half a
//  row, which is what makes the field read as a honeycomb instead of square
//  columns; the remaining web is 2.00 along X and 2.94 between flats.  The
//  field starts 4.50 in from the case screw at x 9.00 and stops 4.50 short of
//  the lead rectangle, so no hole touches either one.
HEX_R       =  3.50;   // circumradius: 7.00 wide, 6.06 across the flats
HEX_DX      =  9.00;   // column pitch along X
HEX_DZ      =  9.00;   // row pitch along Z
HEX_X0      = 17.00;   // first column centre
HEX_NX      =  6;      // columns
HEX_Z0      = 12.00;   // first row centre, even columns
HEX_NZ      =  3;      // rows per column
HEX_HW      =  HEX_R;  // half-width of a hole, for the clearances below
HEX_HH      =  HEX_R * sqrt(3) / 2;         // half-height across the flats

LEAD_RX0    = 70.00;   // battery lead: a plain 10.00 x 6.00 rectangle
LEAD_RX1    = 80.00;
LEAD_RZ0    = 17.00;
LEAD_RZ1    = 23.00;

// ---- vents, in the BASE's -Y wall -----------------------------------
//  The row was the battery bay's air path.  There is nothing in here to vent
//  but the Pi, the WittyPi and the LCD, and a sealed box of those three
//  wants a way out for hot air that is not a port opening.  The BASE is the
//  only wall it fits: the MID's -Y wall is the ports and the panel row, and
//  its +Y wall is now the hex vent field and the lead.  5 x 6.00 x 2.50 at 9.00 pitch, centred on the
//  case, with 1.50 of web above and below it inside the 5.50 rim - and clear
//  of the two case screws in that wall at x 9.00 and 86.62.
//  Set VENT_N = 0 to delete the row, and read panel()'s note on ranges
//  before assuming that does what it looks like it does.
VENT_N      =  5;
VENT_W      =  6.00;
VENT_H      =  2.50;
VENT_P      =  9.00;                        // pitch
VENT_Z      =  2.75;                        // centred in the 5.50 rim

//  EXT_HEADER  -  how far the TOP OF THE PIN TIPS stands above the Pi's PCB
//  top face.  Since v0.7 it is the vendor's figure for the CE09547 rather
//  than the 11.00 placeholder the old case was built on.
//
//  NOTE WHAT IT DOES NOT SET: the case's height.  It used to, on the
//  assumption that the WittyPi's PCB lands on the pin tips - and that is
//  exactly the assumption that was wrong, because a socket swallows the pins
//  it mates with, so the WittyPi's PCB sits BELOW the tips by however deep
//  that socket is.  Nothing published says how deep, which is why the height
//  comes from the assembled measurement below instead (STACK_MEASURED), and
//  why WP_SOCK_D in the DERIVED block is derived from the two of them.
//  Adding the parts up without it put the case 10.2 mm too tall.
//
//  What EXT_HEADER DOES fix is the BODY's position, and that is the part the
//  case has to clear: 23.50 less the 14.50 of pin leaves the body's top at
//  9.00 and its underside at 3.92 (see HDR_BODY), so the pins stop just
//  above the Pi's own GPIO header and the body swallows it.  That is what
//  makes CE09547 a drop-in replacement for a stacking header rather than
//  something to solder flat into the Pi's own holes - soldered flush, its
//  pins would stop about 4 mm short.
EXT_HEADER  = 23.50;

//  STACK_MEASURED  -  the assembled electronics, measured END TO END: the
//  Pi's PCB UNDERSIDE to the LCD's TOP FACE, 40.0 +/- 0.2 mm.
//
//  THE AUTHORITATIVE NUMBER, and the only one that closes the whole chain -
//  PCB, header standoff, body, pins, the WittyPi's socket, the WittyPi, the
//  LCD's socket, the slab - in a single measurement.  Everything above the
//  Pi follows from it in the DERIVED block.  The one thing it leaves
//  implicit, the depth of the WittyPi's socket, is derived there as
//  WP_SOCK_D and cross-checked against EXT_HEADER, so the published figure
//  and the measurement cannot disagree without verify.py saying so.
//
//  Re-measure the stack and this is the only line to change.
STACK_MEASURED = 40.00;

//  LCD_UNDER_MEASURED  -  override for the LCD slab's underside.
//  Leave at -1 and it comes off STACK_MEASURED, which is the number to
//  trust.  Set a positive value to pin the slab itself with a caliper
//  reading instead; the WittyPi moves with it, because it hangs off the LCD
//  rather than sitting on the pins (see the DERIVED block).
LCD_UNDER_MEASURED = -1;

// ---- the front panel -------------------------------------------------
//  Three indicator LEDs and three momentary switches in the -Y wall, the
//  same face the power, HDMI and audio ports are on.
//
//  WHERE THIS IS ALLOWED TO GO, AND WHY IT IS A NARROW BAND
//  The -Y wall is only free between ABSOLUTE z 36.56 and 61.10, which is
//  stack z 15.56 .. 38.60:
//    - below, the HDMI opening tops out at stack z 15.56, the highest of
//      the three ports on this wall;
//    - above, the MID's inner shelf starts at SPLIT_B - SHELF_T = 38.60, and
//      the MID / BEZEL seam groove reaches down to SPLIT_B - 0.80 = 39.80 -
//      so it is the shelf, not the groove, that sets the ceiling.
//  Nothing can go higher than that.  Above the shelf is the BEZEL, whose
//  rim is only 4.26 wide at the pocket with the LCD slab 0.40 mm behind it, so
//  the bezel can never take a hole.  The panel's ceiling is abs 61.10 of the
//  case's 70.20, so 87% of its height, which is as near the top as this case
//  gets.  (The band's LOWER bound is the one that is fixed: it is set by the
//  Pi's HDMI opening and does not move when the stack does.)
//
//  It is also clear of the LCD socket (x 12.31..46.60, y 55.00..60.08) and
//  of the two M3 bores in this wall, which sit at x 9.00 and 86.62 and run
//  the FULL height of the MID.
PANEL_Z     = 33.00;                         // stack z of the row; 80% up

//  A 5 mm LED is 8.60 long overall on a o5.00 barrel, so it cannot hide in a
//  4.50 wall.  Dropped in from the cavity, its flange stops against the wall's
//  inner face and the lens stands 3.60 mm proud of the outer face.  That is
//  the part, not a modelling error: a 5 mm LED in this wall is a proud lamp,
//  and the bore is sized for the barrel rather than the old 3 mm part.
//
//  There is deliberately NO flange counterbore.  An LED's flange is at its
//  BASE, so sinking it into the inner face carries the lens further out, not
//  further in.  The plain bore plus the flange against the inner face is the
//  shortest protrusion this wall can give.
LED_N       =  3;
LED_D       =  5.20;                         // the bore, for a o5.00 barrel
LED_PITCH   =  7.00;
LED_X0      = 26.00;                         // leftmost, and + pitch

//  A 6x6 tactile has no flange, so unlike the LEDs it needs something to
//  stop it - hence the pocket.  The body is pushed in from the cavity side
//  and the wall in front of it is left SW_LIP thick, with the button
//  through that.  The switch's four pins then point into the cavity, where
//  nothing is within 45 mm of them at this height.
SW_N        =  3;
SW_BODY     =  6.00;                         // the "6 x 6" of a 6 x 6 x H
SW_H        =  5.00;                         // <- the H.  SET THIS TO YOURS.
SW_POCKET   =  6.20;                         // +0.20 on the body, a slip fit
SW_LIP      =  0.45;                         // wall left in front of the body
SW_BTN_D    =  3.60;                         // button clearance through it -
                                             //  the measured actuator is
                                             //  SW_ACT_D = 3.50, so this leaves
                                             //  it 0.05 radially.  That is the
                                             //  tightest fit in the panel and
                                             //  the reason the ribs have to
                                             //  locate the body at all.
SW_PITCH    =  9.00;
SW_X0       = 50.00;                         // leftmost, and + pitch

//  Crush ribs.  A plain interference fit would let the printer's tolerance
//  decide whether the switch falls out or will not go in at all; ribs
//  deform, so they grip across that whole range and the pocket can stay a
//  clean slip fit everywhere else.  They are made by taking the rib volume
//  OUT OF THE CUT, which leaves material where the rib is.
SW_RIB      =  0.20;                         // proud, per side

//  Terminal clearance notches.  A 6x6 tactile's four strips hang outside the
//  body and bend down; their tops sit SW_LEG_UP (0.90) above the seat plane.
//  With SW_H 5.00 and the body pushed back to the lip, the seat lands at
//  SW_LIP + SW_H = 5.45, so the strip tops reach 4.55 - only 0.05 clear of
//  the inner face at WALL 4.50.  A printed wall and a real switch will not
//  hold 0.05, so each strip gets a notch behind it.  The depth also covers
//  the measured 3.86-tall part: its seat is at 4.31, so its strip tops reach
//  3.41 and need the notch to run back to at least 3.10 to keep 0.25 clear.
//  The notch is cut from the inner face SW_TERM_NOTCH deep and lapped
//  SW_TERM_MARGIN into both the pocket and the cavity so the union is
//  unambiguous; it leaves the lip and the rest of the wall intact.
SW_TERM_NOTCH  = 1.40;
SW_TERM_MARGIN = 0.20;

// ---- the reference hardware ------------------------------------------
//  The LEDs and the switches, as geometry.  Until now the panel had only
//  their NEGATIVE space - three bores and three pockets, in panel() below
//  - and verify.py confirmed they were safe by probing a box it built in
//  Python.  That box was a guess about the parts.  These are the parts.
//
//  WHERE THE NUMBERS COME FROM, because they are not all the same kind.
//
//  The LED is drawn from PUBLISHED figures, because the vendor CAD in
//  ../../base/3mm-led/ is wrong for the part that is actually fitted (and
//  unusable besides: its .stp holds three construction solids, the .igs is
//  in INCHES, and the datasheet is an outline-only AutoCAD plot).  The
//  fitted part is a standard 5 mm flanged LED - o5.00 barrel, o5.90 flange,
//  8.60 overall on a 0.50 flange, so 8.10 from the flange's bearing face to
//  the tip.  That last number is what the panel block above now records: in
//  a 4.50 wall the tip finishes 3.60 PROUD of the outer face.
//
//  The SWITCH is MEASURED, off the vendor CAD in
//  ../../base/te-tactile-momentary-switches-1.snapshot.1/1825910-6.step.
//  Not with a B-rep kernel - there is none installed - but by walking the
//  entity graph (MANIFOLD_SOLID_BREP -> CLOSED_SHELL -> ... -> VERTEX_POINT
//  -> CARTESIAN_POINT) and taking each solid's extents, which is exact for
//  a part this angular and needs nothing but the unit prefix read:
//  SI_UNIT(.MILLI.,.METRE.) - these files are in METRES, so every raw
//  number in them is 1000x what it looks like and 0.00599 is 6 mm.
//  Measured, seat plane at z 0, body corner at x/y 0:
//
//      6.00 x 6.00 body, R0.25 corners      z  0.00 ..  3.36
//      6.00 square lid, 0.25 thick          z  3.36 ..  3.61
//      4.99 square raised centre, R0.375    z  3.36 ..  3.86
//      o3.50 actuator, 0.75 proud           z  2.11 ..  4.61
//      4 legs 0.71 x 0.60, tails outside    z  0.00 .. -3.51
//         ... on a 4.50 x 6.59 pattern
//
//  So the prose above - "the four pins splay to a 6.5 x 4.5 footprint" -
//  is right to 0.09 on the long axis, and it is no longer a guess.
//
//  Two of those need a word, because the raw vertex boxes read differently.
//  The lid and the raised centre are both filleted squares, so their extreme
//  VERTICES are the tangent points, not the corners: the lid's vertex box
//  measures 5.49 and the centre's 4.24, while the plates themselves are 6.00
//  and 4.99.  Reading a vertex box as a part is the exact trap the README
//  warns about with these files, and it is why SW_TOP is 4.99 and not 4.24.
//
//  BUT THE BODY IS 3.86 TALL AND SW_H IS 5.00.  That is deliberate, and it
//  is the user's call.  At 3.86 the pocket would gain a 0.69 floor behind
//  the body, and the pins - which splay to 6.59, wider than this 6.20
//  pocket - would drive into it, so the case would need a slot cut through
//  that floor at every leg.  At 5.00 the pocket reaches the wall's inner
//  face, there is no floor, and the legs start in free cavity, which is
//  the design as verified.  So the body is drawn SW_H deep - the measured
//  part with its one full-section tier stretched, and nothing else - which
//  also means the model follows SW_H wherever it is later set, and stays
//  consistent with the pocket's own cut for free.
LED_BODY_D   =  5.00;                        // the barrel
LED_FLANGE_D =  5.90;                        // the rim that stops it
LED_FLANGE_T =  0.50;                        // ...and how thick it is
LED_LEN      =  8.60;                        // the flange's back to the tip
LED_LEAD     =  0.45;                        // square leads, on 2.54 centres
LED_LEAD_DX  =  1.27;
LED_LEAD_L   =  2.50;                        // drawn, not cut to length

SW_BODY_R    =  0.25;                        // corner fillet, measured
SW_LID_T     =  0.25;                        // the pressed metal lid, thick
SW_TOP       =  4.99;                        // the raised centre round the
SW_TOP_R     =  0.375;                       //  button - 4.99 on its R0.375
SW_TOP_H     =  0.50;                        //  corners, which is why the
                                             //  raw vertex box reads 4.24:
                                             //  that is the tangent points.
SW_ACT_D     =  3.50;                        // the actuator itself
SW_ACT_UP    =  0.75;                        // ...proud of the body's front face
SW_ACT_L     =  2.50;                        // its length, measured
SW_LEG_W     =  0.71;                        // leg, measured
SW_LEG_D     =  0.60;
SW_LEG_X0    =  1.90;                        // legs sit at +/- these, in X
SW_LEG_X1    =  2.61;
SW_LEG_Y0    =  3.00;                        // ...and OUTSIDE the body, in Y -
SW_LEG_Y1    =  3.60;                        //  the tail hangs off the edge
SW_LEG_L     =  3.51;                        // how far below the seat plane
SW_LEG_UP    =  0.90;                        // ...and the side exit's height
SW_LEG_IN    =  0.10;                        // pulled into the body, not measured

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

//  THE STACK, top-down.  The one measurement there is (STACK_MEASURED) is
//  spent here and nothing below re-enters it: LCD_TOP_Z from the PCB, the
//  slab's underside a slab-thickness below that, then the WittyPi hung
//  LCD_DROP + WP_H under the slab, because the LCD's socket is LCD_DROP long
//  and lands on the WittyPi's top face.  Every one of those is a measured
//  length; the sum is what closes the assembly.
LCD_TOP_Z  = PCB_Z + STACK_MEASURED;                // = 47.60, slab top face
LCD_UNDER  = (LCD_UNDER_MEASURED > 0) ? LCD_UNDER_MEASURED
                                     : LCD_TOP_Z - LCD_T;   // = 40.60
WITTY_Z    = LCD_UNDER - LCD_DROP - WP_H;           // = 20.72, WittyPi PCB
//  ...and THAT is what decides how far the CE09547's pins are swallowed.  The
//  tips stand EXT_HEADER above the Pi's PCB top face; the WittyPi's socket
//  mouth is level with its own PCB's underside, at WP_SOCK_D below them.
//  = 11.71 for the measured stack, which is deep for a 2x20 socket - so it is
//  derived here and asserted in verify.py rather than assumed: the check
//  fails if the pins do not reach the socket, if what stands proud of the
//  WittyPi is more than the LCD's socket can cover, or if the WittyPi fouls
//  the header's body on the way down.
WP_SOCK_D  = PCB_Z + PI_PCB_T + EXT_HEADER - WITTY_Z;       // = 11.71
HDR_PIN_UP = PCB_Z + PI_PCB_T + EXT_HEADER - WITTY_Z - WP_H;  // = 4.63 proud
//  How far the CE09547's insulator stands clear of the Pi's PCB - the gap that
//  has to swallow the Pi's own GPIO header.  Written as the subtraction rather
//  than as the 3.92 it comes out at, so that the three published figures and
//  the standoff cannot disagree: change EXT_HEADER and this follows, which is
//  what the header() module below draws and what verify.py checks.  It is
//  only consistent for a 5.08 body - see the header block for why that is the
//  value and not a guess.
HDR_STANDOFF = EXT_HEADER - HDR_BODY - HDR_PIN_L;   // = 3.92
//  The body's top face, which is as high as the RELIEF below has to reach.
//  = EXT_HEADER - HDR_PIN_L above the Pi's PCB, since the pins are the rest.
HDR_BODY_TOP = PCB_Z + PI_PCB_T + EXT_HEADER - HDR_PIN_L;   // = 17.93
HDR_TIP_Z   = PCB_Z + PI_PCB_T + EXT_HEADER;                // = 32.43, pin tips
PI_GPIO_CX = (PI_GPIO_X0 + PI_GPIO_X1) / 2 + OFF[0];
PI_GPIO_CY = (PI_GPIO_Y0 + PI_GPIO_Y1) / 2 + OFF[1];
WP_SOCK_CX = (WP_SOCK_X0 + WP_SOCK_X1) / 2;
WP_SOCK_CY = (WP_SOCK_Y0 + WP_SOCK_Y1) / 2;

SPLIT_B   = LCD_UNDER;                     // MID / BEZEL joint = LCD underside
MID_H     = SPLIT_B - JOINT_A - MATE_GAP;  // the shim, less the BASE gap
OH        = SPLIT_B + LCD_T + BEZEL_T;     // = 49.20, the whole shell

//  OH is the case's outer height, full stop: nothing sits below the BASE any
//  more, so this one number is the stack's height AND what you measure with
//  calipers.  It used to be OH_TOTAL = MOUNT_H + OH with the 21.00 tub under
//  it, and that 21 mm is exactly what this case no longer has.  Every part
//  above the BASE kept its old z when the tub went - the whole stack came
//  down with it rather than being re-derived, which is why no port, no relief
//  and no screw axis in the file needed touching.

// =====================================================================
//  THE PLATE, AND THE INTERFACE IT BOLTS TO
// =====================================================================
//  The case does not touch fabric.  It touches this plate, and the plate
//  touches the fabric - so the plate is SWAPPABLE: any plate on this bolt
//  rectangle fits, and the case does not change when you find a better way to
//  hang it.  Three are drawn; see PLATE_STYLE.
//
//  WHY THE INTERFACE IS ON THE UNDERSIDE
//  Hanging the case by its -Z face is what puts the LCD PARALLEL to the
//  mounting plane: the screen faces straight out from the belt instead of up
//  the body's side, which is the only orientation you can read while wearing
//  it.
//
//  WHY IT BOLTS RATHER THAN CLIPS
//  The plate has to come off to reach the Pi's own four screws AND the six
//  case screws that clamp the BASE to the MID - both go up from underneath the
//  case.  So it is the FIRST thing off and the LAST thing on, and four bolts
//  into the printed plastic is the least that survives being taken off and put
//  back any number of times.  Not into heat-set inserts: there are none in
//  this build.
//
//  THE INTERFACE, in base(): four o7.00 bosses standing off the INSIDE of the
//  BASE's floor, so the case's own underside stays flat and the plate's case
//  face has nothing to sit on but the case.  Each carries a BLIND o2.75 pilot
//  from the case's underside up into the boss, so the screw comes up from
//  under the plate and threads into plastic.
//
//  HOW TALL THEY MAY BE IS SET BY THE PI, NOT BY THE SCREW.  The BASE's floor
//  is 5.00 under the Pi's PCB, and the .scad already records the lowest things
//  hanging off that PCB: the Ethernet shell at 5.93 and the microSD socket at
//  6.01.  JOINT_A = 5.50 is under both of them for exactly this reason - the
//  Pi drops into the BASE instead of onto its rim.  So the bosses stop at the
//  rim: PLATE_BOSS_H is written as JOINT_A - FLOOR, and ONE of the four -
//  the +X / -Y one at (78.81, 15.85) - actually sits under the shell, which
//  spans case x 71.32 .. 92.72, y 7.75 .. 23.63.  The other three have clear
//  air above them up to the PCB at 7.60.
//
//  THAT ONE BOSS IS WHAT CAPS THE PLATE'S SCREWS, and it is why their pilot is
//  5.30 rather than the 15.00 the case screws get.  The window is 2.85 .. 8.15
//  of screw length, so M3 x 4 through M3 x 8 all fit; 6 is specified, whose
//  tip lands at 3.15 - 2.15 above the pilot's floor, with 3.15 of bite.  A
//  longer one would bottom out on the boss's 0.20 cap and stand the plate off
//  its seat, which is the one thing this joint must not do.
PLATE_BOLT_DX  = 31.00;                    // half-spacing, X
PLATE_BOLT_DY  = 17.50;                    // half-spacing, Y
PLATE_CX       = OW / 2;                   // = 48.06, the case's centre
PLATE_CY       = OD / 2;                   // = 33.60
PLATE_PILOT_D  =  SCREW_PILOT;             // M3, so the same o2.75 as the case
PLATE_PILOT_DEEP = JOINT_A - 0.20;         // = 5.30, leaving a 0.20 cap under
                                           //  the boss's top face at JOINT_A
PLATE_BOSS_D   =  7.00;
PLATE_BOSS_H   =  JOINT_A - FLOOR;         // = 2.90, up from the floor's top
                                           //  face - i.e. to the rim, and not
                                           //  one micron past it
PLATE_CLR      =  3.40;                    // M3 clearance, through the plate

PLATE_BOLTS = [
    [PLATE_CX - PLATE_BOLT_DX, PLATE_CY - PLATE_BOLT_DY],
    [PLATE_CX + PLATE_BOLT_DX, PLATE_CY - PLATE_BOLT_DY],
    [PLATE_CX - PLATE_BOLT_DX, PLATE_CY + PLATE_BOLT_DY],
    [PLATE_CX + PLATE_BOLT_DX, PLATE_CY + PLATE_BOLT_DY],
];

//  The plate.  It sits PLATE_GAP clear of the case rather than face to face:
//  both are printed parts and neither first layer is ever quite flat, so a
//  0.50 gap is what keeps the case from rocking on the plate.
//
//  PLATE_W and PLATE_D are the hook / pals footprint.  The hook's depth is
//  the case INTERIOR's, 57.20, because it has to reach the belt's lower edge:
//  a 50 mm belt on the 66.20 case leaves that edge 8.10 in from the face -
//  inside the plate, but only just.  A shallower plate would miss it.  The
//  strap's tray does not use these two; it is derived from OW / OD below.
PLATE_GAP     =  0.50;                     // case face to the plate's top face
PLATE_T       =  4.00;                     // the slab
PLATE_W       = 76.20;                     // X, 3 x the 25.4 module
PLATE_D       = OD - 2 * WALL;             // = 57.20, the case interior
PLATE_R       =  3.20;                     // corner radius; 3.20 keeps the
                                           //  corner M3 heads 0.50 clear,
                                           //  where 3.00 left only 0.44
PLATE_CBORE_D =  6.20;                     // M3 button head (dk 5.70 + 0.50),
PLATE_CBORE_H =  1.65;                     //  cut in the OUTER face and deep
                                           //  enough to bury the head's 1.65
                                           //  exactly flush - nothing stands
                                           //  proud of the face the belt lies
                                           //  against, which is the one place
                                           //  in the case a proud head would
                                           //  be felt.  (The twelve case
                                           //  screws have no such option; see
                                           //  the screw block.)

//  The screw length falls out of those: the head seats 1.65 into the outer
//  face at z -2.85, and the pilot is 0.00..5.30, so the tip has to land in
//  2.85..8.15.  -> 4 x M3 x 6, tip at 3.15: 3.15 of thread in the plastic and
//  2.15 clear of the pilot's floor, so it can neither pull out nor bottom out.
//  M3 x 8 also fits (tip 5.15, 0.15 clear) but that 0.15 is inside the
//  printer's own hole-depth tolerance, and a screw that bottoms stands the
//  plate off its seat - the one failure this joint cannot have.
PLATE_SCREW_L =  6.00;

//  "strap" - a shallow tray that hugs the case, with four arms on the corner
//  diagonals.  "hook" - two prongs that hook the belt's lower edge.  "pals" -
//  a slot field on the webbing module.  All three bolt to the same four
//  bosses; the hook and pals bodies share the 25.40 webbing grid, and the
//  strap tray is the new fabric interface.
PLATE_STYLE = "strap";

//  The hook, as a J in the Y-Z plane: a web leaves the plate's outer face and
//  runs out PLATE_HOOK_PROJ; at the far end a PLATE_HOOK_T lip turns and runs
//  back along +Y, PLATE_HOOK_LIP long.  The belt lies in the channel between
//  the plate's outer face and the lip's inner face - PLATE_HOOK_PROJ less
//  PLATE_HOOK_T = 6.00 deep, so a 4-5 mm belt has room to breathe - and its
//  LOWER EDGE rests on the lip's upper face, with the web behind it as the
//  stop.  That is the whole mount: two hooks catching the belt's lower edge at
//  the PALS module, 25.40 apart, so the case cannot rock about the belt.
BELT_W          = 50.00;                   // the belt this is sized for
PLATE_HOOK_N    =  2;
PLATE_MOD       = 25.40;                   // the webbing module, X and Y alike
PLATE_HOOK_W    = 12.00;                   // each prong's width, along X
PLATE_HOOK_PROJ =  8.00;                   // out from the plate's outer face
PLATE_HOOK_T    =  2.00;                   // the web, and so the lip
PLATE_HOOK_LIP  =  6.00;                   // the lip, along +Y
PLATE_HOOK_Y    = PLATE_CY - BELT_W / 2;   // = 8.10, the belt's lower edge

//  The webbing field, on the PALS module both ways: 1 in slots, 1.5 in rows.
PLATE_SLOT_W    = 25.40;                   // X
PLATE_SLOT_H    =  6.00;                   // Y - the gap webbing threads
PLATE_ROW_P     = 38.10;                   // Y pitch
PLATE_SLOT_N    =  2;                      // per row
PLATE_ROW_N     =  2;

//  THE STRAP PLATE.  A shallow tray under the whole case, with four arms on
//  the corner diagonals.  The tray's skirt wraps the case's lower 3.00, so
//  the plate locates itself on the case instead of merely hanging under it;
//  the arms fan out past the corners, where an elastic strap can loop over a
//  tip and seat in the waist behind it.
//
//  THE WAIST IS CUT, NOT IMPLIED BY THE NECK CIRCLE.  The tip paddle's rear
//  arc reaches back to r 60.00, so a hull whose only narrow point is the neck
//  at r 64.00 is simply swallowed by the paddle: the exported arm measured
//  16.00 wide there, not 14.00.  Two o8.00 circles per arm, 10.00 off the axis
//  at the neck's radius, cut a concave waist 12.00 wide over about 6.00 along
//  the arm.  A strap that has stretched over the 20.00 tip seats in that
//  12.00 groove and cannot slide forward again under tension.  That is the
//  same one-way logic as the belt hook, without a hook that would stand off
//  the fabric.
//
//  THE SKIRT IS OUTSIDE THE CASE, NOT INSIDE IT.  It clears the case's outer
//  wall by PLATE_SKIRT_CLR all round, so it locates without binding, and its
//  four corner radii are the case's own 3.00 plus that clearance.  It stops
//  at PLATE_SKIRT_TOP = 3.00 so it is a hug, not a shell - the MID's ports
//  start at 5.50 and nothing on the case is touched.
//
//  THE FIVE VENTS CROSS THE SKIRT, so the skirt is notched at exactly the
//  BASE's vent columns.  A continuous 3.00 skirt would have covered the
//  lower 1.50 of every vent; the notch is cut full-width, so the vent sees
//  air rather than plastic 0.50 away from it.
//
//  PRINT IT OUTER-FACE DOWN.  The skirt is on the CASE side (it points up at
//  the case), so the plate prints tray-open-up, unlike the hook plate.  The
//  four counterbores are then on the bed; each is a 6.20 pocket with a 1.40
//  inward lip, which is a trivial cantilever and needs no support.
PLATE_SKIRT_CLR = 0.50;                    // skirt inner face to the case wall
PLATE_SKIRT_T   = 3.00;                    // the skirt wall
PLATE_SKIRT_TOP = 3.00;                    // its top above the case underside
PLATE_SKIRT_OVERLAP = 0.50;                // sunk into the floor, so the union
                                           //  is one solid and not two shells
                                           //  touching on a coplanar face
PLATE_SKIRT_R   = 3.00 + PLATE_SKIRT_CLR;  // = 3.50, the skirt's inner corner
PLATE_TRAY_X0   = -PLATE_SKIRT_CLR - PLATE_SKIRT_T;
PLATE_TRAY_X1   =  OW + PLATE_SKIRT_CLR + PLATE_SKIRT_T;
PLATE_TRAY_Y0   = -PLATE_SKIRT_CLR - PLATE_SKIRT_T;
PLATE_TRAY_Y1   =  OD + PLATE_SKIRT_CLR + PLATE_SKIRT_T;
PLATE_TRAY_R    =  3.00 + PLATE_SKIRT_CLR + PLATE_SKIRT_T;   // = 6.50

//  One arm, on a radial line through a case corner.  Distances are from the
//  plate's centre along that line; the root circle sits inside the tray, the
//  neck marks where the strap's seat is cut, and the tip paddle is what the
//  strap has to stretch over to reach it.
PLATE_ARM_ANG    = atan(OD / OW);          // = 34.85 deg, the real diagonal
PLATE_ARM_ROOT_R = 46.00;
PLATE_ARM_ROOT_D = 16.00;
PLATE_ARM_NECK_R = 64.00;
PLATE_ARM_NECK_D = 14.00;
PLATE_ARM_TIP_R  = 70.00;
PLATE_ARM_TIP_D  = 20.00;
//  The cut waist.  Each circle is centred PLATE_ARM_WAIST_OFF off the arm's
//  axis at the neck's radius and removes everything outboard of
//  OFF - R = 6.00, so the strap seat is 12.00 wide.
PLATE_ARM_WAIST_OFF = 10.00;
PLATE_ARM_GROOVE_R  = 4.00;
PLATE_ARM_WAIST_D   = 2 * (PLATE_ARM_WAIST_OFF - PLATE_ARM_GROOVE_R);  // 12.00

//  How deep the switch pocket sinks into the wall.  The lip in front of the
//  body is 0.45 of wall that is never cut, only pierced by the button hole, so
//  the pocket starts at SW_LIP and cannot reach it however deep it goes.
//
//  At SW_H = WALL the pocket reaches the inner face and leaves no floor behind
//  the body, so the pins begin in free cavity space and can splay as they like.
//  A SHORTER body leaves a floor - good for taking the button's force, but
//  the four pins of a 6 x 6 tactile splay to a 6.5 x 4.5 footprint, wider
//  than this 6.20 pocket, so they would drive into it.  Either widen
//  SW_POCKET past 7.00 or drill the pins' own pattern through the floor.
//
//  The cut is the body's own height, started at the lip - not the seat depth.
//  Those differ, and getting it wrong is subtle: the body spans
//  SW_LIP .. SW_LIP + SW_H, so a cut only SW_POCKET_D deep would leave the
//  back of the body buried in a floor it is supposed to clear.  Stated as the
//  body's height, a taller-than-the-wall switch runs out the far side of the
//  wall on its own and a shorter one stops inside it and leaves a floor -
//  both without a clamp, and the overshoot comes free.
SW_POCKET_D   = min(SW_H, WALL - SW_LIP);    // the SEAT; = 4.55 for a 6x6x5
SW_POCKET_CUT = SW_H;                        // the CUT; breaks through by itself
SW_FLOOR      = WALL - SW_LIP - SW_POCKET_D; // material left behind the body
SW_BTN_OVER   = min(SW_POCKET_CUT / 2, 1.00); // how far the button hole laps
PANEL_LO      = PANEL_Z - SW_POCKET / 2;     // the pocket's z extent, stack
PANEL_HI      = PANEL_Z + SW_POCKET / 2;

//  Why the cut must never be sized to land exactly on an existing face.
//  A cut whose face coincides with the solid's face does not come out as a
//  hole: CGAL keeps the pocket as a SEPARATE closed shell inside the wall and
//  leaves a zero-thickness membrane where the opening should be.  The mesh
//  stays closed, manifold and arithmetically the right volume, so nothing
//  catches it - the MID just quietly exports as four shells instead of one,
//  and a slicer is free to read that membrane as a sealed floor with the
//  switch standing on top of it.  Every other cut in this file already
//  overshoots for the same reason (the LED bore is WALL + 2 long); sizing this
//  one from SW_H is what makes it automatic here.

// ---- the accessory opening -------------------------------------------
//  A 12 x 7 slot through the -Y wall, directly under the switch row, for
//  whatever wants to come out of the front of the case - a connector, a
//  cable gland, a lead.  It is the ONE opening in this case that no part on
//  the Pi asks for, so it is sized to the request rather than to a
//  component, and it is cut at 12.20 x 7.20 so the FINISHED opening still
//  clears 12.00 x 7.00 after the slicer's usual hole undersize - the same
//  +0.20 the switch pockets take for the same reason.  The design minimum
//  is ACC_MIN_W x ACC_MIN_H; the geometry is ACC_W x ACC_H.
//
//  WHY IT GOES HERE.  Under the switch row is the only place on this wall
//  that is free above AND below: the switch pockets' floor is at stack z
//  29.90 (PANEL_LO) and the highest port on the wall, the HDMI opening,
//  tops out at 15.56.  Centred between the two it leaves 3.57 of wall above
//  and 3.57 below, and it sits 12.90 clear of the LED row's right-hand bore
//  (x 40.00) so the panel itself is untouched.  It is 21.52 clear of the
//  M3 column at x 86.62 and 43.90 clear of the one at x 9.00.
//
//  THE FILLET IS NOT COSMETIC.  A 90 degree internal corner is a stress
//  riser in a printed wall - it is where a crack starts when the wall is
//  flexed or when the part is levered off the bed.  R1.50 rounds it off and
//  costs nothing.
ACC_MIN_W = 12.00;                     // the request: at least this, across X
ACC_MIN_H =  7.00;                     // ...and this, across Z
ACC_W     = ACC_MIN_W + 0.20;          // cut size, so the print still clears
ACC_H     = ACC_MIN_H + 0.20;          //  the minimum after hole undersize
ACC_R     =  1.50;                     // corner fillet
ACC_CX    = SW_X0 + (SW_N - 1) * SW_PITCH / 2;  // = 59.00, under the buttons
ACC_LO    = HDMI[5] + OFF[2] + PORT_G;          // = 15.56, HDMI's top edge
ACC_HI    = PANEL_LO;                           // = 29.90, the pocket floors
ACC_CZ    = (ACC_LO + ACC_HI) / 2;              // = 22.73, centred in the band

LCD_X = PCB_X + (PI_PCB_W - LCD_W) / 2;    // the LCD sits centred on the Pi
LCD_Y = PCB_Y + (PI_PCB_D - LCD_D) / 2;
LCD_Z = SPLIT_B;                           // LCD slab underside
LCD_CX = PCB_X + PI_PCB_W / 2;
LCD_CY = PCB_Y + PI_PCB_D / 2;

//  THE BEZEL's pocket and window.  The pocket is the MID's cavity plus
//  whatever the LCD's measured outline needs: LCD_FIT per side in X, and the
//  cavity already gives more than that in Y, so only X grows.  That takes the
//  BEZEL's wall from 4.50 to 4.26 - still four times the screw clearance
//  around it - and buys the LCD 0.40 a side instead of the 0.16 the bare
//  cavity would leave on the measured 85.80.
POCK_W = max(IW, LCD_W + 2 * LCD_FIT);     // = 86.60, the cavity is 86.12
POCK_D = max(ID, LCD_D + 2 * LCD_FIT);     // = 57.20, the cavity is deeper
POCK_X = (OW - POCK_W) / 2;                // = 4.26
POCK_Y = (OD - POCK_D) / 2;                // = 4.50, unchanged

//  The window is the measured panel less LCD_LIP on every side, centred on
//  the LCD.  It used to be the visible area plus WIN_CLR, which left a 5.50
//  lip in X and 2.90 in Y over the glass - too much bezel on the screen. At
//  LCD_LIP = 2.00 the opening still clears the visible area by 3.90 in X and
//  1.30 in Y, so the picture cannot be clipped, and the bezel still overlaps
//  the LCD's edge by 2.00, which is what holds it down on the shelf.
WIN_W = LCD_W - 2 * LCD_LIP;               // = 81.80
WIN_D = LCD_D - 2 * LCD_LIP;               // = 51.60
WIN_X = LCD_X + LCD_LIP;                   // = 6.66
WIN_Y = LCD_Y + LCD_LIP;                   // = 7.30

//  THE LCD's UNDERSIDE, and the two things the MID has to know about it.
//  Measured off the mesh: the slab hangs its 26-pin socket 12.80 below itself
//  (LCD_DROP), and in case coordinates that socket is x 11.81..46.10 and
//  y 54.50..59.58.  (The mesh figures were 12.31..46.60 / 55.00..60.08 at the
//  5.00 wall; the 0.50 wall reduction carries the whole board stack -0.50 in
//  X and Y, so these follow it.)  Everything else under the slab is either
//  flat panel or a component lying within 2.75 of it.
LCD_SOCK_X0 = 11.81;
LCD_SOCK_X1 = 46.10;
LCD_SOCK_Y0 = 54.50;
LCD_SOCK_Y1 = 59.58;

//  THE NOTCH.  The MID's shelf ring is the LCD's seat - its top face IS
//  SPLIT_B, and it is the only reason the LCD has anything to rest on at all.
//  But its inner edge is at y 59.20 and the socket reaches y 60.08, so 0.88 mm
//  of socket is buried inside the ledge: the LCD jams 12.8 mm above its seat,
//  standing on its own socket, which is exactly the load path that puts a
//  finger's worth of force into the GPIO header pins.
//
//  So the ledge gets a notch.  It is sized over the FULL 40-PIN HEADER, not
//  just the 26-pin LCD socket: the request is that no supporting part enters
//  the GPIO envelope, and the header body is the widest thing there.  The
//  notch is the header body's X span plus 1.00 all round, with the same
//  margin carried to the socket's Y footprint.  It runs the ledge's full
//  width, stopping on the wall's inner face so the wall itself is untouched,
//  and overshoots 1.00 past the ledge above and below: a cut landing exactly
//  on an existing face is the one thing CGAL will not forgive.
NOTCH_X0 = PI_GPIO_CX - HDR_BODY_W / 2 - 1.00;  // = 10.85, whole 40-pin body
NOTCH_X1 = PI_GPIO_CX + HDR_BODY_W / 2 + 1.00;  // = 64.35, plus 1.00 margin
NOTCH_Y0 = WALL + ID - SHELF_W;             // = 58.70, the ledge's inner edge
NOTCH_Y1 = WALL + ID;                       // = 61.70, the wall's inner face

//  What survives of the +Y ledge is x 4.50..10.85 and 64.35..90.62.  The
//  header body spans x 11.85..63.35, so no ledge material is left over any of
//  the 40 pins, and the socket's whole footprint sits inside the same cut.

//  THE SUPPORT FLANGES.  The ring bears on the LCD's edges; the flanges are
//  what stops a thumb in the middle of the screen from being the thing that
//  takes the load.  Each reaches inward from the ring's top face, SHELF_T
//  thick with its top coplanar with the ring, so the LCD sees one continuous
//  seat rather than a ring with four lumps on it.
//
//  FOUR, one per wall: the load case is a fingertip anywhere on the glass, and
//  one flange leaves three quadrants with nothing behind them.  They are
//  cantilevered off the wall with no web beneath - sound at this size, since
//  5 N on one of them at a 20 N press bends it under 0.05 mm.  They are also,
//  deliberately, not a closed frame: the LCD's edge has LCD_FIT = 0.40 mm of
//  fit in X and 0.80 in Y, and a frame that surrounded it would eat that.
//
//  WHERE THEY MAY SIT is fixed by the LCD's own underside - the socket box
//  above, and the three shallow components.  All four rectangles are clear of
//  both by construction; verify.py re-checks them against the mesh rather than
//  against these numbers.
LCD_PAD_IN =  8.00;                         // how far each reaches in
LCD_PAD_W  = 12.00;                         // and how far along the wall
LCD_PADS = [
    [WALL,                   30.00, WALL + LCD_PAD_IN,  42.00],  // -X wall
    [OW - WALL - LCD_PAD_IN, 30.00, OW - WALL,          42.00],  // +X wall
    [60.00,                  WALL,  72.00, WALL + LCD_PAD_IN],   // -Y wall
    [70.00, WALL + ID - LCD_PAD_IN, 82.00, WALL + ID],           // +Y wall
];
//  The +Y flange moved from x 55..67 to 70..82.  The old position sat directly
//  over the last seven columns of the 40-pin header and was the one support
//  that entered its plan envelope; 70..82 is past the body's 63.35 edge and
//  still on bare LCD PCB, so it carries the same load without standing over a
//  pin.

//  THE +Y WALL'S RELIEF, for the header's body.
//  This is the one place the CE09547 does not fit as drawn, and it is worth
//  being exact about why, because the fix is a hole in an otherwise plain
//  wall.  Its insulator is 8.50 in Y (see the header block - that number is
//  the REFERENCE part's, not CE09547's) and it centres on the Pi's GPIO, whose
//  centre is 3.50 in from the Pi's PCB edge.  4.25 - 3.50 = 0.75, so the body
//  overhangs the PCB's edge the way every stacking header does; and the case
//  leaves only CLR = 0.60 between that edge and the wall.  So the body's +Y
//  face lands at 62.35 and the wall's inner face is at 62.20: 0.15 mm of
//  header inside the wall, and the MID could not be slid down over it.
//
//  A relief rather than a wider case, because 8.50 is the ONE dimension in
//  this part that is neither published nor readable off the CAD in ../base/ -
//  it is the reference stacking header's, and the reference is a different
//  part.  Removing HDR_RELIEF_D = 1.00 of wall from the inside buys a body up
//  to 10.20 wide against the 8.50 assumed, so the case works either way, and
//  costs 1.00 of a 5.00 wall over a patch nothing else is in.  The OUTER face
//  is untouched: outside, this wall still reads as a plain +Y wall.
//
//  It runs from below the MID's own bottom edge - the MID slides DOWN over
//  the stack, so a relief that started at the header's underside would catch
//  on the joint - up past HDR_BODY_TOP, and it stops 1.00 clear of the M3
//  clearance bore's own edge at x 9.00 + SCREW_CLR / 2.  That edge moved out
//  from 10.10 to 10.70 when the screws went to M3, so this follows it to
//  11.70 on its own; at 10.70 it would leave a 0.10 sliver of wall between the
//  two holes over the relief's whole height - a piece that size is a breakage
//  waiting to happen, and there is no reason to go that close.
HDR_RELIEF_D  =  1.30;                      // into the wall, from the inside -
                                            // the 4.50 wall leaves body
                                            // intrusion 0.65, so this keeps
                                            // 0.65 clear, not a hairline
HDR_RELIEF_X0 =  9.00 + SCREW_CLR / 2 + 1.00;   // = 11.70, clear of the bore
HDR_RELIEF_X1 = 66.00;                      // past the body's 63.35 edge
HDR_RELIEF_Z0 = JOINT_A - 1.00;             // below the MID's bottom edge
HDR_RELIEF_Z1 = HDR_TIP_Z + 1.50;           // = 33.93, past the WHOLE 40-pin
                                            // column, not just the body.

//  THE WITTYPI'S BUTTON, AND WHY THE -X WALL NOW HAS A SLOT.
//
//  With the 4.50 wall the WittyPi's board edge lands at case x 5.10 - the same
//  plane as the Pi's PCB edge - so the board itself is 0.60 clear of the wall
//  and needs no relief.  What still enters the wall is the BUTTON: a boss on
//  the board's -X edge, measured off the mesh at local x 65.00..66.10,
//  y 13.93..16.47, z 0.00..1.00.  In case coordinates that is x 4.00..5.10,
//  y 44.83..47.37, z 23.80..24.80, so 0.50 of it is inside the wall and the
//  MID would stop on it 20 mm above its seat.
//
//  The opening is a slot, not a hole: it runs from below the MID's bottom edge
//  (JOINT_A) to 1.00 above the button, so the MID can slide down over the
//  button, and through the full wall plus 1.50 into the cavity so the button
//  stays reachable from outside.  0.50 of margin on every side of the button
//  is the assembly tolerance, and the z overshoot is what makes it a slot
//  rather than a cut landing on the joint face.
WITTY_BTN_X0 = -1.00;                       // through the outer face
WITTY_BTN_X1 = WALL + 1.50;                 // and 1.50 into the cavity
WITTY_BTN_Y0 = 44.30;                       // button y 44.83..47.37, +0.53/-0.50
WITTY_BTN_Y1 = 47.90;
WITTY_BTN_Z0 = JOINT_A - 1.00;              // open to the MID's bottom edge
WITTY_BTN_Z1 = 25.80;                       // button z 23.80..24.80, +1.00

//  The vertical stack screws.  On the wall centreline so the clearance bores
//  stay buried in the wall at 0.80 a side, and 9 mm in from each outer face,
//  which keeps all six clear of every port opening and of the service openings
//  in the +Y wall.
//
//  The +X wall is the one to watch, because it is where the Pi's Ethernet and
//  USB bank goes: those two cuts take it from y 7.75 to y 60.18 below z 25.07,
//  so a screw further in from the corner than 9.00 would land in one of them.
//  These two sit at y 2.50 and 64.20, in the wall either side of the bank.
//
//  SIX COLUMNS, TWELVE SCREWS.  There used to be a second set of four 21 mm
//  further down, holding the MOUNT to the BASE from underneath; with the MOUNT
//  gone there is one set of six, and each column now carries TWO screws - a
//  BEZEL one down from the top and a BASE one up from underneath - both
//  threading into the same column of MID wall.  See the screw block.  They are
//  the case's whole retention scheme, and the belt plate's load goes through
//  the BASE's own floor rather than through any of them.
SCREWS = [
    [WALL / 2,     9.00],
    [WALL / 2,     OD - 9.00],
    [9.00,         OD - WALL / 2],
    [OW - 9.00,    OD - WALL / 2],
    [9.00,         WALL / 2],
    [OW - 9.00,    WALL / 2],
];

echo(str("outer    : ", OW, " x ", OD, " x ", OH, " mm"));
echo(str("interior : ", IW, " x ", ID, " x ", JOINT_A - FLOOR, " mm below the ",
         "Pi's PCB, plus ", MID_H, " of MID  (whole case ", OH, " tall)"));
echo(str("splits   : plate -", PLATE_GAP + PLATE_T, "..",
         PLATE_STYLE == "strap" ? PLATE_SKIRT_TOP : -PLATE_GAP,
         "  base 0..", JOINT_A, "  mid ..", SPLIT_B, "  bezel ..", OH,
         "   (mid is ", MID_H, " tall)"));
echo(str("plate    : style ", PLATE_STYLE,
         PLATE_STYLE == "strap"
           ? str("  tray ", PLATE_TRAY_X1 - PLATE_TRAY_X0, " x ",
                 PLATE_TRAY_Y1 - PLATE_TRAY_Y0, "  skirt ",
                 PLATE_SKIRT_T, " x ", PLATE_SKIRT_TOP, " above the case face",
                 "  arms to r ", PLATE_ARM_TIP_R + PLATE_ARM_TIP_D / 2,
                 " on ", PLATE_ARM_ANG, " deg, waist ",
                 PLATE_ARM_WAIST_D, " / tip ", PLATE_ARM_TIP_D)
           : str("  ", PLATE_W, " x ", PLATE_D, " x ", PLATE_T),
         "  gap to the BASE ", PLATE_GAP, "  bolt rectangle ",
         2 * PLATE_BOLT_DX, " x ", 2 * PLATE_BOLT_DY, "  screw ", PLATE_SCREW_L,
         " long into a blind o", PLATE_PILOT_D, " x ", PLATE_PILOT_DEEP,
         " pilot, tip at ", PLATE_SCREW_L + PLATE_GAP - PLATE_CBORE_H));
echo(str("case screws: ", len(SCREWS), " columns x 2 = ", 2 * len(SCREWS),
         " x M3 x ", SCREW_L, " button head"));
echo(str("  BEZEL->MID  head flush at z ", OH, "  shank through ", OH - SPLIT_B,
         " of BEZEL  pilot ", SPLIT_B - SCREW_DEEP, "..", SPLIT_B,
         "  tip ", OH - SCREW_CBORE_H - SCREW_L, "  bite ",
         SPLIT_B - (OH - SCREW_CBORE_H - SCREW_L)));
echo(str("  BASE->MID   head flush at z 0  shank through ", JOINT_A,
         " of BASE  ", "pilot ", JOINT_A + MATE_GAP, "..",
         JOINT_A + MATE_GAP + SCREW_DEEP,
         "  tip ", SCREW_CBORE_H + SCREW_L,
         "  bite ", SCREW_CBORE_H + SCREW_L - JOINT_A - MATE_GAP));
echo(str("  window: any M3 from ",
         max(OH - SCREW_CBORE_H - SPLIT_B,
             JOINT_A + MATE_GAP - SCREW_CBORE_H), " to ",
         min(OH - SCREW_CBORE_H - SPLIT_B + SCREW_DEEP,
             JOINT_A + MATE_GAP + SCREW_DEEP - SCREW_CBORE_H),
         " fits both  (o", SCREW_PILOT, " pilot, o", SCREW_CLR,
         " clearance, o", SCREW_CBORE_D, " x ", SCREW_CBORE_H,
         " flush counterbores at both ends)"));
echo(str("service: hex vent field ", HEX_NX, " x ", HEX_NZ,
         " o", 2 * HEX_R, " holes in the +Y wall, columns at ", HEX_DX,
         " and rows at ", HEX_DZ, "   lead rectangle x ",
         LEAD_RX0, "..", LEAD_RX1, " z ", LEAD_RZ0, "..", LEAD_RZ1,
         "   vents ", VENT_N, " x ", VENT_W, "x", VENT_H,
         " in the BASE's -Y wall at z ", VENT_Z));
//  Everything below is in STACK coordinates, which is now the only frame in
//  the file - z 0 is the bench, and the case's underside sits on it.
echo(str("STACK z (this IS the height off the bench):"));
echo(str("PCB under z=", PCB_Z, " .. top ", PCB_Z + PI_PCB_T,
         "  header body ", PCB_Z + PI_PCB_T + HDR_STANDOFF, "..", HDR_BODY_TOP,
         "  pins to ", PCB_Z + PI_PCB_T + EXT_HEADER,
         "  WittyPi ", WITTY_Z, "..", WITTY_Z + WP_H,
         "  LCD slab ", LCD_Z, "..", LCD_Z + LCD_T,
         "  LCD top ", LCD_TOP_Z));
echo(str("  header: ", EXT_HEADER, " total = ", HDR_STANDOFF, " standoff + ",
         HDR_BODY, " body + ", HDR_PIN_L, " pin, on a ", HDR_BODY_W, " x ",
         HDR_BODY_D, " insulator over ", HDR_PITCH, " centres  (", HDR_BODY_W,
         " x ", HDR_BODY_D, " at x ", PI_GPIO_CX, " y ", PI_GPIO_CY, ")"));
echo(str("  pins: tips at ", PCB_Z + PI_PCB_T + EXT_HEADER, "  the WittyPi's ",
         "socket swallows ", WP_SOCK_D, " of that, leaving ", HDR_PIN_UP,
         " standing proud of its top face into the LCD's ", LCD_DROP,
         " socket - ", PCB_Z + STACK_MEASURED - LCD_T, " - ",
         PCB_Z + STACK_MEASURED, " is the measured assembled stack"));
echo(str("LCD socket hangs down to stack z=", LCD_Z - LCD_DROP,
         "  = the WittyPi's top face ", WITTY_Z + WP_H));
echo(str("rear wall: hex field x ", HEX_X0 - HEX_HW, "..",
         HEX_X0 + (HEX_NX - 1) * HEX_DX + HEX_HW, " stack z ",
         HEX_Z0 - HEX_HH, "..",
         HEX_Z0 + (HEX_NZ - 1) * HEX_DZ + HEX_DZ / 2 + HEX_HH,
         "   battery lead rectangle x ", LEAD_RX0, "..", LEAD_RX1,
         " stack z ", LEAD_RZ0, "..", LEAD_RZ1));
echo(str("model->case offset : ", OFF));

echo(str("front panel: ", LED_N, " x o", LED_D, " LED at x ",
         LED_X0, "..", LED_X0 + (LED_N - 1) * LED_PITCH,
         "   ", SW_N, " x ", SW_BODY, "x", SW_BODY, "x", SW_H, " switch at x ",
         SW_X0, "..", SW_X0 + (SW_N - 1) * SW_PITCH));
echo(str("  LED bore is plain, ", WALL, " deep.  The flange - o", LED_FLANGE_D,
         ", ", LED_FLANGE_T, " thick - stops on the inner face, so ",
         LED_LEN - LED_FLANGE_T, " of barrel runs through the wall and the ",
         "tip finishes ", LED_LEN - LED_FLANGE_T - WALL, " PROUD of the outer face"));
echo(str("    o", LED_BODY_D, " of barrel in that o", LED_D, " bore is ",
         (LED_D - LED_BODY_D) / 2, " of clearance all round, and it leaves ",
         LED_FLANGE_T, " of flange in the cavity - plus the ", LED_LEAD_L,
         " of drawn lead"));
echo(str("  row at stack z ", PANEL_Z, "   pocket ", SW_POCKET, " x ",
         SW_POCKET, " x ", SW_POCKET_D, " deep, ", SW_LIP,
         " lip in front, ribs ", SW_RIB));
echo(str("  seat: pocket cut ", SW_POCKET_CUT, " from the lip (y ", SW_LIP,
         "..", SW_LIP + SW_POCKET_CUT, "), ", SW_FLOOR > 0
             ? str("floor behind the body ", SW_FLOOR)
             : str("through the inner face by ",
                   SW_LIP + SW_POCKET_CUT - WALL)));
echo(str("  band is stack z 15.56..", SPLIT_B - SHELF_T,
         " - i.e. measured from the case's underside, which is the bench"));
if (SW_H > WALL)
    echo(str("  NOTE: SW_H ", SW_H, " > the ", WALL,
             " wall, so the pocket cut leaves no floor and the body sits ",
             SW_LIP + SW_H - WALL, " proud into the cavity"));
echo(str("  switch, as drawn: ", SW_BODY, " x ", SW_BODY, " x ", SW_H,
         " body in a ", SW_POCKET, " pocket, so ", (SW_POCKET - SW_BODY) / 2,
         " a side - and the ribs stand ", SW_RIB, " proud of the pocket, which ",
         "grips the body by ", SW_RIB - (SW_POCKET - SW_BODY) / 2));
echo(str("    the ", SW_TOP, " raised centre fills the last ", SW_TOP_H,
         " of the pocket; the o", SW_ACT_D, " actuator goes through the o",
         SW_BTN_D, " button hole with ", (SW_BTN_D - SW_ACT_D) / 2,
         " to spare and finishes ", SW_ACT_UP - SW_LIP,
         " proud of the case's outer face, because the lip is only ", SW_LIP));
echo(str("    four legs ", SW_LEG_W, " x ", SW_LEG_D, " on a ",
         2 * SW_LEG_X1 - SW_LEG_W, " x ", 2 * SW_LEG_Y1 - SW_LEG_D,
         " pattern - which is the 6.5 x 4.5 the block above quotes, measured - ",
         "starting ", SW_LIP + SW_H - WALL, " past the inner face and running ",
         SW_LEG_L, " into the cavity"));
echo(str("  opening: ", ACC_W, " x ", ACC_H, " (R", ACC_R, ") cut to give at ",
         "least ", ACC_MIN_W, " x ", ACC_MIN_H, " finished - under the buttons",
         " at x ", ACC_CX - ACC_W / 2, "..", ACC_CX + ACC_W / 2,
         ", stack z ", ACC_CZ - ACC_H / 2, "..", ACC_CZ + ACC_H / 2));
echo(str("    clears the HDMI opening below by ",
         ACC_CZ - ACC_H / 2 - ACC_LO, ", the pocket floors above by ",
         ACC_HI - (ACC_CZ + ACC_H / 2), ", the LED row by ",
         ACC_CX - ACC_W / 2 - (LED_X0 + (LED_N - 1) * LED_PITCH),
         ", and the two M3 columns by ", ACC_CX - ACC_W / 2 - 9.00, " / ",
         OW - 9.00 - (ACC_CX + ACC_W / 2)));

// =====================================================================
//  helpers   (all coordinates below are ABSOLUTE case coordinates)
// =====================================================================
module rbox(w, d, h, r) {
    hull() for (x = [r, w - r], y = [r, d - r])
        translate([x, y, 0]) cylinder(r = r, h = h, $fn = $fn);
}

//  The 2-D twin, for the tray and its arms.  Both are extruded once, so the
//  plate is one prism and not a stack of booleans.
module rrect(w, d, r) {
    hull() for (x = [r, w - r], y = [r, d - r])
        translate([x, y]) circle(r = r);
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

    //  The web between the Ethernet and USB openings is only 1.57 wide - a
    //  free-standing post left between the two clearance cuts.  At the user's
    //  request it is gone, so the pair reads as one stepped opening.  The cut
    //  overlaps 1.00 into each neighbouring opening and runs 0.50 above the
    //  USB opening's top edge, so no new face lands coplanar with either cut.
    web_y0 = ETH[3] + OFF[1] + PORT_G - 1.00;
    web_y1 = USB[2] + OFF[1] - PORT_G + 1.00;
    web_z1 = USB[5] + OFF[2] + PORT_G + 0.50;
    translate([WALL + IW - 1, web_y0, zb])
        cube([WALL + 9.00, web_y1 - web_y0, web_z1 - zb]);
}

// The hex vent field and the battery lead, through the +Y wall.
//
//  These replaced the charging-cable slot, the round lead grommet and the two
//  cable-tie holes that flanked it, all at the user's request.  Every hole is
//  cut from 1.00 inside the wall's inner face outward through the outer face,
//  so none can reach the opposite (-Y) wall; the probes in verify.py assert
//  that geometrically as well as arithmetically.
module service_holes() {
    for (i = [0 : HEX_NX - 1], j = [0 : HEX_NZ - 1])
        translate([HEX_X0 + i * HEX_DX,
                   WALL + ID - 1,
                   HEX_Z0 + j * HEX_DZ + (i % 2) * HEX_DZ / 2])
            rotate([-90, 0, 0])
                cylinder(r = HEX_R, h = WALL + 2, $fn = 6);

    translate([LEAD_RX0, WALL + ID - 1, LEAD_RZ0])
        cube([LEAD_RX1 - LEAD_RX0, WALL + 2, LEAD_RZ1 - LEAD_RZ0]);
}

// The front panel, through the -Y wall.  The mirror of the +Y cut above:
// the -Y wall runs y 0 .. WALL, so a cylinder started at y = -1 and WALL + 2
// long spans -1 .. 6.00 and cuts clean through it.
module panel() {
    // WHY EVERY LOOP HERE IS GUARDED BY AN `if (N > 0)`
    // Writing `for (i = [0 : N - 1])` looks like it does nothing at N = 0.
    // It does not: OpenSCAD normalises a range whose end is below its start
    // into a REVERSED one, so [0 : -1] becomes [-1 : 1 : 0] and the body runs
    // twice, at i = -1 and i = 0.  Setting LED_N = 0 to delete the LEDs would
    // instead add two phantom ones hanging off the left end of the row.  The
    // guard is what makes the documented "set it to 0" idiom true.

    // LEDs.  A plain bore, straight through.  It is the flange against the
    // inner face that stops the LED and sets the lens just inside the outer
    // face; the reasoning for there being no counterbore is in the TUNE block.
    if (LED_N > 0) for (i = [0 : LED_N - 1])
        translate([LED_X0 + i * LED_PITCH, -1, PANEL_Z]) rotate([-90, 0, 0])
            cylinder(d = LED_D, h = WALL + 2, $fn = $fn);

    // Switches.  The button passes through the lip that is left in front
    // of the body; the body itself sits in the pocket behind it.  For the
    // common 6 x 6 x 5 the pocket reaches the wall's inner face exactly, so
    // there is no floor behind the body - which is the point: the four pins
    // splay to a 6.5 x 4.5 footprint, wider than this 6.20 pocket, so they
    // must clear the wall altogether and start in the cavity instead.
    if (SW_N > 0) for (i = [0 : SW_N - 1])
        translate([SW_X0 + i * SW_PITCH, 0, PANEL_Z]) {
            // The button hole reaches into the pocket rather than stopping on
            // its front face.  Two pieces of the same cut that meet exactly
            // face-to-face are as bad as a cut landing on the solid's face:
            // the pocket comes out as its own closed shell, so the pocket ends
            // up sealed and the button hole blind behind it.  Overlapping them
            // makes the union of the cut unambiguous.  SW_POCKET_CUT / 2 keeps
            // the overshoot strictly inside the pocket at any SW_H.
            translate([0, -1, 0]) rotate([-90, 0, 0])
                cylinder(d = SW_BTN_D, h = SW_LIP + 1 + SW_BTN_OVER, $fn = $fn);

            translate([-SW_POCKET / 2, SW_LIP, -SW_POCKET / 2])
                difference() {
                    cube([SW_POCKET, SW_POCKET_CUT, SW_POCKET]);
                    // Take the rib volume OUT OF THE CUT, which leaves
                    // material standing there.  Inset in y and z so each
                    // rib is a ridge with clearance around it, not a
                    // full-length rail the switch has to be forced down.
                    for (sx = [0, SW_POCKET - SW_RIB])
                        translate([sx, 0.60, 0.80])
                            cube([SW_RIB, SW_POCKET_D - 1.20,
                                  SW_POCKET - 1.60]);
                }

            // Clearance behind each splayed terminal.  The strips sit at
            // +/-SW_LEG_X0..X1 in x and +/-SW_LEG_Y0..Y1 in z from the
            // switch centre; only the z reach passes the 6.20 pocket, so
            // these are the four notches that matter.  They start at the
            // inner face, run SW_TERM_NOTCH back into the wall, and lap
            // into the pocket (x) and the cavity (+y) so each is one open
            // cut rather than a sealed void.
            for (sx = [-1, 1])
                for (sz = [-1, 1])
                    translate([
                        sx > 0 ? SW_LEG_X0 - SW_TERM_MARGIN
                               : -SW_LEG_X1 - SW_TERM_MARGIN,
                        WALL - SW_TERM_NOTCH,
                        sz > 0 ? SW_LEG_Y0 - SW_TERM_MARGIN
                               : -SW_LEG_Y1 - SW_TERM_MARGIN])
                        cube([SW_LEG_X1 - SW_LEG_X0 + 2 * SW_TERM_MARGIN,
                              SW_TERM_NOTCH + 1.00,
                              SW_LEG_Y1 - SW_LEG_Y0 + 2 * SW_TERM_MARGIN]);
        }
}

//  The accessory opening, under the switch row in the -Y wall.  See the TUNE
//  block for why it is where it is and what the two sizes mean.
//
//  The rbox is built as w x d x h and then turned a quarter turn about X, so
//  its w stays the opening's width in X, its d becomes the opening's height
//  in Z, and its h runs back down the Y axis through the wall.  That is what
//  puts the fillet in the XZ plane - the plane of the wall's face - instead
//  of in the plane of the cut.  h is WALL + 2 and it starts at WALL + 1, so
//  the cut spans y -1 .. 6 and breaks out of both faces by 1.00.
module accessory_port() {
    translate([ACC_CX - ACC_W / 2, WALL + 1, ACC_CZ - ACC_H / 2])
        rotate([90, 0, 0]) rbox(ACC_W, ACC_H, WALL + 2, ACC_R);
}

//  The BEZEL's share of the joint screws: a plain o3.40 clearance bore, cut
//  right through because the BEZEL is only 8.60 thick.  The other end of the
//  same screws is threaded into the MID - see screw_pilots - and the same
//  columns carry the six that come up from underneath.
module screw_holes() {
    for (s = SCREWS) translate([s[0], s[1], -1])
        cylinder(d = SCREW_CLR, h = OH + 2, $fn = $fn);
}

//  The MID's share: TWO blind pilots per column, from opposite ends.  The MID
//  is the nut for both joints - the BEZEL's six come down into the top of each
//  column and the BASE's six come up into the bottom of it - so each column is
//  drilled 15.00 from the top and 15.00 from the bottom, leaving 4.90 of
//  solid wall between them.
//
//  Both cuts overshoot the face they open onto by 1.00 so the mouth is a clean
//  break-out rather than a cut landing exactly on the part's own face, which
//  is the one thing CGAL will not forgive.
module screw_pilots() {
    for (s = SCREWS) {
        translate([s[0], s[1], SPLIT_B - SCREW_DEEP])
            cylinder(d = SCREW_PILOT, h = SCREW_DEEP + 1, $fn = $fn);
        translate([s[0], s[1], JOINT_A - 1.00])
            cylinder(d = SCREW_PILOT, h = SCREW_DEEP + MATE_GAP + 1, $fn = $fn);
    }
}

//  The flush head seats at the two outer faces.  At the top the recess is cut
//  into the BEZEL's solid lip above the LCD; at the bottom it is buried in the
//  BASE's 2.60 floor.  Both get a 0.20 x 45 deg lead-in so the print has a
//  chamfer rather than a sharp counterbore edge, and the cone is written to
//  meet the outer face exactly: d1 is the counterbore at the bottom of the
//  lead-in, d2 its finished diameter at the face.
module screw_counterbores(top = true) {
    for (s = SCREWS) {
        if (top) {
            translate([s[0], s[1], OH - SCREW_CBORE_H])
                cylinder(d = SCREW_CBORE_D, h = SCREW_CBORE_H + 1, $fn = $fn);
            translate([s[0], s[1], OH - SCREW_CSK_H])
                cylinder(d1 = SCREW_CBORE_D, d2 = SCREW_CSK_D,
                         h = SCREW_CSK_H, $fn = $fn);
        } else {
            translate([s[0], s[1], -1])
                cylinder(d = SCREW_CBORE_D, h = SCREW_CBORE_H + 1, $fn = $fn);
            translate([s[0], s[1], 0])
                cylinder(d1 = SCREW_CSK_D, d2 = SCREW_CBORE_D,
                         h = SCREW_CSK_H, $fn = $fn);
        }
    }
}

// A shallow groove round the outside at height z.  Both parts either side of
// a joint cut the whole groove; each only has material on its own side, so
// together they leave one clean seam line.
//
// The inner cut is the part's own outline offset inwards by SEAM_D, corners
// included: same corner centres (3.0, 3.0), radius reduced to 3.0 - SEAM_D.
// Reusing the part's own radius instead would leave the groove only 0.4 deep
// at the four corners.
//
//  ...AND IT STOPS SHORT OF EVERY SCREW.  An M3 clearance bore is o3.40, so
//  its edge is only 0.80 from the outer face; a groove cut straight across it
//  would leave a 0.20 ligament, which the screw's own expansion will split.
//  So the cutter has a patch taken out of it at each of the six columns,
//  restoring the full wall and keeping the ligament at 0.80.  The patch runs
//  SEAM_PATCH along the wall and reaches SEAM_CLEAR in from the face, which is
//  1.10 clear of the bore it is protecting.
//
//  All six columns are on straight runs, well inside the 3.00 corners, so the
//  patches are plain cubes and the branch below is just which wall each one is
//  in - s[0] < WALL is -X, s[1] < WALL is -Y, everything else is +Y.
module seam(z) {
    translate([0, 0, z - SEAM_H / 2]) difference() {
        difference() {
            rbox(OW + 4, OD + 4, SEAM_H, 3.0);
            translate([SEAM_D, SEAM_D, -1])
                rbox(OW - 2 * SEAM_D, OD - 2 * SEAM_D, SEAM_H + 2,
                     3.0 - SEAM_D);
        }
        for (s = SCREWS) {
            if (s[0] < WALL)
                translate([-1, s[1] - SEAM_PATCH / 2, -1])
                    cube([SEAM_CLEAR + 1, SEAM_PATCH, SEAM_H + 2]);
            else if (s[1] < WALL)
                translate([s[0] - SEAM_PATCH / 2, -1, -1])
                    cube([SEAM_PATCH, SEAM_CLEAR + 1, SEAM_H + 2]);
            else
                translate([s[0] - SEAM_PATCH / 2, OD - SEAM_CLEAR, -1])
                    cube([SEAM_PATCH, SEAM_CLEAR + 1, SEAM_H + 2]);
        }
    }
}

// =====================================================================
//  the belt plate  -  a SEPARATE part, bolted under the BASE
// =====================================================================
//  The only part of this case drawn below zero.  The BASE's underside is the
//  plate's mounting face, and the plate hangs 4.00 of solid slab off it with
//  the hooks standing up off that.
//
//  Print it CASE FACE DOWN - the flat face that touches the BASE on the bed -
//  so the body is 4.00 of solid slab with the hooks standing up off it.  The
//  only overhang then is the lip's underside, a 6.00 cantilever 2.00 thick;
//  short enough to print as it is, and the place to look first if your printer
//  droops.  Chamfering the tip inward at 45 deg is the fix if it does.
module hook() {
    z_face = -(PLATE_GAP + PLATE_T);            // the plate's outer face
    z_far  = z_face - PLATE_HOOK_PROJ;          // the web's far end
    //  The web.  This is what carries the case: the belt's lower edge bears on
    //  its +Y face, over the belt's full thickness.
    translate([0, PLATE_HOOK_Y - PLATE_HOOK_T, z_far])
        cube([PLATE_HOOK_W, PLATE_HOOK_T, PLATE_HOOK_PROJ]);
    //  The lip, turning +Y behind the belt.  This is what keeps the case ON -
    //  without it the case lifts off the belt, hook and all.
    translate([0, PLATE_HOOK_Y, z_far])
        cube([PLATE_HOOK_W, PLATE_HOOK_LIP, PLATE_HOOK_T]);
}

//  One strap arm, in the arm's own frame: +X runs out along the corner
//  diagonal, the arm is centred on y = 0.  Root and tip are separate hulls
//  sharing the neck circle, which is what makes the waist CONCAVE.  A single
//  hull of all three would fill it in: a hull is the convex boundary, so the
//  strap could then slide straight off the tip.
module strap_arm() {
    hull() {
        translate([PLATE_ARM_ROOT_R, 0]) circle(d = PLATE_ARM_ROOT_D);
        translate([PLATE_ARM_NECK_R, 0]) circle(d = PLATE_ARM_NECK_D);
    }
    hull() {
        translate([PLATE_ARM_NECK_R, 0]) circle(d = PLATE_ARM_NECK_D);
        translate([PLATE_ARM_TIP_R, 0])  circle(d = PLATE_ARM_TIP_D);
    }
}

//  The concave waist, cut from the outline after the arm is built.  One circle
//  each side of the axis at the neck's radius; together they leave a 12.00
//  seat.  A hull cannot produce this - it would bridge straight across.
module strap_waist() {
    for (s = [-1, 1])
        translate([PLATE_ARM_NECK_R, s * PLATE_ARM_WAIST_OFF])
            circle(r = PLATE_ARM_GROOVE_R);
}

//  The tray floor and its four arms as ONE 2-D outline, extruded by plate().
//  The arms' root circles sit inside the tray, so the union is a single
//  connected region and not four tabs that merely touch.
module plate_strap_2d() {
    difference() {
        union() {
            translate([PLATE_TRAY_X0, PLATE_TRAY_Y0])
                rrect(PLATE_TRAY_X1 - PLATE_TRAY_X0,
                      PLATE_TRAY_Y1 - PLATE_TRAY_Y0, PLATE_TRAY_R);

            //  One per corner.  The four angles are the diagonal and its three
            //  reflections - written out rather than mirrored so the arm keeps
            //  the same handedness (it does not matter here, but a mirror is
            //  the one operation that would turn a printable part into its
            //  twin).
            for (a = [PLATE_ARM_ANG, 180 - PLATE_ARM_ANG,
                      180 + PLATE_ARM_ANG, -PLATE_ARM_ANG])
                translate([PLATE_CX, PLATE_CY]) rotate(a) strap_arm();
        }
        for (a = [PLATE_ARM_ANG, 180 - PLATE_ARM_ANG,
                  180 + PLATE_ARM_ANG, -PLATE_ARM_ANG])
            translate([PLATE_CX, PLATE_CY]) rotate(a) strap_waist();
    }
}

module plate() {
    difference() {
        union() {
            if (PLATE_STYLE == "strap") {
                //  The floor: 4.00 of solid slab under the whole case, arms
                //  included.  Its top face is PLATE_GAP below the case.
                translate([0, 0, -(PLATE_GAP + PLATE_T)])
                    linear_extrude(height = PLATE_T) plate_strap_2d();

                //  The skirt: the tray's wall, standing on that floor and
                //  wrapping the case's lower PLATE_SKIRT_TOP.  The inner cut
                //  is the case outline plus PLATE_SKIRT_CLR, so the two
                //  printed parts never touch.  It starts PLATE_SKIRT_OVERLAP
                //  inside the floor: a coplanar face-to-face union would
                //  export as two shells touching, not one solid.
                translate([0, 0, -(PLATE_GAP + PLATE_SKIRT_OVERLAP)])
                    linear_extrude(height = PLATE_SKIRT_TOP + PLATE_GAP
                                          + PLATE_SKIRT_OVERLAP)
                        difference() {
                            translate([PLATE_TRAY_X0, PLATE_TRAY_Y0])
                                rrect(PLATE_TRAY_X1 - PLATE_TRAY_X0,
                                      PLATE_TRAY_Y1 - PLATE_TRAY_Y0,
                                      PLATE_TRAY_R);
                            translate([-PLATE_SKIRT_CLR, -PLATE_SKIRT_CLR])
                                rrect(OW + 2 * PLATE_SKIRT_CLR,
                                      OD + 2 * PLATE_SKIRT_CLR,
                                      PLATE_SKIRT_R);
                        }
            } else {
                translate([PLATE_CX - PLATE_W / 2, PLATE_CY - PLATE_D / 2,
                           -(PLATE_GAP + PLATE_T)])
                    rbox(PLATE_W, PLATE_D, PLATE_T, PLATE_R);

                if (PLATE_STYLE == "hook")
                    for (i = [0 : PLATE_HOOK_N - 1])
                        translate([PLATE_CX + (i - (PLATE_HOOK_N - 1) / 2)
                                               * PLATE_MOD - PLATE_HOOK_W / 2,
                                   0, 0])
                            hook();
            }
        }

        //  The four bolts.  The counterbore is in the OUTER face, so the heads
        //  finish flush with the face that lies against the belt - same
        //  reasoning as the BASE's Pi screws.  It leaves 2.35 of the plate's
        //  4.00 under the head, and the screws bottom nowhere near it.
        for (b = PLATE_BOLTS) {
            translate([b[0], b[1], -(PLATE_GAP + PLATE_T) - 1])
                cylinder(d = PLATE_CLR, h = PLATE_T + 2, $fn = $fn);
            translate([b[0], b[1], -(PLATE_GAP + PLATE_T) - 0.01])
                cylinder(d = PLATE_CBORE_D, h = PLATE_CBORE_H + 0.01,
                         $fn = $fn);
        }

        //  The five BASE vents are behind the -Y skirt, so cut the skirt at
        //  the same columns.  The slot opens through the skirt's top edge
        //  (z 1.50..4.00 against a 3.00 skirt), which is deliberate: it is a
        //  crenellation, not a tunnel, and it prints without a bridge.
        if (PLATE_STYLE == "strap")
            for (i = [0 : VENT_N - 1])
                translate([OW / 2 + (i - (VENT_N - 1) / 2) * VENT_P
                               - VENT_W / 2,
                           -PLATE_SKIRT_CLR - PLATE_SKIRT_T - 1,
                           VENT_Z - VENT_H / 2])
                    cube([VENT_W, PLATE_SKIRT_T + PLATE_SKIRT_CLR + 2,
                          VENT_H]);

        //  The webbing field, on the PALS module both ways.  Slots rather
        //  than hooks, for webbing wide enough to thread: the belt goes in
        //  across, over and back, in the standard serpentine.
        if (PLATE_STYLE == "pals")
            for (i = [0 : PLATE_SLOT_N - 1], j = [0 : PLATE_ROW_N - 1])
                translate([PLATE_CX + (i - (PLATE_SLOT_N - 1) / 2) * PLATE_MOD
                                - PLATE_SLOT_W / 2,
                           PLATE_CY + (j - (PLATE_ROW_N - 1) / 2) * PLATE_ROW_P
                                - PLATE_SLOT_H / 2,
                           -(PLATE_GAP + PLATE_T) - 1])
                    cube([PLATE_SLOT_W, PLATE_SLOT_H, PLATE_T + 2]);
    }
}

// =====================================================================
//  PART 1  -  BASE     z 0 .. JOINT_A      the Pi's mounting and the
//                                          belt interface
// =====================================================================
//  The tray the whole case stands on.  It carries the Pi on four bosses, it is
//  CLAMPED to the MID by six M3 x 14 that come up from underneath, and - since
//  the MOUNT was deleted - the belt plate as well: four bolt bosses on the
//  inside of its floor, and the vents that used to be in the tub's wall.
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
            }

            // Pi screw bosses, printed up to the PCB underside.  Added after
            // the cavity is cut, or the cavity would take them with it.
            for (i = [0, 1], j = [0, 1])
                pi_hole(i, j) cylinder(d = BOSS_D, h = PCB_Z, $fn = $fn);

            //  The belt plate's four bolt bosses, standing on the INSIDE of
            //  the floor.  Inside, deliberately: the case's underside is the
            //  plate's mounting face and has to stay flat, so nothing may
            //  stand proud of it.  The screw comes up through the plate and
            //  into the boss from below, threading into plastic - there are no
            //  inserts in this build.  They stop dead at JOINT_A - see
            //  PLATE_BOSS_H - so the Pi drops in over them with the same 0.43
            //  the rim already clears its Ethernet shell by.
            for (b = PLATE_BOLTS)
                translate([b[0], b[1], FLOOR])
                    cylinder(d = PLATE_BOSS_D, h = PLATE_BOSS_H, $fn = $fn);
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

        //  The plate's four bolts, and the BASE's share of the case's own
        //  screws.  Not the same kind of hole at all:
        //
        //    the plate's is the ONLY hole in this build that is threaded in the
        //    BASE - one blind o2.75 pilot per bolt, from the case's underside
        //    right up through the floor and into the boss, stopping 0.20 short
        //    of the boss's top face.  Nothing to counterbore: the head is
        //    buried in the PLATE, which is 1.65 thick there for exactly that.
        //    Nothing to clear either - the pilot IS the thread, all 5.30 of it,
        //    because a clearance bore through the 2.60 floor would leave the
        //    screw only the boss's 2.70 to bite in and its tip lands at 3.15;
        //    that would be 0.55 of thread and it would strip.
        //
        //    the case's is a o3.40 clearance bore clean through the BASE's 5.50
        //    of wall, opening into the MID's lower pilot at the joint.  Nothing
        //    here takes thread - the MID is the nut - but there IS a flush
        //    counterbore, o5.80 x 1.65 with a o6.20 countersink over it, so
        //    the head lands with the case's underside.  Being wider than the
        //    4.50 wall it breaks out through the outer side face for 0.65.
        //    See the screw block.
        for (b = PLATE_BOLTS)
            translate([b[0], b[1], -1])
                cylinder(d = PLATE_PILOT_D, h = PLATE_PILOT_DEEP + 1,
                         $fn = $fn);

        for (s = SCREWS)
            translate([s[0], s[1], -1])
                cylinder(d = SCREW_CLR, h = JOINT_A + 1, $fn = $fn);
        screw_counterbores(false);       // flush heads under the BASE

        //  Vents, in the -Y wall: the one wall with no port opening and no
        //  screw in its lower half.  They came down here from the MOUNT's wall
        //  when it went, and they sit low on purpose - 1.50 of web below them
        //  keeps the BASE's floor edge solid, which matters now that the floor
        //  is also the plate's seat.
        if (VENT_N > 0)
            for (i = [0 : VENT_N - 1])
                translate([OW / 2 + (i - (VENT_N - 1) / 2) * VENT_P
                               - VENT_W / 2,
                           -1, VENT_Z - VENT_H / 2])
                    cube([VENT_W, WALL + 2, VENT_H]);
    }
}

// =====================================================================
//  PART 2  -  MID      z JOINT_A .. SPLIT_B      the shim
// =====================================================================
module mid() {
    difference() {
        union() {
            difference() {
                translate([0, 0, JOINT_A + MATE_GAP])
                    rbox(OW, OD, MID_H, 3.0);

                // full-height cavity, except a ledge at the very top that the
                // LCD slab rests on
                //  + MATE_GAP: the MID itself starts MATE_GAP higher, but the
                //  cavity must still end at SPLIT_B - SHELF_T, the unchanged
                //  LCD seat.  Without it the shortened cut leaves a 0.20 floor
                //  across the cavity for the LCD's socket to land on.
                translate([WALL, WALL, JOINT_A - 1])
                    rbox(IW, ID, MID_H - SHELF_T + 1 + MATE_GAP, 2.0);
                translate([WALL + SHELF_W, WALL + SHELF_W, SPLIT_B - SHELF_T])
                    rbox(IW - 2 * SHELF_W, ID - 2 * SHELF_W, SHELF_T + 1, 2.0);
            }

            //  The LCD's support flanges, added AFTER those two cuts, for the
            //  same reason base() adds its Pi bosses after them: the inner cut
            //  IS the shape of the cavity, so anything drawn before it gets
            //  taken away with the cavity.
            for (p = LCD_PADS)
                translate([p[0], p[1], SPLIT_B - SHELF_T])
                    rbox(p[2] - p[0], p[3] - p[1], SHELF_T, 1.0);
        }

        ports();                        // upper half of every port
        service_holes();
        panel();                        // LEDs + switches, -Y wall
        accessory_port();               // the 12 x 7 opening under them

        //  The LCD socket's notch through the +Y ledge.  Cut here rather than
        //  with the cavity, because it is an opening in the FINISHED ledge and
        //  has to miss the flanges standing on it.  It stops on the wall's
        //  inner face, so the wall itself is untouched.
        translate([NOTCH_X0, NOTCH_Y0, SPLIT_B - SHELF_T - 1.00])
            cube([NOTCH_X1 - NOTCH_X0, NOTCH_Y1 - NOTCH_Y0, SHELF_T + 2.00]);

        //  ...and the +Y wall's relief for the header's body.  This one runs
        //  from y = WALL + ID - 1.00 to past the outer face's inner side, so it
        //  really does take HDR_RELIEF_D off the wall rather than merely
        //  re-cutting the cavity.  See the constants for why it exists.
        translate([HDR_RELIEF_X0, WALL + ID - 1.00, HDR_RELIEF_Z0])
            cube([HDR_RELIEF_X1 - HDR_RELIEF_X0,
                  HDR_RELIEF_D + 1.00,
                  HDR_RELIEF_Z1 - HDR_RELIEF_Z0]);

        //  ...and the -X wall's slot for the WittyPi's button.  It is open to
        //  the MID's bottom edge, so the shell drops over the button instead of
        //  landing on it, and it reaches into the cavity so the button can be
        //  pressed from outside.  See the constants for the measured box.
        translate([WITTY_BTN_X0, WITTY_BTN_Y0, WITTY_BTN_Z0])
            cube([WITTY_BTN_X1 - WITTY_BTN_X0,
                  WITTY_BTN_Y1 - WITTY_BTN_Y0,
                  WITTY_BTN_Z1 - WITTY_BTN_Z0]);

        screw_pilots();
        seam(JOINT_A);
        seam(SPLIT_B);
    }
}

// =====================================================================
//  PART 3  -  BEZEL    stack z SPLIT_B .. OH   (carries the LCD)
// =====================================================================
module bezel() {
    difference() {
        translate([0, 0, SPLIT_B + MATE_GAP])
            rbox(OW, OD, LCD_T + BEZEL_T - MATE_GAP, 3.0);

        // LCD pocket - dropped in from underneath, so the pocket is the
        // continuation of the cavity and the LCD finds its own level.
        //
        //  The pocket is POCK_W x POCK_D, not the bare cavity: the measured
        //  board is 85.80 x 55.60, and the cavity alone would leave 0.16 a
        //  side in X.  POCK_W = 86.60 gives LCD_FIT = 0.40 there, and the
        //  cavity's 57.20 already gives 0.80 in Y.  The BEZEL's wall thins
        //  from 4.50 to 4.26 to pay for it.
        //
        //  r = 1.00, not the 2.00 every other cavity here uses, and it is the
        //  LCD's PCB that sets it.  A square PCB corner in this rounded pocket
        //  keeps 1 - sqrt((1 - 0.40)^2 + (1 - 0.80)^2) = 0.37 at each corner,
        //  and the real board's own corner round only adds to that.  At
        //  r = 2.00 the corner arc would cut into the board; that is the jam
        //  this case is supposed to prevent, because the panel would sit on
        //  its corners instead of on the shelf and the header pins would take
        //  the difference.  verify.py's `lcd n bezel` check keeps it.
        translate([POCK_X, POCK_Y, SPLIT_B - 1])
            rbox(POCK_W, POCK_D, LCD_T + 1, 1.00);

        // the window through the bezel lip.  Only as deep as the lip, so
        // the pocket floor stays solid and the LCD cannot be pushed through.
        // WIN_W x WIN_D is the panel less LCD_LIP on every side: a 2.00 lip
        // still holds the LCD down, without a 5.50 band of bezel over the
        // screen.  The opening keeps WIN_CLR clear of the visible area.
        translate([WIN_X, WIN_Y, SPLIT_B + LCD_T - 0.1])
            cube([WIN_W, WIN_D, BEZEL_T + 1.1]);

        // ...and the six bores the case screws pass down through, counterbored
        // so the button heads finish flush with this top face.  See the WALL
        // note for the 0.65 that opens through the outer side.
        screw_holes();
        screw_counterbores(true);
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
    //  The imported mesh is the old 5.50 slab; the real part is 7.00.  The
    //  extra 1.50 is above the PCB (the screen stack), so a plain spacer on
    //  the mesh's screen top stands in for it.  Without it the mesh would
    //  float 1.50 below the BEZEL's pocket ceiling and every render and
    //  `lcd n bezel` probe would describe the wrong part.
    translate([LCD_CX - LCD_MESH_TOP_W / 2,
               LCD_CY - LCD_MESH_TOP_D / 2,
               LCD_TOP_Z - (LCD_T - LCD_MESH_T)])
        cube([LCD_MESH_TOP_W, LCD_MESH_TOP_D, LCD_T - LCD_MESH_T]);
}

//  The CE09547, as geometry.  Nothing else in the file draws it, and two
//  things need it: verify.py, which can only check that the WittyPi lands ON
//  it and that it clears the Pi's own header if there is something there to
//  measure, and the assembly render, where the gap it spans is the whole
//  reason the case is the height it is.
//
//  Drawn from the PUBLISHED figures, not from the CAD in ../base/ - so this
//  is not the part either, and it is the one thing in the whole model to check
//  with calipers before committing filament.  The body's underside and the
//  Pi's PCB top are left open on purpose: the 3.92 between them is where the
//  Pi's own GPIO header lives, and the Pi's mesh already draws that.
module header() {
    z0 = PCB_Z + PI_PCB_T + HDR_STANDOFF;       // the insulator's underside
    translate([PI_GPIO_CX, PI_GPIO_CY, z0 + HDR_BODY / 2])
        cube([HDR_BODY_W, HDR_BODY_D, HDR_BODY], center = true);
    //  40 pins: 20 columns along X, two rows across Y, on the 2.54 grid the
    //  GPIO footprint is measured on.  They run the full 14.50 and so stand
    //  HDR_PIN_UP proud of the WittyPi's top face - the WittyPi's socket lets
    //  them through, and it is the LCD's socket, LCD_DROP deep, that covers
    //  them.  That is why this stops at the tips and not at WITTY_Z.
    for (i = [0 : 19], j = [0, 1])
        translate([PI_GPIO_CX + (i - 9.5) * HDR_PITCH,
                   PI_GPIO_CY + (j - 0.5) * HDR_PITCH,
                   z0 + HDR_BODY])
            cube([HDR_PIN, HDR_PIN, HDR_PIN_L]);
}

//  The panel hardware, as geometry - the last two reference parts.  Both are
//  drawn in the PART's own frame, the way the vendor CAD measures it: for
//  the switch the seat plane is z 0 and the button points up +z, and for the
//  LED the flange's bearing face is z 0 and the lens points up +z.  Every
//  measured number can then be typed in as measured, with nothing converted,
//  and the two callers after them are what turn a part into a fitting.
module led() {
    //  One solid, by rotate_extrude, rather than a cylinder unioned to a
    //  sphere: at that union the barrel's top edge and the dome's equator
    //  are coincident, and this file does not do coincident faces.  X is
    //  the radius and Y is the height, per rotate_extrude's own convention.
    r   = LED_BODY_D / 2;
    bar = LED_LEN - LED_FLANGE_T - r;               // the barrel, dome excluded

    rotate_extrude($fn = $fn)
        polygon(concat(
            [[0, -LED_FLANGE_T], [LED_FLANGE_D / 2, -LED_FLANGE_T],
             [LED_FLANGE_D / 2, 0], [r, 0], [r, bar]],
            [for (a = [6 : 6 : 90]) [r * cos(a), bar + r * sin(a)]]));

    //  Two square leads on 2.54 centres, run back into the cavity.  Drawn
    //  LED_LEAD_L long, well short of the real thing, because the ones in
    //  the hand are cut to fit and 25 mm of lead would only make the render
    //  unreadable - so this is the one number here that is a drawing
    //  convention rather than a measurement.
    //  The 0.10 on the z is the same trick as everywhere else in this file:
    //  it runs the lead's end INTO the flange rather than stopping on the
    //  flange's back face, which would put two faces in the same plane.
    for (sx = [-LED_LEAD_DX, LED_LEAD_DX])
        translate([sx - LED_LEAD / 2, -LED_LEAD / 2,
                   -LED_FLANGE_T - LED_LEAD_L + 0.10])
            cube([LED_LEAD, LED_LEAD, LED_LEAD_L]);
}

module switch() {
    body_h = SW_H - SW_TOP_H;                       // the full-section tier

    //  The body.  SW_H - SW_TOP_H deep, NOT the measured 3.36: this is the
    //  one dimension in the part that follows a setting instead of the CAD,
    //  and the reasoning is in the TUNE block.  The 0.10 laps it into the
    //  lid so that the two never meet face to face.
    translate([-SW_BODY / 2, -SW_BODY / 2, 0])
        rbox(SW_BODY, SW_BODY, body_h + 0.10, SW_BODY_R);

    //  The pressed metal lid: the full 6.00 square, R0.25, 0.25 thick.
    //  (Its vertex bounding box measures 5.49 - that is the corner tangent
    //  points of a filleted square, not the plate.)  Lapped the same way at
    //  both ends.
    translate([-SW_BODY / 2, -SW_BODY / 2, body_h - 0.10])
        rbox(SW_BODY, SW_BODY, SW_LID_T + 0.20, SW_BODY_R);

    //  The raised centre the button sits on, and the reason the button hole
    //  is o3.60 and can be no wider: 4.99 across, this cannot pass through
    //  the lip, so it is what fills the last of the pocket.  Drawn
    //  concentric - the CAD's own has it 0.375 off centre in X.
    translate([-SW_TOP / 2, -SW_TOP / 2, body_h])
        rbox(SW_TOP, SW_TOP, SW_TOP_H, SW_TOP_R);

    //  The actuator.  o3.50 through the lip's o3.60 button hole, so 0.05 to
    //  spare radially, and finishing SW_ACT_UP proud of the body's front
    //  face - which is 0.30 proud of the CASE, because the lip it passes
    //  through is only 0.45 thick.
    translate([0, 0, SW_H + SW_ACT_UP - SW_ACT_L])
        cylinder(d = SW_ACT_D, h = SW_ACT_L, $fn = $fn);

    //  Four legs, at the tails' measured positions.  A leg leaves the body's
    //  SIDE wall 0.90 above the seat plane, bends outward and folds down to
    //  the board, so what is drawn is its swept volume: one box, SW_LEG_L
    //  below the seat plane and the measured 0.90 above it.  It sits OUTSIDE
    //  the body's 6.00 square - and that is exactly why the pocket having no
    //  floor at SW_H = 5.00 is what lets the legs start in free cavity
    //  instead of driving into a floor they cannot fit through.
    //
    //  SW_LEG_IN is not a measured number: it pulls each leg 0.10 INTO the
    //  body so the two solids interpenetrate.  Stopped at the body's own
    //  face they would meet along a line instead, which is the same
    //  degeneracy as a shared face and shows up as a non-manifold mesh.
    for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * SW_LEG_X0 - (sx < 0 ? SW_LEG_W : 0),
                   sy > 0 ? SW_LEG_Y0 - SW_LEG_IN : -(SW_LEG_Y0 + SW_LEG_D),
                   -SW_LEG_L])
            cube([SW_LEG_W, SW_LEG_D + SW_LEG_IN, SW_LEG_L + SW_LEG_UP]);
}

//  And the two rows, in the wall.  Both go in by a rotate([90, 0, 0]), which
//  sends the local +z to case -Y - out through the panel.  For the LED that
//  is the lens direction, so its flange lands flat on the wall's inner face;
//  for the switch it is the button direction, so the body lands in the
//  pocket with its seat plane, where the pins leave it, on the pocket's own
//  floor line.  Every number here is already the panel's: nothing new is
//  introduced, and a placement that is wrong shows up as a part in the wrong
//  place rather than as a constant that has quietly drifted.
//
//  Both loops keep the `if (N > 0)` guard for the reason panel() documents:
//  [0 : N - 1] at N = 0 is a REVERSED range and runs twice.
module leds() {
    if (LED_N > 0)
        for (i = [0 : LED_N - 1])
            translate([LED_X0 + i * LED_PITCH, WALL, PANEL_Z])
                rotate([90, 0, 0]) led();
}

module switches() {
    if (SW_N > 0)
        for (i = [0 : SW_N - 1])
            translate([SW_X0 + i * SW_PITCH, SW_LIP + SW_H, PANEL_Z])
                rotate([90, 0, 0]) switch();
}

// =====================================================================
//  PLACEMENT  -  one frame, and one part that sits outside it
// =====================================================================
//  There is nothing to place any more.  base(), mid(), bezel() and the four
//  board modules all put their z 0 at the BASE's underside, and so does the
//  bench: with the MOUNT gone there is no 21 mm of tub between the two, so
//  stack coordinates ARE case coordinates and a part exported from here
//  already sits flat on the bed.  This block used to hold seven
//  translate([0, 0, MOUNT_H]) wrappers; deleting them is the whole change.
//
//  plate() is the one exception, and only because it hangs below z 0.

//  plate() is drawn where it fits - under the case - which is the wrong way up
//  to print.  The print orientation depends on which face has to be on the bed:
//
//    hook / pals  the hook stands off the OUTER face, so the part turns over
//                 and the case face goes on the bed (the hook points up).
//    strap        the skirt stands off the CASE face, so the OUTER face goes
//                 on the bed and the tray prints open-side up.  No flip: the
//                 part is drawn with its outer face already at the bottom, so
//                 this is a pure lift, and a flip here would put the skirt's
//                 3.00 rim on the bed and ask the floor to bridge the whole
//                 tray.  The lift is PLATE_GAP + PLATE_T, which puts the outer
//                 face at z 0 and the skirt's top at PLATE_T + PLATE_GAP +
//                 PLATE_SKIRT_TOP.
//
//  A rotation and not a mirror, so it is the same part in both cases - only
//  where it sits in the STL changes.  The Y shift is only to bring it back
//  over its own footprint.
module plate_placed() {
    if (PLATE_STYLE == "strap")
        translate([0, 0, PLATE_GAP + PLATE_T]) plate();
    else
        translate([0, OD, -PLATE_GAP]) rotate([180, 0, 0]) plate();
}

module boards() {
    color("DarkGreen")      pi();
    color("DarkOliveGreen") wittypi();
    color("SlateGray")      lcd();
    color("Goldenrod")      header();
}

//  The assembly sweep.  Only the parts that are present while the MID is
//  lowered: the BASE, the Pi, the stacking header and the WittyPi.  The LCD
//  rests on the MID's shelf, so it cannot be there yet; the panel hardware,
//  BEZEL and plate are fitted after the MID too.  Including any of them would
//  make the view lie about the order of assembly.
function sweep_z() = SWEEP_LIFT >= 0 ? SWEEP_LIFT : $t * SWEEP_SPAN;

module sweep() {
    color("SteelBlue")      base();
    color("DarkGreen")      pi();
    color("Goldenrod")      header();
    color("DarkOliveGreen") wittypi();
    translate([0, 0, sweep_z()])
        color("CornflowerBlue") mid();
}

module shell() {
    if (SHOW_PLATE) color("Plum")           plate();
    if (SHOW_BASE)  color("SteelBlue")      base();
    if (SHOW_MID)   color("CornflowerBlue") mid();
    if (SHOW_BEZEL) color("BurlyWood")      bezel();
}

module electronics() {
    if (SHOW_PI)    color("DarkGreen")      pi();
    if (SHOW_WITTY) color("DarkOliveGreen") wittypi();
    if (SHOW_HDR)   color("Goldenrod")      header();
    if (SHOW_LCD)   color("SlateGray")      lcd();
    if (SHOW_LED)   color("Crimson")        leds();
    if (SHOW_SW)    color("DimGray")        switches();
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
//  TRAILER  -  the assembly, coming together, for the demo video
// =====================================================================
//  Reached only with PART = "trailer" and driven by OpenSCAD's animation
//  clock:
//
//      openscad -o f.png --animate 480 --camera=... \
//          -D 'PART="trailer"' pi-stack-v0.7.scad
//
//  Nothing here can reach anything else.  It is its own PART, so the four
//  exports and verify.py never evaluate one line of it, and no module above
//  is touched - this block decides only WHERE each already-built part is
//  drawn and how far along it is.  Every part is the same module the
//  assembly view draws, in the same place, at offset zero.
//
//  $t is 0 when nothing is animating, so PART="trailer" outside an animation
//  renders the model fully exploded.  That is the useful failure: it says at
//  a glance that --animate was forgotten.  TRAILER_AT freezes one frame.

TRAILER_AT = -1;        // 0..1 to hold a frame still; -1 to follow $t

//  The beats: [start, end] of the clock, in the order they arrive.  The gaps
//  between the windows are deliberate - one part settles before the next
//  starts moving, so the eye has something stationary to measure against.
TRAILER_BEATS = [
    [0.00, 0.13],       //  the plate, up onto the bench under everything
    [0.15, 0.28],       //  the Pi, down onto its standoffs
    [0.23, 0.36],       //  the extended header, onto the Pi's own pins
    [0.31, 0.43],       //  the WittyPi, onto the header - not the other way
    [0.39, 0.52],       //  and the 3.5" panel, last of the stack
    [0.58, 0.74],       //  the MID, down over the whole of it
    [0.78, 0.88],       //  the BEZEL
    [0.89, 0.95],       //  the three LEDs
    [0.91, 0.97],       //  ...and the three switches under them
];

//  How far each thing starts from where it belongs.  Ordered by arrival, so
//  the parts form a queue standing in the sky above the bench and each one is
//  above everything it has to pass on the way down: the MID starts clear of the
//  LCD's top, the BEZEL clear of the MID's.  A part that starts lower than one
//  arriving before it would be seen sliding *through* it - and a shell sliding
//  down over a board is right, while a board sliding up through a shell's top
//  plate is not.
//  The whole queue is scaled by one number.  At 1.0 - how the film is composed
//  - the parts still to come stand in the top of the frame and are meant to be
//  seen waiting there; that is what makes the shot read as a build.  Raise it
//  and the queue climbs out of frame instead, which is the other film you
//  could make: raise it until the sky is empty (about 2.8 at this camera) and
//  every part then enters from off-screen.  It is here as one number because
//  how far up the queue has to stand is a fact about the CAMERA, not about the
//  case, so it wants re-sweeping - render one frame at TRAILER_AT=0 and look -
//  if the camera or the aspect ever moves.  The front pair are not scaled:
//  they are staged to one side, in shot, and are waiting on the bench.
TRAILER_LIFT   = 1.0;

TRAILER_PLATE  =  55;   // below, rising  - the plate goes on from underneath
TRAILER_PI     =  70;   // and everything else falls in, in build order
TRAILER_HDR    =  95;
TRAILER_WITTY  = 120;
TRAILER_LCD    = 145;
TRAILER_MID    = 215;   // clear of the LCD's top, which starts at 192.60
TRAILER_BEZEL  = 270;   // clear of the MID's top, which starts at 257.10
TRAILER_FACE   =  85;   // out the front, for the panel's hardware

//  The clock the beats are laid out on.  OpenSCAD's $t stops one frame short
//  of 1.0, and the last beat ends at 0.97, so the whole score is compressed
//  into the first TRAILER_SPAN of the frame count and the rest is a held shot
//  of the finished case - room for the last card to sit still.
TRAILER_SPAN = 0.86;

function tclock() = min(1, (TRAILER_AT < 0 ? $t : TRAILER_AT) / TRAILER_SPAN);

//  Eased 0..1 through the window [a, b].  Smoothstep, so every part starts
//  and stops at rest - a part that snaps to a halt reads as a bug rather
//  than as a part settling.
function ss(a, b) =
    let (u = max(0, min(1, (tclock() - a) / (b - a))))
    u * u * (3 - 2 * u);
function beat(i) = ss(TRAILER_BEATS[i][0], TRAILER_BEATS[i][1]);

module falls(z0, e) { translate([0, 0, z0 * (1 - e)]) children(); }
module enters(y0, e) { translate([0, y0 * (1 - e), 0]) children(); }

module trailer() {
    color("Plum")           falls(-TRAILER_PLATE * TRAILER_LIFT, beat(0)) plate();
    color("SteelBlue")      base();
    color("DarkGreen")      falls(TRAILER_PI    * TRAILER_LIFT, beat(1)) pi();
    color("Goldenrod")      falls(TRAILER_HDR   * TRAILER_LIFT, beat(2)) header();
    color("DarkOliveGreen") falls(TRAILER_WITTY * TRAILER_LIFT, beat(3)) wittypi();
    color("SlateGray")      falls(TRAILER_LCD   * TRAILER_LIFT, beat(4)) lcd();
    color("CornflowerBlue") falls(TRAILER_MID   * TRAILER_LIFT, beat(5)) mid();
    color("BurlyWood")      falls(TRAILER_BEZEL * TRAILER_LIFT, beat(6)) bezel();
    color("Crimson")        enters(-TRAILER_FACE, beat(7)) leds();
    color("DimGray")        enters(-TRAILER_FACE, beat(8)) switches();
}

// =====================================================================
//  output
// =====================================================================
if      (PART == "plate")    { color("Plum")      plate_placed(); }
else if (PART == "base")     { color("SteelBlue") base(); }
else if (PART == "mid")      { color("SteelBlue") mid(); }
else if (PART == "bezel")    { color("SteelBlue") bezel(); }
else if (PART == "header")   { color("Goldenrod") header(); }
else if (PART == "boards")   { electronics(); }
else if (PART == "stack")    { electronics(); }   // the electronics alone
else if (PART == "assembly") { preview(); }
else if (PART == "sweep")    { sweep(); }          // the MID descending
else if (PART == "trailer")  { trailer(); }        // the demo video, see above
else {  // "all" - all four laid out along X for printing
    color("SteelBlue") base();
    translate([OW + 10, 0, 0])       color("CornflowerBlue") mid();
    translate([2 * (OW + 10), 0, 0]) color("BurlyWood")      bezel();
    //  The strap plate is wider than the case (its arms reach 19.88 past the
    //  case's -X edge), so it needs more than one 105.12 pitch of clearance
    //  from the BEZEL.  25.00 on top of the pitch leaves 15.12 between them.
    translate([3 * (OW + 10) + 25, 0, 0]) color("Plum")      plate_placed();
}
