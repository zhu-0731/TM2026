"""Online monitor loop for realtime anomaly triggering and diagnosis."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiops_agent.offline.detector import RuleBasedDetector
from aiops_agent.offline.diagnoser import RuleBasedDiagnoser
from aiops_agent.offline.models import DatasetArtifacts

from .collector import OnlineMetricsCollector
from .lifecycle import KubernetesLifecycleWatcher
from .reasoner import OnlineReasoner
from .reporter import OnlineReportWriter
from .window_builder import build_online_window

DEFAULT_DATASET_ROOT = "data/datasets/online_boutique_rca_full_v1"
DEFAULT_QUERIES_PATH = "configs/prometheus_queries.yaml"
DEFAULT_OUTPUT_DIR = "aiops_agent/output/online_reports"

TRIGGER_RULES = {
    "frontend_latency_p95": {"metric_type": "latency_p95", "fallback_threshold": 500.0},
    "frontend_error_rate": {"metric_type": "error_rate", "fallback_threshold": 0.05},
    "frontend_cpu_usage": {"metric_type": "cpu_usage", "fallback_threshold": 0.15},
    "frontend_restart_count": {"metric_type": "restart_count", "fallback_threshold": 1.0},
    "cartservice_latency_p95": {"metric_type": "latency_p95", "fallback_threshold": 300.0},
    "cartservice_error_rate": {"metric_type": "error_rate", "fallback_threshold": 0.05},
    "cartservice_cpu_usage": {"metric_type": "cpu_usage", "fallback_threshold": 0.15},
    "cartservice_restart_count": {"metric_type": "restart_count", "fallback_threshold": 1.0},
    "checkoutservice_latency_p95": {"metric_type": "latency_p95", "fallback_threshold": 400.0},
    "checkoutservice_error_rate": {"metric_type": "error_rate", "fallback_threshold": 0.05},
    "checkoutservice_cpu_usage": {"metric_type": "cpu_usage", "fallback_threshold": 0.15},
    "checkoutservice_restart_count": {"metric_type": "restart_count", "fallback_threshold": 1.0},
    "productcatalogservice_latency_p95": {"metric_type": "latency_p95", "fallback_threshold": 250.0},
    "productcatalogservice_error_rate": {"metric_type": "error_rate", "fallback_threshold": 0.05},
    "productcatalogservice_cpu_usage": {"metric_type": "cpu_usage", "fallback_threshold": 0.15},
    "productcatalogservice_restart_count": {"metric_type": "restart_count", "fallback_threshold": 1.0},
    "recommendationservice_latency_p95": {"metric_type": "latency_p95", "fallback_threshold": 300.0},
    "recommendationservice_error_rate": {"metric_type": "error_rate", "fallback_threshold": 0.05},
    "recommendationservice_cpu_usage": {"metric_type": "cpu_usage", "fallback_threshold": 0.15},
    "recommendationservice_restart_count": {"metric_type": "restart_count", "fallback_threshold": 1.0},
    "redis-cart_cpu_usage": {"metric_type": "cpu_usage", "fallback_threshold": 0.10},
    "redis-cart_restart_count": {"metric_type": "restart_count", "fallback_threshold": 1.0},
}

TRIGGER_WEIGHTS = {
    "restart_count": 5.0,
    "error_rate": 4.0,
    "latency_p95": 3.0,
    "cpu_usage": 1.5,
}


DEFAULT_FAULT_RECORD_PATH = "aiops_agent/output/last_fault_injection.json"


def load_recent_fault_injection(
    record_path: str | Path = DEFAULT_FAULT_RECORD_PATH,
    max_age_seconds: int = 300,
) -> dict[str, Any] | None:
    """读取最近一次故障注入记录，过期或格式错误时返回 None。"""

    path = Path(record_path)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        injected_at_text = str(payload.get("injected_at") or "").strip()
        if not injected_at_text:
            return None

        injected_at = datetime.fromisoformat(
            injected_at_text.replace("Z", "+00:00")
        )
        if injected_at.tzinfo is None:
            injected_at = injected_at.replace(tzinfo=timezone.utc)

        age_seconds = (
            datetime.now(timezone.utc) - injected_at.astimezone(timezone.utc)
        ).total_seconds()
        if age_seconds < 0 or age_seconds > max_age_seconds:
            return None

        return payload
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


@dataclass
class TriggerDecision:
    triggered: bool
    reason: str
    triggered_metrics: dict[str, float]
    missing_metrics: list[str]
    breaches: list[dict[str, Any]]
    service_scores: dict[str, float]


@dataclass
class TriggerSnapshot:
    """一次轻量巡检的结果。

    这里只采集触发指标并完成阈值判断，不执行窗口构建、诊断、
    LLM 推理或报告写入。
    """

    collector: OnlineMetricsCollector
    decision: TriggerDecision
    trigger_metrics: dict[str, float | None]
    trigger_analysis: dict[str, Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Online monitoring loop for the AIOps agent")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--namespace", default="online-boutique")
    parser.add_argument("--dataset-root", default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--queries-path", default=DEFAULT_QUERIES_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--interval-seconds", type=int, default=10)
    parser.add_argument("--lookback-minutes", type=int, default=10)
    parser.add_argument("--step-seconds", type=int, default=5)
    parser.add_argument("--cooldown-seconds", type=int, default=300)
    parser.add_argument("--disable-llm", action="store_true", help="Disable LLM reasoning and keep rule-only explanations")
    parser.add_argument(
        "--allow-actions",
        action="store_true",
        help="Allow the online LLM agent to execute restart_pod tool actions.",
    )
    parser.add_argument("--once", action="store_true", help="Run one polling cycle and exit")
    return parser


def _feature_stats(dataset: DatasetArtifacts, feature_name: str) -> tuple[float, float]:
    stats = dataset.norm_stats.get("features", {}).get(feature_name, {})
    mean = float(stats.get("mean", 0.0))
    std = float(stats.get("std", 0.0)) or 1e-6
    return mean, std


def _compute_threshold(feature_name: str, observed_value: float, rule: dict[str, float | str], dataset: DatasetArtifacts) -> dict[str, float | str | bool | None]:
    metric_type = str(rule["metric_type"])
    fallback_threshold = float(rule["fallback_threshold"])
    baseline_mean, baseline_std = _feature_stats(dataset, feature_name)

    if metric_type == "restart_count":
        dynamic_threshold = max(1.0, baseline_mean + 3.0 * baseline_std)
        threshold = max(dynamic_threshold, fallback_threshold)
        exceeded = observed_value > threshold
        exceed_ratio = round(observed_value / threshold, 3) if threshold else None
        return {
            "metric_type": metric_type,
            "threshold": round(threshold, 3),
            "baseline_mean": round(baseline_mean, 3),
            "baseline_std": round(baseline_std, 3),
            "exceeded": exceeded,
            "exceed_ratio": exceed_ratio,
            "threshold_mode": "baseline+absolute",
        }

    if metric_type == "error_rate":
        dynamic_threshold = max(baseline_mean + 3.0 * baseline_std, baseline_mean * 2.0, 0.01)
        threshold = min(max(dynamic_threshold, 0.01), fallback_threshold)
        exceeded = observed_value > threshold
        exceed_ratio = round(observed_value / threshold, 3) if threshold else None
        return {
            "metric_type": metric_type,
            "threshold": round(threshold, 3),
            "baseline_mean": round(baseline_mean, 3),
            "baseline_std": round(baseline_std, 3),
            "exceeded": exceeded,
            "exceed_ratio": exceed_ratio,
            "threshold_mode": "baseline-capped",
        }

    if metric_type == "latency_p95":
        dynamic_threshold = max(baseline_mean + 3.0 * baseline_std, baseline_mean * 1.8, baseline_mean + 20.0)
        threshold = min(dynamic_threshold, fallback_threshold)
        exceeded = observed_value > threshold
        exceed_ratio = round(observed_value / threshold, 3) if threshold else None
        return {
            "metric_type": metric_type,
            "threshold": round(threshold, 3),
            "baseline_mean": round(baseline_mean, 3),
            "baseline_std": round(baseline_std, 3),
            "exceeded": exceeded,
            "exceed_ratio": exceed_ratio,
            "threshold_mode": "baseline-capped",
        }

    if metric_type == "cpu_usage":
        dynamic_threshold = max(baseline_mean + 3.0 * baseline_std, baseline_mean * 2.5, baseline_mean + 0.02)
        threshold = min(dynamic_threshold, fallback_threshold)
        exceeded = observed_value > threshold
        exceed_ratio = round(observed_value / threshold, 3) if threshold else None
        return {
            "metric_type": metric_type,
            "threshold": round(threshold, 3),
            "baseline_mean": round(baseline_mean, 3),
            "baseline_std": round(baseline_std, 3),
            "exceeded": exceeded,
            "exceed_ratio": exceed_ratio,
            "threshold_mode": "baseline-capped",
        }

    exceeded = observed_value > fallback_threshold
    exceed_ratio = round(observed_value / fallback_threshold, 3) if fallback_threshold else None
    return {
        "metric_type": metric_type,
        "threshold": round(fallback_threshold, 3),
        "baseline_mean": round(baseline_mean, 3),
        "baseline_std": round(baseline_std, 3),
        "exceeded": exceeded,
        "exceed_ratio": exceed_ratio,
        "threshold_mode": "absolute",
    }


def evaluate_trigger(metrics: dict[str, float | None], dataset: DatasetArtifacts) -> TriggerDecision:
    triggered_metrics: dict[str, float] = {}
    missing_metrics: list[str] = []
    reasons: list[str] = []
    breaches: list[dict[str, Any]] = []
    service_scores: dict[str, float] = {}

    for feature_name, rule in TRIGGER_RULES.items():
        value = metrics.get(feature_name)
        if value is None:
            missing_metrics.append(feature_name)
            continue

        observed_value = float(value)
        threshold_info = _compute_threshold(feature_name, observed_value, rule, dataset)
        if bool(threshold_info["exceeded"]):
            observed_value = round(float(value), 3)
            service = feature_name.split("_", 1)[0]
            metric_type = str(threshold_info["metric_type"])
            threshold = float(threshold_info["threshold"])
            exceed_ratio = threshold_info["exceed_ratio"]
            threshold_mode = str(threshold_info["threshold_mode"])
            triggered_metrics[feature_name] = observed_value
            if threshold_mode == "absolute":
                reasons.append(f"{feature_name}={float(value):.3f} 超过阈值 {threshold:.3f}")
            else:
                reasons.append(
                    f"{feature_name}={float(value):.3f} 超过基线阈值 {threshold:.3f}"
                    f"（mean={float(threshold_info['baseline_mean']):.3f}, std={float(threshold_info['baseline_std']):.3f}）"
                )
            breaches.append(
                {
                    "feature_name": feature_name,
                    "service": service,
                    "metric_type": metric_type,
                    "observed_value": observed_value,
                    "threshold": threshold,
                    "exceed_ratio": exceed_ratio,
                    "baseline_mean": threshold_info["baseline_mean"],
                    "baseline_std": threshold_info["baseline_std"],
                    "threshold_mode": threshold_mode,
                }
            )
            weighted_score = (float(exceed_ratio or 1.0)) * TRIGGER_WEIGHTS.get(metric_type, 1.0)
            service_scores[service] = round(service_scores.get(service, 0.0) + weighted_score, 3)

    if not triggered_metrics:
        return TriggerDecision(
            triggered=False,
            reason="未命中任何触发阈值。",
            triggered_metrics={},
            missing_metrics=missing_metrics,
            breaches=[],
            service_scores={},
        )

    return TriggerDecision(
        triggered=True,
        reason="；".join(reasons),
        triggered_metrics=triggered_metrics,
        missing_metrics=missing_metrics,
        breaches=breaches,
        service_scores=dict(sorted(service_scores.items(), key=lambda kv: kv[1], reverse=True)),
    )




def join_reasons(*reasons: str | None) -> str:
    """拼接多段原因并统一末尾标点，避免出现“。；”等重复标点。"""

    cleaned: list[str] = []

    for reason in reasons:
        if not reason:
            continue

        value = str(reason).strip().rstrip("。；;，, ")

        if value and value not in cleaned:
            cleaned.append(value)

    if not cleaned:
        return "暂无诊断原因。"

    return "；".join(cleaned) + "。"


def collect_trigger_snapshot(
    prometheus_url: str = "http://localhost:9090",
    namespace: str = "online-boutique",
    dataset_root: str | Path = DEFAULT_DATASET_ROOT,
    queries_path: str | Path = DEFAULT_QUERIES_PATH,
    step_seconds: int = 5,
) -> TriggerSnapshot:
    """只执行轻量触发检查，不进行深度诊断和报告写入。"""

    # 当前指标查询配置中暂未直接使用 namespace，保留该参数用于接口一致性。
    _ = namespace

    collector = OnlineMetricsCollector(
        prometheus_url=prometheus_url,
        queries_path=queries_path,
        dataset_root=dataset_root,
    )
    if not collector.check_reachable():
        raise RuntimeError(f"Prometheus 不可达：{prometheus_url}")

    trigger_metrics = collector.collect_trigger_metrics(
        feature_names=list(TRIGGER_RULES.keys()),
        step_seconds=step_seconds,
    )
    decision = evaluate_trigger(trigger_metrics, collector.dataset_artifacts())
    trigger_analysis = {
        "triggered": decision.triggered,
        "reason": decision.reason,
        "breaches": decision.breaches,
        "missing_metrics": decision.missing_metrics,
        "service_scores": decision.service_scores,
    }

    return TriggerSnapshot(
        collector=collector,
        decision=decision,
        trigger_metrics=trigger_metrics,
        trigger_analysis=trigger_analysis,
    )


def run_monitor_once(
    prometheus_url: str = "http://localhost:9090",
    namespace: str = "online-boutique",
    dataset_root: str | Path = DEFAULT_DATASET_ROOT,
    queries_path: str | Path = DEFAULT_QUERIES_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    lookback_minutes: int = 10,
    step_seconds: int = 5,
    enable_llm: bool = True,
    allow_actions: bool = False,
    trigger_snapshot: TriggerSnapshot | None = None,
    kubernetes_lifecycle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = trigger_snapshot or collect_trigger_snapshot(
        prometheus_url=prometheus_url,
        namespace=namespace,
        dataset_root=dataset_root,
        queries_path=queries_path,
        step_seconds=step_seconds,
    )
    collector = snapshot.collector
    decision = snapshot.decision
    trigger_metrics = snapshot.trigger_metrics
    trigger_analysis = snapshot.trigger_analysis

    lifecycle = kubernetes_lifecycle or {
        "triggered": False,
        "reason": "未提供 Kubernetes 生命周期变化。",
        "events": [],
        "affected_services": [],
    }
    lifecycle_triggered = bool(lifecycle.get("triggered"))
    fault_injection = load_recent_fault_injection()
    combined_triggered = decision.triggered or lifecycle_triggered
    combined_reason = join_reasons(
        decision.reason if decision.triggered else None,
        (
            str(lifecycle.get("reason") or "检测到 Pod 生命周期变化")
            if lifecycle_triggered
            else None
        ),
    )

    trigger_analysis["metric_triggered"] = decision.triggered
    trigger_analysis["kubernetes_lifecycle"] = lifecycle
    trigger_analysis["fault_injection"] = fault_injection
    trigger_analysis["triggered"] = combined_triggered
    trigger_analysis["reason"] = combined_reason

    result: dict[str, Any] = {
        "triggered": combined_triggered,
        "trigger_reason": combined_reason,
        "trigger_metrics": trigger_metrics,
        "trigger_analysis": trigger_analysis,
        "kubernetes_lifecycle": lifecycle,
        "fault_injection": fault_injection,
    }
    if not combined_triggered:
        return result

    features = collector.collect_window_frame(
        lookback_minutes=lookback_minutes,
        step_seconds=step_seconds,
        feature_names=collector.available_feature_names(),
    )
    trigger_context = {
        "trigger_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trigger_reason": combined_reason,
        "triggered_metrics": decision.triggered_metrics,
        "kubernetes_lifecycle": lifecycle,
        "fault_injection": fault_injection,
        "lookback_minutes": lookback_minutes,
        "step_seconds": step_seconds,
    }

    window = build_online_window(
        dataset=collector.dataset_artifacts(),
        features=features,
        trigger_context=trigger_context,
    )
    dataset = collector.dataset_artifacts()
    detection = RuleBasedDetector().detect(dataset, window)
    diagnosis = RuleBasedDiagnoser().diagnose(detection, trigger_context=trigger_context)

    reasoner = OnlineReasoner(
        prometheus_url=prometheus_url,
        namespace=namespace,
        allow_actions=allow_actions,
    )
    evidence_bundle = reasoner.build_evidence_bundle(
        window=window,
        detection=detection,
        diagnosis=diagnosis,
        trigger_analysis=trigger_analysis,
        trigger_metrics=trigger_metrics,
    )
    llm_reasoning = (
        reasoner.reason_with_llm(
            trigger_analysis=trigger_analysis,
            diagnosis=diagnosis,
            evidence_bundle=evidence_bundle,
        )
        if enable_llm
        else {
            "status": "disabled",
            "provider": "disabled",
            "incident_overview": "LLM 推理已关闭。",
            "root_cause_hypothesis": diagnosis.summary,
            "evidence_summary": [],
            "missing_observations": decision.missing_metrics,
            "operator_actions": [],
            "report_explanation": diagnosis.summary,
        }
    )

    report_info = OnlineReportWriter().write(
        window,
        diagnosis,
        trigger_context=trigger_context,
        trigger_analysis=trigger_analysis,
        evidence_bundle=evidence_bundle,
        llm_reasoning=llm_reasoning,
        output_dir=output_dir,
    )

    result.update(
        {
            "window_start": window.start_time,
            "window_end": window.end_time,
            "abnormal_services": diagnosis.abnormal_services,
            "suspected_root_cause_service": diagnosis.suspected_root_cause_service,
            "summary": diagnosis.summary,
            "evidence_bundle": evidence_bundle,
            "llm_reasoning": llm_reasoning,
            "report": report_info,
        }
    )
    return result


def run_monitor_loop(
    prometheus_url: str = "http://localhost:9090",
    namespace: str = "online-boutique",
    dataset_root: str | Path = DEFAULT_DATASET_ROOT,
    queries_path: str | Path = DEFAULT_QUERIES_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    interval_seconds: int = 10,
    lookback_minutes: int = 10,
    step_seconds: int = 5,
    cooldown_seconds: int = 300,
    enable_llm: bool = True,
    allow_actions: bool = False,
) -> None:
    # monotonic 不受系统时间调整影响，更适合计算冷却间隔。
    last_report_at: float | None = None
    lifecycle_watcher = KubernetesLifecycleWatcher(namespace=namespace)
    previous_pod_snapshot = lifecycle_watcher.capture()
    if previous_pod_snapshot.error:
        print(f"[初始化] Kubernetes Pod 快照采集失败：{previous_pod_snapshot.error}")
    else:
        print(
            f"[初始化] 已记录 {len(previous_pod_snapshot.pods)} 个 Pod，"
            "后续将检测 Pod 删除和重建。"
        )

    while True:
        cycle_started_at = time.monotonic()
        try:
            # 第一阶段：只采集少量触发指标并判断是否异常。
            # 此阶段不会构建窗口、调用 LLM，也不会写报告。
            snapshot = collect_trigger_snapshot(
                prometheus_url=prometheus_url,
                namespace=namespace,
                dataset_root=dataset_root,
                queries_path=queries_path,
                step_seconds=step_seconds,
            )
            current_pod_snapshot = lifecycle_watcher.capture()
            lifecycle_change = lifecycle_watcher.compare(
                previous_pod_snapshot,
                current_pod_snapshot,
            )
            previous_pod_snapshot = current_pod_snapshot
            cycle_triggered = snapshot.decision.triggered or bool(
                lifecycle_change.get("triggered")
            )

            if not cycle_triggered:
                timestamp = datetime.now().strftime("%H:%M:%S")
                normal_reason = join_reasons(
                    snapshot.decision.reason,
                    str(lifecycle_change.get("reason") or ""),
                )
                print(f"[{timestamp}] 未触发在线诊断：{normal_reason}")
            else:
                now = time.monotonic()
                in_cooldown = (
                    last_report_at is not None
                    and now - last_report_at < cooldown_seconds
                )

                if in_cooldown:
                    remaining = max(
                        0,
                        int(cooldown_seconds - (now - last_report_at)),
                    )
                    print(
                        "检测到异常，但当前仍在冷却时间内，"
                        f"已跳过深度诊断和报告生成（剩余约 {remaining} 秒）。"
                    )
                else:
                    # 第二阶段：只有不在冷却期时，才执行完整诊断、
                    # LLM 推理和报告写入。
                    result = run_monitor_once(
                        prometheus_url=prometheus_url,
                        namespace=namespace,
                        dataset_root=dataset_root,
                        queries_path=queries_path,
                        output_dir=output_dir,
                        lookback_minutes=lookback_minutes,
                        step_seconds=step_seconds,
                        enable_llm=enable_llm,
                        allow_actions=allow_actions,
                        trigger_snapshot=snapshot,
                        kubernetes_lifecycle=lifecycle_change,
                    )
                    print(json.dumps(result, ensure_ascii=False, indent=2))

                    # 仅在完整诊断和报告写入成功后进入冷却期。
                    last_report_at = time.monotonic()

        except Exception as exc:  # noqa: BLE001
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 在线巡检失败：{exc}")

        elapsed = time.monotonic() - cycle_started_at
        time.sleep(max(0.0, interval_seconds - elapsed))


def main() -> None:
    args = build_parser().parse_args()
    if args.once:
        result = run_monitor_once(
            prometheus_url=args.prometheus_url,
            namespace=args.namespace,
            dataset_root=args.dataset_root,
            queries_path=args.queries_path,
            output_dir=args.output_dir,
            lookback_minutes=args.lookback_minutes,
            step_seconds=args.step_seconds,
            enable_llm=not args.disable_llm,
            allow_actions=args.allow_actions,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    run_monitor_loop(
        prometheus_url=args.prometheus_url,
        namespace=args.namespace,
        dataset_root=args.dataset_root,
        queries_path=args.queries_path,
        output_dir=args.output_dir,
        interval_seconds=args.interval_seconds,
        lookback_minutes=args.lookback_minutes,
        step_seconds=args.step_seconds,
        cooldown_seconds=args.cooldown_seconds,
        enable_llm=not args.disable_llm,
        allow_actions=args.allow_actions,
    )


if __name__ == "__main__":
    main()
