#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.aos_config import POSITIONING_CONFIG_KEYS
from src.config_io import load_json_file, save_json_file
from src.services.file_store_migration_service import (
    ensure_primary_config_snapshots,
    migrate_aos_history_jsonl_to_store,
    migrate_reports_to_run_reports_store,
    sync_live_trader_artifacts_to_store,
)
from src.services.local_config_service import LocalConfigService
from src.services.saas_bootstrap_service import bootstrap_saas_runtime


def _build_local_config_service(project_root: Path, logger: Any) -> LocalConfigService:
    return LocalConfigService(
        default_aos_path=project_root / "aos_optimization" / "aos_config.json",
        default_positioning_path=project_root
        / "aos_optimization"
        / "positioning_config.json",
        load_json_file=load_json_file,
        save_json_file=save_json_file,
        positioning_config_keys=POSITIONING_CONFIG_KEYS,
        logger=logger,
    )


def run_migration(
    *,
    project_root: Path,
    reports_dir: Path,
    artifacts_dir: Path,
    aos_history_path: Path,
    overwrite_reports: bool,
    max_report_files: int | None,
    logger: Any,
) -> Dict[str, Any]:
    bootstrap = bootstrap_saas_runtime(logger=logger, project_root=project_root)
    state_store = bootstrap.v2_services.store
    run_reports_store = bootstrap.run_reports_store or state_store

    local_cfg = _build_local_config_service(project_root, logger)
    config_stats = ensure_primary_config_snapshots(
        store=state_store,
        load_aos_config=lambda: local_cfg.load_aos_config(None),
        load_positioning_config=lambda: local_cfg.load_positioning_config(None),
        logger=logger,
    )
    aos_history_stats = migrate_aos_history_jsonl_to_store(
        history_path=aos_history_path,
        store=state_store,
        logger=logger,
    )
    reports_stats = migrate_reports_to_run_reports_store(
        reports_dir=reports_dir,
        run_reports_store=run_reports_store,
        logger=logger,
        overwrite_existing=overwrite_reports,
        max_files=max_report_files,
    )
    live_stats = sync_live_trader_artifacts_to_store(
        artifacts_dir=artifacts_dir,
        store=state_store,
        logger=logger,
    )
    return {
        "db_path": str(getattr(state_store, "db_path", "")),
        "run_reports_source_mode": bootstrap.run_reports_source_mode,
        "reports_dir": str(reports_dir),
        "artifacts_dir": str(artifacts_dir),
        "aos_history_path": str(aos_history_path),
        "config_stats": config_stats,
        "aos_history_stats": aos_history_stats,
        "reports_stats": reports_stats,
        "live_stats": live_stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy file-backed app artifacts into DB-backed stores.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root path (default: current directory).",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Path to legacy reports directory.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="../ibkr-realtime-trader/artifacts",
        help="Path to live-trader artifacts directory.",
    )
    parser.add_argument(
        "--aos-history",
        default="aos_optimization/aos_history.jsonl",
        help="Path to legacy AOS history jsonl.",
    )
    parser.add_argument(
        "--overwrite-existing-reports",
        action="store_true",
        help="Overwrite existing run summaries with migrated report payloads.",
    )
    parser.add_argument(
        "--max-report-files",
        type=int,
        default=None,
        help="Optional cap for number of JSON report files to scan.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("migrate_file_storage_to_db")

    project_root = Path(args.project_root).expanduser().resolve()
    reports_dir = Path(args.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = (project_root / reports_dir).resolve()
    artifacts_dir = Path(args.artifacts_dir)
    if not artifacts_dir.is_absolute():
        artifacts_dir = (project_root / artifacts_dir).resolve()
    aos_history = Path(args.aos_history)
    if not aos_history.is_absolute():
        aos_history = (project_root / aos_history).resolve()

    result = run_migration(
        project_root=project_root,
        reports_dir=reports_dir,
        artifacts_dir=artifacts_dir,
        aos_history_path=aos_history,
        overwrite_reports=bool(args.overwrite_existing_reports),
        max_report_files=args.max_report_files,
        logger=logger,
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
