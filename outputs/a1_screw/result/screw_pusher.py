#!/usr/bin/env python3
"""
screw_pusher.py -- build123d model of the motorised screw-driven bed sweeper
for a Bambu Lab A1 (full size).

WHAT THIS IS
------------
A "screw with a front pusher": a square-thread lead screw runs front-to-back
along the bed (Y axis).  A wide pusher carriage -- its front spans the full
width of the A1 build plate (256 mm in X) -- threads onto the screw and is
swept across the *top* of the build plate (Z =  scores, i.e. 100 mm) to push
finished prints off the front edge (Y = -128 mm).

A small high-torque DC motor with a D-shaft sits on a holder bolted to the
printer base frame (top at Z = 70 mm), behind the plate and clear of the
moving bed.  A D-shaft coupler gear on the motor shaft meshes with a spur
gear printed integrally on the back of the lead screw.

PRINTABLE PARTS (each exported as its own STEP + STL)
-----------------------------------------------------
  * motor_holder          -- clamps the DC motor, bolts to base frame
  * d_shaft_coupler_gear  -- D-bore hub + 15T spur gear for the motor shaft
  * screw_gear            -- lead screw (square thread) + integral 30T gear
  * pusher_carriage       -- 256 mm wide pusher blade + internal-thread nut
  * front_support         -- bearing block for the front of the screw
  * rear_support          -- bearing block for the rear of the screw

INTERFACE (from a1_model.py)
----------------------------
  build plate : X in [-128,128], Y in [-128,128], top at Z=100, front Y=-128
  base frame  : top at Z=70 (carriage occupies Z 70..94, X/Y within +/-128)
  envelope    : 385 (X) x 410 (Y) x 430 (Z)

UNITS: millimetres.  Uses build123d.
"""
from __future__ import annotations

import json
import math
import os

from build123d import (
    Box,
    Compound,
    Cylinder,
    Helix,
    Plane,
    Polygon,
    Pos,
    Rectangle,
    Rot,
    Vector,
    export_step,
    export_stl,
    extrude,
    sweep,
)

# ===========================================================================
# 1. REFERENCE GEOMETRY (must match a1_model.py)
# ===========================================================================
BED_W = 256.0          # build plate width  (X)
BED_D = 256.0          # build plate depth  (Y)
BED_TOP_Z = 100.0      # top surface of the build plate
BASE_H = 70.0          # base frame top
FRAME_W = 385.0
FRAME_D = 410.0

# ===========================================================================
# 2. MOTOR  (small high-torque DC motor with a D-shaft)
# ===========================================================================
MOTOR_BODY_D = 28.0        # body diameter
MOTOR_BODY_L = 38.0        # body length
MOTOR_SHAFT_D = 5.0        # shaft diameter
MOTOR_SHAFT_L = 12.0       # shaft protrusion
MOTOR_FLAT_OFF = 2.15      # distance from shaft axis to the D flat
MOTOR_X = 45.0             # motor axis X (offset from screw -> gear mesh)
MOTOR_Y = 183.0            # centre of motor body (behind the bed)
MOTOR_BODY_Y0 = MOTOR_Y - MOTOR_BODY_L / 2.0   # 164
MOTOR_BODY_Y1 = MOTOR_Y + MOTOR_BODY_L / 2.0   # 202

# ===========================================================================
# 3. GEAR PAIR  (module 2, spur)
# ===========================================================================
MODULE = 2.0
SCREW_GEAR_N = 30          # pitch r = 30
MOTOR_GEAR_N = 15          # pitch r = 15
GEAR_TH = 12.0             # face width (both gears)
GEAR_Y = 158.0             # Y plane where the two gears mesh
CENTER_DIST = MODULE * (SCREW_GEAR_N + MOTOR_GEAR_N) / 2.0   # 45 = 30+15

