"""Repeat an already sliced A1 executable block to print N copies in one job."""

from __future__ import annotations

from .slicer import (
    EXECUTABLE_BLOCK_END,
    EXECUTABLE_BLOCK_START,
    PLATE_GCODE_NAME,
    PLATE_MD5_NAME,
    assert_no_placeholders,
    find_unique_line,
    md5_hex,
    read_archive,
    rewrite_archive,
)

MIN_COPIES = 1
MAX_COPIES = 100


def _copies(n: int) -> int:
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError("n must be an integer")
    if not MIN_COPIES <= n <= MAX_COPIES:
        raise ValueError(f"n must be between {MIN_COPIES} and {MAX_COPIES}")
    return n


def loop_3mf(gcode_3mf_bytes: bytes, n: int) -> bytes:
    """Repeat the ``; EXECUTABLE_BLOCK_START``..``; EXECUTABLE_BLOCK_END`` body.

    The body already contains the machine start, the print, the cooldown/eject
    sequence and the machine end, so repeating it restores the starting
    temperatures and initial conditions before every copy.  The plate MD5
    companion is rewritten and raw placeholders on executable lines are
    rejected.
    """
    count = _copies(n)

    entries = read_archive(gcode_3mf_bytes)
    if PLATE_GCODE_NAME not in entries:
        raise ValueError(f"archive has no {PLATE_GCODE_NAME}")
    text = entries[PLATE_GCODE_NAME].decode("utf-8")

    lines = text.splitlines(keepends=True)
    start = find_unique_line(lines, EXECUTABLE_BLOCK_START)
    end = find_unique_line(lines, EXECUTABLE_BLOCK_END)
    if end <= start:
        raise ValueError(f"{EXECUTABLE_BLOCK_END!r} must follow {EXECUTABLE_BLOCK_START!r}")
    body = lines[start + 1 : end]
    if not body:
        raise ValueError("executable block is empty")

    updated = "".join(lines[: start + 1] + body * count + lines[end:])
    assert_no_placeholders(updated)

    gcode_bytes = updated.encode("utf-8")
    return rewrite_archive(
        gcode_3mf_bytes,
        {
            PLATE_GCODE_NAME: gcode_bytes,
            PLATE_MD5_NAME: md5_hex(gcode_bytes).encode("ascii"),
        },
    )
