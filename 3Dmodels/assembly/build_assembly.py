"""
Crimson Veil - whole-device assembly for Blender.

Run headless:
    ~/.local/bin/blender --background --factory-startup --python build_assembly.py

Builds, from the exported component meshes in ./parts:

  * the pi-stack (v0.7) case: plate, base, mid, bezel, Pi 3, WittyPi,
    LCD, CE09547 header, LEDs and switches;
  * the CE07929 protoboard case: base, lid, both protoboards and the
    ESP32 DevKit (the vendor mesh);
  * the fabric belt: a 130 mm band on a 320 x 220 mm rounded-rectangle
    loop, built as one folded pocket (a U in section: outer wall, inner
    wall and the bottom fold) with rolled hems on both top edges and
    eight 4 mm ECG snaps on the inner wall;
  * the CE07929 protoboard case, in the pocket at the back of the loop;
  * the four elastic loops that hold the pi-stack's strap plate to the
    inner ring (one per arm waist).

Everything is named and collected so it can be animated.  Units are
metres in Blender (STLs are millimetres, imported at 0.001).

Assumed belt layout - the only numbers here that are not from the CAD:
  belt 320 x 220 mm outside, r75 corners, 130 mm tall, 3 mm fabric
  41 mm gap between the rings; the whole belt is the pocket
  pi-stack strapped to the OUTWARD face of the inner ring, in the pocket,
  looking out through a window cut in the outer ring
  protoboard case at the back of the pocket, opposite the pi stack
  eight electrodes on the inner ring, 45 deg apart
Change the BELT_* constants below to refit it.
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
PARTS = HERE / "parts"
PREVIEW = HERE / "preview"

# ---------------------------------------------------------------------------
#  Belt parameters (metres).  These are the design's assumptions.
# ---------------------------------------------------------------------------
BELT_W = 0.320          # outside X
BELT_D = 0.220          # outside Y
BELT_R = 0.075          # outside corner radius
BELT_H = 0.130          # band height (pocket must clear the 123 mm case)
BELT_T = 0.003          # fabric thickness
BELT_CAVITY = 0.041     # gap between the two walls (37 mm case + clearance)
BAND_T = 2 * BELT_T + BELT_CAVITY   # overall wall-to-wall band thickness
HEM_R = 0.0018          # rolled hem cord radius

CASE_W = 0.174          # CE07929 base
CASE_D = 0.119
CASE_H = 0.037          # base + lid

PLATE_CX = 0.04756      # pi-stack plate centre, from pi-stack-v0.7.scad
PLATE_CY = 0.03310
PLATE_Z0 = -0.0045      # plate outer face (case frame)
PLATE_WAIST_R = 0.064
PLATE_ARM_ANG = math.atan(0.0662 / 0.09512)   # 34.85 deg

# The pi stack rides on the OUTWARD face of the inner ring, inside the pocket,
# and looks out through a window cut in the outer ring.  The plate's belt face
# sits on the inner ring's pocket-side face; the case then runs outward through
# the outer wall, so its bezel ends up standing proud of the belt by the depth
# it does not fit: PIP_CASE_DEPTH - (pocket + outer wall).
PIP_CASE_PROFILE = (0.09512, 0.06620)   # case body, x and y in the case frame
PIP_CASE_DEPTH = 0.0537                  # plate back face to bezel front face
INNER_FACE_Y = -(BELT_D / 2 - BELT_T - BELT_CAVITY)   # inner ring, pocket side
PIP_ROOT_Y = INNER_FACE_Y - abs(PLATE_Z0)
WINDOW_CLEAR = 0.0015                   # fabric clearance round the case

# ---------------------------------------------------------------------------
#  Small helpers
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def link(obj, coll):
    coll.objects.link(obj)
    return obj


def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def set_input(node, name, value):
    sock = node.inputs.get(name)
    if sock is not None:
        sock.default_value = value


def principled(name, base, rough=0.5, metallic=0.0, emission=None,
               emission_strength=0.0, sheen=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    set_input(bsdf, "Base Color", (*base, 1.0))
    set_input(bsdf, "Roughness", rough)
    set_input(bsdf, "Metallic", metallic)
    set_input(bsdf, "Sheen Weight", sheen)
    set_input(bsdf, "Alpha", alpha)
    if emission is not None:
        set_input(bsdf, "Emission Color", (*emission, 1.0))
        set_input(bsdf, "Emission Strength", emission_strength)
    return mat


def fabric_material(name, base=(0.20, 0.014, 0.028), rough=0.92, variation=0.22):
    """Cloth: low-frequency colour variation plus a fine woven bump."""
    mat = principled(name, base, rough=rough, sheen=0.45)
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])

    blotch = nt.nodes.new("ShaderNodeTexNoise")
    blotch.inputs["Scale"].default_value = 120.0
    blotch.inputs["Detail"].default_value = 5.0
    blotch.inputs["Roughness"].default_value = 0.60
    nt.links.new(mapping.outputs["Vector"], blotch.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (base[0] * (1 - variation),
                                         base[1] * (1 - variation),
                                         base[2] * (1 - variation), 1)
    ramp.color_ramp.elements[1].position = 0.80
    ramp.color_ramp.elements[1].color = (min(1, base[0] * (1 + variation)),
                                         min(1, base[1] * (1 + variation)),
                                         min(1, base[2] * (1 + variation)), 1)
    nt.links.new(blotch.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    weave = nt.nodes.new("ShaderNodeTexNoise")
    weave.inputs["Scale"].default_value = 2400.0
    weave.inputs["Detail"].default_value = 3.0
    weave.inputs["Roughness"].default_value = 0.5
    nt.links.new(mapping.outputs["Vector"], weave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.00018
    nt.links.new(weave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def print_material(name, base, rough=0.62):
    """Smooth matte print: flat colour, soft specular, no layer lines."""
    mat = principled(name, base, rough=rough, sheen=0.0)
    set_input(mat.node_tree.nodes.get("Principled BSDF"),
              "Specular IOR Level", 0.3)
    return mat


def import_stl(path, name, mat, coll, origin="bounds"):
    bpy.ops.wm.stl_import(filepath=str(path), global_scale=0.001)
    obj = bpy.context.selected_objects[0]
    obj.name = name
    obj.data.name = name
    # STL import sets object scale, not mesh scale; bake it to metres so
    # shared meshes and glTF export behave predictably.
    select_only(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # one material per imported part
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    if origin == "bounds":
        select_only(obj)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    if coll is not None:
        # stl_import links into the scene collection; move it
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)
    return obj


def parent_only(child, parent):
    """Keep the child's local transform; let the parent supply its frame."""
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)


