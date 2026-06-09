"""Rule-based anomaly detector for offline incident replay."""

from __future__ import annotations

from collections import defaultdict

from .models import DatasetArtifacts, DetectionResult, DiagnosticWindow, MetricEvidence


PRIORITY_METRICS = {
    "restart_count": 5.0,
    "error_rate": 4.0,
    "latency_p95": 3.5,
    "cpu_usage": 2.5,
    "memory_usage": 1.2,
    "qps": 1.0,
}

METRIC_DIRECTION = {
    "restart_count": "high_only",
    "error_rate": "high_only",
    "latency_p95": "high_only",
    "cpu_usage": "high_only",
    "memory_usage": "high_only",
    "qps": "low_only",
}

# 在线场景下用于抑制“无流量假异常”和“小绝对 CPU 高 z-score”。
ONLINE_MIN_ACTIVE_QPS = 0.1
ONLINE_MIN_QPS_DROP_RATIO = 0.5
ONLINE_LOW_CPU_VALUE = 0.03
ONLINE_LOW_CPU_WEIGHT_FACTOR = 0.25


class RuleBasedDetector:
    """Detect suspicious services by comparing one window against train baselines."""

    def __init__(self, min_score: float = 3.0, max_evidence_items: int = 8) -> None:
        self.min_score = min_score
        self.max_evidence_items = max_evidence_items

    def detect(self, dataset: DatasetArtifacts, window: DiagnosticWindow) -> DetectionResult:
        features_stats = dataset.norm_stats.get("features", {})
        evidence: list[MetricEvidence] = []
        service_scores: dict[str, float] = defaultdict(float)
        notes: list[str] = []

        for feature_name in dataset.feature_columns:
            stats = features_stats.get(feature_name)
            if not stats or feature_name not in window.features.columns:
                continue

            series = window.features[feature_name].dropna()
            if series.empty:
                continue

            mean = float(stats.get("mean", 0.0))
            std = float(stats.get("std", 1.0)) or 1.0
            max_value = float(series.max())
            min_value = float(series.min())
            max_z = (max_value - mean) / std
            min_z = (min_value - mean) / std

            service = feature_name.split("_", 1)[0]
            metric = feature_name[len(service) + 1 :]

            # 在线模式：如果整个窗口几乎没有流量，不把 QPS=0 当作故障性下降。
            if (
                window.split == "online"
                and metric == "qps"
                and not self._is_valid_online_qps_drop(series, mean)
            ):
                notes.append(
                    f"{feature_name} 在当前在线窗口缺少稳定非零流量，"
                    "已跳过 QPS 下降异常判定。"
                )
                continue

            score, observed_value, direction = self._select_metric_signal(
                metric=metric,
                max_value=max_value,
                min_value=min_value,
                max_z=max_z,
                min_z=min_z,
            )
            if score < self.min_score:
                continue

            weighted_score = score * PRIORITY_METRICS.get(metric, 1.0)

            # 在线模式：CPU 绝对值很低时，只保留为弱证据，避免小方差放大。
            if (
                window.split == "online"
                and metric == "cpu_usage"
                and observed_value < ONLINE_LOW_CPU_VALUE
            ):
                weighted_score *= ONLINE_LOW_CPU_WEIGHT_FACTOR
                reason_suffix = (
                    f"；CPU 绝对值仅 {observed_value:.3f}，"
                    "虽然相对基线偏离明显，但资源压力证据较弱"
                )
            else:
                reason_suffix = ""

            reason = self._build_reason(
                metric=metric,
                score=score,
                observed_value=observed_value,
                mean=mean,
                direction=direction,
            ) + reason_suffix

            item = MetricEvidence(
                service=service,
                metric=metric,
                feature_name=feature_name,
                score=round(score, 3),
                observed_value=round(observed_value, 3),
                baseline_mean=round(mean, 3),
                baseline_std=round(std, 3),
                reason=reason,
            )
            evidence.append(item)
            service_scores[service] += weighted_score

        evidence.sort(key=lambda item: item.score, reverse=True)
        abnormal_services = [
            service
            for service, _ in sorted(
                service_scores.items(),
                key=lambda kv: kv[1],
                reverse=True,
            )
        ]
        incident_ids = sorted(
            {
                str(incident_id)
                for incident_id in window.labels.get("incident_id", [])
                if isinstance(incident_id, str) and incident_id
            }
        )
        if not evidence:
            notes.append("当前时间窗口内没有任何特征超过异常阈值。")

        return DetectionResult(
            is_anomaly=bool(evidence),
            abnormal_services=abnormal_services,
            abnormal_metrics=evidence[: self.max_evidence_items],
            incident_ids=incident_ids,
            notes=notes,
        )

    @staticmethod
    def _is_valid_online_qps_drop(series, baseline_mean: float) -> bool:
        """在线窗口必须先有真实流量，才能把 QPS 下降视为异常。"""

        if series.empty:
            return False

        current_value = float(series.iloc[-1])
        window_peak = float(series.max())
        early_count = max(3, min(len(series) // 3, 20))
        early_reference = float(series.iloc[:early_count].mean())

        # 当前窗口从头到尾几乎无流量，属于无负载，而不是故障性下降。
        if window_peak < ONLINE_MIN_ACTIVE_QPS:
            return False

        # 历史基线也接近无流量时，不做下降判定。
        if baseline_mean < ONLINE_MIN_ACTIVE_QPS:
            return False

        reference_value = max(early_reference, window_peak * 0.5)
        if reference_value < ONLINE_MIN_ACTIVE_QPS:
            return False

        # 当前值必须相比窗口前段/峰值下降至少 50%。
        return current_value <= reference_value * ONLINE_MIN_QPS_DROP_RATIO

    @staticmethod
    def _select_metric_signal(
        metric: str,
        max_value: float,
        min_value: float,
        max_z: float,
        min_z: float,
    ) -> tuple[float, float, str]:
        behavior = METRIC_DIRECTION.get(metric, "two_sided")
        if behavior == "high_only":
            return max(max_z, 0.0), max_value, "高于"
        if behavior == "low_only":
            return max(-min_z, 0.0), min_value, "低于"

        if abs(max_z) >= abs(min_z):
            return abs(max_z), max_value, "高于" if max_z >= 0 else "低于"
        return abs(min_z), min_value, "低于" if min_z <= 0 else "高于"

    @staticmethod
    def _build_reason(
        metric: str,
        score: float,
        observed_value: float,
        mean: float,
        direction: str,
    ) -> str:
        if metric == "qps" and direction == "低于":
            return f"{metric} 相比基线明显下降，z-score={score:.2f}"
        if observed_value == mean:
            return f"{metric} 接近基线，z-score={score:.2f}"
        return f"{metric} 相比基线明显{direction}，z-score={score:.2f}"
