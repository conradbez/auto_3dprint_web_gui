import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from autoeject.end_block import EjectBlockParams, build_end_block
from autoeject.slicer import (
    PLATE_GCODE_NAME,
    PLATE_MD5_NAME,
    SliceError,
    inject_end_block,
    md5_hex,
    read_archive,
    slice_stl,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "real_a1.gcode.3mf"


def plate_gcode(archive: bytes) -> str:
    return read_archive(archive)[PLATE_GCODE_NAME].decode("utf-8")


def assert_md5_matches(archive: bytes) -> None:
    entries = read_archive(archive)
    gcode = entries[PLATE_GCODE_NAME]
    recorded = entries[PLATE_MD5_NAME].decode("ascii").strip()
    assert recorded == hashlib.md5(gcode).hexdigest().upper()
    assert recorded == recorded.upper()


def test_fixture_md5_is_self_consistent():
    assert_md5_matches(FIXTURE.read_bytes())


def test_inject_replaces_only_the_stock_end_block_span():
    raw = FIXTURE.read_bytes()
    template = build_end_block(
        EjectBlockParams(
            cool_bed_temp_c=22,
            cool_hold_s=90,
            heat_bed_temp_c=65,
            heat_hold_s=45,
            heat_cool_cycles=2,
            push_feedrate_mm_min=450,
        )
    )
    result = inject_end_block(raw, template)
    gcode = plate_gcode(result)
    original = plate_gcode(raw)

    assert gcode.count("; MACHINE_END_GCODE_START") == 1
    assert gcode.count("; EXECUTABLE_BLOCK_END") == 1
    assert "G1 Y-0.5 F450" in gcode
    assert gcode.count("M190 S22 ;") == 2
    assert gcode.count("M190 S65 ;") == 2
    assert gcode.count("G4 S90 ;") == 2
    assert gcode.count("G4 S45 ;") == 2
    assert "G1 Z1 F600" in gcode

    # Everything outside the replaced span is byte-identical.
    head, _, remainder = original.partition("; MACHINE_END_GCODE_START")
    _, _, tail = remainder.partition("; EXECUTABLE_BLOCK_END")
    new_head, _, new_remainder = gcode.partition("; MACHINE_END_GCODE_START")
    _, _, new_tail = new_remainder.partition("; EXECUTABLE_BLOCK_END")
    assert head == new_head
    assert tail == new_tail

    for line in gcode.splitlines():
        if not line.lstrip().startswith(";"):
            assert "{" not in line and "}" not in line
    assert_md5_matches(result)


def test_inject_rejects_archive_without_unique_end_block():
    raw = FIXTURE.read_bytes()
    entries = read_archive(raw)
    broken = entries[PLATE_GCODE_NAME].replace(b"; MACHINE_END_GCODE_START", b"; nothing")
    buffer = BytesIO()
    with zipfile.ZipFile(BytesIO(raw)) as source:
        new_archive = source.namelist()
    with zipfile.ZipFile(buffer, "w") as destination:
        for name in new_archive:
            destination.writestr(name, broken if name == PLATE_GCODE_NAME else entries[name])
    with pytest.raises(ValueError):
        inject_end_block(buffer.getvalue(), build_end_block())


FAKE_CLI = """#!/usr/bin/env python3
import hashlib
import json
import sys
import zipfile

args = sys.argv[1:]


def value(flag):
    return args[args.index(flag) + 1]


machine = json.load(open(value("--load-settings").split(";")[0]))
block = machine["machine_end_gcode"]
payload = (
    "; HEADER_BLOCK_START\\n"
    "; max_z_height: 20.08\\n"
    "; HEADER_BLOCK_END\\n\\n"
    "; EXECUTABLE_BLOCK_START\\n"
    "; MACHINE_END_GCODE_START\\n"
    + block
    + "\\n; EXECUTABLE_BLOCK_END\\n"
)
encoded = payload.encode("utf-8")
with zipfile.ZipFile(value("--export-3mf"), "w") as archive:
    archive.writestr("Metadata/plate_1.gcode", encoded)
    archive.writestr("Metadata/plate_1.gcode.md5", hashlib.md5(encoded).hexdigest().upper())
print("fake sliced")
"""


FAILING_CLI = """#!/usr/bin/env python3
import sys

print("boom", file=sys.stderr)
sys.exit(3)
"""


def _write_cli(tmp_path: Path, body: str) -> Path:
    cli = tmp_path / "fake_bambu"
    cli.write_text(body, encoding="utf-8")
    cli.chmod(0o755)
    return cli


def _write_profiles(tmp_path: Path) -> Path:
    root = tmp_path / "profiles"
    (root / "machine").mkdir(parents=True)
    (root / "process").mkdir()
    (root / "filament").mkdir()
    (root / "machine" / "Bambu Lab A1 0.4 nozzle.json").write_text(
        json.dumps(
            {
                "machine_end_gcode": "stock",
                "default_print_profile": "0.20mm Standard @BBL A1",
                "default_filament_profile": ["Bambu PLA Basic @BBL A1"],
            }
        ),
        encoding="utf-8",
    )
    (root / "process" / "0.20mm Standard @BBL A1.json").write_text(
        json.dumps({"layer_height": "0.2"}), encoding="utf-8"
    )
    (root / "filament" / "Bambu PLA Basic @BBL A1.json").write_text(
        json.dumps({"filament_type": "PLA"}), encoding="utf-8"
    )
    return root


def test_slice_stl_patches_machine_end_gcode_through_the_cli(
    tmp_path, monkeypatch
):
    cli = _write_cli(tmp_path, FAKE_CLI)
    root = _write_profiles(tmp_path)
    monkeypatch.setenv("BAMBU_CLI", str(cli))
    monkeypatch.setenv("BAMBU_PROFILE_ROOT", str(root))

    block = build_end_block(EjectBlockParams(push_feedrate_mm_min=450))
    result = slice_stl(b"synthetic stl bytes", block)

    gcode = plate_gcode(result)
    assert "G1 Y-0.5 F450" in gcode
    assert "G1 Z{max_layer_z + 0.5} F900" in gcode  # CLI evaluates in real use
    assert_md5_matches(result)


def test_slice_stl_failure_directs_to_presliced_fallback(tmp_path, monkeypatch):
    cli = _write_cli(tmp_path, FAILING_CLI)
    root = _write_profiles(tmp_path)
    monkeypatch.setenv("BAMBU_CLI", str(cli))
    monkeypatch.setenv("BAMBU_PROFILE_ROOT", str(root))

    with pytest.raises(SliceError) as error:
        slice_stl(b"synthetic stl bytes", build_end_block())
    assert "pre-sliced" in str(error.value)


def test_slice_stl_requires_bambu_cli(monkeypatch):
    monkeypatch.delenv("BAMBU_CLI", raising=False)
    with pytest.raises(SliceError):
        slice_stl(b"synthetic stl bytes", build_end_block())


def test_md5_hex_is_uppercase():
    assert md5_hex(b"abc") == "900150983CD24FB0D6963F7D28E17F72"
