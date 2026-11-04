"""Deterministic STL ejectability checks for the 256 x 256 mm A1 bed."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

BED_WIDTH_MM = 256.0
BED_DEPTH_MM = 256.0
NOZZLE_PUSH_HEIGHT_MM = 32.0
GANTRY_PUSH_MIN_LAYER_Z_MM = 41.0
MIN_BASE_AREA_MM2 = 100.0
MAX_TIP_RATIO = 2.0


@dataclass(frozen=True)
class Rule:
    id: str
    measured: float | bool
    threshold: str
    verdict: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Report:
    verdict: str
    rules: tuple[Rule, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "rules": [rule.to_dict() for rule in self.rules],
        }


def _base_footprint(mesh: trimesh.Trimesh) -> Polygon | Any:
    """Return the union of triangles touching the lowest plane of the mesh."""
    z_min = float(mesh.bounds[0, 2])
    triangles = mesh.triangles
    on_base = np.all(np.isclose(triangles[:, :, 2], z_min, atol=1e-7), axis=1)
    polygons = []
    for triangle in triangles[on_base, :, :2]:
        polygon = Polygon(triangle)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if not polygon.is_empty:
            polygons.append(polygon)
    if not polygons:
        # A degenerate contact still receives deterministic fail measurements.
        minimum, maximum = mesh.bounds[:, :2]
        return Polygon(
            [
                (minimum[0], minimum[1]),
                (maximum[0], minimum[1]),
                (maximum[0], maximum[1]),
                (minimum[0], maximum[1]),
            ]
        )
    return unary_union(polygons)


def _shortest_width(footprint: Any) -> float:
    rectangle = footprint.minimum_rotated_rectangle
    coordinates = list(rectangle.exterior.coords)
    if len(coordinates) < 2:
        return 0.0
    lengths = [
        float(np.hypot(b[0] - a[0], b[1] - a[1]))
        for a, b in zip(coordinates, coordinates[1:])
    ]
    return min(lengths, default=0.0)


def check(stl_bytes: bytes) -> Report:
    """Measure an STL and return all five binding-v1 ejectability rules.

    STL coordinates are expected to use the A1 plate coordinate system, whose
    printable footprint is 0..256 mm on both X and Y.
    """
    if not isinstance(stl_bytes, (bytes, bytearray)):
        raise ValueError("STL content must be bytes")
    try:
        mesh = trimesh.load(
            BytesIO(bytes(stl_bytes)), file_type="stl", force="mesh", process=False
        )
    except Exception as exc:
        raise ValueError("Could not read STL geometry") from exc
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
        raise ValueError("STL contains no geometry")
    if not np.all(np.isfinite(mesh.bounds)):
        raise ValueError("STL contains non-finite geometry")

    minimum, maximum = mesh.bounds
    height = float(maximum[2] - minimum[2])
    footprint = _base_footprint(mesh)
    base_area = float(footprint.area)
    shortest_width = _shortest_width(footprint)
    tip_ratio = height / shortest_width if shortest_width > 0 else float("inf")

    low_height = height < NOZZLE_PUSH_HEIGHT_MM
    wrong_gantry_branch = height <= GANTRY_PUSH_MIN_LAYER_Z_MM
    area_fail = base_area < MIN_BASE_AREA_MM2
    tip_fail = tip_ratio > MAX_TIP_RATIO
    outside = (
        float(footprint.bounds[0]) < 0.0
        or float(footprint.bounds[1]) < 0.0
        or float(footprint.bounds[2]) > BED_WIDTH_MM
        or float(footprint.bounds[3]) > BED_DEPTH_MM
    )

    rules = (
        Rule(
            id="nozzle_push_height",
            measured=height,
            threshold=f"< {NOZZLE_PUSH_HEIGHT_MM:g} mm height",
            verdict="warn" if low_height else "pass",
            reason=(
                "Part is below gantry-push height; use the supervised nozzle-push "
                "branch, including G1 Z1."
                if low_height
                else "Part is not below the nozzle-push warning height."
            ),
        ),
        Rule(
            id="gantry_push_branch",
            measured=height,
            threshold=f"> {GANTRY_PUSH_MIN_LAYER_Z_MM:g} mm max_layer_z",
            verdict="warn" if wrong_gantry_branch else "pass",
            reason=(
                "The end block selects nozzle push because max_layer_z does not exceed 41 mm."
                if wrong_gantry_branch
                else "The end block can select its gantry-push branch."
            ),
        ),
        Rule(
            id="base_area",
            measured=base_area,
            threshold=f">= {MIN_BASE_AREA_MM2:g} mm²",
            verdict="fail" if area_fail else "pass",
            reason=(
                "Projected base contact area is too small for adhesion release and push contact."
                if area_fail
                else "Projected base contact area meets the v1 minimum."
            ),
        ),
        Rule(
            id="tip_ratio",
            measured=tip_ratio,
            threshold=f"<= {MAX_TIP_RATIO:g}",
            verdict="fail" if tip_fail else "pass",
            reason=(
                "Height divided by shortest base-contact width exceeds the tip-over limit."
                if tip_fail
                else "Height divided by shortest base-contact width is within the limit."
            ),
        ),
        Rule(
            id="bed_footprint",
            measured=not outside,
            threshold=f"{BED_WIDTH_MM:g} × {BED_DEPTH_MM:g} mm A1 bed",
            verdict="fail" if outside else "pass",
            reason=(
                "The complete base footprint and its eject exit path do not fit the A1 envelope."
                if outside
                else "The complete base footprint fits the A1 bed and eject clearance envelope."
            ),
        ),
    )
    if any(rule.verdict == "fail" for rule in rules):
        verdict = "fail"
    elif any(rule.verdict == "warn" for rule in rules):
        verdict = "warn"
    else:
        verdict = "pass"
    return Report(verdict=verdict, rules=rules)
