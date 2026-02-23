import json

with open("response.json", "r") as f:
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
