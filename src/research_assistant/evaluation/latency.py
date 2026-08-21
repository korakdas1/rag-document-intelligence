"""Latency summaries. Do not report p95 from tiny samples."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from research_assistant.evaluation.metrics import mean, percentile

MIN_SAMPLES_FOR_P90 = 10
MIN_SAMPLES_FOR_P95 = 20


def summarize_latency(values: Sequence[float], *, skip_first: bool = False) -> dict[str, Any]:
    series = list(values)
    cold = series[0] if series else None
    warm = series[1:] if skip_first and len(series) > 1 else series
    payload: dict[str, Any] = {
        "n": len(series),
        "mean_ms": _round(mean(series)),
        "median_ms": _round(percentile(series, 50) if series else None),
        "p90_ms": None,
        "p95_ms": None,
        "min_ms": _round(min(series) if series else None),
        "max_ms": _round(max(series) if series else None),
        "cold_first_ms": _round(cold),
        "warm_n": len(warm),
        "warm_mean_ms": _round(mean(warm) if warm else None),
        "warm_median_ms": _round(percentile(warm, 50) if warm else None),
    }
    if len(series) >= MIN_SAMPLES_FOR_P90:
        payload["p90_ms"] = _round(percentile(series, 90))
    if len(series) >= MIN_SAMPLES_FOR_P95:
        payload["p95_ms"] = _round(percentile(series, 95))
    return payload


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)
