from __future__ import annotations

import os
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Union


@dataclass(frozen=True)
class LocalConfigService:
    """Resolve/load/save runtime JSON configs with writable-path fallback logic."""

    default_aos_path: Path
    default_positioning_path: Path
    load_json_file: Callable[[Path, Dict[str, Any]], Dict[str, Any]]
    save_json_file: Callable[[Path, Dict[str, Any]], bool]
    positioning_config_keys: Iterable[str]
    logger: Any

    def resolve_aos_config_path(
        self,
        aos_config_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        return self._resolve_config_path(
            explicit_path=aos_config_path,
            env_name="BACKTEST_AOS_CONFIG_PATH",
            default_path=self.default_aos_path,
            filename="aos_config.json",
            default_payload={"version": "1.0.0", "tickers": {}},
        )

    def load_aos_config(
        self,
        aos_config_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        path = self.resolve_aos_config_path(aos_config_path)
        config = self.load_json_file(path, default={"version": "1.0.0", "tickers": {}})

        tickers_dir = path.parent / "tickers"
        if "tickers" not in config or not isinstance(config["tickers"], dict):
            config["tickers"] = {}

        if tickers_dir.exists() and tickers_dir.is_dir():
            for ticker_file in tickers_dir.glob("*.json"):
                ticker = ticker_file.stem.upper()
                try:
                    ticker_data = self.load_json_file(ticker_file, default={})
                    config["tickers"][ticker] = ticker_data
                except Exception as e:
                    self.logger.error(
                        f"Failed to load ticker config from {ticker_file}: {e}"
                    )

        return config

    def save_aos_config(
        self,
        config: Dict[str, Any],
        aos_config_path: Optional[Union[str, Path]] = None,
    ) -> bool:
        path = self.resolve_aos_config_path(aos_config_path)

        config_to_save = dict(config)
        tickers = config_to_save.pop("tickers", {})
        config_to_save["tickers"] = {}

        tickers_dir = path.parent / "tickers"
        tickers_dir.mkdir(parents=True, exist_ok=True)

        success = True
        for ticker, ticker_data in tickers.items():
            if isinstance(ticker_data, dict):
                ticker_file = tickers_dir / f"{ticker.upper()}.json"
                if not self.save_json_file(ticker_file, payload=ticker_data):
                    self.logger.error(f"Failed to save ticker config to {ticker_file}")
                    success = False

        ok = self.save_json_file(path, payload=config_to_save)
        if not ok:
            self.logger.error("Failed to save base AOS config: %s", path)
            success = False

        config_to_save["tickers"] = tickers
        return success

    def resolve_positioning_config_path(
        self,
        positioning_config_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        return self._resolve_config_path(
            explicit_path=positioning_config_path,
            env_name="BACKTEST_POSITIONING_CONFIG_PATH",
            default_path=self.default_positioning_path,
            filename="positioning_config.json",
            default_payload={"version": "1.0.0", "tickers": {}},
        )

    def load_positioning_config(
        self,
        positioning_config_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        path = self.resolve_positioning_config_path(positioning_config_path)
        return self.load_json_file(path, default={"version": "1.0.0", "tickers": {}})

    def save_positioning_config(
        self,
        config: Dict[str, Any],
        positioning_config_path: Optional[Union[str, Path]] = None,
    ) -> bool:
        path = self.resolve_positioning_config_path(positioning_config_path)
        ok = self.save_json_file(path, payload=config)
        if not ok:
            self.logger.error("Failed to save positioning config: %s", path)
        return ok

    def get_ticker_positioning_config(
        self,
        ticker: str,
        positioning_config: Optional[Dict[str, Any]] = None,
        positioning_config_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        cfg = (
            positioning_config
            if isinstance(positioning_config, dict)
            else self.load_positioning_config(positioning_config_path)
        )
        tickers = cfg.get("tickers", {}) if isinstance(cfg, dict) else {}
        if not isinstance(tickers, dict):
            return {}
        raw = tickers.get(str(ticker or "").upper(), {})
        return dict(raw) if isinstance(raw, dict) else {}

    def merge_positioning_into_aos_snapshot(
        self,
        aos_config: Dict[str, Any],
        positioning_config: Optional[Dict[str, Any]] = None,
        positioning_config_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        merged = copy.deepcopy(aos_config if isinstance(aos_config, dict) else {})
        tickers = merged.get("tickers")
        if not isinstance(tickers, dict):
            tickers = {}
            merged["tickers"] = tickers

        pos_cfg = (
            positioning_config
            if isinstance(positioning_config, dict)
            else self.load_positioning_config(positioning_config_path)
        )
        pos_tickers = pos_cfg.get("tickers", {}) if isinstance(pos_cfg, dict) else {}
        if not isinstance(pos_tickers, dict):
            pos_tickers = {}

        for ticker, ticker_cfg in list(tickers.items()):
            if not isinstance(ticker_cfg, dict):
                continue
            legacy = {}
            for key in self.positioning_config_keys:
                if key in ticker_cfg:
                    legacy[key] = ticker_cfg.get(key)
            if legacy:
                current = pos_tickers.get(ticker, {})
                if not isinstance(current, dict):
                    current = {}
                merged_legacy = dict(legacy)
                merged_legacy.update(current)
                pos_tickers[ticker] = merged_legacy

        for ticker, p_cfg in pos_tickers.items():
            if not isinstance(p_cfg, dict):
                continue
            base = tickers.get(ticker, {})
            if not isinstance(base, dict):
                base = {}
            overlay = dict(base)
            overlay["positioning"] = dict(p_cfg)
            tickers[ticker] = overlay

        return merged

    def _resolve_config_path(
        self,
        *,
        explicit_path: Optional[Union[str, Path]],
        env_name: str,
        default_path: Path,
        filename: str,
        default_payload: Dict[str, Any],
    ) -> Path:
        if explicit_path is not None:
            raw = str(explicit_path).strip()
            if raw:
                return self._resolve_input_path(raw)

        env_raw = str(os.getenv(env_name, "") or "").strip()
        if env_raw:
            resolved = self._resolve_input_path(env_raw)
            self._mkdir_parents(resolved)
            if not resolved.exists():
                self._seed_from_default(
                    target=resolved,
                    source=default_path,
                    default_payload=default_payload,
                )
            return resolved

        self._mkdir_parents(default_path)
        if os.access(default_path.parent, os.W_OK):
            return default_path

        runtime_dir = str(
            os.getenv("BACKTEST_RUNTIME_CONFIG_DIR", "/tmp/backtest-runner-config")
            or "/tmp/backtest-runner-config"
        ).strip()
        runtime_path = (Path(runtime_dir).expanduser() / filename).resolve()
        self._mkdir_parents(runtime_path)
        if not runtime_path.exists():
            self._seed_from_default(
                target=runtime_path,
                source=default_path,
                default_payload=default_payload,
            )
        return runtime_path

    @staticmethod
    def _resolve_input_path(raw: str) -> Path:
        path = Path(raw).expanduser()
        return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()

    @staticmethod
    def _mkdir_parents(path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _seed_from_default(
        self,
        *,
        target: Path,
        source: Path,
        default_payload: Dict[str, Any],
    ) -> None:
        seed = self.load_json_file(source, default=default_payload)
        self.save_json_file(target, payload=seed)