def parent_keep(child, parent):
    """Parent the child but keep the world transform it already has.

    Used for cabling, which is laid out in world coordinates but should still
    follow the case it plugs into.
    """
    world = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = world
    bpy.context.view_layer.update()


# ---------------------------------------------------------------------------
#  Belt geometry
# ---------------------------------------------------------------------------

def rounded_rect_points(w, d, r, n_arc=16, n_straight=24):
    """Closed CCW path on a rounded rectangle centred on the origin.

    Returns points in the XY plane, starting on the +X straight edge and
    turning anticlockwise (looking down +Z).
    """
    hw, hd = w / 2.0, d / 2.0
    cx, cy = hw - r, hd - r
    pts = []

    def straight(a, b, n):
        for i in range(n):
            t = i / n
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))

    def arc(c, start, end, n):
        for i in range(n):
            t = i / n
            ang = start + (end - start) * t
            pts.append((c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)))

    # +X side, bottom to top
    straight((hw, -cy), (hw, cy), n_straight)
    arc((cx, cy), 0.0, math.pi / 2, n_arc)
    # +Y side, left to right
    straight((cx, hd), (-cx, hd), n_straight)
    arc((-cx, cy), math.pi / 2, math.pi, n_arc)
    # -X side, top to bottom
    straight((-hw, cy), (-hw, -cy), n_straight)
    arc((-cx, -cy), math.pi, 3 * math.pi / 2, n_arc)
    # -Y side, right to left
    straight((-cx, -hd), (cx, -hd), n_straight)
    arc((cx, -cy), 3 * math.pi / 2, 2 * math.pi, n_arc)
    return pts


def make_band(name, w, d, r, h, t, cavity, mat, coll, windows=()):
    """The belt as a folded pocket: a U section swept round the loop.

    Outer wall, inner wall and the fold that joins them at the bottom.  The
    top is open all the way round, and the gap between the walls is the
    pocket that carries the pi stack and the protoboard case.

    ``windows`` are rectangular cut-outs in the outer wall only, given as
    (centre_x, centre_z, half_x, half_z).  The pi stack looks out through one.
    """
    total = 2 * t + cavity
    outer = rounded_rect_points(w, d, r)
    outer_in = rounded_rect_points(w - 2 * t, d - 2 * t, r - t)
    inner_out = rounded_rect_points(w - 2 * t - 2 * cavity, d - 2 * t - 2 * cavity,
                                    r - t - cavity)
    inner = rounded_rect_points(w - 2 * total, d - 2 * total, r - total)
    n = len(outer)
    z0, zc, z1 = -h / 2.0, -h / 2.0 + t, h / 2.0

    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    ob = [bm.verts.new((x, y, z0)) for x, y in outer]
    ot = [bm.verts.new((x, y, z1)) for x, y in outer]
    oic = [bm.verts.new((x, y, zc)) for x, y in outer_in]
    oit = [bm.verts.new((x, y, z1)) for x, y in outer_in]
    iwc = [bm.verts.new((x, y, zc)) for x, y in inner_out]
    iwt = [bm.verts.new((x, y, z1)) for x, y in inner_out]
    iib = [bm.verts.new((x, y, z0)) for x, y in inner]
    iit = [bm.verts.new((x, y, z1)) for x, y in inner]

    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ob[i], ob[j], ot[j], ot[i]))       # outside
        bm.faces.new((oit[i], oit[j], ot[j], ot[i]))     # outer wall rim
        bm.faces.new((oic[i], oic[j], oit[j], oit[i]))   # outer wall, pocket side
        bm.faces.new((oic[i], oic[j], iwc[j], iwc[i]))   # fold / pocket floor
        bm.faces.new((iwc[i], iwc[j], iwt[j], iwt[i]))   # inner wall, pocket side
        bm.faces.new((iwt[i], iwt[j], iit[j], iit[i]))   # inner wall rim
        bm.faces.new((iib[j], iib[i], iit[i], iit[j]))   # inside (electrode face)
        bm.faces.new((iib[i], iib[j], ob[j], ob[i]))     # bottom fold

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(mat)
    coll.objects.link(obj)
    bevel = obj.modifiers.new("soft_edges", "BEVEL")
    bevel.width = 0.0012
    bevel.segments = 2
    select_only(obj)
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    if windows:
        cut_windows(obj, windows, coll, -d / 2.0, -d / 2.0 + t)
    # Split the hard edges physically.  Smooth-by-angle leaves the window's
    # reveal sharing vertices with the front face, and the averaged normals
    # shade the whole front column visibly lighter.
    split = obj.modifiers.new("hard_edges", "EDGE_SPLIT")
    split.split_angle = math.radians(38)
    split.use_edge_angle = True
    split.use_edge_sharp = False
    select_only(obj)
    bpy.ops.object.modifier_apply(modifier=split.name)
    bpy.ops.object.shade_smooth()
    return obj


