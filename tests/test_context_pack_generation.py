from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


def _load_generator_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / "generate_context_pack.py"
    spec = importlib.util.spec_from_file_location("generate_context_pack", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_python_metadata_symbols_and_routes(tmp_path: Path) -> None:
    module = _load_generator_module()
    sample = tmp_path / "sample_api.py"
    sample.write_text(
        """
class Demo:
    pass


def helper():
    return 1


@app.get("/health")
async def health():
    return {"ok": True}
""".strip()
    )

    meta = module.extract_python_metadata(sample)
    symbol_names = {item["name"] for item in meta["symbols"]}
    assert "Demo" in symbol_names
    assert "helper" in symbol_names
    assert "health" in symbol_names

    assert len(meta["routes"]) == 1
    route = meta["routes"][0]
    assert route["method"] == "GET"
    assert route["path"] == "/health"
    assert route["handler"] == "health"


def test_build_machine_index_collects_routes(tmp_path: Path) -> None:
    module = _load_generator_module()
    sample = tmp_path / "sample_api.py"
    sample.write_text(
        """
@app.post("/do")
def do_it():
    return {"ok": True}
""".strip()
    )

    config = {
        "version": 2,
        "project": {"name": "X"},
        "domains": [
            {
                "id": "orchestration",
                "title": "Orchestration",
                "files": [str(sample)],
                "depends_on": [],
                "entrypoints": [],
                "change_checks": [],
                "critical_invariants": ["a"],
                "tests": ["tests/x.py"],
            }
        ],
    }

    machine = module.build_machine_index(config)
    assert len(machine["domains"]) == 1
    assert machine["domains"][0]["files"][0]["exists"] is True
    assert len(machine["route_catalog"]) == 1
    assert machine["route_catalog"][0]["method"] == "POST"
    assert machine["route_catalog"][0]["path"] == "/do"


def test_generate_context_pack_smoke_outputs_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["python3", "scripts/generate_context_pack.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    expected = [
        root / "bmad/context/generated/00-index.md",
        root / "bmad/context/generated/00-machine-index.json",
        root / "bmad/context/generated/00-endpoint-map.md",
        root / "bmad/context/generated/orchestration.md",
        root / "bmad/context/generated/strategy-engine.md",
        root / "bmad/context/generated/data-l2.md",
        root / "bmad/context/generated/optimization-validation.md",
        root / "bmad/context/generated/frontend.md",
    ]
    for path in expected:
        assert path.exists(), f"Missing generated artifact: {path}"
        assert path.stat().st_size > 0, f"Empty generated artifact: {path}"