# ===========================================================================
# 4. LEAD SCREW  (square thread along Y)
# ===========================================================================
SCREW_X = 0.0              # screw axis X (centre of machine)
SCREW_Z = 150.0            # screw axis height (clears 256 wide pusher below)
SCREW_MINOR_R = 6.0        # core radius
SCREW_MAJOR_R = 13.0       # thread crest radius
SCREW_PITCH = 16.0         # thread pitch
SCREW_THREAD_T = 6.0       # axial thread thickness (square thread)
SCREW_Y0 = -150.0          # threaded length start (front)
SCREW_Y1 = 150.0           # threaded length end (back)
SCREW_FRONT_Y = -165.0     # front shaft tip
SCREW_BACK_Y = 190.0     # rear shaft tip (clears rear support)
SCREW_CLEAR = 0.75         # radial/axial clearance for the printed nut

# ===========================================================================
# 5. PUSHER  (front as wide as the A1 build plate)
# ===========================================================================
PUSHER_WIDTH = BED_W       # 256 mm in X -- "front as wide as the build plate"
PUSHER_BOT_Z = BED_TOP_Z   # sweeping plane: bottom of blade at Z = 100
BLADE_H = 35.0             # blade height (stays below the screw thread)
BLADE_T = 8.0              # blade thickness (Y)
HUB_X = 44.0               # nut block width
HUB_Y = 28.0               # nut block depth
HUB_Z = 48.0               # nut block height
CARRIAGE_PARK = -108.0     # carriage centre Y in the assembly view (front edge)

# ===========================================================================
# 6. SUPPORTS
# ===========================================================================
SUPPORT_X = 13.0           # half width of an end support wall
SUPPORT_TOP_Z = SCREW_Z + SCREW_MINOR_R + 10.0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def spur_pts(module: float, teeth: int) -> list[tuple[float, float]]:
    """Return a closed 2D spur-gear outline (involute approximated)."""
    rp = module * teeth / 2.0
    ra = rp + module
    rf = rp - 1.25 * module
    pa = 2.0 * math.pi / teeth
    hp = pa / 4.0            # half tooth thickness angle at the pitch circle
    ht = hp * 0.60           # ... at the tip
    hr = hp * 1.35           # ... at the root
    pts: list[tuple[float, float]] = []
    for i in range(teeth):
        c = i * pa
        pts += [
            (rf * math.cos(c - hr), rf * math.sin(c - hr)),
            (rp * math.cos(c - hp), rp * math.sin(c - hp)),
            (ra * math.cos(c - ht), ra * math.sin(c - ht)),
            (ra * math.cos(c + ht), ra * math.sin(c + ht)),
            (rp * math.cos(c + hp), rp * math.sin(c + hp)),
            (rf * math.cos(c + hr), rf * math.sin(c + hr)),
        ]
        for k in range(1, 4):                       # root-circle arc points
            a = c + hr + (pa - 2.0 * hr) * k / 4.0
            pts.append((rf * math.cos(a), rf * math.sin(a)))
    return pts


def spur_gear(module: float, teeth: int, thickness: float,
              bore_r: float = 0.0, flat: float | None = None):
    """Spur gear centred on the origin, axis along Z."""
    g = extrude(Polygon(*spur_pts(module, teeth)), thickness)
    g = Pos(0, 0, -thickness / 2.0) * g
    if bore_r > 0:
        g -= Cylinder(bore_r, thickness + 4.0)
    if flat is not None:                            # D flat on the +X side
        g -= Pos(flat + 15.0, 0, 0) * Box(30.0, 4.0 * max(bore_r, 1.0),
                                          thickness + 6.0)
    return g


def helix_ribbon_y(y0: float, length: float, mid_r: float, radial_h: float,
                   axial_t: float, pitch: float, lefthand: bool = False):
    """A helical ribbon swept around the (global) Y axis at the screw axis.

    The helix always starts at angle 0 at global Y = y0, so a screw and the
    matching nut cutter generated with the same y0/pitch are in phase.
    """
    h = Helix(pitch=pitch, height=length, radius=mid_r, lefthand=lefthand)
    tangent = Vector(0.0, mid_r, pitch / (2.0 * math.pi)).normalized()
    plane = Plane(origin=(mid_r, 0, 0), x_dir=(1, 0, 0), z_dir=tangent)
    profile = plane * Rectangle(radial_h, axial_t)
    ribbon = sweep(profile, path=h, is_frenet=True)
    # local +Z -> global +Y, local origin -> (0, y0, SCREW_Z)
    return Pos(0, y0, SCREW_Z) * Rot(-90, 0, 0) * ribbon


