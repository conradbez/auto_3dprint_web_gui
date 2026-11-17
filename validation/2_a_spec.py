"""Schema check for spec: the agent downstream reads these fields blindly."""
import json

REQUIRED = ["features", "ejectability_rules", "eject_block_params", "api", "out_of_scope", "open_questions"]


def validate(prompt: str, result):
    data = json.loads(result) if isinstance(result, str) else result
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError(f"spec missing keys: {missing}")
    for f in data["features"]:
        if not f.get("acceptance"):
            raise ValueError(f"feature {f.get('id')} has no acceptance checks")
    return data
