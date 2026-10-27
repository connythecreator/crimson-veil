# Pi-stack case v0.7 — dimensioned drawings

Eight A3-landscape (420 × 297 mm) sheets for the four printed parts and the assembled case.
Everything is generated from the constants and formulas in
`../pi-stack-v0.7.scad`; `../verify.py` is parsed only as a second source for
shared constants.  No existing project file is modified by the generator.

All dimensions are millimetres.  One SVG user unit is one millimetre of paper;
a 1:1 view draws one model millimetre per user unit.  Print the SVG at 100 %
("actual size") on A3; do not use "fit to page".  Every sheet carries a scale
bar and the actual scale in its title block.

## Regeneration

Python 3 standard library only.  PNG previews additionally need a headless
Chromium/Chrome (`chromium`, `chromium-browser`, `google-chrome`,
`/snap/bin/chromium`, or `CHROME_PATH`); they are a convenience for visual
checking, not the dimensioned deliverable.

```sh
cd 3Dmodels/case/drawings
python3 make_drawings.py          # write all eight SVGs, then run checks
python3 make_drawings.py --png    # same, plus PNG previews
python3 make_drawings.py --check  # checks only; writes nothing
```

The generator writes only into `drawings/`.  Exit status is non-zero if a
constant check, a derived-value check, an SVG sanity check, or the XML parse
fails.

## Sheets

| # | File | Views and scale | What it covers |
|---|------|-----------------|----------------|
| 1 | `assembly-top.svg` | Top from +Z, 1:1 | 95.12 × 66.20 × 49.20 envelope; LCD window 81.80 × 51.60 centred at 6.66 / 7.30 from the edges; six flush M3 columns with Ø6.20 × 0.20 csk, Ø5.80 × 1.65 cbore and Ø3.40 through, dimensioned by ordinates; dashed LCD active area. |
| 2 | `assembly-front.svg` | Front from -Y, 1:1 | PWR, HDMI and AUDIO slots; three Ø5.20 LEDs; three 6.20-square switch pockets with Ø3.60 buttons; accessory opening 12.20 × 7.20 R1.50; five 6.00 × 2.50 BASE vents at 9.00 pitch; plate and skirt below; stack heights. |
| 3 | `assembly-side.svg` | Side from +X, 1:1 | 8.40 solid BEZEL, 34.90 MID, 5.50 BASE and 4.00 plate; butt joints at 5.50 / 5.70 and 40.60 / 40.80; stepped ETH/USB opening; rear-edge vent/lead features called out; plate arm extents. |
| 4 | `assembly-bottom.svg` | Bottom from -Z, 1:1 | Plate silhouette and four cut waists; plate envelope 134.89 × 99.95; four plate bolts on 62.00 × 35.00; Pi pattern 8.60 / 58.00 across and 49.00 up, with Ø5.00 × 1.40 counterbores; six rim bores by ordinates; hidden case-screw and Pi features dashed. |
| 5 | `plate.svg` | Outer-face plan 1:1; section A-A 1:1 | Tray 102.12 × 73.20 R6.50 with 0.50 clearance; skirt 3.00 thick / 3.00 tall; arms on the 34.84° diagonals — root Ø16.00 at r46, cut waist 12.00 wide at r64, tip Ø20.00 at r70; four M3 bolts with Ø6.20 × 1.65 cbore and Ø2.75 × 5.30 blind pilots; five skirt notches; print envelope 134.89 × 99.95 × 7.50; section through floor and skirt. |
| 6 | `base.svg` | Plan from +Z and front elevation 1:1; section B-B 2:1 | 95.12 × 66.20, wall 4.50, interior 86.12 × 57.20, floor 2.60, rim to 5.50; four Ø7.00 Pi bosses with Ø2.80 through and Ø5.00 × 1.40 counterbores to z 7.60; four Ø7.00 plate bosses with Ø2.75 × 5.30 pilots; six rim bores Ø3.40 with Ø5.80 cbore / Ø6.20 csk on the underside; five wall vents. |
| 7 | `mid.svg` | Front, rear, left, right and plan, 1:1 | All -Y ports and panel openings (PWR 9.48 × 8.71, HDMI 16.50 × 12.06, AUDIO 8.50 × 11.98); LEDs and switch row; accessory 12.20 × 7.20; -X SD and Witty slots; +X stepped ETH/USB opening; 18-hex rear vent field; 10 × 6 battery lead; LCD shelf 80.12 × 51.20 at z 38.60; twelve Ø2.75 × 15.00 blind pilots (two per column); HDR relief; feature schedule. |
| 8 | `bezel.svg` | Plan 1:1; section A-A 2:1 | Pocket 86.60 × 57.20 R1.00; window 81.80 × 51.60 open through the 1.60 lip; solid blank 8.40 (7.00 LCD + 1.60 bezel − 0.20 joint); pocket depth 6.80; six Ø3.40 through holes with Ø5.80 × 1.65 counterbores and Ø6.20 × 0.20 countersinks; section through the window. |

