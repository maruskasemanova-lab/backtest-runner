from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys


_API_SERVER_PATH = Path(__file__).resolve().parents[1] / "api_server.py"
_PROJECT_ROOT = str(_API_SERVER_PATH.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_API_SERVER_SPEC = importlib.util.spec_from_file_location("api_server_module", _API_SERVER_PATH)
assert _API_SERVER_SPEC is not None and _API_SERVER_SPEC.loader is not None
api_server = importlib.util.module_from_spec(_API_SERVER_SPEC)
_API_SERVER_SPEC.loader.exec_module(api_server)


def test_extract_strategy_params_for_profile_sanitizes_payload() -> None:
    payload = {
        "momentum_flow": {
            "name": "MomentumFlow",
            "display_name": "Momentum Flow",
            "enabled": True,
            "min_confidence": 60.0,
            "allowed_regimes": ["TRENDING", "invalid", "MIXED"],
            "last_signal": {"foo": "bar"},
            "unsupported": {"nested": True},
        },
        "absorption_reversal": {
            "enabled": False,
            "regimes": ["CHOPPY", "MIXED"],
            "rr_ratio": 1.8,
        },
    }

    out = api_server._extract_strategy_params_for_profile(payload)

    assert out["momentum_flow"]["enabled"] is True
    assert out["momentum_flow"]["min_confidence"] == 60.0
    assert out["momentum_flow"]["allowed_regimes"] == ["TRENDING", "MIXED"]
    assert "unsupported" not in out["momentum_flow"]
    assert out["absorption_reversal"]["enabled"] is False
    assert out["absorption_reversal"]["allowed_regimes"] == ["CHOPPY", "MIXED"]


def test_capture_strategy_combo_persists_profile(monkeypatch, tmp_path) -> None:
    temp_aos = tmp_path / "aos_config.json"
    temp_aos.write_text(json.dumps({"version": "1.0.0", "tickers": {}}))
    monkeypatch.setattr(api_server, "AOS_CONFIG_PATH", temp_aos)

    async def _fake_fetch(_strategy_api_url: str):
        return {
            "momentum_flow": {
                "enabled": True,
                "min_confidence": 58.0,
                "allowed_regimes": ["TRENDING", "MIXED"],
            },
            "mean_reversion": {
                "enabled": False,
            },
        }

    monkeypatch.setattr(api_server, "_fetch_remote_strategies", _fake_fetch)

    request = api_server.StrategyComboCaptureRequest(
        ticker="MU",
        profile_name="MU short window v1",
        strategy_api_url="http://localhost:8001",
        set_active=True,
    )
    result = asyncio.run(api_server.capture_strategy_combo(request))

    assert result["success"] is True
    assert result["ticker"] == "MU"
    assert result["profile"]["profile_name"] == "MU short window v1"
    assert result["active_profile_id"] == result["profile"]["profile_id"]
    saved = json.loads(temp_aos.read_text())
    mu_cfg = saved["tickers"]["MU"]
    assert mu_cfg["active_strategy_combo_profile_id"] == result["profile"]["profile_id"]
    assert len(mu_cfg["strategy_combo_profiles"]) == 1
    assert mu_cfg["strategy_combo_profiles"][0]["strategy_params"]["mean_reversion"]["enabled"] is False


def test_apply_strategy_combo_sets_active_and_apply_result(monkeypatch, tmp_path) -> None:
    temp_aos = tmp_path / "aos_config.json"
    temp_aos.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "tickers": {
                    "MU": {
                        "strategy_combo_profiles": [
                            {
                                "profile_id": "combo123",
                                "profile_name": "Combo 123",
                                "created_at": "2026-02-09T20:00:00Z",
                                "updated_at": "2026-02-09T20:00:00Z",
                                "strategy_params": {
                                    "momentum_flow": {"enabled": True, "min_confidence": 57.0}
                                },
                            }
                        ]
                    }
                },
            }
        )
    )
    monkeypatch.setattr(api_server, "AOS_CONFIG_PATH", temp_aos)

    async def _fake_apply(_strategy_api_url: str, strategy_params):
        assert "momentum_flow" in strategy_params
        return {
            "applied_strategies": ["momentum_flow"],
            "failed_strategies": [],
            "applied_count": 1,
            "failed_count": 0,
        }

    monkeypatch.setattr(api_server, "_apply_strategy_param_map", _fake_apply)

    request = api_server.StrategyComboApplyRequest(
        ticker="MU",
        profile_id="combo123",
        strategy_api_url="http://localhost:8001",
        apply_now=True,
    )
    result = asyncio.run(api_server.apply_strategy_combo(request))

    assert result["success"] is True
    assert result["profile_id"] == "combo123"
    assert result["apply_result"]["applied_count"] == 1
    saved = json.loads(temp_aos.read_text())
    assert saved["tickers"]["MU"]["active_strategy_combo_profile_id"] == "combo123"