def cut_windows(obj, windows, coll, y_lo, y_hi):
    """Boolean a rectangular window through one wall of the band.

    ``y_lo``/``y_hi`` are the wall's two faces; the cutter overshoots both by
    a millimetre so the difference is clean.
    """
    for k, (cx, cz, hx, hz) in enumerate(windows):
        me = bpy.data.meshes.new(f"_window_cutter_{k}")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x = v.co.x * (2 * hx) + cx
            v.co.y = v.co.y * (y_hi - y_lo + 0.002) + (y_lo + y_hi) / 2.0
            v.co.z = v.co.z * (2 * hz) + cz
        bm.to_mesh(me)
        bm.free()
        cutter = bpy.data.objects.new(f"_window_cutter_{k}", me)
        coll.objects.link(cutter)
        mod = obj.modifiers.new(f"window_{k}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cutter
        select_only(obj)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    # The difference splits vertices along the cut planes even where the
    # surfaces stay coplanar, which shows up as a shading seam on the smooth
    # band.  Weld the coincident pairs back together.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # ... and it leaves the cut edges flagged sharp even where the faces end up
    # coplanar.  Clear the flags; shade_smooth_by_angle re-marks the real ones.
    for e in bm.edges:
        e.smooth = True
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def cut_slots(obj, slots, coll):
    """Punch openings through a ribbon lying on the belt's outer wall.

    ``slots`` is a list of ``(angle, z_centre, z_half, width, gap_lo, gap_hi)``:
    the opening is centred on the outer wall at ``angle``, ``width`` wide along
    the belt and ``2 * z_half`` tall, and spans ``gap_lo``..``gap_hi`` out from
    the fabric so it cuts the ribbon and nothing else.
    """
    for k, (a, zc, zh, wid, g_lo, g_hi) in enumerate(slots):
        p, n = ray_rounded_rect(BELT_W, BELT_D, BELT_R, a)
        n3 = Vector((n.x, n.y, 0.0)).normalized()
        c = Vector((p.x, p.y, zc)) + n3 * (0.5 * (g_lo + g_hi))
        rot = Matrix.Rotation(math.atan2(n3.y, n3.x) + math.pi / 2.0, 4, "Z")
        me = bpy.data.meshes.new(f"_slot_cutter_{k}")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= wid
            v.co.y *= g_hi - g_lo + 0.002
            v.co.z *= 2.0 * zh
            v.co = rot @ v.co + c
        bm.to_mesh(me)
        bm.free()
        cutter = bpy.data.objects.new(f"_slot_cutter_{k}", me)
        coll.objects.link(cutter)
        mod = obj.modifiers.new(f"slot_{k}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cutter
        select_only(obj)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)


def make_curve(name, points, radius, mat, coll, cyclic=True, spline="POLY"):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = 16
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.fill_mode = "FULL"
    if spline == "BEZIER":
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(points) - 1)
        for bp, v in zip(sp.bezier_points, points):
            bp.co = v
            bp.handle_left_type = "AUTO"
            bp.handle_right_type = "AUTO"
    else:
        sp = cu.splines.new("POLY")
        sp.points.add(len(points) - 1)
        for p, v in zip(sp.points, points):
            p.co = (*v, 1.0)
    sp.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, cu)
    obj.data.materials.append(mat)
    coll.objects.link(obj)
    return obj


