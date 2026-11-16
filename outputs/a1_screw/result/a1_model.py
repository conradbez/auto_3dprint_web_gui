#!/usr/bin/env python3
"""
a1_model.py -- build123d model of a Bambu Lab A1 (full size) 3D printer.

WHY THIS FILE EXISTS
--------------------
The next engineer is building a motorised "screw" pusher that sweeps the
full width of the A1 build plate to push finished prints off the bed.
This script gives them the mechanical reference geometry of the printer
(frame, bed, gantry) and a machine-readable set of key dimensions.

RESEARCH (only claims with a URL -- model memory is NOT evidence)
-----------------------------------------------------------------
* Build volume 256 x 256 x 256 mm      -> https://bambulab.com/en/a1/tech-specs
* Build plate / bed 256 x 256 mm       -> https://bambureviews.com/posts/bambu-build-volume-and-footprint/
* Machine envelope ~385 x 410 x 430 mm -> https://filament2print.com/en/filament-fdm/2489-bambu-lab-a1-series-fdm-3d-printers.html
* Chassis: steel + extruded aluminium  -> https://bambulab.com/en/a1/tech-specs

ASSUMPTIONS (NOT in the research; chosen so the model is usable, easy to edit)
------------------------------------------------------------------------------
* BED_TOP_Z = 100 mm  : height of the build-plate top surface above the desk.
* BASE_H    = 70 mm   : electronics / base box height.
* The A1 is a "bedslinger": the bed travels in Y, the X gantry rides in Z.

COORDINATE SYSTEM
-----------------
Origin at the centre of the printer footprint on the desk (Z = 0, up).
+Z up, +X right, +Y toward the back of the machine.
"""
from __future__ import annotations

import json
import os

from build123d import (
    Box,
    Compound,
    Cylinder,
    Pos,
    export_step,
    export_stl,
)

# ---------------------------------------------------------------------------
# Research-backed dimensions (mm)
# ---------------------------------------------------------------------------
BED_W = 256.0        # build plate width  (X)  -- tech-specs
BED_D = 256.0        # build plate depth  (Y)  -- tech-specs
MAX_PRINT_Z = 256.0  # usable build height (Z)  -- tech-specs
FRAME_W = 385.0      # machine width  (X)  -- filament2print
FRAME_D = 410.0      # machine depth  (Y)  -- filament2print
FRAME_H = 430.0      # machine height (Z)  -- filament2print

# ---------------------------------------------------------------------------
# Assumed / derived dimensions (mm) -- edit freely
# ---------------------------------------------------------------------------
BASE_H = 70.0            # base / electronics box
BED_T = 3.0              # spring-steel build plate thickness
BED_TOP_Z = 100.0        # top of the build plate above the desk
CARRIAGE_H = 24.0        # Y-axis bed carriage under the plate
COL_W = 36.0             # Z column cross section (X)
COL_D = 36.0             # Z column cross section (Y)
BEAM_H = 46.0            # X gantry beam height
BEAM_D = 40.0            # X gantry beam depth
HEAD_W, HEAD_D, HEAD_H = 62.0, 54.0, 72.0  # toolhead bounding box


def box(x0: float, y0: float, z0: float, dx: float, dy: float, dz: float) -> Box:
    """Axis-aligned box placed by its minimum corner (x0, y0, z0)."""
    return Pos(x0 + dx / 2.0, y0 + dy / 2.0, z0 + dz / 2.0) * Box(dx, dy, dz)


