"""Minimal axis-aligned-box simulation of the evaluated A1 eject end block.

The simulator replays only the ``G0``/``G1``/``G90``/``G91`` moves of an
already evaluated eject block against four axis-aligned boxes:

* the toolhead/nozzle box, following the programmed nozzle position,
* the gantry bar, spanning X at the nozzle height,
* the bed, which moves in Y and carries the part,
* the part, positioned by the caller's bounding box.

The box dimensions below are deliberately approximate and are **not measured**
from a real A1.  They exist to give deterministic, reproducible findings and a
short animation for the UI, not to make a physical safety claim.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .slicer import EXECUTABLE_BLOCK_END, MACHINE_END_START

# --- approximate box dimensions, not measured ------------------------------
TOOLHEAD_SIZE_MM = 40.0  # approximate, not measured
TOOLHEAD_HEIGHT_MM = 40.0  # approximate, not measured
GANTRY_BAR_Y_THICKNESS_MM = 10.0  # approximate, not measured
GANTRY_BAR_Z_CLEARANCE_MM = 8.0  # approximate, not measured
GANTRY_BAR_HEIGHT_MM = 60.0  # approximate, not measured
BED_WIDTH_MM = 256.0  # approximate, not measured
BED_DEPTH_MM = 256.0  # approximate, not measured
BED_THICKNESS_MM = 5.0  # approximate, not measured
OVERLAP_EPS_MM = 1e-6

_NUMBER = r"-?(?:\d+(?:\.\d+)?|\.\d+)"
_COMMAND = re.compile(rf"^([A-Za-z])\s*({_NUMBER})?")
_WORD = re.compile(rf"([A-Za-z])\s*({_NUMBER})")
_LAYER_MARKER = re.compile(r"^;\s*(?:CHANGE_LAYER|LAYER_CHANGE)\s*$")
_MAX_Z_HEIGHT = re.compile(r"^;\s*max_z_height:\s*(-?[0-9.]+)\s*$")


@dataclass(frozen=True)
class Box:
    """Axis-aligned bounding box in plate coordinates (millimetres)."""

    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    @classmethod
    def from_bounds(cls, bounds: Sequence[float]) -> "Box":
        if len(bounds) != 6:
            raise ValueError("part_bbox must have six values")
        values = [float(value) for value in bounds]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("part_bbox must be finite")
        xmin, ymin, zmin, xmax, ymax, zmax = values
        if xmin > xmax or ymin > ymax or zmin > zmax:
            raise ValueError("part_bbox min values must not exceed max values")
        return cls(xmin, ymin, zmin, xmax, ymax, zmax)

    @property
    def center_x(self) -> float:
        return (self.xmin + self.xmax) / 2.0

    @property
    def center_y(self) -> float:
        return (self.ymin + self.ymax) / 2.0


@dataclass(frozen=True)
class Move:
    """One replayed spatial G0/G1 move."""

    i: int
    x: float
    y: float
    z: float
    feedrate: float | None = None

    def to_dict(self) -> dict[str, float | int]:
        return {"i": self.i, "x": self.x, "y": self.y, "z": self.z}


@dataclass(frozen=True)
class Collision:
    """A toolhead or gantry box that hit the part outside a Y push move."""

    move_index: int
    box: str

    def to_dict(self) -> dict[str, Any]:
        return {"move_index": self.move_index, "box": self.box}


@dataclass(frozen=True)
class SimReport:
    """Deterministic simulation result for the UI and the API."""

    pushed: bool
    pushed_by: tuple[str, ...]
    collisions: tuple[Collision, ...]
    moves: tuple[Move, ...]
    unknown_commands: int

    @property
    def missed_push(self) -> bool:
        return not self.pushed

    def to_dict(self) -> dict[str, Any]:
        return {
            "pushed": self.pushed,
            "pushed_by": list(self.pushed_by),
            "missed_push": self.missed_push,
            "collisions": [collision.to_dict() for collision in self.collisions],
            "moves": [move.to_dict() for move in self.moves],
            "unknown_commands": self.unknown_commands,
        }


def _overlaps(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    """Strict overlap so merely touching a face is not a collision."""
    return a_min < b_max - OVERLAP_EPS_MM and a_max > b_min + OVERLAP_EPS_MM


def _hits(box: Box, part: Box) -> bool:
    return (
        _overlaps(box.xmin, box.xmax, part.xmin, part.xmax)
        and _overlaps(box.ymin, box.ymax, part.ymin, part.ymax)
        and _overlaps(box.zmin, box.zmax, part.zmin, part.zmax)
    )


def _swept(previous: tuple[float, float, float], current: tuple[float, float, float]):
    """Return the toolhead and gantry boxes swept by one move."""
    px, py, pz = previous
    cx, cy, cz = current
    toolhead = Box(
        min(px, cx) - TOOLHEAD_SIZE_MM / 2.0,
        min(py, cy) - TOOLHEAD_SIZE_MM / 2.0,
        min(pz, cz),
        max(px, cx) + TOOLHEAD_SIZE_MM / 2.0,
        max(py, cy) + TOOLHEAD_SIZE_MM / 2.0,
        max(pz, cz) + TOOLHEAD_HEIGHT_MM,
    )
    gantry = Box(
        0.0,
        min(py, cy) - GANTRY_BAR_Y_THICKNESS_MM / 2.0,
        min(pz, cz) + GANTRY_BAR_Z_CLEARANCE_MM,
        BED_WIDTH_MM,
        max(py, cy) + GANTRY_BAR_Y_THICKNESS_MM / 2.0,
        max(pz, cz) + GANTRY_BAR_Z_CLEARANCE_MM + GANTRY_BAR_HEIGHT_MM,
    )
    return toolhead, gantry


def _strip_comment(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _words(rest: str) -> dict[str, float]:
    return {letter.upper(): float(value) for letter, value in _WORD.findall(rest)}


def simulate(eject_gcode_evaluated: str, part_bbox: Any) -> SimReport:
    """Replay an evaluated eject block and report push/collision findings.

    ``part_bbox`` is the part's real axis-aligned box in plate coordinates as
    ``(xmin, ymin, zmin, xmax, ymax, zmax)`` (a ``(2, 3)`` trimesh-style bounds
    array is also accepted).  Only ``G0``/``G1``/``G90``/``G91`` are understood;
    every other command is ignored and counted in ``unknown_commands``.
    """
    if not isinstance(eject_gcode_evaluated, str):
        raise ValueError("eject_gcode_evaluated must be text")

    bounds = getattr(part_bbox, "bounds", None)
    if bounds is not None and bounds is not part_bbox:
        part = Box.from_bounds(list(bounds.reshape(-1)))
    else:
        part = Box.from_bounds(part_bbox)

    # The block starts where printing stopped: over the part, at its top surface.
    x, y, z = part.center_x, part.center_y, part.zmax
    absolute = True
    feedrate: float | None = None

    moves: list[Move] = []
    collisions: list[Collision] = []
    pushed_by: set[str] = set()
    ejected = False
    unknown = 0

    for raw_line in eject_gcode_evaluated.splitlines():
        line = _strip_comment(raw_line)
        if not line:
            continue
        match = _COMMAND.match(line)
        if not match:
            unknown += 1
            continue
        letter = match.group(1).upper()
        number = match.group(2)

        if letter == "G" and number in {"0", "1"}:
            params = _words(line[match.end(1) :])
            if "F" in params:
                feedrate = params["F"]
            previous = (x, y, z)
            if absolute:
                next_x = params.get("X", x)
                next_y = params.get("Y", y)
                next_z = params.get("Z", z)
            else:
                next_x = x + params["X"] if "X" in params else x
                next_y = y + params["Y"] if "Y" in params else y
                next_z = z + params["Z"] if "Z" in params else z
            if (next_x, next_y, next_z) == previous:
                continue

            toolhead, gantry = _swept(previous, (next_x, next_y, next_z))
            contact = [
                name
                for name, box in (("nozzle", toolhead), ("gantry", gantry))
                if _hits(box, part)
            ]
            if contact and not ejected:
                has_y_motion = abs(next_y - y) > OVERLAP_EPS_MM
                if has_y_motion:
                    # The Y push is the intended ejection move.
                    pushed_by.update(contact)
                    ejected = True
                else:
                    # Any other box contact is an unintended collision.
                    move_index = len(moves)
                    collisions.extend(
                        Collision(move_index=move_index, box=name)
                        for name in contact
                    )

            x, y, z = next_x, next_y, next_z
            moves.append(Move(len(moves), x, y, z, feedrate))
        elif letter == "G" and number == "90":
            absolute = True
        elif letter == "G" and number == "91":
            absolute = False
        else:
            unknown += 1

    return SimReport(
        pushed=bool(pushed_by),
        pushed_by=tuple(sorted(pushed_by)),
        collisions=tuple(collisions),
        moves=tuple(moves),
        unknown_commands=unknown,
    )


def extract_end_block(gcode_text: str) -> str:
    """Return the text from ``; MACHINE_END_GCODE_START`` through the block end.

    The eject simulation and preview only care about the end block, so callers
    pass this slice rather than a whole printed plate.
    """
    if not isinstance(gcode_text, str):
        raise ValueError("gcode_text must be text")
    start = gcode_text.find(MACHINE_END_START)
    if start < 0 or gcode_text.find(MACHINE_END_START, start + 1) >= 0:
        raise ValueError(f"expected exactly one {MACHINE_END_START!r} marker")
    end = gcode_text.find(EXECUTABLE_BLOCK_END, start)
    if end < 0 or gcode_text.find(EXECUTABLE_BLOCK_END, end + 1) >= 0:
        raise ValueError(f"expected exactly one {EXECUTABLE_BLOCK_END!r} marker")
    return gcode_text[start : end + len(EXECUTABLE_BLOCK_END)]


def part_bbox_from_gcode(gcode_text: str) -> tuple[float, float, float, float, float, float]:
    """Derive a part box from header ``max_z_height`` and the first layer.

    The XY extent comes from the first layer's extrusion moves, which is the
    base footprint that actually sits on the plate.  This is the pre-sliced
    counterpart of measuring an STL's bounds.
    """
    if not isinstance(gcode_text, str):
        raise ValueError("gcode_text must be text")
    lines = gcode_text.splitlines()

    max_z: float | None = None
    for line in lines:
        match = _MAX_Z_HEIGHT.match(line.strip())
        if match:
            max_z = float(match.group(1))
            break
    if max_z is None or not math.isfinite(max_z):
        raise ValueError("gcode has no finite max_z_height header")

    markers = [i for i, line in enumerate(lines) if _LAYER_MARKER.match(line.strip())]
    if not markers:
        start, stop = 0, len(lines)
    else:
        start = markers[0] + 1
        stop = markers[1] if len(markers) > 1 else len(lines)

    extrusion_x: list[float] = []
    extrusion_y: list[float] = []
    loose_x: list[float] = []
    loose_y: list[float] = []
    for raw_line in lines[start:stop]:
        line = _strip_comment(raw_line)
        if not line:
            continue
        match = _COMMAND.match(line)
        if not match or match.group(1).upper() != "G" or match.group(2) not in {"0", "1"}:
            continue
        params = _words(line[match.end(1) :])
        if "X" not in params or "Y" not in params:
            continue
        loose_x.append(params["X"])
        loose_y.append(params["Y"])
        if params.get("E", 0.0) > 0.0:
            extrusion_x.append(params["X"])
            extrusion_y.append(params["Y"])

    xs = extrusion_x or loose_x
    ys = extrusion_y or loose_y
    if not xs or not ys:
        raise ValueError("first layer has no XY moves to measure")
    return (min(xs), min(ys), 0.0, max(xs), max(ys), max_z)
