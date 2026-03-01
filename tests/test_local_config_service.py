from pathlib import Path
import json

from src.config_io import load_json_file, save_json_file
from src.services.local_config_service import LocalConfigService


class _LoggerStub:
    def error(self, *args, **kwargs):
        return None


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def test_load_aos_config_falls_back_to_default_tickers_and_runtime_overrides(tmp_path):
    default_aos = tmp_path / "default" / "aos_config.json"
    runtime_aos = tmp_path / "runtime" / "aos_config.json"
    default_tickers_dir = default_aos.parent / "tickers"
    runtime_tickers_dir = runtime_aos.parent / "tickers"

    _write_json(default_aos, {"version": "1.0.0", "tickers": {}})
    _write_json(runtime_aos, {"version": "1.0.0", "tickers": {}})
    _write_json(
        default_tickers_dir / "MU.json",
        {
            "notes": "default-mu",
            "unified_profiles": [{"profile_id": "ctx050", "profile_name": "ctx050"}],
        },
    )
    _write_json(
        default_tickers_dir / "GOOGL.json",
        {
            "notes": "default-googl",
            "unified_profiles": [{"profile_id": "ctx050", "profile_name": "ctx050"}],
        },
    )

    service = LocalConfigService(
        default_aos_path=default_aos,
        default_positioning_path=tmp_path / "default" / "positioning_config.json",
        load_json_file=load_json_file,
        save_json_file=save_json_file,
        positioning_config_keys=(),
        logger=_LoggerStub(),
    )

    loaded = service.load_aos_config(runtime_aos)
    assert loaded["tickers"]["MU"]["notes"] == "default-mu"
    assert loaded["tickers"]["GOOGL"]["notes"] == "default-googl"
    assert loaded["tickers"]["MU"]["unified_profiles"][0]["profile_id"] == "ctx050"

    _write_json(
        runtime_tickers_dir / "MU.json",
        {
            "notes": "runtime-mu",
            "unified_profiles": [{"profile_id": "ctx051", "profile_name": "ctx051"}],
        },
    )
    loaded_after_runtime = service.load_aos_config(runtime_aos)
    assert loaded_after_runtime["tickers"]["MU"]["notes"] == "runtime-mu"
    assert (
        loaded_after_runtime["tickers"]["MU"]["unified_profiles"][0]["profile_id"]
        == "ctx051"
    )
    assert loaded_after_runtime["tickers"]["GOOGL"]["notes"] == "default-googl"
