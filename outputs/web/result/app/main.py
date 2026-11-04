"""FastAPI surface for the supervised Bambu Lab A1 auto-eject workflow.

The three endpoints mirror the binding v1 API list and are synchronous: every
request does its work inline and either returns the finished ``.gcode.3mf``
payload or a validation/slicing error.  There is no printer field, no printer
connection, no background job and no acknowledgement step.

Both ``.gcode.3mf`` readers (this module and :mod:`autoeject.slicer`) are
exercised against ``fixtures/real_a1.gcode.3mf`` in ``tests/test_app.py``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import trimesh
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from autoeject.ejectability import check
from autoeject.end_block import EjectBlockParams, build_end_block
from autoeject.loop import loop_3mf
from autoeject.sim import (
    part_bbox_from_gcode,
    simulate,
)
from autoeject.slicer import (
    EXECUTABLE_BLOCK_END,
    MACHINE_END_START,
    SliceError,
    inject_end_block,
    read_plate_gcode,
    slice_stl,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DOWNLOAD_NAME = "autoeject_a1.gcode.3mf"

app = FastAPI(
    title="Auto-eject A1",
    version="1.0",
    description="Supervised N-copy eject jobs for the Bambu Lab A1 (256 x 256 mm).",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_archive(filename: str | None, content: bytes) -> bool:
    """A ``.gcode.3mf`` is a ZIP archive; sniff the magic first, name second."""
    if content[:4] == b"PK\x03\x04":
        return True
    return (filename or "").lower().endswith(".3mf")


def _parse_bbox(raw: str | None) -> list[float] | None:
    if raw is None or not raw.strip():
        return None
    try:
        values = json.loads(raw)
    except ValueError:
        values = [item for item in raw.replace(",", " ").split() if item]
    try:
        numbers = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox must be six numbers") from exc
    if len(numbers) != 6:
        raise ValueError("bbox must be six numbers")
    return numbers


def _first_end_block(gcode_text: str) -> str:
    """Return the first eject span, tolerating an N-copy (repeated) archive."""
    start = gcode_text.find(MACHINE_END_START)
    if start < 0:
        raise ValueError(f"expected at least one {MACHINE_END_START!r} marker")
    end = gcode_text.find(EXECUTABLE_BLOCK_END, start)
    if end < 0:
        raise ValueError(f"expected {EXECUTABLE_BLOCK_END!r} after the end marker")
    return gcode_text[start : end + len(EXECUTABLE_BLOCK_END)]


def _preview(stl_bytes: bytes) -> dict[str, Any]:
    mesh = trimesh.load(
        io.BytesIO(stl_bytes), file_type="stl", force="mesh", process=False
    )
    bounds = mesh.bounds
    return {"bounds": [float(value) for value in bounds.reshape(-1)]}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/check")
async def api_check(
    file: UploadFile = File(...),
    min_base_area_mm2: float | None = Form(None),
    max_tip_ratio: float | None = Form(None),
) -> dict[str, Any]:
    """Measure an STL and return its verdict, reasons and preview box."""
    content = await file.read()
    if _is_archive(file.filename, content):
        raise HTTPException(
            status_code=422,
            detail=(
                "assessment needs an STL; upload the .gcode.3mf to /api/build "
                "and simulate it directly"
            ),
        )
    try:
        report = check(
            content,
            min_base_area_mm2=min_base_area_mm2,
            max_tip_ratio=max_tip_ratio,
        )
        preview = _preview(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = report.to_dict()
    payload["measurements"] = {
        rule["id"]: rule["measured"] for rule in payload["rules"]
    }
    payload["preview"] = preview
    return payload


@app.post("/api/build")
async def _build(
    file: UploadFile = File(...),
    n: int = Form(1),
    cool_bed_temp_c: int = Form(25),
    cool_hold_s: int = Form(120),
    heat_bed_temp_c: int = Form(60),
    heat_hold_s: int = Form(60),
    heat_cool_cycles: int = Form(1),
    push_feedrate_mm_min: int = Form(600),
    min_base_area_mm2: float | None = Form(None),
    max_tip_ratio: float | None = Form(None),
) -> Response:
    """Slice or patch an A1 job and repeat it N times, then download it."""
    content = await file.read()
    try:
        eject_params = EjectBlockParams(
            cool_bed_temp_c=cool_bed_temp_c,
            cool_hold_s=cool_hold_s,
            heat_bed_temp_c=heat_bed_temp_c,
            heat_hold_s=heat_hold_s,
            heat_cool_cycles=heat_cool_cycles,
            push_feedrate_mm_min=push_feedrate_mm_min,
        )
        end_block = build_end_block(eject_params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    warnings: list[dict[str, Any]] = []
    if _is_archive(file.filename, content):
        try:
            result = loop_3mf(inject_end_block(content, end_block), n)
        except (ValueError, SliceError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        try:
            report = check(
                content,
                min_base_area_mm2=min_base_area_mm2,
                max_tip_ratio=max_tip_ratio,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if report.verdict == "fail":
            # A failing verdict blocks the download synchronously.
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Part failed the ejectability assessment; build blocked.",
                    "verdict": report.verdict,
                    "reasons": [
                        rule.reason
                        for rule in report.rules
                        if rule.verdict == "fail"
                    ],
                    "rules": [rule.to_dict() for rule in report.rules],
                },
            )
        warnings = [
            rule.to_dict() for rule in report.rules if rule.verdict == "warn"
        ]
        try:
            sliced = slice_stl(content, end_block)
            result = loop_3mf(sliced, n)
        except (ValueError, SliceError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    headers = {
        "Content-Disposition": f'attachment; filename="{DOWNLOAD_NAME}"',
        "X-Eject-Verdict": "warn" if warnings else "pass",
    }
    return Response(
        content=result,
        media_type="application/octet-stream",
        headers=headers,
    )


@app.post("/api/simulate")
async def api_simulate(
    file: UploadFile = File(...),
    bbox: str | None = Form(None),
) -> dict[str, Any]:
    """Replay eject moves from a plate G-code, end block or archive."""
    content = await file.read()
    try:
        supplied = _parse_bbox(bbox)
        if _is_archive(file.filename, content):
            gcode = read_plate_gcode(content)
            block = _first_end_block(gcode)
            part = supplied if supplied is not None else part_bbox_from_gcode(gcode)
        else:
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("G-code must be UTF-8 text") from exc
            block = (
                _first_end_block(text)
                if MACHINE_END_START in text
                else text
            )
            if supplied is None:
                raise ValueError(
                    "a bounding box is required when simulating a bare end block"
                )
            part = supplied
        report = simulate(block, part)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return report.to_dict()


# The static single page is mounted last so the API routes win.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