def cyl_y(center_y: float, radius: float, length: float):
    """Cylinder whose axis is along global Y, centred at (SCREW_X, cy, SCREW_Z)."""
    return (Pos(SCREW_X, center_y, SCREW_Z) * Rot(-90, 0, 0)
            * Cylinder(radius, length))


def box_center(cx: float, cy: float, cz: float, sx: float, sy: float, sz: float):
    return Pos(cx, cy, cz) * Box(sx, sy, sz)


# ===========================================================================
# PART 1 -- LEAD SCREW + INTEGRAL SPUR GEAR  ("spinning screw gear")
# ===========================================================================
def build_screw_gear():
    core_len = SCREW_BACK_Y - SCREW_FRONT_Y
    core = cyl_y((SCREW_FRONT_Y + SCREW_BACK_Y) / 2.0,
                 SCREW_MINOR_R, core_len)                    # shaft / core
    rib = helix_ribbon_y(SCREW_Y0, SCREW_Y1 - SCREW_Y0,
                         (SCREW_MINOR_R + SCREW_MAJOR_R) / 2.0,
                         SCREW_MAJOR_R - SCREW_MINOR_R,
                         SCREW_THREAD_T, SCREW_PITCH)        # square thread
    gear = (Pos(SCREW_X, GEAR_Y, SCREW_Z) * Rot(-90, 0, 0)
            * spur_gear(MODULE, SCREW_GEAR_N, GEAR_TH))      # 30T gear
    screw = core + rib + gear
    screw.label = "screw_gear"
    return screw


# ===========================================================================
# PART 2 -- D-SHAFT COUPLER WITH SPUR GEAR
# ===========================================================================
def build_d_shaft_coupler_gear(local: bool = True):
    hub = Cylinder(MOTOR_SHAFT_D / 2.0 + 4.0, MOTOR_SHAFT_L + 4.0)   # r=6.5
    gear = spur_gear(MODULE, MOTOR_GEAR_N, GEAR_TH)                  # 15T
    part = hub + gear
    # D bore for the motor shaft
    part -= Cylinder(MOTOR_SHAFT_D / 2.0 + 0.1, MOTOR_SHAFT_L + 20.0)
    part -= Pos(MOTOR_FLAT_OFF + 15.0, 0, 0) * Box(30.0, 20.0, 60.0)
    # radial set-screw hole (M3) above the shaft
    part -= Pos(0, 0, 4.0) * Rot(0, 90, 0) * Cylinder(1.6, 40.0)
    part.label = "d_shaft_coupler_gear"
    if local:
        return part
    return Pos(MOTOR_X, GEAR_Y, SCREW_Z) * Rot(-90, 0, 0) * part


# ===========================================================================
# PART 3 -- PUSHER CARRIAGE (nut + full-plate-width blade)
# ===========================================================================
def build_pusher_carriage(center_y: float = CARRIAGE_PARK, local: bool = False):
    # hub / nut block, centred on the screw
    hub = box_center(SCREW_X, center_y, SCREW_Z, HUB_X, HUB_Y, HUB_Z)
    # blade: full plate width, bottom on the bed top surface, in front of hub
    blade = box_center(SCREW_X, center_y - HUB_Y / 2.0 - BLADE_T / 2.0 + 2.0,
                       PUSHER_BOT_Z + BLADE_H / 2.0,
                       PUSHER_WIDTH, BLADE_T, BLADE_H)
    part = hub + blade
    # internal square thread: subtract a screw-shaped cutter (with clearance)
    cutter = (cyl_y(center_y, SCREW_MINOR_R + SCREW_CLEAR, 340.0)
              + helix_ribbon_y(SCREW_Y0, SCREW_Y1 - SCREW_Y0,
                               (SCREW_MINOR_R + SCREW_CLEAR
                                + SCREW_MAJOR_R + SCREW_CLEAR) / 2.0,
                               (SCREW_MAJOR_R - SCREW_MINOR_R) + 2 * SCREW_CLEAR,
                               SCREW_THREAD_T + 2 * SCREW_CLEAR, SCREW_PITCH))
    part -= cutter
    part.label = "pusher_carriage"
    if local:
        part = Pos(0, -center_y, -SCREW_Z) * part
    return part


