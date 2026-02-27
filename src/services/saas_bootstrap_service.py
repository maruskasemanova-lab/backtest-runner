from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.observability.runtime_metrics import RuntimeMetrics
from src.services.saas_service import (
    InMemorySlidingWindowLimiter,
    SaaSStateStore,
    SupabaseRunReportsStore,
    SupabaseUserSettingsStore,
    V2Services,
)


@dataclass(frozen=True)
class SaaSBootstrapResult:
    v2_services: V2Services
    run_reports_store: Optional[Any]
    run_reports_source_mode: str
    runtime_metrics: RuntimeMetrics
    supabase_user_settings_store: Optional[SupabaseUserSettingsStore]
    supabase_run_reports_store: Optional[SupabaseRunReportsStore]


def safe_env_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = os.getenv(name)
    try:
        value = int(str(raw).strip()) if raw is not None else int(default)
    except Exception:
        value = int(default)
    return max(min_value, value)


def safe_env_float(name: str, default: float, *, min_value: float = 0.05) -> float:
    raw = os.getenv(name)
    try:
        value = float(str(raw).strip()) if raw is not None else float(default)
    except Exception:
        value = float(default)
    return max(min_value, value)


def parse_bool_value(raw: Any, default: bool = False) -> bool:
    if raw is None:
        return bool(default)
    if isinstance(raw, bool):
        return raw
    token = str(raw).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def load_report_storage_config(*, project_root: Path, logger: Any) -> Dict[str, Any]:
    default_path = project_root / "config" / "report_storage.json"
    raw_path = str(os.getenv("BACKTEST_REPORT_STORAGE_CONFIG_PATH") or "").strip()
    config_path = Path(raw_path).expanduser() if raw_path else default_path
    if not config_path.exists() or not config_path.is_file():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load report storage config %s: %s", config_path, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def build_supabase_user_settings_store(
    *,
    logger: Any,
) -> Optional[SupabaseUserSettingsStore]:
    enabled_raw = (
        str(os.getenv("BACKTEST_SUPABASE_USER_SETTINGS_ENABLED", "0") or "")
        .strip()
        .lower()
    )
    enabled = enabled_raw in {"1", "true", "yes", "on"}
    if not enabled:
        return None

    supabase_url = str(
        os.getenv("BACKTEST_SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "",
    ).strip()
    service_role_key = str(
        os.getenv("BACKTEST_SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or "",
    ).strip()
    table_name = (
        str(
            os.getenv("BACKTEST_SUPABASE_USER_SETTINGS_TABLE", "user_settings") or ""
        ).strip()
        or "user_settings"
    )
    timeout_seconds = safe_env_float(
        "BACKTEST_SUPABASE_USER_SETTINGS_TIMEOUT_SEC",
        8.0,
        min_value=1.0,
    )

    if not supabase_url or not service_role_key:
        logger.warning(
            "Supabase user settings store enabled but missing url/service key; falling back to local SQLite store."
        )
        return None

    try:
        return SupabaseUserSettingsStore(
            supabase_url=supabase_url,
            service_role_key=service_role_key,
            table_name=table_name,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        logger.warning(
            "Failed to initialize Supabase user settings store; falling back to local SQLite store: %s",
            exc,
        )
        return None


def build_supabase_run_reports_store(
    *,
    project_root: Path,
    logger: Any,
) -> Optional[SupabaseRunReportsStore]:
    config = load_report_storage_config(project_root=project_root, logger=logger)
    supabase_cfg = (
        config.get("supabase", {}) if isinstance(config.get("supabase"), dict) else {}
    )
    enabled = parse_bool_value(
        os.getenv("BACKTEST_SUPABASE_RUN_REPORTS_ENABLED"),
        parse_bool_value(supabase_cfg.get("enabled"), False),
    )
    if not enabled:
        return None

    supabase_url = str(
        os.getenv("BACKTEST_SUPABASE_URL")
        or os.getenv("VITE_SUPABASE_URL")
        or supabase_cfg.get("url")
        or "",
    ).strip()
    service_role_key = str(
        os.getenv("BACKTEST_SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or supabase_cfg.get("service_role_key")
        or "",
    ).strip()
    table_name = (
        str(
            os.getenv("BACKTEST_SUPABASE_RUN_REPORTS_TABLE")
            or supabase_cfg.get("table_name")
            or "run_summaries",
        ).strip()
        or "run_summaries"
    )
    default_user_id = (
        str(
            os.getenv("BACKTEST_SUPABASE_RUN_REPORTS_USER_ID")
            or supabase_cfg.get("user_id")
            or "backtest-runner",
        ).strip()
        or "backtest-runner"
    )
    default_tenant_id = str(
        os.getenv("BACKTEST_SUPABASE_RUN_REPORTS_TENANT_ID")
        or supabase_cfg.get("tenant_id")
        or "",
    ).strip()

    timeout_raw = os.getenv("BACKTEST_SUPABASE_RUN_REPORTS_TIMEOUT_SEC")
    if timeout_raw is None:
        timeout_raw = supabase_cfg.get("timeout_seconds", 8.0)
    try:
        timeout_seconds = max(1.0, float(timeout_raw))
    except Exception:
        timeout_seconds = 8.0

    if not supabase_url or not service_role_key:
        logger.warning(
            "Supabase run reports store enabled but missing url/service key; skipping external report persistence."
        )
        return None

    try:
        return SupabaseRunReportsStore(
            supabase_url=supabase_url,
            service_role_key=service_role_key,
            table_name=table_name,
            timeout_seconds=timeout_seconds,
            default_user_id=default_user_id,
            default_tenant_id=default_tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "Failed to initialize Supabase run reports store; skipping external report persistence: %s",
            exc,
        )
        return None


def resolve_run_reports_store(
    *,
    state_store: SaaSStateStore,
    supabase_store: Optional[SupabaseRunReportsStore],
) -> tuple[Optional[Any], str]:
    if supabase_store is not None:
        return supabase_store, "supabase_run_reports"
    return state_store, "sqlite_run_reports"


def bootstrap_saas_runtime(*, logger: Any, project_root: Path) -> SaaSBootstrapResult:
    v2_worker_concurrency = safe_env_int(
        "BACKTEST_V2_WORKER_CONCURRENCY", 4, min_value=1
    )
    v2_max_queue_backlog = safe_env_int(
        "BACKTEST_V2_MAX_QUEUE_BACKLOG", 200, min_value=1
    )
    v2_default_job_max_attempts = safe_env_int(
        "BACKTEST_V2_JOB_MAX_ATTEMPTS", 2, min_value=1
    )
    v2_retry_base_seconds = safe_env_float(
        "BACKTEST_V2_JOB_RETRY_BASE_SECONDS", 0.75, min_value=0.05
    )
    v2_retry_max_delay_seconds = safe_env_float(
        "BACKTEST_V2_JOB_RETRY_MAX_DELAY_SECONDS", 8.0, min_value=0.10
    )
    runtime_metrics_window = safe_env_int(
        "BACKTEST_RUNTIME_METRICS_WINDOW", 2000, min_value=100
    )

    supabase_user_settings_store = build_supabase_user_settings_store(logger=logger)
    supabase_run_reports_store = build_supabase_run_reports_store(
        project_root=project_root,
        logger=logger,
    )
    saas_state_store = SaaSStateStore(
        os.getenv("BACKTEST_SAAS_DB_PATH", "data/saas_state.db")
    )
    run_reports_store, run_reports_source_mode = resolve_run_reports_store(
        state_store=saas_state_store,
        supabase_store=supabase_run_reports_store,
    )

    v2_services = V2Services(
        store=saas_state_store,
        limiter=InMemorySlidingWindowLimiter(default_window_seconds=60),
        internal_strategy_api_url=os.getenv(
            "BACKTEST_INTERNAL_STRATEGY_API_URL", "http://localhost:8001"
        ),
        ads_enabled=str(os.getenv("BACKTEST_ADS_ENABLED", "false")).strip().lower()
        in {"1", "true", "yes", "on"},
        ads_provider=str(os.getenv("BACKTEST_ADS_PROVIDER", "none")).strip().lower()
        or "none",
        ads_placements=[
            item.strip()
            for item in str(
                os.getenv(
                    "BACKTEST_ADS_PLACEMENTS",
                    "dashboard,diagnostics,data-manager,settings",
                )
            ).split(",")
            if item.strip()
        ],
        user_settings_store=supabase_user_settings_store,
        job_semaphore=asyncio.Semaphore(v2_worker_concurrency),
        max_queue_backlog=v2_max_queue_backlog,
        default_job_max_attempts=v2_default_job_max_attempts,
        job_retry_base_seconds=v2_retry_base_seconds,
        job_retry_max_delay_seconds=max(
            v2_retry_base_seconds, v2_retry_max_delay_seconds
        ),
    )

    runtime_metrics = RuntimeMetrics(max_samples=runtime_metrics_window)

    return SaaSBootstrapResult(
        v2_services=v2_services,
        run_reports_store=run_reports_store,
        run_reports_source_mode=run_reports_source_mode,
        runtime_metrics=runtime_metrics,
        supabase_user_settings_store=supabase_user_settings_store,
        supabase_run_reports_store=supabase_run_reports_store,
    )
