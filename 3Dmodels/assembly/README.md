# Whole-device assembly (Blender)

`crimson-veil-assembly.blend` is the complete Crimson Veil MK1 wearable in one
scene: the pi-stack case with the Pi, Witty Pi, LCD and panel parts inside it,
the CE07929 protoboard case with both boards and the ESP32, the fabric belt, and
the four elastic loops that hold the pi-stack to the belt.

The belt is one continuous folded pocket: in section it is a U, with an outer
wall, an inner wall and the fold that joins them at the bottom, open along the
whole top edge. The pi-stack sits in that pocket strapped to the outward face
of the inner wall, standing proud through a window cut in the outer wall so the
LCD is visible from outside. The protoboard case is at the back of the pocket,
opposite it. The eight ECG snaps sit on the inner wall, facing the body. The
belt closes on the left with hook-and-loop alone: the free end is one thickness
of cloth, bound along its free edge, that lies back over the belt's outer face
and presses flat onto it — a loop pad sewn to the belt, a hook pad on the end's
underside, nothing else. No sleeve, no strap, no keeper.
No cable runs on the body face — the electrode harness stays inside the pocket,
between the walls.

The scene is finished in stone grey and crimson: the belt is a stone-grey woven
nylon (procedural weave), the printed pi-stack and protoboard cases are smooth
matte crimson, and the ECG snaps are silver. The elastic loops, LCD glass and
PCBs keep their own materials.

Everything is separate, named and parented so it can be rigged and animated;
the `.glb` is the same model without the studio (lights, floor, camera).

## Files

| | |
|---|---|
| `crimson-veil-assembly.blend` | the scene, metres, Z up, front is −Y |
| `crimson-veil-assembly.glb` | model only, Y-up, studio excluded |
| `build_assembly.py` | builds the scene from `parts/` and renders the previews |
| `preview/assembly-*.png` | EEVEE renders, one per view |
| `parts/*.stl` | component meshes exported in their assembled frames |
| `export/_pi_part.scad`, `export/_ce_part.scad` | one-component wrappers around the case SCAD |
| `export/export_all.sh` | regenerates every STL in `parts/` |
| `pi-stack-anim/` | separate pi-stack assembly animation (see its own README) |
| `belt-anim/` | separate belt assembly animation, built around the pi stack (see its own README) |

## Rebuild

The case part exports need OpenSCAD; the assembly needs Blender 4.x+ (built
with 5.2.2 LTS).

```bash
cd 3Dmodels/assembly
./export/export_all.sh                     # OpenSCAD -> parts/*.stl
~/.local/bin/blender --background --factory-startup --python build_assembly.py
```

The script builds the mesh, renders the previews, saves the `.blend`, then
exports the `.glb`. It takes about eleven seconds on the development machine.
`parts/` and the `.glb` are large generated outputs; only the SCAD wrappers,
the script and this README are meant to be tracked.

## Coordinates and layout

Units are metres; the model spans roughly X ±160 mm, Y −164…+110 mm,
Z ±65 mm. Front is −Y (LCD), back is +Y, +X is the device's right.

The case frames come from the SCAD sources and are used unchanged:

* **pi-stack v0.7** — plate outer face against the inner wall's pocket face,
  case stacked outward through the 98 × 65 mm window in the outer wall. Plate
  centre at (−47.56, −33.10) mm from the belt centre; the bezel stands 9.7 mm
  proud of the outer face.
* **CE07929** — base 174 × 119 mm, base + lid 37 mm; boards sit at z = 4.4 mm
  in the case frame, the ESP32 at (−60, 26.5) mm. It is turned on its side so
  the 37 mm thickness spans the belt pocket: 174 mm runs around the loop,
  119 mm stands vertically, and the lid faces the body.

The belt itself is **not modelled in the repository CAD**. Its numbers here are
a fit to the parts and are the only assumptions in the scene:

| | |
|---|---|
| band | 320 × 220 mm outside, r75 mm corners, 130 mm tall |
| section | U: 3 mm outer wall, 41 mm pocket, 3 mm inner wall, 3 mm bottom fold |
| inner opening | 226 × 126 mm, r28 mm corners |
| hems | rolled hems on both top edges |
| electrodes | eight 4 mm ECG snaps, inner wall, mid-height, 45° apart; flange on the fabric, stud facing the body, wire on the pocket side |
| closure | hook-and-loop on the left side only: the free end lies back over the belt's outer face and presses flat onto it, one bound edge down the free end, loop pad sewn to the belt and hook pad to the end's underside |
| pi-stack mount | strap plate on the inner wall's pocket face, elastic loops over the four arm waists; the case looks out through the window |
| protoboard mount | case at the back of the pocket, standing vertically, opposite the pi-stack |
| cabling | USB lead from the pi-stack's +X USB deck, round the inside of the pocket to the protoboard case's open end and the ESP32; 8-way harness from that open end, inside the pocket, on a thin loom along the inner wall's pocket face (through the 2 mm clearance beside the case) with a lead up to every snap's back. Nothing runs on the body side |

Change the `BELT_*` and `PLATE_*` constants at the top of `build_assembly.py`
to refit the belt to a real one.

## Collections and animation

```
Belt            BELT_ROOT                Belt_Fabric,
                                         Belt_Hem_Top_Outer, Belt_Hem_Top_Inner,
                                         Belt_End, Belt_End_Hem,
                                         Belt_End_Velcro_Loop,
                                         Belt_End_Velcro_Hook,
                                         Elastic_Loop_1..4
Electrodes      (parented to BELT_ROOT)  Electrode_1..8_Snap + _Patch
Pi Case         PI_CASE_ROOT             PiCase_Base/Mid/Bezel/StrapPlate,
                                         RaspberryPi3, WittyPi4, LCD_3v5in,
                                         CE09547_Header, Panel_LEDs/Switches
Protoboard Case PROTO_CASE_ROOT          ProtoCase_Base/Lid, Protoboard_A/B,
                                         ESP32_DevKit_V1
Cables          BELT_ROOT (harness)      Cable_USB_Pi_To_Protoboard (PI_CASE_ROOT),
                PI_CASE_ROOT (USB)       USB_Plug_Pi, USB_Plug_Protoboard
                                         (PROTO_CASE_ROOT),
                                         Harness_Trunk, Harness_Strain_Relief,
                                         Harness_Breakout, Harness_Loom_A/B,
                                         Electrode_Lead_1..8
Studio                                   STUDIO_Key/Fill/Rim/BackFill/Interior,
                                         STUDIO_Camera, STUDIO_Floor
```

`PI_CASE_ROOT`, `PROTO_CASE_ROOT` and `BELT_ROOT` are empties placed at the
parts' mounting points; move or rotate a root to animate a whole case, then
work inside a case for individual boards and panels. The LCD's glass face is a
second material slot (`LCD_Glass`) on `LCD_3v5in`, selected by face normal.

The GLB keeps the same hierarchy. Because it is exported Y-up, animations
imported elsewhere should treat Blender's −Y as glTF +Z.

## Notes

* The case parts are imported at 0.001 and their scale applied, so the mesh
  data is in metres rather than carrying an object scale.
* The belt is a single U-section solid with a window cut in the outer wall: the
  pocket cavity is open along the top all the way round, and the studio floor
  visible through the opening is not part of the model.
* Hems, electrode patches and elastic loops are curves with a bevel radius;
  glTF export converts them to meshes.
* The closure is three ribbons following the belt's outer wall: the loop pad on
  the fabric, the hook pad on it, and the end itself on top of both. They are
  offset in `make_wall_ribbon`'s gap so the pads meet face to face, and the hook
  pad stops with the free edge so the loop pad is what shows past it.