# ===========================================================================
# PART 4 -- MOTOR HOLDER (bolts to the base frame top, Z = 70)
# ===========================================================================
def build_motor_holder():
    # base plate sitting on the base frame (top Z = BASE_H)
    base = box_center(50.0, 177.0, BASE_H + 3.0, 52.0, 54.0, 6.0)
    # cradle block, horizontal through-bore (along Y) for the motor body
    block = box_center(50.0, 183.0, 122.0, 44.0, 34.0, 92.0)
    block -= Pos(MOTOR_X, 183.0, SCREW_Z) * Rot(-90, 0, 0) \
        * Cylinder(MOTOR_BODY_D / 2.0 + 0.4, 60.0)          # motor bore
    holder = base + block
    # vertical set-screw hole to lock the motor in the cradle
    holder -= Pos(MOTOR_X, 183.0, 163.0) * Cylinder(1.7, 30.0)
    # four frame mounting holes
    for dx in (-20.0, 20.0):
        for dy in (-24.0, 24.0):
            holder -= Pos(50.0 + dx, 177.0 + dy, BASE_H + 3.0) \
                * Cylinder(2.2, 20.0)
    holder.label = "motor_holder"
    return holder


# ===========================================================================
# PART 5 -- SCREW END SUPPORTS
# ===========================================================================
def _end_support(center_y: float, label: str):
    base = box_center(SCREW_X, center_y,
                      BASE_H + 3.0, 2 * SUPPORT_X + 12.0, 24.0, 6.0)
    wall = box_center(SCREW_X, center_y, (BASE_H + SUPPORT_TOP_Z) / 2.0,
                      2 * SUPPORT_X, 20.0, SUPPORT_TOP_Z - BASE_H)
    wall -= Pos(SCREW_X, center_y, SCREW_Z) * Rot(-90, 0, 0) \
        * Cylinder(SCREW_MINOR_R + 0.4, 40.0)                # bushing hole
    part = base + wall
    part.label = label
    return part


def build_front_support():
    return _end_support(-160.0, "front_support")


def build_rear_support():
    return _end_support(180.0, "rear_support")


# ===========================================================================
# ASSEMBLY
# ===========================================================================
def build_assembly():
    parts = [
        build_screw_gear(),
        build_d_shaft_coupler_gear(local=False),
        build_pusher_carriage(local=False),
        build_motor_holder(),
        build_front_support(),
        build_rear_support(),
        # motor body shown for reference (not a printed part)
        _motor_for_reference(),
    ]
    return Compound(children=parts, label="A1_screw_pusher_assembly")


def _motor_for_reference():
    m = (Pos(MOTOR_X, MOTOR_Y, SCREW_Z) * Rot(-90, 0, 0)
         * Cylinder(MOTOR_BODY_D / 2.0, MOTOR_BODY_L))
    s = (Pos(MOTOR_X, GEAR_Y, SCREW_Z) * Rot(-90, 0, 0)
         * Cylinder(MOTOR_SHAFT_D / 2.0, MOTOR_SHAFT_L))
    m = m + s
    m.label = "motor_reference"
    return m


# ===========================================================================
# MAIN
# ===========================================================================
PARTS = {
    "motor_holder": build_motor_holder,
    "d_shaft_coupler_gear": lambda: build_d_shaft_coupler_gear(local=True),
    "screw_gear": build_screw_gear,
    "pusher_carriage": lambda: build_pusher_carriage(local=True),
    "front_support": build_front_support,
    "rear_support": build_rear_support,
}

