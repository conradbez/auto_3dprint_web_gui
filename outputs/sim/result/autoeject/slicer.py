"""Headless A1 slicing and safe end-block injection for ``.gcode.3mf`` files.

Two independent entry points live here:

* :func:`slice_stl` drives the BambuStudio CLI with the CLI's own installed
  system profiles, patching only ``machine_end_gcode`` in a copy of the A1
  machine profile.
* :func:`inject_end_block` rewrites the evaluated stock end block of an
  already sliced A1 ``.gcode.3mf``.

Both keep the archive valid by recomputing ``Metadata/plate_1.gcode.md5``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from .end_block import evaluate_end_block

PLATE_GCODE_NAME = "Metadata/plate_1.gcode"
PLATE_MD5_NAME = "Metadata/plate_1.gcode.md5"
PLATE_JSON_NAME = "Metadata/plate_1.json"

MACHINE_END_START = "; MACHINE_END_GCODE_START"
EXECUTABLE_BLOCK_START = "; EXECUTABLE_BLOCK_START"
EXECUTABLE_BLOCK_END = "; EXECUTABLE_BLOCK_END"

A1_MACHINE_PROFILE = "Bambu Lab A1 0.4 nozzle"

_PLACEHOLDER = re.compile(r"\{[^{}]*\}")
_SAFE_POS = re.compile(r"^G1\s+X(-?[\d.]+)\s+Y(-?[\d.]+)\s+F18000\b")


class SliceError(RuntimeError):
    """Raised when headless slicing cannot produce a plate archive."""


# ---------------------------------------------------------------------------
# Archive helpers
# ---------------------------------------------------------------------------


def read_archive(archive_bytes: bytes) -> dict[str, bytes]:
    """Return ``name -> bytes`` for every member of a ZIP-based 3MF."""
    if not isinstance(archive_bytes, (bytes, bytearray)):
        raise ValueError("archive content must be bytes")
    try:
        with zipfile.ZipFile(BytesIO(bytes(archive_bytes))) as archive:
            if archive.testzip() is not None:
                raise ValueError("archive is corrupt")
            return {info.filename: archive.read(info) for info in archive.infolist()}
    except zipfile.BadZipFile as exc:
        raise ValueError("not a ZIP-based .gcode.3mf archive") from exc


def rewrite_archive(archive_bytes: bytes, replacements: dict[str, bytes]) -> bytes:
    """Rebuild an archive replacing member payloads while keeping metadata."""
    if not isinstance(archive_bytes, (bytes, bytearray)):
        raise ValueError("archive content must be bytes")
    source = zipfile.ZipFile(BytesIO(bytes(archive_bytes)))
    if source.testzip() is not None:
        raise ValueError("archive is corrupt")
    output = BytesIO()
    with source, zipfile.ZipFile(output, "w") as destination:
        for info in source.infolist():
            data = replacements.get(info.filename)
            if data is None:
                data = source.read(info.filename)
            destination.writestr(info, data)
    return output.getvalue()


def md5_hex(data: bytes) -> str:
    """Uppercase hex MD5, matching BambuStudio's ``.gcode.md5`` companion."""
    return hashlib.md5(data).hexdigest().upper()


def read_plate_gcode(archive_bytes: bytes) -> str:
    entries = read_archive(archive_bytes)
    if PLATE_GCODE_NAME not in entries:
        raise ValueError(f"archive has no {PLATE_GCODE_NAME}")
    return entries[PLATE_GCODE_NAME].decode("utf-8")


def assert_no_placeholders(gcode_text: str) -> None:
    """Reject raw BambuStudio placeholders on executable (non-comment) lines."""
    for number, line in enumerate(gcode_text.splitlines(), start=1):
        if line.lstrip().startswith(";"):
            continue
        match = _PLACEHOLDER.search(line)
        if match:
            raise ValueError(
                f"unevaluated placeholder {match.group(0)} on line {number}"
            )


def find_unique_line(lines: list[str], marker: str) -> int:
    """Return the index of the single line equal to ``marker`` else raise."""
    indexes = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == marker]
    if len(indexes) != 1:
        raise ValueError(f"expected exactly one {marker!r} marker, found {len(indexes)}")
    return indexes[0]


def replace_between_lines(
    text: str, start_marker: str, end_marker: str, replacement: str
) -> str:
    """Replace the content between two unique marker lines, keeping the markers."""
    lines = text.splitlines(keepends=True)
    start = find_unique_line(lines, start_marker)
    end = find_unique_line(lines, end_marker)
    if end <= start:
        raise ValueError(f"{end_marker!r} must follow {start_marker!r}")
    block = replacement if replacement.endswith("\n") else replacement + "\n"
    return "".join(lines[: start + 1]) + block + "".join(lines[end:])


# ---------------------------------------------------------------------------
# Header / config parsing
# ---------------------------------------------------------------------------