## Datums and projection

- **Case X / Y / Z:** X = 0 at the left (-X) outer face, +X to the right;
  Y = 0 at the front (-Y) outer face, +Y to the rear; Z = 0 at the case
  underside (the bench), +Z up.
- **Top view (sheet 1):** X right, Y up in the sheet.
- **Front view (sheet 2):** X right, Z up; looking along +Y.
- **Side view (sheet 3):** Y right, Z up; looking along -X.
- **Bottom view (sheet 4):** X right, Y up in the sheet; looking along +Z.
  The light chain rectangle is the 95.12 × 66.20 case datum.
- **MID (sheet 7):** absolute case Z; the part occupies z 5.70–40.60.
- **BEZEL (sheet 8):** absolute case Z; the part occupies z 40.80–49.20.
- **PLATE (sheet 5):** plan X/Y use the case datums, so the tray overhangs
  X = 0 and Y = 0 by 3.50 and the arms run out to -19.89 / 115.01 in X.
  Section A-A is the exception: its Z = 0 is the plate's outer face on the
  print bed, not the case underside.

Third-angle projection throughout.

## Checks performed by the generator

- Parses the SCAD constant block and compares every shared constant against
  `verify.py`.  Current result: no disagreements.
- Checks the stated envelope, stack joints, wall/interior, plate tray and arm
  geometry, waist width, bolt/Pi/screw patterns, hole counts and port/shelf
  relations against the brief's values (`derived_checks()`).
- The traced plate outline is checked for closure: every marching-squares
  junction has degree 2 and all segments form exactly one loop.
- Per sheet: no text-on-text overlap above 1.2 mm², views inside the frame,
  no dimension value below -0.001 or above 500, all SVG well-formed XML.
- PNG previews were rendered and visually inspected for legibility.

## Caveats and source discrepancies

1. **BASE height.** The stack note says BASE 0.00–5.50.  That is the outer
   rim/body; the four Pi bosses inside the BASE rise to **z 7.60** (2.10 above
   the rim).  Sheet 6 dimensions and annotates both; sheets 2 and 3 use 5.50
   for the outside silhouette.
2. **Stale SCAD comments.** `PLATE_CX` / `PLATE_CY` are commented as 48.06 /
   33.60 but evaluate to **47.56 / 33.10**; `SW_POCKET_D` is commented 4.55
   but evaluates to **4.05**.  The drawings use the evaluated values.
3. **Arm angle rounding.** The exact angle is atan(66.20 / 95.12) =
   34.8365°, shown as **34.84°**; the brief and the SCAD comment round this
   to 34.85°.  Arm geometry uses the exact atan.
4. **Arm envelope.** The exported/faceted bounding box is **134.89 × 99.95**,
   while the analytic tip-circle extremes at $fn = 48 are 134.90998 ×
   99.97310.  Sheet 5 gives both; the 0.02 difference comes from the faceted
   circles and the export bounding box.
5. **Plate arm waist.** The waist is now a *cut*, not a turned neck: two
   Ø8.00 circles at r 64.00, ±10.00 off each arm axis, leave a concave
   12.00-wide strap seat roughly 6.00 long.  The outlines on sheets 4 and 5
   are traced from that geometry, not drawn by hand.
6. **Bezel counterbores break out.** The Ø5.80 counterbores are on a 4.50
   wall, so each breaks out 0.65 through the side.  This is intentional in
   the SCAD and is called out on sheets 1 and 8.
7. **Plate covers the case screws.** The six M3 case-screw heads sit under
   the plate; sheet 4 shows them dashed and notes that the plate must come
   off to reach them.
8. **Window through the lip.** The 81.80 × 51.60 window passes through the
   1.60 bezel lip; the pocket is 6.80 deep (7.00 LCD − 0.20 joint gap).  The
   remaining lip is 2.40 wide at the left/right sides and 2.80 at the
   top/bottom.  The pocket top is z 47.60 and the bezel top z 49.20.
9. **`verify.py` was not executed.**  It was edited concurrently with this
   work; only its constant assignments were parsed and compared.  No
   existing SCAD, verify, README or render file was modified.
10. **Formatting.** Feature sizes come from SCAD expressions, not
    transcription; values are displayed to two decimal places (one for
    integer stock sizes), so a displayed value can differ from the exact
    expression in the last digit.  Paper positions, title block text and
    sheet layout are the only hand-set numbers.
