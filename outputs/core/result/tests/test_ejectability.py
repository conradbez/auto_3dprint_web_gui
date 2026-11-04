import trimesh

from autoeject.ejectability import check


def stl(mesh):
    return mesh.export(file_type="stl")


def centered_box(x, y, z):
    mesh = trimesh.creation.box(extents=(x, y, z))
    mesh.apply_translation((128, 128, z / 2))
    return mesh


def rule(report, rule_id):
    return next(item for item in report.rules if item.id == rule_id)


def test_40_mm_cube_warns_only_about_gantry_branch_threshold():
    report = check(stl(centered_box(40, 40, 40)))
    assert report.verdict == "warn"
    assert rule(report, "nozzle_push_height").verdict == "pass"
    assert rule(report, "base_area").measured == 1600
    assert report.to_dict()["rules"][0]["id"] == "nozzle_push_height"


def test_20_mm_cube_warns_and_does_not_fail():
    first = check(stl(centered_box(20, 20, 20)))
    second = check(stl(centered_box(20, 20, 20)))
    assert first.verdict == "warn"
    assert not any(item.verdict == "fail" for item in first.rules)
    assert rule(first, "nozzle_push_height").verdict == "warn"
    assert first.to_dict() == second.to_dict()


def test_tall_thin_rod_fails_tip_ratio():
    report = check(stl(centered_box(10, 10, 100)))
    assert report.verdict == "fail"
    assert rule(report, "tip_ratio").measured == 10
    assert rule(report, "tip_ratio").verdict == "fail"


def test_small_contact_area_fails():
    report = check(stl(centered_box(4, 20, 20)))
    assert rule(report, "base_area").verdict == "fail"


def test_part_off_bed_fails_footprint():
    mesh = centered_box(40, 40, 40)
    mesh.apply_translation((200, 0, 0))
    report = check(stl(mesh))
    assert report.verdict == "fail"
    assert rule(report, "bed_footprint").verdict == "fail"
