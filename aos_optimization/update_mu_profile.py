import json
from pathlib import Path

if __name__ == "__main__":
    path = Path(__file__).resolve().parent / "aos_config.json"
    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    mu_config = config.get("tickers", {}).get("MU", {})
    if not mu_config:
        print("MU not found")
        raise SystemExit(0)

    mu_config["max_position_notional_pct"] = 100.0
    mu_config["account_size_usd"] = 10000.0
    mu_config["max_fill_participation_rate"] = 1.0
    mu_config["min_fill_ratio"] = 1.0

    mu_config["context_aware_risk_enabled"] = True
    mu_config["context_risk_trailing_tighten_zone"] = 0.20
    mu_config["context_risk_min_effective_rr"] = 0.5

    mu_config["intraday_levels_enabled"] = True
    mu_config["intraday_levels_spike_detection_enabled"] = True
    mu_config["intraday_levels_gap_analysis_enabled"] = True
    mu_config["intraday_levels_entry_quality_enabled"] = True

    # General tweaks to get a good win rate
    mu_config["adverse_flow_exit_enabled"] = True
    mu_config["adverse_flow_threshold"] = 0.15

    active_id = mu_config.get("active_unified_profile_id")
    print(f"Updating MU profile {active_id}")

    for profile in mu_config.get("unified_profiles", []):
        if profile.get("profile_id") == active_id:
            sp = profile.get("strategy_profile", {})
            target_strategy = "vwap_magnet"

            for s_name, s_params in sp.get("strategy_params", {}).items():
                if s_name == target_strategy:
                    s_params["enabled"] = True
                    s_params["allowed_regimes"] = ["TRENDING", "MIXED", "CHOPPY"]

                    s_params["min_distance_pct"] = 0.45
                    s_params["max_distance_pct"] = 2.8
                    s_params["bars_since_vwap_threshold"] = 6
                    s_params["volume_confirm"] = True
                    s_params["volume_stop_pct"] = 0.7
                    s_params["min_confidence"] = 55.0

                    s_params["atr_stop_multiplier"] = 1.8
                    s_params["rr_ratio"] = 2.0
                    s_params["trailing_stop_pct"] = 0.4
                else:
                    s_params["enabled"] = False

            sp["strategy_selection_mode"] = "all_enabled"
            sp["max_active_strategies"] = 1
            sp["trading_hours"] = [9, 10, 11, 12, 13, 14, 15]

            ep = profile.get("execution_profile", {})
            if not isinstance(ep, dict):
                ep = {}
            positioning = ep.get("positioning", {})
            if not isinstance(positioning, dict):
                positioning = {}
            positioning["max_position_notional_pct"] = 100.0
            positioning["max_fill_participation_rate"] = 1.0
            positioning["min_fill_ratio"] = 1.0
            positioning["context_aware_risk_enabled"] = True
            positioning["context_risk_min_effective_rr"] = 0.5
            ep["positioning"] = positioning
            profile["execution_profile"] = ep

            if "adaptive_candidate" in sp:
                ac = sp["adaptive_candidate"]
                ac["strategy_selection_mode"] = "all_enabled"
                ac["max_active_strategies"] = 1
                ac["enabled_strategies"] = [target_strategy]

            break

    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