def _parse_header(gcode_text: str) -> dict[str, str]:
    header: dict[str, str] = {}
    for line in gcode_text.splitlines():
        stripped = line.strip()
        if stripped == "; HEADER_BLOCK_END":
            break
        if not stripped.startswith(";"):
            continue
        key, separator, value = stripped[1:].partition(":")
        key = key.strip()
        if separator and re.fullmatch(r"[A-Za-z0-9_]+", key):
            header[key] = value.strip()
    return header


def _parse_config(gcode_text: str) -> dict[str, str]:
    config: dict[str, str] = {}
    inside = False
    for line in gcode_text.splitlines():
        stripped = line.strip()
        if stripped == "; CONFIG_BLOCK_START":
            inside = True
            continue
        if stripped == "; CONFIG_BLOCK_END":
            break
        if not inside or not stripped.startswith(";") or "=" not in stripped:
            continue
        key, _, value = stripped[1:].partition("=")
        config[key.strip()] = value.strip()
    return config


def _float_list(value: str) -> list[float]:
    numbers = []
    for item in value.replace(",", " ").split():
        numbers.append(float(item))
    return numbers


def _first_layer_center(
    gcode_text: str, entries: dict[str, bytes], config: dict[str, str]
) -> list[float]:
    if "first_layer_center_no_wipe_tower" in config:
        numbers = _float_list(config["first_layer_center_no_wipe_tower"])
        if len(numbers) >= 2:
            return numbers[:2]

    minimum = config.get("first_layer_print_min")
    size = config.get("first_layer_print_size")
    if minimum and size:
        lower = _float_list(minimum)
        extent = _float_list(size)
        if len(lower) >= 2 and len(extent) >= 2:
            return [lower[0] + extent[0] / 2.0, lower[1] + extent[1] / 2.0]

    plate_json = entries.get(PLATE_JSON_NAME)
    if plate_json:
        try:
            bbox = json.loads(plate_json.decode("utf-8")).get("bbox_all")
        except (ValueError, TypeError):
            bbox = None
        if isinstance(bbox, list) and len(bbox) == 4:
            return [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0]

    for line in gcode_text.splitlines():
        match = _SAFE_POS.match(line.strip())
        if match:
            return [float(match.group(1)), float(match.group(2))]

    raise ValueError("cannot determine first_layer_center_no_wipe_tower")


def frame_values(gcode_text: str, entries: dict[str, bytes]) -> dict[str, Any]:
    """Collect the BambuStudio values the A1 end block needs to evaluate."""
    header = _parse_header(gcode_text)
    config = _parse_config(gcode_text)

    if "max_z_height" not in header:
        raise ValueError("header does not define max_z_height")
    max_layer_z = float(header["max_z_height"])

    spiral_raw = config.get("spiral_mode", "0").strip()
    spiral_mode = spiral_raw not in {"0", "", "false", "False"}

    print_sequence = config.get("print_sequence", "by layer").strip()

    return {
        "max_layer_z": max_layer_z,
        "spiral_mode": spiral_mode,
        "print_sequence": print_sequence,
        "first_layer_center_no_wipe_tower": _first_layer_center(
            gcode_text, entries, config
        ),
    }


# ---------------------------------------------------------------------------
# Pre-sliced fallback
# ---------------------------------------------------------------------------


def inject_end_block(gcode_3mf_bytes: bytes, end_block_template: str) -> bytes:
    """Replace the evaluated stock end block of a sliced A1 archive.

    The span ``; MACHINE_END_GCODE_START`` .. ``; EXECUTABLE_BLOCK_END`` is
    replaced with ``end_block_template`` evaluated against the file's own
    header and config values.  The plate MD5 companion is rewritten.
    """
    if not isinstance(end_block_template, str) or not end_block_template.strip():
        raise ValueError("end_block_template must be non-empty text")

    entries = read_archive(gcode_3mf_bytes)
    if PLATE_GCODE_NAME not in entries:
        raise ValueError(f"archive has no {PLATE_GCODE_NAME}")
    text = entries[PLATE_GCODE_NAME].decode("utf-8")

    values = frame_values(text, entries)
    evaluated = evaluate_end_block(end_block_template, values)

    updated = replace_between_lines(
        text, MACHINE_END_START, EXECUTABLE_BLOCK_END, evaluated
    )
    assert_no_placeholders(updated)

    gcode_bytes = updated.encode("utf-8")
    return rewrite_archive(
        gcode_3mf_bytes,
        {
            PLATE_GCODE_NAME: gcode_bytes,
            PLATE_MD5_NAME: md5_hex(gcode_bytes).encode("ascii"),
        },
    )


# ---------------------------------------------------------------------------
# Headless slicing
# ---------------------------------------------------------------------------


