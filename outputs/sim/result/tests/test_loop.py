import hashlib
from pathlib import Path

import pytest

from autoeject.end_block import EjectBlockParams, build_end_block
from autoeject.loop import loop_3mf
from autoeject.slicer import (
    PLATE_GCODE_NAME,
    PLATE_MD5_NAME,
    inject_end_block,
    read_archive,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "real_a1.gcode.3mf"

TEMPLATE = build_end_block(
    EjectBlockParams(
        cool_bed_temp_c=25,
        cool_hold_s=120,
        heat_bed_temp_c=60,
        heat_hold_s=60,
        heat_cool_cycles=2,
        push_feedrate_mm_min=600,
    )
)


def injected_fixture() -> bytes:
    return inject_end_block(FIXTURE.read_bytes(), TEMPLATE)


def test_loop_n3_repeats_print_and_eject_from_the_real_fixture():
    result = loop_3mf(injected_fixture(), 3)
    entries = read_archive(result)
    gcode = entries[PLATE_GCODE_NAME].decode("utf-8")

    # Three ordered print bodies and three eject sequences.
    assert gcode.count("; EXECUTABLE_BLOCK_START") == 1
    assert gcode.count("; EXECUTABLE_BLOCK_END") == 1
    assert gcode.count("G1 Y-0.5 F600") == 3
    # Two low-Z moves per copy: the nozzle-push selection and the safety clear.
    assert gcode.count("G1 Z1 F600") == 6

    # Two configured cool-and-heat cycles per copy.
    assert gcode.count("M190 S25 ;") == 6
    assert gcode.count("M190 S60 ;") == 6
    assert gcode.count("G4 S120 ; hold at cool temperature") == 6
    assert gcode.count("G4 S60 ; hold at heated temperature") == 6

    # Matching md5 and no raw placeholders on executable lines.
    recorded = entries[PLATE_MD5_NAME].decode("ascii").strip()
    assert recorded == hashlib.md5(entries[PLATE_GCODE_NAME]).hexdigest().upper()
    for line in gcode.splitlines():
        if not line.lstrip().startswith(";"):
            assert "{" not in line and "}" not in line


def test_loop_n1_is_a_single_printable_copy():
    result = loop_3mf(injected_fixture(), 1)
    gcode = read_archive(result)[PLATE_GCODE_NAME].decode("utf-8")
    assert gcode.count("G1 Y-0.5 F600") == 1


@pytest.mark.parametrize("n", [0, -1, 101, True, "3", None])
def test_loop_rejects_invalid_iteration_counts(n):
    with pytest.raises(ValueError):
        loop_3mf(injected_fixture(), n)


def test_loop_rejects_archive_without_executable_block():
    with pytest.raises(ValueError):
        loop_3mf(b"not a zip", 3)


def test_loop_rejects_placeholder_on_an_executable_line(monkeypatch):
    import io
    import zipfile

    gcode = (
        "; EXECUTABLE_BLOCK_START\n"
        "G1 Z{max_layer_z + 0.5} F900\n"
        "; EXECUTABLE_BLOCK_END\n"
    ).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(PLATE_GCODE_NAME, gcode)
    with pytest.raises(ValueError):
        loop_3mf(buffer.getvalue(), 3)
