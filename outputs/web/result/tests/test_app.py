"""End-to-end tests for the FastAPI surface, calling the real autoeject core.

Nothing here is mocked across a module boundary: ``TestClient`` drives the real
handlers and those handlers call the real :mod:`autoeject` functions.  There is
no printer, network or BambuStudio dependency.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import trimesh
from fastapi.testclient import TestClient

from app.main import app
from autoeject.slicer import PLATE_GCODE_NAME, PLATE_MD5_NAME, read_archive

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "real_a1.gcode.3mf"

client = TestClient(app)


def _stl(mesh: trimesh.Trimesh) -> bytes:
    return mesh.export(file_type="stl")


def _centered_box(x: float, y: float, z: float) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(x, y, z))
    mesh.apply_translation((128, 128, z / 2))
    return mesh


def test_check_40_mm_cube_returns_warn_verdict():
    response = client.post(
        "/api/check",
        files={"file": ("cube.stl", _stl(_centered_box(40, 40, 40)), "model/stl")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "warn"
    assert payload["measurements"]["base_area"] == 1600
    assert payload["preview"]["bounds"][5] == 40
    assert {rule["id"] for rule in payload["rules"]} >= {
        "nozzle_push_height",
        "gantry_push_branch",
        "base_area",
        "tip_ratio",
        "bed_footprint",
    }


def test_build_real_fixture_n3_returns_three_pushes_and_matching_md5():
    response = client.post(
        "/api/build",
        files={
            "file": (
                "real_a1.gcode.3mf",
                FIXTURE.read_bytes(),
                "application/octet-stream",
            )
        },
        data={"n": "3"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"

    entries = read_archive(response.content)
    gcode = entries[PLATE_GCODE_NAME].decode("utf-8")
    assert gcode.count("G1 Y-0.5 F600") == 3
    recorded = entries[PLATE_MD5_NAME].decode("ascii").strip()
    assert recorded == hashlib.md5(entries[PLATE_GCODE_NAME]).hexdigest().upper()


def test_simulate_generated_job_reports_push_without_collisions():
    built = client.post(
        "/api/build",
        files={
            "file": (
                "real_a1.gcode.3mf",
                FIXTURE.read_bytes(),
                "application/octet-stream",
            )
        },
        data={"n": "3"},
    )
    assert built.status_code == 200

    response = client.post(
        "/api/simulate",
        files={
            "file": (
                "autoeject_a1.gcode.3mf",
                built.content,
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["pushed"] is True
    assert payload["missed_push"] is False
    assert payload["collisions"] == []
    assert len(payload["moves"]) > 0


def test_build_blocks_a_part_off_the_bed_with_a_reason():
    mesh = _centered_box(40, 40, 40)
    mesh.apply_translation((200, 0, 0))
    response = client.post(
        "/api/build",
        files={"file": ("off_bed.stl", _stl(mesh), "model/stl")},
        data={"n": "1"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["verdict"] == "fail"
    assert any("footprint" in reason for reason in payload["reasons"])


def test_check_rejects_an_archive_upload():
    response = client.post(
        "/api/check",
        files={
            "file": (
                "real_a1.gcode.3mf",
                FIXTURE.read_bytes(),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 422


def test_static_index_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Auto-eject A1" in response.text
    assert "three.js" in response.text