def build_a1() -> Compound:
    """Return the A1 printer as a labelled compound of solids."""
    hw, hd = FRAME_W / 2.0, FRAME_D / 2.0
    parts: list = []

    # -- base / electronics box -------------------------------------------
    base = box(-hw, -hd, 0.0, FRAME_W, FRAME_D, BASE_H)
    base.label = "base"
    parts.append(base)

    # -- Y-axis bed carriage ----------------------------------------------
    carriage = box(
        -BED_W / 2.0, -BED_D / 2.0, BASE_H, BED_W, BED_D, CARRIAGE_H
    )
    carriage.label = "bed_carriage"
    parts.append(carriage)

    # -- build plate (the surface prints sit on) --------------------------
    bed = box(
        -BED_W / 2.0,
        -BED_D / 2.0,
        BED_TOP_Z - BED_T,
        BED_W,
        BED_D,
        BED_T,
    )
    bed.label = "build_plate"
    parts.append(bed)

    # -- two Z columns at the back ----------------------------------------
    col_z0, col_h = BASE_H, FRAME_H - BASE_H
    for sign in (-1.0, 1.0):
        col = box(
            sign * (hw - COL_W) - (COL_W if sign < 0 else 0.0),
            hd - COL_D,
            col_z0,
            COL_W,
            COL_D,
            col_h,
        )
        col.label = "z_column"
        parts.append(col)

    # -- Z lead screws (visual) -------------------------------------------
    for sign in (-1.0, 1.0):
        screw = Pos(sign * (hw - COL_W / 2.0), hd - COL_D / 2.0,
                    (col_z0 + col_z0 + col_h) / 2.0) * Cylinder(4.0, col_h)
        screw.label = "z_leadscrew"
        parts.append(screw)

    # -- X gantry beam spanning the columns -------------------------------
    beam_len = FRAME_W - 2.0 * COL_W
    beam = box(
        -beam_len / 2.0,
        hd - COL_D - BEAM_D,
        FRAME_H - BEAM_H,
        beam_len,
        BEAM_D,
        BEAM_H,
    )
    beam.label = "x_gantry"
    parts.append(beam)

    # -- toolhead hanging from the gantry ---------------------------------
    head = box(
        -HEAD_W / 2.0,
        hd - COL_D - BEAM_D + (BEAM_D - HEAD_D) / 2.0,
        FRAME_H - BEAM_H - HEAD_H,
        HEAD_W,
        HEAD_D,
        HEAD_H,
    )
    head.label = "toolhead"
    parts.append(head)

    return Compound(children=parts, label="Bambu_Lab_A1")


# Key dimensions handed to the next engineer (the screw-pusher builder).
INTERFACE = {
    "units": "mm",
    "origin": "centre of footprint on the desk; +Z up, +Y toward the back",
    "build_plate": {
        "width_x": BED_W,
        "depth_y": BED_D,
        "top_surface_z": BED_TOP_Z,
        "thickness": BED_T,
    },
    "machine_envelope": {"width_x": FRAME_W, "depth_y": FRAME_D, "height_z": FRAME_H},
    "max_print_height_z": MAX_PRINT_Z,
    "screw_pusher_notes": (
        "Pusher front must span the full plate width (256 mm in X). "
        "Sweep the pusher across the plate top surface at Z="
        f"{BED_TOP_Z:.0f} mm; the plate front edge is at Y=-{BED_D/2:.0f} mm. "
        "Mount the motor holder on the base frame (top at Z="
        f"{BASE_H:.0f} mm) clear of the moving bed carriage."
    ),
    "sources": {
        "build_volume": "https://bambulab.com/en/a1/tech-specs",
        "bed_size": "https://bambureviews.com/posts/bambu-build-volume-and-footprint/",
        "machine_size": "https://filament2print.com/en/filament-fdm/2489-bambu-lab-a1-series-fdm-3d-printers.html",
    },
}


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    printer = build_a1()

    step_path = os.path.join(here, "a1_model.step")
    stl_path = os.path.join(here, "a1_model.stl")
    export_step(printer, step_path)
    export_stl(printer, stl_path)

    json_path = os.path.join(here, "a1_model_dimensions.json")
    with open(json_path, "w") as fh:
        json.dump(INTERFACE, fh, indent=2)

    bb = printer.bounding_box()
    print("Bambu Lab A1 model built.")
    print(f"  parts          : {len(printer.children)}")
    print(f"  bounding box   : {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
    print(f"  build plate    : {BED_W:.0f} x {BED_D:.0f} mm, top at Z={BED_TOP_Z:.0f} mm")
    print(f"  STEP           : {step_path}")
    print(f"  STL            : {stl_path}")
    print(f"  dimensions JSON: {json_path}")


if __name__ == "__main__":
    main()
