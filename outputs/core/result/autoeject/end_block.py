"""Build and safely evaluate the Factorian Designs A1 end block."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

MIN_BED_TEMP_C = 0
MAX_BED_TEMP_C = 120
MIN_HOLD_S = 0
MAX_HOLD_S = 3600
MIN_CYCLES = 1
MAX_CYCLES = 100
MIN_PUSH_FEEDRATE_MM_MIN = 1
MAX_PUSH_FEEDRATE_MM_MIN = 18000

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "profiles" / "a1_end.gcode"
_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
_ARITHMETIC = re.compile(r"^(max_layer_z)(?:\s*([+-])\s*(\d+(?:\.\d+)?))?$")


@dataclass(frozen=True)
class EjectBlockParams:
    cool_bed_temp_c: int = 25
    cool_hold_s: int = 120
    heat_bed_temp_c: int = 60
    heat_hold_s: int = 60
    heat_cool_cycles: int = 1
    push_feedrate_mm_min: int = 600


def _integer(name: str, value: Any, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _validated_params(params: EjectBlockParams | Mapping[str, Any] | None) -> EjectBlockParams:
    if params is None:
        result = EjectBlockParams()
    elif isinstance(params, EjectBlockParams):
        result = params
    elif isinstance(params, Mapping):
        known = {field.name for field in fields(EjectBlockParams)}
        unknown = set(params) - known
        if unknown:
            raise ValueError(f"Unknown end-block parameter: {sorted(unknown)[0]}")
        try:
            result = EjectBlockParams(**params)
        except TypeError as exc:
            raise ValueError(str(exc)) from exc
    else:
        raise ValueError("params must be an EjectBlockParams or a mapping")

    _integer("cool_bed_temp_c", result.cool_bed_temp_c, MIN_BED_TEMP_C, MAX_BED_TEMP_C)
    _integer("cool_hold_s", result.cool_hold_s, MIN_HOLD_S, MAX_HOLD_S)
    _integer("heat_bed_temp_c", result.heat_bed_temp_c, MIN_BED_TEMP_C, MAX_BED_TEMP_C)
    _integer("heat_hold_s", result.heat_hold_s, MIN_HOLD_S, MAX_HOLD_S)
    _integer("heat_cool_cycles", result.heat_cool_cycles, MIN_CYCLES, MAX_CYCLES)
    _integer(
        "push_feedrate_mm_min",
        result.push_feedrate_mm_min,
        MIN_PUSH_FEEDRATE_MM_MIN,
        MAX_PUSH_FEEDRATE_MM_MIN,
    )
    return result


def build_end_block(params: EjectBlockParams | Mapping[str, Any] | None = None) -> str:
    """Apply user parameters while retaining BambuStudio slicer placeholders."""
    settings = _validated_params(params)
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    cycles = []
    for _ in range(settings.heat_cool_cycles):
        cycles.extend(
            [
                f"M190 S{settings.cool_bed_temp_c} ; wait for configured cool bed temperature",
                f"G4 S{settings.cool_hold_s} ; hold at cool temperature",
                f"M190 S{settings.heat_bed_temp_c} ; wait for configured heated bed temperature",
                f"G4 S{settings.heat_hold_s} ; hold at heated temperature",
            ]
        )
    replacement = "\n".join(
        [
            "; --- ADDED: Special Cooling/Heating Sequence ---",
            *cycles,
            "; --- END Special Cooling/Heating Sequence ---",
            "M140 S0 ; turn off bed",
            "G4 S60 ; wait one minute for bed to cool fully",
            "",
            ";======= Cool Down Done, Start Push Off =============",
        ]
    )
    pattern = re.compile(
        r"; --- ADDED: Special Cooling/Heating Sequence ---.*?"
        r";======= Cool Down Done, Start Push Off =============",
        re.DOTALL,
    )
    block, count = pattern.subn(lambda _: replacement, template)
    if count != 1:
        raise ValueError("A1 end template does not contain exactly one heat/cool sequence")
    block, count = re.subn(
        r"(?m)^G1 Y-0\.5 F300(\s*;.*)$",
        f"G1 Y-0.5 F{settings.push_feedrate_mm_min}\\1",
        block,
    )
    if count != 1:
        raise ValueError("A1 end template does not contain exactly one push move")
    return block


def _number(value: float) -> str:
    return f"{value:.12g}"


def _expression(expression: str, values: Mapping[str, Any]) -> str:
    expression = expression.strip()
    if expression == "first_layer_center_no_wipe_tower[1]":
        try:
            value = values["first_layer_center_no_wipe_tower"][1]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError
            if not math.isfinite(value):
                raise ValueError
            return _number(value)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("Invalid first_layer_center_no_wipe_tower[1]") from exc
    match = _ARITHMETIC.fullmatch(expression)
    if match:
        try:
            value = values["max_layer_z"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError
            value = float(value)
            if not math.isfinite(value):
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid max_layer_z") from exc
        if match.group(2):
            operand = float(match.group(3))
            value = value + operand if match.group(2) == "+" else value - operand
        return _number(value)
    raise ValueError(f"Unsupported BambuStudio placeholder: {{{expression}}}")


def _condition(condition: str, values: Mapping[str, Any]) -> bool:
    compact = re.sub(r"\s+", "", condition)
    if compact == "!spiral_mode&&print_sequence!=\"byobject\"":
        try:
            spiral_mode = values["spiral_mode"]
            print_sequence = values["print_sequence"]
        except KeyError as exc:
            raise ValueError(f"Missing end-block value: {exc.args[0]}") from exc
        if not isinstance(spiral_mode, bool) or not isinstance(print_sequence, str):
            raise ValueError("Invalid spiral_mode or print_sequence")
        return not spiral_mode and print_sequence != "by object"
    if compact in {"(max_layer_z)>41", "(max_layer_z+100.0)<256"}:
        try:
            value = values["max_layer_z"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError
            if not math.isfinite(value):
                raise ValueError
            return value > 41 if compact == "(max_layer_z)>41" else value + 100.0 < 256
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid max_layer_z") from exc
    raise ValueError(f"Unsupported BambuStudio conditional: {{if {condition}}}")


def evaluate_end_block(block: str, values: Mapping[str, Any]) -> str:
    """Evaluate only the expressions and conditionals used by the A1 template.

    Unknown placeholders and malformed conditional nesting are rejected rather
    than being allowed to reach printer G-code.
    """
    if not isinstance(block, str) or not isinstance(values, Mapping):
        raise ValueError("block must be text and values must be a mapping")

    # Validate even placeholders in branches which will not be emitted.
    for match in _PLACEHOLDER.finditer(block):
        expression = match.group(1).strip()
        if expression.startswith("if ") or expression in {"else", "endif"}:
            if expression.startswith("if "):
                _condition(expression[3:], values)
        else:
            _expression(expression, values)

    output: list[str] = []
    # Each stack item is (parent_active, condition, in_else).
    conditions: list[tuple[bool, bool, bool]] = []
    active = True
    for line in block.splitlines(keepends=True):
        stripped = line.strip()
        # Commented template directives remain comments but use the same syntax.
        directive = stripped[1:].strip() if stripped.startswith(";{") else stripped
        if directive.startswith("{if ") and directive.endswith("}"):
            condition = _condition(directive[4:-1], values)
            conditions.append((active, condition, False))
            active = active and condition
        elif directive == "{else}":
            if not conditions or conditions[-1][2]:
                raise ValueError("Unexpected or duplicate {else}")
            parent, condition, _ = conditions.pop()
            conditions.append((parent, condition, True))
            active = parent and not condition
        elif directive == "{endif}":
            if not conditions:
                raise ValueError("Unexpected {endif}")
            parent, _, _ = conditions.pop()
            active = parent
        elif active:
            output.append(_PLACEHOLDER.sub(lambda m: _expression(m.group(1), values), line))
    if conditions:
        raise ValueError("Unclosed {if} block")
    result = "".join(output)
    leftover = _PLACEHOLDER.search(result)
    if leftover:
        raise ValueError(f"Unevaluated placeholder: {leftover.group(0)}")
    return result