def _profile_roots(cli_path: Path) -> list[Path]:
    roots: list[Path] = []
    override = os.environ.get("BAMBU_PROFILE_ROOT")
    if override:
        roots.append(Path(override))
    for base in (cli_path.parent, cli_path.parent.parent):
        roots.append(base / "resources" / "profiles" / "BBL")
        roots.append(base / "resources" / "profiles")
        roots.append(base / "profiles")
    roots.extend(
        [
            Path("/opt/bambustudio/resources/profiles/BBL"),
            Path("/usr/share/BambuStudio/resources/profiles/BBL"),
            Path.home() / ".config" / "BambuStudio" / "system" / "BBL",
            Path.home() / "Library/Application Support/BambuStudio/system/BBL",
        ]
    )
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.add(root)
            unique.append(root)
    return unique


def _find_profile(name: str, cli_path: Path, kind: str | None = None) -> Path:
    for root in _profile_roots(cli_path):
        if not root.is_dir():
            continue
        candidates = [root / f"{name}.json"]
        if kind:
            candidates.insert(0, root / kind / f"{name}.json")
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        for candidate in root.rglob(f"{name}.json"):
            if candidate.is_file():
                return candidate
    suffix = f" ({kind})" if kind else ""
    raise SliceError(f"installed BambuStudio profile {name!r}{suffix} not found")


def _resolve_profile(value: str, cli_path: Path, kind: str) -> Path:
    direct = Path(value)
    if direct.is_file():
        return direct
    return _find_profile(value, cli_path, kind)


def slice_stl(stl_bytes: bytes, end_block: str) -> bytes:
    """Slice ``stl_bytes`` with the stock A1 profile and return a ``.gcode.3mf``.

    The CLI path comes from ``BAMBU_CLI``.  ``end_block`` (which may still hold
    BambuStudio placeholders) is written into a copy of the CLI's own installed
    ``Bambu Lab A1 0.4 nozzle`` machine profile under ``machine_end_gcode``;
    the profile is passed to the CLI rather than the block appearing as a shell
    argument, so BambuStudio evaluates the placeholders itself.
    """
    if not isinstance(stl_bytes, (bytes, bytearray)):
        raise SliceError("STL content must be bytes")
    if not isinstance(end_block, str) or not end_block.strip():
        raise SliceError("end block must be non-empty text")

    cli_env = os.environ.get("BAMBU_CLI")
    if not cli_env:
        raise SliceError(
            "BAMBU_CLI is not set; upload a pre-sliced .gcode.3mf instead"
        )
    cli_path = Path(cli_env)
    if not cli_path.is_file():
        raise SliceError(
            f"BAMBU_CLI {cli_env!r} does not exist; use the pre-sliced fallback"
        )

    machine_name = os.environ.get("BAMBU_MACHINE_PROFILE", A1_MACHINE_PROFILE)
    machine_path = _find_profile(machine_name, cli_path, "machine")
    try:
        machine = json.loads(machine_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SliceError(f"could not read machine profile {machine_path}") from exc
    if not isinstance(machine, dict):
        raise SliceError(f"machine profile {machine_path} is not a JSON object")

    process_name = os.environ.get("BAMBU_PROCESS_PROFILE") or machine.get(
        "default_print_profile"
    )
    filament_name = os.environ.get("BAMBU_FILAMENT_PROFILE")
    if not filament_name:
        default_filament = machine.get("default_filament_profile")
        if isinstance(default_filament, list) and default_filament:
            filament_name = default_filament[0]
        elif isinstance(default_filament, str):
            filament_name = default_filament
    if not process_name or not filament_name:
        raise SliceError(
            "machine profile does not name default process/filament profiles; "
            "set BAMBU_PROCESS_PROFILE and BAMBU_FILAMENT_PROFILE"
        )
    process_path = _resolve_profile(str(process_name), cli_path, "process")
    filament_path = _resolve_profile(str(filament_name), cli_path, "filament")

    with tempfile.TemporaryDirectory(prefix="autoeject-slice-") as workspace:
        directory = Path(workspace)
        stl_path = directory / "model.stl"
        stl_path.write_bytes(bytes(stl_bytes))
        patched_path = directory / "machine.json"
        machine["machine_end_gcode"] = end_block
        patched_path.write_text(json.dumps(machine, indent=2), encoding="utf-8")
        output_path = directory / "result.gcode.3mf"

        command = [
            str(cli_path),
            "--load-settings",
            f"{patched_path};{process_path}",
            "--load-filaments",
            str(filament_path),
            "--export-3mf",
            str(output_path),
            str(stl_path),
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        except OSError as exc:
            raise SliceError(
                f"could not run BambuStudio CLI: {exc}; "
                "use the pre-sliced .gcode.3mf fallback"
            ) from exc

        if completed.returncode != 0 or not output_path.is_file():
            detail = (completed.stderr or completed.stdout or "").strip()
            raise SliceError(
                "BambuStudio slicing failed; use the pre-sliced .gcode.3mf "
                f"fallback. {detail}".strip()
            )
        return output_path.read_bytes()
