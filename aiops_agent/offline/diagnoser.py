"""Root-cause ranking logic built on top of detector evidence."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import DetectionResult, DiagnosisResult, MetricEvidence
from .service_map import get_downstream_services


TRIGGER_SERVICE_BONUS = 4.0
TRIGGER_RESTART_BONUS = 2.5
LIFECYCLE_EVENT_BONUS = 20.0


class RuleBasedDiagnoser:
    """Rank candidate root-cause services using evidence and dependency edges."""

    def diagnose(
        self,
        detection: DetectionResult,
        trigger_context: dict[str, Any] | None = None,
    ) -> DiagnosisResult:
        lifecycle_events = self._lifecycle_events(trigger_context)
        if not detection.is_anomaly and not lifecycle_events:
            return DiagnosisResult(
                is_anomaly=False,
                abnormal_services=[],
                suspected_root_cause_service=None,
                supporting_metrics=[],
                candidate_scores={},
                incident_ids=detection.incident_ids,
                summary="在当前选定的时间窗口内，没有检测到显著异常信号。",
            )

        if not detection.is_anomaly and lifecycle_events:
            lifecycle_scores: dict[str, float] = defaultdict(float)
            for event in lifecycle_events:
                service = str(event.get("service") or "unknown")
                lifecycle_scores[service] += float(event.get("score", LIFECYCLE_EVENT_BONUS))
            ranked = dict(sorted(lifecycle_scores.items(), key=lambda kv: kv[1], reverse=True))
            root_cause = next(iter(ranked), None)
            services = list(ranked.keys())
            return DiagnosisResult(
                is_anomaly=True,
                abnormal_services=services,
                suspected_root_cause_service=root_cause,
                supporting_metrics=[],
                candidate_scores={key: round(value, 3) for key, value in ranked.items()},
                incident_ids=detection.incident_ids,
                summary=(
                    f"Kubernetes 生命周期快照检测到 {root_cause} 的 Pod 被删除或重建。"
                    "即使 Prometheus 窗口尚未形成明显指标异常，该生命周期证据也足以将其列为首要候选根因。"
                ),
            )

        service_scores: dict[str, float] = defaultdict(float)
        metrics_by_service: dict[str, list[MetricEvidence]] = defaultdict(list)
        abnormal_service_set = set(detection.abnormal_services)

        for item in detection.abnormal_metrics:
            service_scores[item.service] += item.score
            metrics_by_service[item.service].append(item)

            if item.metric == "restart_count":
                service_scores[item.service] += 2.0

            if item.metric in {"cpu_usage", "latency_p95", "error_rate"}:
                service_scores[item.service] += 0.5

        for service in list(service_scores.keys()):
            for downstream in get_downstream_services(service):
                if downstream in abnormal_service_set:
                    service_scores[downstream] += 1.5
                    service_scores[service] -= 0.5

        self._apply_trigger_context(service_scores, trigger_context)
        self._apply_lifecycle_context(service_scores, trigger_context)

        ranked_candidates = dict(sorted(service_scores.items(), key=lambda kv: kv[1], reverse=True))
        root_cause_service = next(iter(ranked_candidates), None)
        supporting_metrics = metrics_by_service.get(root_cause_service, [])
        summary = self._build_summary(
            abnormal_services=detection.abnormal_services,
            root_cause_service=root_cause_service,
            supporting_metrics=supporting_metrics,
            trigger_context=trigger_context,
        )

        return DiagnosisResult(
            is_anomaly=True,
            abnormal_services=detection.abnormal_services,
            suspected_root_cause_service=root_cause_service,
            supporting_metrics=supporting_metrics,
            candidate_scores={key: round(value, 3) for key, value in ranked_candidates.items()},
            incident_ids=detection.incident_ids,
            summary=summary,
        )

    @staticmethod
    def _apply_trigger_context(
        service_scores: dict[str, float],
        trigger_context: dict[str, Any] | None,
    ) -> None:
        if not trigger_context:
            return

        triggered_metrics = trigger_context.get("triggered_metrics", {})
        if not isinstance(triggered_metrics, dict):
            return

        for feature_name in triggered_metrics.keys():
            service = str(feature_name).split("_", 1)[0]
            service_scores[service] += TRIGGER_SERVICE_BONUS
            if str(feature_name).endswith("restart_count"):
                service_scores[service] += TRIGGER_RESTART_BONUS


    @staticmethod
    def _lifecycle_events(trigger_context: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not trigger_context:
            return []
        lifecycle = trigger_context.get("kubernetes_lifecycle", {})
        if not isinstance(lifecycle, dict):
            return []
        events = lifecycle.get("events", [])
        return events if isinstance(events, list) else []

    @classmethod
    def _apply_lifecycle_context(
        cls,
        service_scores: dict[str, float],
        trigger_context: dict[str, Any] | None,
    ) -> None:
        for event in cls._lifecycle_events(trigger_context):
            service = str(event.get("service") or "")
            if not service:
                continue
            service_scores[service] += float(event.get("score", LIFECYCLE_EVENT_BONUS))

    @staticmethod
    def _build_summary(
        abnormal_services: list[str],
        root_cause_service: str | None,
        supporting_metrics: list[MetricEvidence],
        trigger_context: dict[str, Any] | None,
    ) -> str:
        if not root_cause_service:
            return "虽然检测到了异常，但当前根因排序没有给出明确的首要候选服务。"

        abnormal_services_text = ", ".join(abnormal_services[:3]) if abnormal_services else "未知服务"
        trigger_reason = ""
        if trigger_context and trigger_context.get("trigger_reason"):
            trigger_reason = f"结合在线触发信息（{trigger_context['trigger_reason']}），"

        if supporting_metrics:
            top_metrics = "、".join(item.metric for item in supporting_metrics[:3])
            return (
                f"异常现象主要体现在 {abnormal_services_text} 等服务上。"
                f"{trigger_reason}{root_cause_service} 在 {top_metrics} 等关键指标上最可疑，因此被判为当前最可能的根因服务。"
            )

        return (
            f"异常现象主要体现在 {abnormal_services_text} 等服务上。"
            f"{trigger_reason}当前排序结果认为 {root_cause_service} 是最可能的根因服务。"
        )
