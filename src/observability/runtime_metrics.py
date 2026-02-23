from __future__ import annotations

import threading
from collections import deque
from typing import Any, Deque, Dict, Optional


def _percentile(values: list[float], ratio: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])

    clamped = min(1.0, max(0.0, float(ratio)))
    rank = (len(ordered) - 1) * clamped
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return float(ordered[lower])
    weight = rank - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * weight)


class RuntimeMetrics:
    """In-process rolling runtime metrics for quick observability snapshots."""

    def __init__(self, *, max_samples: int = 2000):
        self.max_samples = max(100, int(max_samples))
        self._latency_ms: Deque[float] = deque(maxlen=self.max_samples)
        self._http_total = 0
        self._http_5xx_total = 0
        self._status_counts: Dict[int, int] = {}
        self._lock = threading.Lock()

    def record_http(self, *, duration_ms: float, status_code: int) -> None:
        safe_duration = max(0.0, float(duration_ms))
        safe_status = int(status_code)

        with self._lock:
            self._http_total += 1
            self._latency_ms.append(safe_duration)
            self._status_counts[safe_status] = (
                int(self._status_counts.get(safe_status, 0)) + 1
            )
            if safe_status >= 500:
                self._http_5xx_total += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            sample = list(self._latency_ms)
            total = int(self._http_total)
            errors_5xx = int(self._http_5xx_total)
            status_counts = {
                str(code): int(count) for code, count in self._status_counts.items()
            }

        p50 = _percentile(sample, 0.50)
        p95 = _percentile(sample, 0.95)
        avg = (sum(sample) / len(sample)) if sample else None
        error_rate = (errors_5xx / total) if total > 0 else 0.0

        return {
            "http_requests_total": total,
            "http_errors_5xx_total": errors_5xx,
            "http_error_rate_5xx": round(error_rate, 6),
            "latency_window_samples": len(sample),
            "http_latency_ms": {
                "avg": round(avg, 3) if avg is not None else None,
                "p50": round(p50, 3) if p50 is not None else None,
                "p95": round(p95, 3) if p95 is not None else None,
            },
            "http_status_counts": status_counts,
        }
