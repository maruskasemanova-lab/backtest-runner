from __future__ import annotations

from typing import Any, Iterable, Optional, Tuple


def normalize_text_items(
    values: Optional[Iterable[Any]],
    *,
    lower: bool,
) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for item in values:
        text = str(item).strip()
        if not text:
            continue
        normalized.append(text.lower() if lower else text)
    return normalized


def build_jobs_count_query(
    *,
    statuses: Optional[Iterable[str]],
    job_types: Optional[Iterable[str]],
    user_id: Optional[str],
) -> Tuple[str, tuple[Any, ...]]:
    args: list[Any] = []
    clauses: list[str] = []

    if user_id is not None:
        clauses.append("user_id = ?")
        args.append(str(user_id))

    normalized_statuses = normalize_text_items(statuses, lower=True)
    if normalized_statuses:
        placeholders = ",".join("?" for _ in normalized_statuses)
        clauses.append(f"lower(status) IN ({placeholders})")
        args.extend(normalized_statuses)

    normalized_types = normalize_text_items(job_types, lower=False)
    if normalized_types:
        placeholders = ",".join("?" for _ in normalized_types)
        clauses.append(f"job_type IN ({placeholders})")
        args.extend(normalized_types)

    query = "SELECT COUNT(*) AS c FROM jobs"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    return query, tuple(args)


def build_run_keys_by_user_query(
    *,
    user_id: str,
    statuses: Iterable[str],
) -> Optional[Tuple[str, tuple[Any, ...]]]:
    normalized_statuses = normalize_text_items(statuses, lower=True)
    if not normalized_statuses:
        return None
    placeholders = ",".join("?" for _ in normalized_statuses)
    query = (
        "SELECT run_key FROM runs WHERE user_id = ? "
        f"AND lower(status) IN ({placeholders})"
    )
    args: tuple[Any, ...] = (user_id, *normalized_statuses)
    return query, args
