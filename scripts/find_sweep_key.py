import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_input_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser()

    direct = REPO_ROOT / "response.json"
    if direct.exists():
        return direct

    artifacts_root = Path("/tmp/backtest-runner-artifacts")
    matches = sorted(artifacts_root.glob("**/response.json"))
    if matches:
        return matches[-1]

    raise FileNotFoundError(
        "response.json not found; pass a path explicitly as the first argument"
    )


with resolve_input_path().open("r", encoding="utf-8") as f:
    data = json.load(f)


def find_paths(obj, target_key, current_path=""):
    paths = []
    if isinstance(obj, dict):
        if target_key in obj:
            paths.append(current_path)
        for k, v in obj.items():
            paths.extend(find_paths(v, target_key, f"{current_path}['{k}']"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            paths.extend(find_paths(v, target_key, f"{current_path}[{i}]"))
    return paths


paths = set(find_paths(data, "sweep_detected"))
if not paths:
    print(f"Key 'sweep_detected' not found anywhere in response.json")
else:
    print(
        f"Found 'sweep_detected' at the following paths (showing up to 5 unique path structures):"
    )
    # Simplify paths for output (e.g. replace indices with [*])
    import re

    simplified_paths = {re.sub(r"\[\d+\]", "[*]", p) for p in paths}
    for p in list(simplified_paths)[:5]:
        print(p)
