#!/bin/sh
# Render the preview/ images for pi-stack-v0.7.
#
#     ./render.sh            all views
#     ./render.sh assembly   just one
#
# WHY THIS IS COMMITTED
# The v0.6 README credits its renders to a software rasteriser that lived in
# /tmp/cv_models and no longer exists, so those images cannot be regenerated
# from this repo.  OpenSCAD's own renderer works here (it needs a real X
# display; `DISPLAY` must be set, there is no --headless in 2021.01), so these
# views are reproducible instead.
#
# The v0.6 note about depth fog is worth keeping in mind: OpenSCAD shades by
# face normal, so two walls facing the same way come out the same tone and an
# opening in one of them reads as a flat patch.  Colour per PART is what makes
# the joints legible here, and the section views are what make the openings
# legible.  Check a wall in v0.7-section before believing it.
set -e
cd "$(dirname "$0")"
OUT=preview
SIZE=1200,900

# tx,ty,tz,rotx,roty,rotz,dist  - --viewall fits the object, so dist is unused
ISO="--camera=0,0,0,58,0,32,0"
UNDER="--camera=0,0,0,126,0,32,0"
# rotz = 0 puts the camera on the -Y side, which is the PANEL wall.  Tilted off
# horizontal on purpose: face-on, you look straight down a through-hole and see
# the far wall's inner face in the same tone, so the holes simply disappear.
FRONT="--camera=0,0,0,78,0,0,0"
# rotz = 180 is the +Y side, where the LCD's socket hangs and the shelf is
# notched for it.
BACK="--camera=0,0,0,72,0,180,0"

render() {
    name=$1; shift
    echo "  $name"
    openscad -o "$OUT/v0.7-$name.png" --imgsize=$SIZE --projection=o \
        --viewall --autocenter "$@" pi-stack-v0.7.scad >/dev/null
}

