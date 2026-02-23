"""
Centralized runtime settings for data roots and Databento credentials.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config_io import load_json_file, save_json_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "data" / "system_settings.json"
DEFAULT_EXTERNAL_DATA_DIR = Path(
    "/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/databento_data"
)


def _normalize_dirs(raw_value: Any, fallback: List[str]) -> List[str]:
    if not isinstance(raw_value, list):
        raw_value = []
    normalized: List[str] = []
    seen = set()
    for value in raw_value:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if not candidate:
            continue
        resolved = str(Path(candidate).expanduser().resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        normalized.append(resolved)
    if normalized:
        return normalized
    # Keep defaults usable even if they do not exist yet.
    return [str(Path(p).expanduser().resolve()) for p in fallback]


def mask_secret(secret: str) -> str:
    value = str(secret or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


class SystemSettings:
    """Load/save system settings shared by data services and API endpoints."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_SETTINGS_PATH
        self._settings: Dict[str, Any] = {}
        self.reload()
        self._apply_runtime_env()

    def _defaults(self) -> Dict[str, Any]:
        local_ohlcv = PROJECT_ROOT / "data"
        local_l2 = PROJECT_ROOT / "data" / "l2"
        external_ohlcv = DEFAULT_EXTERNAL_DATA_DIR
        external_l2 = DEFAULT_EXTERNAL_DATA_DIR / "l2"
        return {
            "ohlcv_data_dirs": [
                str(local_ohlcv),
                str(external_ohlcv),
            ],
            "l2_data_dirs": [
                str(local_l2),
                str(external_l2),
                str(external_ohlcv),
            ],
            "databento_api_key": "",
        }

    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        defaults = self._defaults()
        return {
            "ohlcv_data_dirs": _normalize_dirs(
                payload.get("ohlcv_data_dirs"), defaults["ohlcv_data_dirs"]
            ),
            "l2_data_dirs": _normalize_dirs(
                payload.get("l2_data_dirs"), defaults["l2_data_dirs"]
            ),
            "databento_api_key": str(payload.get("databento_api_key") or "").strip(),
        }

    def reload(self) -> Dict[str, Any]:
        raw = load_json_file(self.path, default=self._defaults())
        self._settings = self._normalize_payload(raw)
        return dict(self._settings)

    def save(self) -> bool:
        return save_json_file(self.path, self._settings)

    def _apply_runtime_env(self) -> None:
        # Respect shell-provided env first, else hydrate from persisted settings.
        if os.environ.get("DATABENTO_API_KEY"):
            return
        key = self.get_persisted_databento_api_key()
        if key:
            os.environ["DATABENTO_API_KEY"] = key

    def get_persisted_databento_api_key(self) -> str:
        return str(self._settings.get("databento_api_key") or "").strip()

    def resolve_databento_api_key(self) -> str:
        return str(
            os.environ.get("DATABENTO_API_KEY")
            or self.get_persisted_databento_api_key()
        ).strip()

    def set_databento_api_key(self, api_key: str) -> bool:
        key = str(api_key or "").strip()
        self._settings["databento_api_key"] = key
        ok = self.save()
        if ok:
            if key:
                os.environ["DATABENTO_API_KEY"] = key
            elif "DATABENTO_API_KEY" in os.environ:
                # Allow explicit clear from UI.
                del os.environ["DATABENTO_API_KEY"]
        return ok

    def update_data_dirs(
        self,
        ohlcv_data_dirs: Optional[List[str]] = None,
        l2_data_dirs: Optional[List[str]] = None,
    ) -> bool:
        defaults = self._defaults()
        if ohlcv_data_dirs is not None:
            self._settings["ohlcv_data_dirs"] = _normalize_dirs(
                ohlcv_data_dirs, defaults["ohlcv_data_dirs"]
            )
        if l2_data_dirs is not None:
            self._settings["l2_data_dirs"] = _normalize_dirs(
                l2_data_dirs, defaults["l2_data_dirs"]
            )
        return self.save()

    def get_ohlcv_dirs(self, existing_only: bool = False) -> List[Path]:
        paths = [Path(p) for p in self._settings.get("ohlcv_data_dirs", [])]
        if existing_only:
            return [p for p in paths if p.exists()]
        return paths

    def get_l2_dirs(self, existing_only: bool = False) -> List[Path]:
        paths = [Path(p) for p in self._settings.get("l2_data_dirs", [])]
        if existing_only:
            return [p for p in paths if p.exists()]
        return paths

    def primary_ohlcv_dir(self) -> Path:
        dirs = self.get_ohlcv_dirs(existing_only=False)
        return dirs[0] if dirs else (PROJECT_ROOT / "data")

    def primary_l2_dir(self) -> Path:
        dirs = self.get_l2_dirs(existing_only=False)
        return dirs[0] if dirs else (PROJECT_ROOT / "data" / "l2")

    def to_public_dict(self) -> Dict[str, Any]:
        resolved_key = self.resolve_databento_api_key()
        persisted_key = self.get_persisted_databento_api_key()
        return {
            "ohlcv_data_dirs": [
                str(p) for p in self.get_ohlcv_dirs(existing_only=False)
            ],
            "l2_data_dirs": [str(p) for p in self.get_l2_dirs(existing_only=False)],
            "databento_api_key_set": bool(resolved_key),
            "databento_api_key_hint": mask_secret(resolved_key),
            "databento_api_key_source": (
                "env"
                if os.environ.get("DATABENTO_API_KEY")
                else ("settings" if persisted_key else "unset")
            ),
        }