def make_box(name, centre, size, mat, coll, bevel=0.0007):
    """Small rounded box for plugs, breakouts and connectors."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] + centre[0],
                       v.co.y * size[1] + centre[1],
                       v.co.z * size[2] + centre[2]))
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(mat)
    coll.objects.link(obj)
    if bevel:
        mod = obj.modifiers.new("soft_edges", "BEVEL")
        mod.width = min(bevel, min(size) * 0.35)
        mod.segments = 2
        select_only(obj)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(38))
    return obj


def make_wall_ribbon(name, angles, z_centre, half_h, gap, thickness, mat, coll,
                     bevel=0.0004, surface=None, normal_sign=1):
    """A flat strap lying on the belt's outer wall and following its curve.

    ``gap`` is the clearance between the fabric and the strap's underside.
    Pass a callable of the angle to ramp the strap over an overlapping end.
    ``surface`` swaps the belt face the strap follows and ``normal_sign``
    flips which way it grows, so the same helper makes an inner-face ply.
    """
    sw, sd, sr = surface if surface else (BELT_W, BELT_D, BELT_R)
    bm = bmesh.new()
    inner, outer = [], []
    for a in angles:
        p, n = ray_rounded_rect(sw, sd, sr, a)
        n3 = Vector((n.x, n.y, 0.0)).normalized() * normal_sign
        g = gap(a) if callable(gap) else gap
        h = half_h(a) if callable(half_h) else half_h
        th = thickness(a) if callable(thickness) else thickness
        pin = Vector((p.x, p.y, 0.0)) + n3 * g
        pout = pin + n3 * th
        z0, z1 = z_centre - h, z_centre + h
        inner.append((bm.verts.new((pin.x, pin.y, z0)),
                      bm.verts.new((pin.x, pin.y, z1))))
        outer.append((bm.verts.new((pout.x, pout.y, z0)),
                      bm.verts.new((pout.x, pout.y, z1))))
    for i in range(len(angles) - 1):
        i0, i1 = inner[i], inner[i + 1]
        o0, o1 = outer[i], outer[i + 1]
        bm.faces.new((i0[0], i1[0], i1[1], i0[1]))   # underside
        bm.faces.new((o0[0], o0[1], o1[1], o1[0]))   # face
        bm.faces.new((i0[0], i1[0], o1[0], o0[0]))   # bottom edge
        bm.faces.new((i0[1], o0[1], o1[1], i1[1]))   # top edge
    bm.faces.new((inner[0][0], inner[0][1], outer[0][1], outer[0][0]))
    bm.faces.new((inner[-1][0], outer[-1][0], outer[-1][1], inner[-1][1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(mat)
    coll.objects.link(obj)
    select_only(obj)
    if bevel:
        mod = obj.modifiers.new("soft_edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(38))
    return obj


def make_rounded_rect_ring(name, centre, e1, e2, half_a, half_b, corner, radius,
                           mat, coll):
    """Closed rounded-rectangle loop in the plane (e1, e2)."""
    pts = rounded_rect_points(2 * half_a, 2 * half_b, corner, n_arc=10, n_straight=8)
    out = []
    for x, y in pts:
        v = Vector(centre) + e1 * x + e2 * y
        out.append(tuple(v))
    return make_curve(name, out, radius, mat, coll, cyclic=True)


def ray_rounded_rect(w, d, r, theta):
    """Surface point and outward normal where a centre ray meets the boundary."""
    direction = Vector((math.cos(theta), math.sin(theta)))
    lo, hi = 0.0, max(w, d)

    def inside(x, y):
        qx = abs(x) - (w / 2.0 - r)
        qy = abs(y) - (d / 2.0 - r)
        if qx <= 0 and qy <= 0:
            return True
        if qx > 0 and qy > 0:
            return qx * qx + qy * qy <= r * r
        # One coordinate is in a straight run: only the other one is limited.
        if qx > 0:
            return qx <= r
        return qy <= r

    for _ in range(70):
        mid = 0.5 * (lo + hi)
        if inside(direction.x * mid, direction.y * mid):
            lo = mid
        else:
            hi = mid
    p = direction * lo
    qx = abs(p.x) - (w / 2.0 - r)
    qy = abs(p.y) - (d / 2.0 - r)
    if qx > 0 and qy > 0:
        n = Vector((math.copysign(qx, p.x), math.copysign(qy, p.y))).normalized()
    elif qx > 0:
        n = Vector((math.copysign(1.0, p.x), 0.0))
    else:
        n = Vector((0.0, math.copysign(1.0, p.y)))
    return p, n


# ---------------------------------------------------------------------------
#  Materials
# ---------------------------------------------------------------------------

def build_materials():
    m = {}
    m["fabric"] = fabric_material("Belt_Stone_Grey_Nylon", (0.185, 0.183, 0.175),
                                  variation=0.06)
    m["seam"] = fabric_material("Belt_Seam_Grey", (0.090, 0.089, 0.085),
                                variation=0.05)
    m["elastic"] = principled("Elastic_Charcoal", (0.012, 0.012, 0.015),
                              rough=0.95, sheen=0.0)
    # Woven elastic is matte; the default 0.5 specular turns the thin cord
    # into a white highlight under the studio key.
    set_input(m["elastic"].node_tree.nodes.get("Principled BSDF"),
              "Specular IOR Level", 0.0)
    m["crimson"] = print_material("Print_Crimson_Matte", (0.200, 0.010, 0.026),
                                  rough=0.68)
    m["bezel"] = print_material("Print_Crimson_Bezel", (0.155, 0.008, 0.021),
                                rough=0.66)
    m["pcb_green"] = principled("PCB_Green", (0.010, 0.075, 0.035),
                                rough=0.38, metallic=0.08)
    m["pcb_dark"] = principled("PCB_Dark", (0.012, 0.014, 0.018), rough=0.42)
    m["gold"] = principled("Metal_Gold", (0.75, 0.48, 0.14),
                           rough=0.28, metallic=1.0)
    m["silver"] = principled("Metal_Silver", (0.62, 0.63, 0.66),
                             rough=0.26, metallic=1.0)
    m["lcd"] = principled("LCD_Slate", (0.018, 0.020, 0.024), rough=0.30)
    m["screen"] = principled("LCD_Glass", (0.002, 0.006, 0.008),
                             rough=0.06, metallic=0.35,
                             emission=(0.01, 0.16, 0.19), emission_strength=1.6)
    m["switch"] = principled("Switch_Dark", (0.020, 0.021, 0.024), rough=0.55)
    m["cable"] = principled("Cable_Black", (0.007, 0.0075, 0.009), rough=0.52)
    m["wire"] = principled("Wire_Dark_Grey", (0.014, 0.0145, 0.016), rough=0.60)
    m["velcro"] = principled("Velcro_Hook_Dark", (0.045, 0.045, 0.050),
                             rough=0.98)
    m["velcro_pad"] = fabric_material("Velcro_Loop_Grey", (0.112, 0.111, 0.107),
                                      variation=0.15)
    m["led"] = principled("LED_Red", (0.35, 0.01, 0.01), rough=0.25,
                          emission=(1.0, 0.05, 0.03), emission_strength=2.2)
    m["floor"] = principled("Studio_Floor", (0.018, 0.019, 0.022), rough=0.62)
    return m


# ---------------------------------------------------------------------------
#  Build
# ---------------------------------------------------------------------------

def main():
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"

    m = build_materials()

    coll_belt = make_collection("Belt")
    coll_elec = make_collection("Electrodes")
    coll_pi = make_collection("Pi Case")
    coll_proto = make_collection("Protoboard Case")
    coll_cable = make_collection("Cables")
    coll_studio = make_collection("Studio")

    # ---- roots ---------------------------------------------------------
    belt_root = bpy.data.objects.new("BELT_ROOT", None)
    belt_root.empty_display_type = "PLAIN_AXES"
    belt_root.empty_display_size = 0.03
    coll_belt.objects.link(belt_root)
    belt_root["note"] = ("Fabric belt root. 320 x 220 mm loop, 130 mm tall, "
                         "U-section pocket all the way round.")

    pi_root = bpy.data.objects.new("PI_CASE_ROOT", None)
    pi_root.empty_display_type = "ARROWS"
    pi_root.empty_display_size = 0.03
    pi_root.location = (-PLATE_CX, PIP_ROOT_Y, -PLATE_CY)
    pi_root.rotation_mode = "XYZ"
    pi_root.rotation_euler = (math.radians(90), 0.0, 0.0)
    coll_pi.objects.link(pi_root)
    pi_root["note"] = ("Pi-stack case root: strapped to the outward face of the "
                       "inner ring, inside the pocket; case +Z faces -Y and looks "
                       "out through the window in the outer ring.")

    proto_root = bpy.data.objects.new("PROTO_CASE_ROOT", None)
    proto_root.empty_display_type = "ARROWS"
    proto_root.empty_display_size = 0.03
    proto_root.location = (0.0, +0.069, 0.0015)
    proto_root.rotation_mode = "QUATERNION"
    proto_root.rotation_quaternion = Matrix(
        ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
    ).to_quaternion()
    coll_proto.objects.link(proto_root)
    proto_root["note"] = ("CE07929 case root: housed in the pocket at the BACK, "
                          "opposite the pi stack; base at y = +69 mm, its front "
                          "face clear of the harness loom.  Lid outboard.")

    # ---- belt: one folded pocket all the way round --------------------
    # The window in the outer ring is the pi stack's: the case passes through
    # it and its bezel stands proud, so the fabric frames the screen.
    window = (0.0, 0.0,
              PIP_CASE_PROFILE[0] / 2.0 + WINDOW_CLEAR,
              PIP_CASE_PROFILE[1] / 2.0 + WINDOW_CLEAR)
    belt = make_band("Belt_Fabric", BELT_W, BELT_D, BELT_R, BELT_H, BELT_T,
                     BELT_CAVITY, m["fabric"], coll_belt, windows=(window,))
    belt["note"] = ("U-section band: outer wall, inner wall and bottom fold. "
                    "The top opening is the pocket, all the way round; the "
                    "outer wall carries the pi-stack window at the front.")
    parent_only(belt, belt_root)

    # rolled hems on both top edges - outer wall and the pocket's inner wall
    hem_rings = (
        ("Belt_Hem_Top_Outer",
         rounded_rect_points(BELT_W - 2.4e-3, BELT_D - 2.4e-3, BELT_R - 1.2e-3)),
        ("Belt_Hem_Top_Inner",
         rounded_rect_points(BELT_W - 2 * BAND_T - 2.4e-3,
                             BELT_D - 2 * BAND_T - 2.4e-3,
                             BELT_R - BAND_T - 1.2e-3)),
    )
    for nm, ring in hem_rings:
        hem = make_curve(nm, [(x, y, BELT_H / 2) for x, y in ring], HEM_R,
                         m["fabric"], coll_belt)
        parent_only(hem, belt_root)

    # ---- velcro closure -----------------------------------------------
    # The belt closes like a belt: the free end of the strap lies back over
    # the outer face and is held there by hook-and-loop alone.  There is no
    # sleeve and no strap - the hook side is sewn to the underside of the end
    # and the loop side to the belt's outer face beneath it, so the end just
    # presses flat onto the belt.  It sits on the left side, clear of the
    # pi-stack (front-left) and the USB lead.
    def ang_range(a0, a1, n):
        return [a0 + (a1 - a0) * k / (n - 1) for k in range(n)]

    def wall_frame(theta):
        p2, n2 = ray_rounded_rect(BELT_W, BELT_D, BELT_R, theta)
        return Vector((p2.x, p2.y, 0.0)), Vector((n2.x, n2.y, 0.0))

    FLAP_FRONT = math.radians(206.0)    # free end of the overlapping strap
    FLAP_BACK = math.radians(148.0)     # where it merges into the belt
    PAD_FRONT = math.radians(213.0)     # loop pad runs on past the free end
    PAD_BACK = math.radians(150.5)
    PAD_T = 0.0012                      # hook side + loop side together

    def flap_thickness(a):
        """Thin out at the back so the strap blends into the belt."""
        d = math.degrees(a)
        if d >= 152.0:
            return 0.0024
        t = max(0.0, (d - 148.0) / 4.0)
        return 0.0002 + (0.0024 - 0.0002) * t

    def flap_gap(a):
        """Lie on the loop pad, settling into the fabric at the back."""
        d = math.degrees(a)
        if d >= 152.0:
            return PAD_T + 0.0002
        t = max(0.0, (d - 148.0) / 4.0)
        return 0.0002 + (PAD_T + 0.0002 - 0.0002) * t

    # The free end is one thickness of cloth lying on the belt's outer face.
    flap = make_wall_ribbon("Belt_End", ang_range(FLAP_FRONT, FLAP_BACK, 63),
                            0.0, 0.062, flap_gap, flap_thickness, m["fabric"],
                            coll_belt)
    parent_only(flap, belt_root)

    # One bound edge, down the free end only: it stops at the flap's own
    # thickness and never turns over the top or down the inside.
    hp, hn = wall_frame(FLAP_FRONT)
    edge = hp + hn * (flap_gap(FLAP_FRONT) + flap_thickness(FLAP_FRONT) * 0.5)
    hem = make_curve(
        "Belt_End_Hem",
        [tuple(edge + Vector((0, 0, -0.0620))),
         tuple(edge + Vector((0, 0, 0.0620)))],
        HEM_R, m["fabric"], coll_belt, cyclic=False)
    parent_only(hem, belt_root)

    # Hook side on the end's underside, loop side on the belt: the two pads
    # meet face to face.  The hook pad stops with the flap so the grey loop
    # pad is what shows past the free edge.
    loop_pad = make_wall_ribbon(
        "Belt_End_Velcro_Loop", ang_range(PAD_FRONT, PAD_BACK, 50),
        0.0, 0.050, 0.0002, PAD_T * 0.5, m["velcro_pad"], coll_belt)
    parent_only(loop_pad, belt_root)
    hook_pad = make_wall_ribbon(
        "Belt_End_Velcro_Hook", ang_range(FLAP_FRONT, FLAP_BACK, 63),
        0.0, 0.050, 0.0002 + PAD_T * 0.5, PAD_T * 0.5, m["velcro"],
        coll_belt)
    parent_only(hook_pad, belt_root)

    # ---- eight electrode snaps on the inner wall ----------------------
    bpy.ops.wm.stl_import(filepath=str(HERE.parent / "derived" / "ECG_Snap_Button_4mm.stl"),
                          global_scale=0.001)
    snap = bpy.context.selected_objects[0]
    snap.name = "ECG_Snap_Master"
    snap.data.name = "ECG_Snap_4mm"
    snap.data.materials.clear()
    snap.data.materials.append(m["silver"])
    select_only(snap)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    snap_mesh = snap.data
    bpy.data.objects.remove(snap, do_unlink=True)

    inner_w, inner_d = BELT_W - 2 * BAND_T, BELT_D - 2 * BAND_T
    inner_r = BELT_R - BAND_T
    # The snap STL is built along local +Y: a 12 mm flange at y = 1.8 mm and a
    # 4 mm stud reaching y = 3.5 mm.  Local +Y therefore faces the body, and
    # the flange sits on the inner wall with the boss buried in the fabric.
    SNAP_FLANGE_Y = 0.0018
    for i in range(8):
        theta = math.radians(360.0 * i / 8.0)
        p2, n2 = ray_rounded_rect(inner_w, inner_d, inner_r, theta)
        p = Vector((p2.x, p2.y, 0.0))
        n_out = Vector((n2.x, n2.y, 0.0))
        inward = -n_out
        e = bpy.data.objects.new(f"Electrode_{i + 1}_Snap", snap_mesh)
        e.location = p + n_out * SNAP_FLANGE_Y
        e.rotation_mode = "QUATERNION"
        e.rotation_quaternion = Vector((0, 1, 0)).rotation_difference(inward)
        e["role"] = "4 mm ECG snap, flange on the inner wall, stud inward"
        coll_elec.objects.link(e)
        parent_only(e, belt_root)

        ring = make_rounded_rect_ring(
            f"Electrode_{i + 1}_Patch",
            p + inward * 0.0010,
            Vector((-inward.y, inward.x, 0.0)), Vector((0, 0, 1)),
            0.0085, 0.0085, 0.0085, 0.0010, m["seam"], coll_elec)
        parent_only(ring, belt_root)

    # ---- pi-stack case ------------------------------------------------
    pi_parts = [
        ("pi-plate.stl", "PiCase_StrapPlate", m["crimson"]),
        ("pi-base.stl", "PiCase_Base", m["crimson"]),
        ("pi-mid.stl", "PiCase_Mid", m["crimson"]),
        ("pi-bezel.stl", "PiCase_Bezel", m["bezel"]),
        ("pi-pi.stl", "RaspberryPi3", m["pcb_green"]),
        ("pi-wittypi.stl", "WittyPi4", m["pcb_dark"]),
        ("pi-lcd.stl", "LCD_3v5in", m["lcd"]),
        ("pi-header.stl", "CE09547_Header", m["gold"]),
        ("pi-leds.stl", "Panel_LEDs", m["led"]),
        ("pi-switches.stl", "Panel_Switches", m["switch"]),
    ]
    for fn, name, mat in pi_parts:
        obj = import_stl(PARTS / fn, name, mat, coll_pi)
        if name == "LCD_3v5in":
            # The top face (the measured 7.00 mm panel stack) gets glass.
            # origin_set has already centred the mesh, so find the top.
            obj.data.materials.append(m["screen"])
            top_z = max(v.co.z for v in obj.data.vertices)
            for poly in obj.data.polygons:
                if poly.normal.z > 0.9 and poly.center.z > top_z - 0.0008:
                    poly.material_index = 1
        parent_only(obj, pi_root)

    # four elastic loops, one per strap-plate waist.  The plate is inside the
    # pocket now, so the loops ring the arms there, straddling the plate's
    # fabric face.
    for k, (sx, sz) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        ang = PLATE_ARM_ANG
        u = Vector((sx * math.cos(ang), 0.0, sz * math.sin(ang)))
        e1 = Vector((-sx * math.sin(ang), 0.0, sz * math.cos(ang)))
        e2 = Vector((0.0, 1.0, 0.0))
        centre = Vector((sx * PLATE_WAIST_R * math.cos(ang),
                          INNER_FACE_Y - 0.0032,
                          sz * PLATE_WAIST_R * math.sin(ang)))
        loop = make_rounded_rect_ring(
            f"Elastic_Loop_{k + 1}", centre, e1, e2,
            0.0078, 0.0035, 0.0025, 0.0020, m["elastic"], coll_belt)
        parent_only(loop, belt_root)

    # ---- CE07929 protoboard case --------------------------------------
    proto_parts = [
        ("ce-base.stl", "ProtoCase_Base", m["crimson"]),
        ("ce-lid.stl", "ProtoCase_Lid", m["crimson"]),
        ("ce-board-.stl", "Protoboard_A", m["pcb_green"]),
        ("ce-board+.stl", "Protoboard_B", m["pcb_green"]),
    ]
    for fn, name, mat in proto_parts:
        obj = import_stl(PARTS / fn, name, mat, coll_proto)
        parent_only(obj, proto_root)

    # the vendor ESP32, at the case's own stand-in's origin
    esp = import_stl(HERE.parent / "derived" / "esp32_dev_kit_v1_asm.stl",
                     "ESP32_DevKit_V1", m["pcb_dark"], coll_proto, origin=None)
    # vendor mesh: X centred, Y 0..51.5, Z -10.54..4.47 (PCB top at 0).
    # case frame: origin at board-top centre with the 10 mm pin strips below.
    # vendor origin (0,0,0) is the PCB-top centre; pins reach to -10.54 mm.
    # case frame: ESP_X, ESP_Y - ESP_L/2, BOARD_TOP + 10.54
    esp.location = (-0.060, 0.00075, 0.01654)
    parent_only(esp, proto_root)

    # ---- cabling ------------------------------------------------------
    # Cable geometry is laid out in world coordinates and parented with
    # parent_keep, so it stays where it was built but still follows its case.

    # USB: the Pi's +X wall carries the Ethernet and dual-USB deck.  The plug
    # sits in the upper USB socket, inside the pocket; the lead then runs round
    # the right side of the loop inside the pocket, in through the open +X end
    # of the CE07929 case at the back, and up into the ESP32's micro-USB.
    USB_PI_PLUG = (0.0536, -0.0868, 0.0200)     # in the upper USB socket
    usb_plug_pi = make_box("USB_Plug_Pi", USB_PI_PLUG,
                           (0.0120, 0.0050, 0.0125), m["cable"], coll_cable)
    parent_keep(usb_plug_pi, pi_root)
    usb_shell_pi = make_box("USB_Shell_Pi",
                            (0.0479, USB_PI_PLUG[1], USB_PI_PLUG[2]),
                            (0.0012, 0.0055, 0.0130), m["silver"], coll_cable,
                            bevel=0.0003)
    parent_keep(usb_shell_pi, pi_root)

    usb = make_curve(
        "Cable_USB_Pi_To_Protoboard",
        [(0.0598, -0.0868, 0.0200),
         (0.0750, -0.0870, 0.0210),
         (0.0950, -0.0870, 0.0225),
         (0.1150, -0.0860, 0.0238),
         (0.1300, -0.0800, 0.0245),
         (0.1390, -0.0680, 0.0250),
         (0.1420, -0.0450, 0.0252),
         (0.1420, 0.0000, 0.0252),
         (0.1420, 0.0450, 0.0250),
         (0.1380, 0.0650, 0.0245),
         (0.1300, 0.0780, 0.0235),
         (0.1150, 0.0845, 0.0215),
         (0.1000, 0.0862, 0.0175),
         (0.0880, 0.0865, 0.0120),   # in through the open +X end of the case
         (0.0750, 0.0865, 0.0055),
         (0.0640, 0.0865, 0.0012),
         (0.0600, 0.0865, 0.0000)],
        0.0018, m["cable"], coll_cable, cyclic=False, spline="BEZIER")
    parent_keep(usb, pi_root)

    # right-angle micro-USB into the ESP32's underside
    usb_plug_proto = make_box("USB_Plug_Protoboard", (0.0600, 0.0865, 0.0000),
                              (0.0080, 0.0026, 0.0080), m["cable"], coll_cable)
    parent_keep(usb_plug_proto, proto_root)
    usb_shell_proto = make_box("USB_Shell_Protoboard",
                               (0.0600, 0.0865, 0.0030),
                               (0.0075, 0.0022, 0.0020), m["silver"], coll_cable,
                               bevel=0.0003)
    parent_keep(usb_shell_proto, proto_root)

    # Electrode harness: the wearer sits against the inner face, so no cable may
    # run there.  The whole harness lives in the pocket instead: a thin loom
    # follows the pocket-side face of the inner ring all the way round and one
    # lead rises from it to the back of each snap.  The protoboard case sits at
    # the back, just clear of the loom.
    POCKET_GAP = 0.0010        # wire centre off the inner ring's pocket face
    LOOM_R = 0.0009
    LOOM_Z = 0.020
    HARNESS_ANCHOR = math.radians(35.0)    # beside the case's open end

    def wall_point(theta, z=0.0):
        p2, _ = ray_rounded_rect(inner_w + 2 * BELT_T, inner_d + 2 * BELT_T,
                                 inner_r + BELT_T, theta)
        return Vector((p2.x, p2.y, z))

    def pocket_point(theta, z=0.0, off=POCKET_GAP):
        p2, _ = ray_rounded_rect(inner_w + 2 * BELT_T + 2 * off,
                                 inner_d + 2 * BELT_T + 2 * off,
                                 inner_r + BELT_T + off, theta)
        return Vector((p2.x, p2.y, z))

    anchor = pocket_point(HARNESS_ANCHOR, LOOM_Z)
    breakout_c = pocket_point(HARNESS_ANCHOR, LOOM_Z, off=0.0025)
    trunk = make_curve(
        "Harness_Trunk",
        [(0.0860, 0.0860, 0.0260),   # out of the case's open +X end
         (0.0950, 0.0840, 0.0262),
         (0.1030, 0.0800, 0.0258),
         (0.1090, 0.0740, 0.0250),
         (0.1120, 0.0660, 0.0238),
         (0.1124, 0.0600, 0.0222),
         tuple(breakout_c)],
        0.0022, m["cable"], coll_cable, cyclic=False, spline="BEZIER")
    parent_keep(trunk, belt_root)
    # clamp where the trunk leaves the case's open end
    relief = make_box("Harness_Strain_Relief", (0.0930, 0.0845, 0.0258),
                      (0.011, 0.020, 0.015), m["cable"], coll_cable)
    parent_keep(relief, belt_root)
    breakout = make_box("Harness_Breakout", tuple(breakout_c),
                        (0.007, 0.007, 0.006), m["cable"], coll_cable)
    parent_keep(breakout, belt_root)

    for nm, a0, a1 in (("A", HARNESS_ANCHOR, HARNESS_ANCHOR + math.pi),
                       ("B", HARNESS_ANCHOR, HARNESS_ANCHOR - math.pi)):
        pts = [tuple(breakout_c)] + [
            tuple(pocket_point(a0 + (a1 - a0) * k / 48.0, LOOM_Z))
            for k in range(1, 49)]
        loom = make_curve(f"Harness_Loom_{nm}", pts, LOOM_R, m["cable"],
                          coll_cable, cyclic=False, spline="POLY")
        parent_keep(loom, belt_root)

    # One drop per snap, from the back of the fabric up to the loom.  The
    # wire is half-buried at the wall so it reads as leaving the snap.
    for i in range(8):
        theta = math.radians(360.0 * i / 8.0)
        lead = make_curve(
            f"Electrode_Lead_{i + 1}",
            [tuple(wall_point(theta, 0.0)),
             tuple(pocket_point(theta, 0.0060, 0.0005)),
             tuple(pocket_point(theta, 0.0140, 0.0008)),
             tuple(pocket_point(theta, LOOM_Z))],
            0.0007, m["wire"], coll_cable, cyclic=False, spline="BEZIER")
        parent_keep(lead, belt_root)

    # ---- scene bookkeeping -------------------------------------------
    scene.render.engine = "BLENDER_EEVEE"
    try:
        scene.eevee.taa_render_samples = 64
    except Exception:
        pass
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    # Studio lights are driven hard; pull the exposure so the material base
    # colours stay physically plausible (stone grey cloth, crimson print).
    scene.view_settings.exposure = -2.3
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    build_studio(scene, coll_studio, m)
    add_notes()

    PREVIEW.mkdir(parents=True, exist_ok=True)
    render_views(scene)

    # save the .blend before exporting
    blend_path = HERE / "crimson-veil-assembly.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    # glTF: model only, no studio
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if obj.name.startswith("STUDIO_"):
            continue
        obj.select_set(True)
    glb_path = HERE / "crimson-veil-assembly.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
    )
    print(f"WROTE {blend_path}")
    print(f"WROTE {glb_path}")
    print("OBJECTS", len(bpy.data.objects))
    print("TRIS", sum(len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH"))


# ---------------------------------------------------------------------------
#  Studio
# ---------------------------------------------------------------------------

def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def add_area(name, loc, energy, size, colour, target=(0, 0, 0.02), coll=None):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = colour
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    coll.objects.link(obj)
    aim(obj, target)
    return obj


def build_studio(scene, coll, m):
    # floor
    bpy.ops.mesh.primitive_plane_add(size=4.0, location=(0, 0, -0.066))
    floor = bpy.context.selected_objects[0]
    floor.name = "STUDIO_Floor"
    floor.data.materials.append(m["floor"])
    for c in list(floor.users_collection):
        c.objects.unlink(floor)
    coll.objects.link(floor)

    add_area("STUDIO_Key", (0.55, -0.60, 0.55), 40, 0.55, (1.0, 0.94, 0.88), coll=coll)
    add_area("STUDIO_Fill", (-0.65, -0.35, 0.28), 13, 0.9, (0.78, 0.86, 1.0), coll=coll)
    add_area("STUDIO_Rim", (0.30, 0.60, 0.50), 32, 0.45, (1.0, 0.97, 0.94), coll=coll)
    add_area("STUDIO_BackFill", (-0.40, 0.55, 0.25), 11, 0.8, (1.0, 0.85, 0.75), coll=coll)
    # Inside the band, so the inner face and the electrode ring read in the
    # top-down view instead of falling into its own shadow.
    add_area("STUDIO_Interior", (0.0, 0.0, 0.030), 0.85, 0.10, (1.0, 0.95, 0.90),
             target=(0.0, 0.0, 0.0), coll=coll)

    world = bpy.data.worlds.new("Studio_World")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.012, 0.013, 0.017, 1.0)
    bg.inputs["Strength"].default_value = 0.35
    scene.world = world

    cam_data = bpy.data.cameras.new("STUDIO_Camera")
    cam_data.lens = 58
    cam_data.clip_start = 0.001
    cam_data.clip_end = 20.0
    cam = bpy.data.objects.new("STUDIO_Camera", cam_data)
    coll.objects.link(cam)
    scene.camera = cam


def render_views(scene):
    cam = bpy.data.objects["STUDIO_Camera"]
    views = [
        ("assembly-front.png", (0.58, -0.86, 0.115), (0.0, -0.015, 0.0), 58),
        ("assembly-back.png", (-0.54, 0.88, 0.115), (0.0, 0.015, 0.0), 58),
        ("assembly-pi-detail.png", (0.10, -0.48, 0.055), (0.0, -0.135, -0.005), 85),
        ("assembly-belt-opening.png", (0.0, -0.20, 0.30), (0.0, -0.085, 0.055), 35),
        ("assembly-inside.png", (0.32, -0.06, 0.36), (0.0, 0.005, -0.010), 38),
        ("assembly-lcd-detail.png", (0.085, -0.40, 0.045), (0.0, -0.150, -0.002), 105),
        ("assembly-mount-detail.png", (-0.05, -0.28, 0.035), (-0.052, -0.108, 0.036), 110),
        ("assembly-closure.png", (-0.62, 0.36, 0.20), (-0.145, 0.005, 0.0), 55),
    ]
    for name, loc, target, lens in views:
        cam.location = loc
        cam.data.lens = lens
        aim(cam, target)
        scene.render.filepath = str(PREVIEW / name)
        scene.render.use_stamp = True
        scene.render.use_stamp_note = True
        scene.render.stamp_note_text = name
        scene.render.use_stamp_date = False
        scene.render.use_stamp_time = False
        scene.render.use_stamp_render_time = False
        scene.render.use_stamp_frame = False
        scene.render.use_stamp_scene = False
        scene.render.use_stamp_camera = False
        scene.render.use_stamp_filename = False
        scene.render.use_stamp_memory = False
        scene.render.use_stamp_hostname = False
        scene.render.stamp_font_size = 20
        bpy.ops.render.render(write_still=True)
        print("RENDERED", name)


def add_notes():
    text = bpy.data.texts.new("ASSEMBLY_NOTES")
    text.write(
        "CRIMSON VEIL - WHOLE-DEVICE ASSEMBLY\n"
        "====================================\n\n"
        "Collections: BELT (belt shell, two top hems, overlapping end and its\n"
        "hook-and-loop pads), ELECTRODES (8 snaps), PI CASE (plate, base, mid,\n"
        "bezel, Pi, WittyPi, LCD, header, LEDs, switches), PROTOBOARD CASE\n"
        "(base, lid, two boards, ESP32), CABLES (USB lead, harness trunk and\n"
        "clamp, two pocket looms, eight electrode leads), STUDIO.\n\n"
        "Root empties:\n"
        "  PI_CASE_ROOT    - moves the whole pi-stack; case +Z faces -Y.\n"
        "  PROTO_CASE_ROOT - moves the protoboard case inside the belt pocket.\n"
        "  BELT_ROOT       - moves the belt and electrodes together.\n\n"
        "Assumptions made for the belt (not in the CAD):\n"
        "  * 320 x 220 mm outside loop, r75 corners, 130 mm tall, 3 mm fabric.\n"
        "  * the whole belt is one pocket: a U section swept round the loop,\n"
        "    outer wall, inner wall and bottom fold, open at the top.\n"
        "  * 41 mm between the walls; the protoboard case sits inside it,\n"
        "    vertically, behind the pi-stack (+Y).\n"
        "  * 8 ECG snaps on the inner wall at mid-height, 45 deg pitch; the\n"
        "    flange sits on the fabric with the 4 mm stud facing the body.\n"
        "  * pi-stack carried on the front by four elastic loops over the\n"
        "    strap plate's arm waists (plate lies on the fabric).\n"
        "  * the belt closes on the left with hook-and-loop only: the free\n"
        "    end overlaps the belt and presses flat onto a sewn loop pad.\n"
        "  * a USB lead runs from the pi-stack +X port, over the outer hem,\n"
        "    into the open end of the protoboard case.\n"
        "  * the electrode harness stays inside the U-pocket - nothing runs on\n"
        "    the body face.  A thin loom hugs the inner wall's pocket face\n"
        "    (through the 2 mm gap beside the case) with one lead per snap.\n\n"
        "Materials: stone-grey woven nylon belt, smooth matte crimson cases,\n"
        "silver ECG snaps, charcoal elastic, green/dark PCBs, teal LCD glass.\n\n"
        "Geometry sources: parts/ exported from pi-stack-v0.7.scad and\n"
        "ce07929-case.scad in their assembled frames; vendor meshes for the\n"
        "Pi 3, WittyPi, 3.5in LCD, ESP32 and ECG snap button.\n"
    )


if __name__ == "__main__":
    main()
