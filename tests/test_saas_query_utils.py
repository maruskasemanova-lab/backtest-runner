from __future__ import annotations

from src.services.saas_query_utils import (
    build_jobs_count_query,
    build_run_keys_by_user_query,
    normalize_text_items,
)


def test_normalize_text_items_trims_and_optionally_lowercases() -> None:
    values = [" queued ", "", "RUNNING", None, " done "]

    lowered = normalize_text_items(values, lower=True)
    raw = normalize_text_items(values, lower=False)

    assert lowered == ["queued", "running", "none", "done"]
    assert raw == ["queued", "RUNNING", "None", "done"]


def test_build_jobs_count_query_without_filters() -> None:
    query, args = build_jobs_count_query(statuses=None, job_types=None, user_id=None)

    assert query == "SELECT COUNT(*) AS c FROM jobs"
    assert args == ()


def test_build_jobs_count_query_with_all_filters() -> None:
    query, args = build_jobs_count_query(
        statuses=[" queued ", "RUNNING", ""],
        job_types=["download", "  ", "adaptive"],
        user_id="user-1",
    )

    assert (
        query
        == "SELECT COUNT(*) AS c FROM jobs WHERE user_id = ? AND lower(status) IN (?,?) AND job_type IN (?,?)"
    )
    assert args == ("user-1", "queued", "running", "download", "adaptive")


def test_build_run_keys_by_user_query_requires_non_empty_statuses() -> None:
    assert build_run_keys_by_user_query(user_id="u", statuses=[" ", ""]) is None


def test_build_run_keys_by_user_query_normalizes_statuses() -> None:
    payload = build_run_keys_by_user_query(
        user_id="u-1",
        statuses=["QUEUED", " running "],
    )
    assert payload is not None
    query, args = payload

    assert (
        query
        == "SELECT run_key FROM runs WHERE user_id = ? AND lower(status) IN (?,?)"
    )
    assert args == ("u-1", "queued", "running")
