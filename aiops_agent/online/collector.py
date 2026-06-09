"""Prometheus-backed realtime data collection for online diagnosis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from benchmark.prometheus_client import PrometheusClient

from aiops_agent.offline.loader import load_dataset
from aiops_agent.offline.models import DatasetArtifacts


class OnlineMetricsCollector:
    """Collect trigger metrics and feature windows from Prometheus."""

    def __init__(
        self,
        prometheus_url: str,
        queries_path: str | Path,
        dataset_root: str | Path,
    ) -> None:
        self.client = PrometheusClient(prometheus_url)
        self.queries_path = Path(queries_path)
        self.dataset = load_dataset(dataset_root)
        self.queries = self._load_queries(self.queries_path)

    @staticmethod
    def _load_queries(path: Path) -> dict[str, str]:
        content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        queries = content.get("queries")
        if not isinstance(queries, dict) or not queries:
            raise ValueError(f"Prometheus query config is invalid or empty: {path}")
        return queries

    def check_reachable(self) -> bool:
        return self.client.check_reachable()

    def collect_trigger_metrics(
        self,
        feature_names: list[str],
        end_time: datetime | None = None,
        window_seconds: int = 60,
        step_seconds: int = 5,
    ) -> dict[str, float | None]:
        """Collect latest values for a small set of trigger metrics."""

        end = end_time or datetime.now(timezone.utc)
        start = end - timedelta(seconds=window_seconds)
        result: dict[str, float | None] = {}

        for feature_name in feature_names:
            query = self.queries.get(feature_name)
            if not query:
                result[feature_name] = None
                continue

            series = self.client.query_range(query=query, start=start, end=end, step=step_seconds)
            if series is None or series.empty:
                result[feature_name] = None
                continue

            if feature_name.endswith("restart_count"):
                result[feature_name] = self._restart_increment(series)
            else:
                result[feature_name] = float(series.iloc[-1])

        return result

    def collect_window_frame(
        self,
        end_time: datetime | None = None,
        lookback_minutes: int = 10,
        step_seconds: int = 5,
        feature_names: list[str] | None = None,
    ) -> pd.DataFrame:
        """Collect a full metrics window and align it into one feature frame."""

        end = end_time or datetime.now(timezone.utc)
        start = end - timedelta(minutes=lookback_minutes)
        feature_names = feature_names or self.dataset.feature_columns

        timestamps: list[str] | None = None
        columns: dict[str, list[float]] = {}

        for feature_name in feature_names:
            query = self.queries.get(feature_name)
            baseline_mean = self._baseline_mean(feature_name)
            if not query:
                if timestamps is not None:
                    columns[feature_name] = [baseline_mean] * len(timestamps)
                continue

            series = self.client.query_range(query=query, start=start, end=end, step=step_seconds)
            if series is None or series.empty:
                if timestamps is not None:
                    columns[feature_name] = [baseline_mean] * len(timestamps)
                continue

            if timestamps is None:
                timestamps = [str(index) for index in series.index]

            aligned = series.reindex(timestamps)
            aligned = aligned.fillna(baseline_mean)
            columns[feature_name] = [float(value) for value in aligned.tolist()]

        if not timestamps:
            raise RuntimeError("Prometheus returned no timeseries for the selected online window.")

        frame = pd.DataFrame({"timestamp": timestamps})
        for feature_name in feature_names:
            values = columns.get(feature_name)
            if values is None:
                values = [self._baseline_mean(feature_name)] * len(timestamps)
            frame[feature_name] = values
        return frame

    def _baseline_mean(self, feature_name: str) -> float:
        feature_stats = self.dataset.norm_stats.get("features", {}).get(feature_name, {})
        return float(feature_stats.get("mean", 0.0))

    @staticmethod
    def _restart_increment(series: pd.Series) -> float:
        """Convert cumulative restart counters into recent increments."""

        if series.empty:
            return 0.0

        start_value = float(series.iloc[0])
        end_value = float(series.iloc[-1])
        increment = end_value - start_value
        if increment < 0:
            # Counter reset or pod recreation; treat it as at least one restart event.
            return float(end_value)
        return float(increment)

    def sampling_interval_seconds(self) -> int:
        return int(self.dataset.meta.get("sampling_interval_seconds", 5))

    def dataset_name(self) -> str:
        return str(self.dataset.meta.get("dataset_name", self.dataset.root.name))

    def dataset_artifacts(self) -> DatasetArtifacts:
        return self.dataset

    def available_feature_names(self) -> list[str]:
        return [feature for feature in self.dataset.feature_columns if feature in self.queries]
