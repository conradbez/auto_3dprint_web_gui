import pytest

from autoeject.end_block import EjectBlockParams, build_end_block, evaluate_end_block


VALUES = {
    "max_layer_z": 20.08,
    "first_layer_center_no_wipe_tower": [128.0, 128.0],
    "spiral_mode": False,
    "print_sequence": "by layer",
}


def test_build_substitutes_parameters_and_retains_slicer_placeholders():
    block = build_end_block(
        EjectBlockParams(
            cool_bed_temp_c=22,
            cool_hold_s=90,
            heat_bed_temp_c=65,
            heat_hold_s=45,
            heat_cool_cycles=2,
            push_feedrate_mm_min=450,
        )
    )
    assert block.count("M190 S22 ;") == 2
    assert block.count("M190 S65 ;") == 2
    assert block.count("G4 S90 ;") == 2
    assert block.count("G4 S45 ;") == 2
    assert "G1 Y-0.5 F450" in block
    assert "{if (max_layer_z ) > 41}" in block
    assert "{max_layer_z + 0.5}" in block


@pytest.mark.parametrize(
    "params",
    [
        {"heat_cool_cycles": 0},
        {"cool_bed_temp_c": -1},
        {"heat_bed_temp_c": 121},
        {"cool_hold_s": -1},
        {"heat_hold_s": 3601},
        {"push_feedrate_mm_min": 0},
        {"unknown": 1},
    ],
)
def test_invalid_parameters_fail(params):
    with pytest.raises(ValueError):
        build_end_block(params)


def test_20_08_evaluates_nozzle_push_with_z1():
    result = evaluate_end_block(build_end_block(), VALUES)
    assert "G1 Z1 F600" in result
    assert "G1 Z-19.92 F600" not in result
    assert "G1 Z20.58 F900" in result
    for line in result.splitlines():
        if not line.lstrip().startswith(";"):
            assert "{" not in line


def test_60_evaluates_gantry_push_with_z20():
    result = evaluate_end_block(build_end_block(), {**VALUES, "max_layer_z": 60})
    assert "G1 Z20 F600" in result
    assert "G1 Z60.5 F900" in result


def test_unknown_placeholder_fails_closed_even_in_unused_branch():
    block = "{if (max_layer_z ) > 41}\nG1 X{unknown}\n{else}\nG1 X0\n{endif}\n"
    with pytest.raises(ValueError, match="Unsupported"):
        evaluate_end_block(block, VALUES)
