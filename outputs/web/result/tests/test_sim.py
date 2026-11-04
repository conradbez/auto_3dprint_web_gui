from pathlib import Path

import pytest

from autoeject.end_block import build_end_block
from autoeject.sim import (
    extract_end_block,
    part_bbox_from_gcode,
    simulate,
)
from autoeject.slicer import (
    PLATE_GCODE_NAME,
    inject_end_block,
    read_archive,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "real_a1.gcode.3mf"


def cube_bbox(size):
    half = size / 2.0
    return (128.0 - half, 128.0 - half, 0.0, 128.0 + half, 128.0 + half, float(size))


GANTRY_PUSH = (
    "G90\n"
    "G1 Z40.5 F600\n"
    "G1 X-48 Y262 F3600\n"
    "G1 Z20 F600\n"
    "G1 Y-0.5 F300\n"
)

NOZZLE_PUSH = (
    "G90\n"
    "G1 Z20.5 F600\n"
    "G1 X128 Y262 F3600\n"
    "G1 Z15 F600\n"
    "G1 Y-0.5 F300\n"
)


def test_40_mm_cube_is_pushed_by_the_gantry():
    report = simulate(GANTRY_PUSH, cube_bbox(40))
    assert report.pushed is True
    assert report.pushed_by == ("gantry",)
    assert report.collisions == ()


def test_20_mm_cube_is_pushed_by_the_nozzle():
    report = simulate(NOZZLE_PUSH, cube_bbox(20))
    assert report.pushed is True
    assert report.pushed_by == ("nozzle",)
    assert report.collisions == ()


def test_push_line_removed_reports_a_missed_push():
    block = GANTRY_PUSH.replace("G1 Y-0.5 F300\n", "")
    report = simulate(block, cube_bbox(40))
    assert report.pushed is False
    assert report.missed_push is True
    assert report.pushed_by == ()


def test_y_push_that_misses_the_part_reports_a_missed_push():
    block = "G90\nG1 X-48 Y262 F3600\nG1 Z20 F600\nG1 Y200 F300\n"
    report = simulate(block, cube_bbox(40))
    assert report.pushed is False
    assert report.missed_push is True


def test_non_push_contact_reports_a_collision_with_its_move_index():
    # Driving the nozzle down onto the part is a Z move, not a Y push.
    block = "G90\nG1 Z20 F600\n"
    report = simulate(block, cube_bbox(40))
    assert report.pushed is False
    assert {collision.move_index for collision in report.collisions} == {0}
    assert {collision.box for collision in report.collisions} == {"nozzle", "gantry"}


def test_unknown_commands_are_ignored_and_counted():
    block = (
        "G90\n"
        "M400 ; wait for buffer\n"
        "T255\n"
        "G1 Z40.5 F600\n"
        "G1 X-48 Y262 F3600\n"
        "G1 Z20 F600\n"
        "G1 Y-0.5 F300\n"
        "M18 X Y Z\n"
    )
    report = simulate(block, cube_bbox(40))
    assert report.pushed is True
    assert report.unknown_commands == 3


def test_move_list_is_json_friendly_for_the_ui():
    report = simulate(GANTRY_PUSH, cube_bbox(40))
    payload = report.to_dict()
    assert [move["i"] for move in payload["moves"]] == list(
        range(len(payload["moves"]))
    )
    for move in payload["moves"]:
        assert set(move) == {"i", "x", "y", "z"}


def test_relative_moves_are_supported():
    absolute = simulate("G90\nG1 Z40.5 F600\nG1 Y262 F3600\nG1 Z20\nG1 Y-0.5 F300\n", cube_bbox(40))
    relative = simulate("G90\nG1 Z40.5 F600\nG91\nG1 Y134 F3600\nG1 Z-20.5\nG1 Y-262.5 F300\n", cube_bbox(40))
    assert absolute.pushed is True
    assert relative.pushed is True
    assert absolute.moves[-1].y == relative.moves[-1].y


def test_part_bbox_from_gcode_and_end_block_extraction():
    injected = inject_end_block(FIXTURE.read_bytes(), build_end_block())
    gcode = read_archive(injected)[PLATE_GCODE_NAME].decode("utf-8")

    bbox = part_bbox_from_gcode(gcode)
    assert bbox[2] == 0.0
    assert bbox[5] == 20.08
    assert 0.0 < bbox[0] < bbox[3] < 256.0
    assert 0.0 < bbox[1] < bbox[4] < 256.0

    block = extract_end_block(gcode)
    assert block.startswith("; MACHINE_END_GCODE_START")
    assert block.rstrip().endswith("; EXECUTABLE_BLOCK_END")


def test_real_a1_fixture_is_pushed_without_collisions():
    injected = inject_end_block(FIXTURE.read_bytes(), build_end_block())
    gcode = read_archive(injected)[PLATE_GCODE_NAME].decode("utf-8")
    report = simulate(extract_end_block(gcode), part_bbox_from_gcode(gcode))

    assert report.pushed is True
    assert report.collisions == ()
    assert report.pushed_by == ("gantry",)
    assert report.unknown_commands > 0


def test_invalid_part_bbox_is_rejected():
    with pytest.raises(ValueError):
        simulate(GANTRY_PUSH, (0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        simulate(GANTRY_PUSH, (10.0, 0.0, 0.0, 5.0, 5.0, 5.0))


def test_part_bbox_from_gcode_without_extrusions_falls_back():
    gcode = (
        "; max_z_height: 5.0\n"
        "; CHANGE_LAYER\n"
        "G1 X10 Y20 F3000\n"
        "G1 X30 Y40 F3000\n"
    )
    assert part_bbox_from_gcode(gcode) == (10.0, 20.0, 0.0, 30.0, 40.0, 5.0)
