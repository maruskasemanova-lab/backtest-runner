from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass(frozen=True)
class HistoryQuery:
    safe_ticker: str
    run_id_exact_filter: str
    run_id_contains_filter: str
    requested_profile_id: str
    include_multi_day: bool
    include_zero_trade_runs: bool


@dataclass
class HistoryAccumulator:
    day_rows: List[Dict[str, object]] = field(default_factory=list)
    matched_reports: int = 0
    scanned_reports: int = 0
    skipped_invalid: int = 0
    run_latest_saved_at: Dict[str, Optional[str]] = field(default_factory=dict)
    history_profile_names: Dict[str, Set[str]] = field(default_factory=dict)
    seen_run_identity_keys: Set[str] = field(default_factory=set)

    def note_invalid_report(self) -> None:
        self.scanned_reports += 1
        self.skipped_invalid += 1

    def note_scanned_report(self) -> None:
        self.scanned_reports += 1

    def note_matched_rows(self, rows: List[Dict[str, object]]) -> None:
        self.day_rows.extend(rows)
        self.matched_reports += 1

    def remember_run_saved_at(
        self, *, run_id: str, normalized_saved_at: Optional[str]
    ) -> None:
        current_latest = str(self.run_latest_saved_at.get(run_id) or "")
        if normalized_saved_at and normalized_saved_at > current_latest:
            self.run_latest_saved_at[run_id] = normalized_saved_at
        elif run_id not in self.run_latest_saved_at:
            self.run_latest_saved_at[run_id] = normalized_saved_at

    def remember_profile_name(
        self, *, profile_id: str, profile_name: Optional[str]
    ) -> None:
        if not profile_id:
            return
        self.history_profile_names.setdefault(profile_id, set())
        if profile_name:
            self.history_profile_names[profile_id].add(profile_name)

    def already_seen_identity(self, identity_key: str) -> bool:
        if not identity_key:
            return False
        if identity_key in self.seen_run_identity_keys:
            return True
        self.seen_run_identity_keys.add(identity_key)
        return False