want=${1:-all}
for v in parts assembly internals stack joints underside section base plate pals pads panel midpanel rear front fittings; do
    [ "$want" = all ] || [ "$want" = "$v" ] || continue
    case $v in
        # all four printable parts, laid out along X
        parts)     render parts     $ISO  -D 'PART="all"' ;;
        # everything, in place
        assembly)  render assembly  $ISO  -D 'PART="assembly"' ;;
        # bezel off: the LCD pocket and the top of the stack, with the header
        # standing in the gap the case grew to make for it
        internals) render internals $ISO  -D 'PART="assembly"' -D 'SHOW_BEZEL=false' ;;
        # the electronics alone, no case in the way
        stack)     render stack     $ISO  -D 'PART="stack"' ;;
        # case parts only, so the joint lines are the only thing to see.  The
        # plate is the one joint this case is built around, and it is not a
        # seam but a 0.50 gap - the plate comes off first, on its own bolts,
        # and it is what you reach the Pi's four screws through.  The seam
        # grooves are interrupted at all six screw columns, which is why they
        # read as six dashes rather than two unbroken rings.
        joints)    render joints    $ISO  -D 'PART="assembly"' \
                   -D 'SHOW_PI=false' -D 'SHOW_WITTY=false' \
                   -D 'SHOW_HDR=false' -D 'SHOW_LCD=false' \
                   -D 'SHOW_LED=false' -D 'SHOW_SW=false' ;;
        # from below: the strap plate's outer face fills the view - four bolt
        # counterbores flush in it and the four arm paddles fanning past the
        # case corners.  The six case heads and the Pi's four are all behind
        # that floor now, which is exactly the order they come apart in:
        # plate first, on its own four bolts.
        underside) render underside $UNDER -D 'PART="assembly"' ;;
        # Half-section, case parts only.  The boards are left out on purpose:
        # the imported LCD is a SURFACE model, so cutting it leaves coplanar
        # faces for OpenCSG to fight over and the whole image comes out
        # striped.  The clearances the boards need are what verify.py measures
        # numerically; this view is for reading the wall sections and the
        # openings cut through them.
        section)   render section   $ISO  -D 'PART="assembly"' -D 'CUT_AWAY="-Y"' \
                   -D 'SHOW_PI=false' -D 'SHOW_WITTY=false' -D 'SHOW_HDR=false' \
                   -D 'SHOW_LCD=false' -D 'SHOW_LED=false' -D 'SHOW_SW=false' ;;
        # the BASE on its own, open side up: the tray the whole case stands
        # on, with the four plate-bolt bosses standing on its floor and the
        # Pi's bosses either side of them.  Look for the four blind o2.50
        # pilots down the middle of those bosses - they are the only holes in
        # the case that take a thread.  The six in the rim are clearances.
        base)      render base      $ISO  -D 'PART="base"' ;;
        # the strap plate on the bed, as it prints: outer face down, the tray
        # open, the skirt standing up and the four arms flat on the bed
        plate)     render plate     $ISO  -D 'PART="plate"' ;;
        # ...and the other way to hang it: a slot field on the PALS module
        pals)      render pals      $ISO  -D 'PART="plate"' -D 'PLATE_STYLE="pals"' ;;
        # the LCD's seat, which is the whole reason the flanges exist: the MID
        # alone, cut in half, so the shelf, the outcrops standing on it and the
        # notch the socket drops through all read in one image.  Tilted well
        # off the seat plane on purpose - the flanges' tops are COPLANAR with
        # the shelf, so from a shallow angle they and the ring come out one
        # flat tone and the whole point of the feature disappears.  The green
        # strips are the cut faces, not geometry.
        pads)      render pads      --camera=0,0,0,66,0,205,0 -D 'PART="assembly"' -D 'CUT_AWAY="-X"' \
                   -D 'SHOW_PLATE=false' \
                   -D 'SHOW_BASE=false' -D 'SHOW_BEZEL=false' \
                   -D 'SHOW_PI=false' -D 'SHOW_WITTY=false' \
                   -D 'SHOW_HDR=false' -D 'SHOW_LCD=false' \
                   -D 'SHOW_LED=false' -D 'SHOW_SW=false' ;;
        # the front panel in place: where the LED row and the switch row sit
        # against the ports below them and the LCD above, with the accessory
        # opening under the buttons.  Boards off, so nothing shows through the
        # openings from behind - which is also why that opening comes out as a
        # flat patch here and needs the `front` view to read as a hole.
        panel)     render panel     $FRONT -D 'PART="assembly"' \
                   -D 'SHOW_PI=false' -D 'SHOW_WITTY=false' \
                   -D 'SHOW_HDR=false' -D 'SHOW_LCD=false' ;;
        # and the MID alone, where the pockets read with their depth and ribs
        midpanel)  render midpanel  $FRONT -D 'PART="mid"' ;;
        # the rear (+Y) wall square on: the hexagonal vent field and, at its
        # left as seen from behind, the 10 x 6 battery-lead rectangle.  The MID
        # alone, because the wall is the whole point of the view.
        rear)      render rear      $BACK  -D 'PART="mid"' ;;
        # the front wall square on, with the case cut back to just behind that
        # wall.  This is the view for the ACCESSORY OPENING, and it is the one
        # view that shows it as a hole rather than as a flat patch: a
        # through-hole seen against the far wall's inner face is the same tone
        # as the wall round it, which is the v0.6 note at the top of this file.
        # Cut back with CUT_AWAY="+Y" and CUT_AT=0.20, so everything past
        # y 13.34 is gone and the openings look out at the background.  The
        # tilt is shallow on purpose - 6 degrees off horizontal, so the
        # opening's 7.20 of height is not foreshortened away.
        front)     render front     --camera=0,0,0,84,0,0,0 -D 'PART="assembly"' \
                   -D 'CUT_AWAY="+Y"' -D 'CUT_AT=0.20' \
                   -D 'SHOW_PI=false' -D 'SHOW_WITTY=false' \
                   -D 'SHOW_HDR=false' -D 'SHOW_LCD=false' ;;
        # the panel hardware seated, which is what this file could not show
        # until the LEDs and switches became geometry.  The cut has to come
        # from BEHIND them: there is no plane that removes the wall and
        # leaves them, because they are IN the wall - the switch body's
        # front face is 0.45 behind the outer face and the LED's tip is
        # 0.20 - so any cut in front of them cuts them too.  CUT_AWAY="+Y"
        # at 0.20 takes everything past y 13.34 instead, which is the far
        # wall, the shelf and the boards, and leaves the panel whole with
        # its hardware standing off it: the three switches with their four
        # legs each splaying into the cavity, and the three red LEDs with
        # their leads, at panel height.
        #
        # Boards off, and the imported LCD especially: it is a SURFACE model
        # and fights OpenCSG when it is cut - see the warning at the top of
        # this file.  The two reference parts are CSG solids and section
        # cleanly, so nothing here needs that caveat.
        #
        # The angle is 25 degrees off straight-on rather than the `front`
        # view's 12, because the point of this view is DEPTH - the bodies
        # standing off the inner face and the legs splaying into the cavity
        # are what a face-on camera flattens away.  Past about 30 degrees the
        # coplanar fight the header warns about comes back on the far wall's
        # upper corner and stripes the image; 25 is where it stops reading.
        fittings)  render fittings  --camera=0,0,0,70,0,205,0 -D 'PART="assembly"' \
                   -D 'CUT_AWAY="+Y"' -D 'CUT_AT=0.20' \
                   -D 'SHOW_PI=false' -D 'SHOW_WITTY=false' \
                   -D 'SHOW_HDR=false' -D 'SHOW_LCD=false' ;;
    esac
done
echo "done -> $OUT/v0.7-*.png"