INTERFACE = {
    "units": "mm",
    "origin": "centre of printer footprint; +Z up, +Y toward the back",
    "build_plate": {
        "width_x": BED_W,
        "depth_y": BED_D,
        "top_surface_z": BED_TOP_Z,
        "front_edge_y": -BED_D / 2.0,
    },
    "base_frame_top_z": BASE_H,
    "motor": {
        "type": "small high-torque DC motor with D-shaft",
        "body_diameter": MOTOR_BODY_D,
        "body_length": MOTOR_BODY_L,
        "shaft_diameter": MOTOR_SHAFT_D,
        "shaft_length": MOTOR_SHAFT_L,
        "flat_offset_from_axis": MOTOR_FLAT_OFF,
        "axis_position": [MOTOR_X, MOTOR_Y, SCREW_Z],
    },
    "gear_pair": {
        "module": MODULE,
        "screw_gear_teeth": SCREW_GEAR_N,
        "motor_gear_teeth": MOTOR_GEAR_N,
        "face_width": GEAR_TH,
        "centre_distance": CENTER_DIST,
        "mesh_y": GEAR_Y,
    },
    "lead_screw": {
        "axis_x": SCREW_X,
        "axis_z": SCREW_Z,
        "minor_radius": SCREW_MINOR_R,
        "major_radius": SCREW_MAJOR_R,
        "pitch": SCREW_PITCH,
        "thread": "square",
        "threaded_length_y": [SCREW_Y0, SCREW_Y1],
        "overall_length_y": [SCREW_FRONT_Y, SCREW_BACK_Y],
    },
    "pusher": {
        "front_width_x": PUSHER_WIDTH,
        "sweep_plane_z": BED_TOP_Z,
        "blade_height": BLADE_H,
        "travel_y": [-BED_D / 2.0, BED_D / 2.0],
    },
    "printed_parts": list(PARTS.keys()),
    "print_notes": [
        "All parts exported as watertight STEP + STL, ready for slicing.",
        "pusher_carriage 256 x 34 x 74 mm: front fits the A1 plate exactly (256 mm).",
        "d_shaft_coupler_gear: 5 mm D-bore; an M3 set screw locks it to the shaft.",
        "Printed square lead screw uses 0.75 mm radial/axial thread clearance.",
        "screw_gear is 355 mm long: on A1 (256 mm build volume) print it in two",
        "threaded segments, or print the whole screw on a larger machine.",
        "Gear pair meshes at centre distance 45 mm (30T/15T, module 2).",
    ],
}


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))

    assembly = build_assembly()
    assembly_path = os.path.join(here, "screw_pusher_assembly")
    export_step(assembly, assembly_path + ".step")
    export_stl(assembly, assembly_path + ".stl")

    print("A1 screw-pusher model built (build123d).")
    print(f"  printed parts : {len(PARTS)}")
    for name, factory in PARTS.items():
        part = factory()
        bb = part.bounding_box()
        export_step(part, os.path.join(here, name + ".step"))
        export_stl(part, os.path.join(here, name + ".stl"))
        print(f"    - {name:22s} {bb.size.X:6.1f} x {bb.size.Y:6.1f} "
              f"x {bb.size.Z:6.1f} mm")

    bb = assembly.bounding_box()
    print(f"  assembly bbox : {bb.size.X:.1f} x {bb.size.Y:.1f} "
          f"x {bb.size.Z:.1f} mm")
    print(f"  pusher front  : {PUSHER_WIDTH:.0f} mm wide (build plate width)")
    print(f"  sweep plane   : Z={BED_TOP_Z:.0f} mm, front edge Y={-BED_D/2:.0f} mm")
    print(f"  motor mount   : base frame top Z={BASE_H:.0f} mm")

    json_path = os.path.join(here, "screw_pusher_dimensions.json")
    with open(json_path, "w") as fh:
        json.dump(INTERFACE, fh, indent=2)
    print(f"  dimensions    : {json_path}")


if __name__ == "__main__":
    main()
