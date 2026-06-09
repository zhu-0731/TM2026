"""LLM-assisted reasoning and evidence packaging for online diagnosis."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import yaml

from aiops_agent.offline.models import DetectionResult, DiagnosisResult, DiagnosticWindow

from .prompts import SYSTEM_PROMPT
from .tools import OnlineToolbox

def load_online_model_settings() -> dict[str, str]:
    """读取 aiops_agent/config.yaml，并同步到 VeADK 所需环境变量。"""

    config_path = Path(__file__).resolve().parents[1] / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"在线 LLM 配置文件不存在：{config_path}"
        )

    try:
        payload = yaml.safe_load(
            config_path.read_text(encoding="utf-8")
        ) or {}
    except Exception as exc:
        raise RuntimeError(
            f"读取在线 LLM 配置失败：{exc}"
        ) from exc

    agent_config = (
        (payload.get("model") or {}).get("agent") or {}
    )

    api_key = str(agent_config.get("api_key") or "").strip()
    api_base = str(agent_config.get("api_base") or "").strip()
    provider = str(agent_config.get("provider") or "").strip()
    model_name = str(agent_config.get("name") or "").strip()

    missing = []

    if not api_key:
        missing.append("api_key")
    if not api_base:
        missing.append("api_base")
    if not provider:
        missing.append("provider")
    if not model_name:
        missing.append("name")

    if missing:
        raise RuntimeError(
            "config.yaml 中缺少模型配置："
            + ", ".join(missing)
        )

    resolved = {
        "MODEL_AGENT_API_KEY": api_key,
        "MODEL_AGENT_API_BASE": api_base,
        "MODEL_AGENT_PROVIDER": provider,
        "MODEL_AGENT_MODEL": model_name,
    }

    for key, value in resolved.items():
        os.environ[key] = value

    return resolved


def patch_online_veadk_defaults(
    resolved: dict[str, str],
) -> None:
    """覆盖 VeADK 默认模型配置，避免其继续使用默认火山 AK/SK 认证。"""

    import veadk.consts as veadk_consts

    model_name = resolved.get("MODEL_AGENT_MODEL")
    provider = resolved.get("MODEL_AGENT_PROVIDER")
    api_base = resolved.get("MODEL_AGENT_API_BASE")

    if model_name:
        veadk_consts.DEFAULT_MODEL_AGENT_NAME = model_name

    if provider:
        veadk_consts.DEFAULT_MODEL_AGENT_PROVIDER = provider

    if api_base:
        veadk_consts.DEFAULT_MODEL_AGENT_API_BASE = api_base

    try:
        import veadk.memory.short_term_memory_processor as stm

        if model_name:
            stm.DEFAULT_MODEL_AGENT_NAME = model_name

        if provider:
            stm.DEFAULT_MODEL_AGENT_PROVIDER = provider

        if api_base:
            stm.DEFAULT_MODEL_AGENT_API_BASE = api_base

    except Exception:
        pass


_ONLINE_MODEL_SETTINGS = load_online_model_settings()
patch_online_veadk_defaults(_ONLINE_MODEL_SETTINGS)


class OnlineReasoner:
    """Package evidence and synthesize a final explanation with a tool-calling LLM."""

    def __init__(
        self,
        prometheus_url: str,
        namespace: str = "online-boutique",
        allow_actions: bool = False,
    ) -> None:
        self.prometheus_url = prometheus_url
        self.namespace = namespace
        self.allow_actions = allow_actions
        self.toolbox = OnlineToolbox(
            prometheus_url=prometheus_url,
            namespace=namespace,
            allow_actions=allow_actions,
        )

    def build_evidence_bundle(
        self,
        window: DiagnosticWindow,
        detection: DetectionResult,
        diagnosis: DiagnosisResult,
        trigger_analysis: dict[str, Any],
        trigger_metrics: dict[str, float | None],
    ) -> dict[str, Any]:
        self.toolbox.reset_call_history()
        missing_trigger_metrics = [
            feature_name for feature_name, value in trigger_metrics.items() if value is None
        ]
        abnormal_metric_evidence = [
            {
                "service": item.service,
                "metric": item.metric,
                "feature_name": item.feature_name,
                "score": item.score,
                "observed_value": item.observed_value,
                "baseline_mean": item.baseline_mean,
                "baseline_std": item.baseline_std,
                "reason": item.reason,
            }
            for item in detection.abnormal_metrics
        ]
        supporting_metrics = [
            {
                "service": item.service,
                "metric": item.metric,
                "feature_name": item.feature_name,
                "score": item.score,
                "observed_value": item.observed_value,
                "baseline_mean": item.baseline_mean,
                "baseline_std": item.baseline_std,
                "reason": item.reason,
            }
            for item in diagnosis.supporting_metrics
        ]
        latest_row = window.features.iloc[-1].to_dict()
        lifecycle_summary = trigger_analysis.get("kubernetes_lifecycle", {})
        affected_services = (
            lifecycle_summary.get("affected_services", [])
            if isinstance(lifecycle_summary, dict)
            else []
        )
        kubernetes_runtime_evidence: dict[str, Any] = {}
        for service in affected_services[:3]:
            kubernetes_runtime_evidence[str(service)] = {
                "pod_status": self.toolbox.get_pod_status(str(service)),
                "events": self.toolbox.get_kubernetes_events(str(service), limit=20),
            }

        return {
            "window": {
                "dataset_name": window.dataset_name,
                "split": window.split,
                "start_time": window.start_time,
                "end_time": window.end_time,
                "row_count": len(window.features),
            },
            "runtime_context": {
                "namespace": self.namespace,
                "prometheus_url": self.prometheus_url,
                "allow_actions": self.allow_actions,
                "fault_injection": trigger_analysis.get("fault_injection"),
            },
            "data_quality": {
                "trigger_metric_count": len(trigger_metrics),
                "available_trigger_metric_count": len(trigger_metrics) - len(missing_trigger_metrics),
                "missing_trigger_metrics": missing_trigger_metrics,
            },
            "trigger_evidence": trigger_analysis,
            "fault_injection": trigger_analysis.get("fault_injection"),
            "kubernetes_lifecycle_evidence": lifecycle_summary,
            "kubernetes_runtime_evidence": kubernetes_runtime_evidence,
            "detection_evidence": abnormal_metric_evidence,
            "supporting_evidence": supporting_metrics,
            "candidate_services": diagnosis.candidate_scores,
            "service_snapshots": self._build_service_snapshots(latest_row),
            "detector_notes": detection.notes,
        }

    def reason_with_llm(
        self,
        trigger_analysis: dict[str, Any],
        diagnosis: DiagnosisResult,
        evidence_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "trigger_analysis": trigger_analysis,
            "diagnosis": {
                "is_anomaly": diagnosis.is_anomaly,
                "abnormal_services": diagnosis.abnormal_services,
                "suspected_root_cause_service": diagnosis.suspected_root_cause_service,
                "candidate_scores": diagnosis.candidate_scores,
                "summary": diagnosis.summary,
            },
            "evidence_bundle": evidence_bundle,
            "tool_usage_policy": {
                "promql_allowed": True,
                "log_collection_allowed": True,
                "kubernetes_events_allowed": True,
                "pod_status_allowed": True,
                "restart_allowed": self.allow_actions,
                "preferred_services": diagnosis.abnormal_services[:5],
            },
        }

        try:
            content = asyncio.run(self._run_llm(payload))
            parsed = self._parse_llm_output(content)
            parsed["status"] = "ok"
            parsed["provider"] = "veadk"
            parsed["tool_mode"] = "enabled"
            parsed["agent_tool_trace"] = self.toolbox.get_call_history()
            return parsed
        except Exception as exc:  # noqa: BLE001
            fallback = self._fallback_reasoning(payload, str(exc))
            fallback["agent_tool_trace"] = self.toolbox.get_call_history()
            return fallback

    async def _run_llm(self, payload: dict[str, Any]) -> str:
        from veadk import Agent, Runner

        model_name = _ONLINE_MODEL_SETTINGS["MODEL_AGENT_MODEL"]
        provider = _ONLINE_MODEL_SETTINGS["MODEL_AGENT_PROVIDER"]
        api_base = _ONLINE_MODEL_SETTINGS["MODEL_AGENT_API_BASE"]
        api_key = _ONLINE_MODEL_SETTINGS["MODEL_AGENT_API_KEY"]


        agent = Agent(
            name="online_aiops_reasoner",
            instruction=SYSTEM_PROMPT,
            model_name=model_name,
            model_provider=provider,
            model_api_base=api_base,
            model_api_key=api_key,
            tools=[
                self.toolbox.execute_promql,
                self.toolbox.get_service_logs,
                self.toolbox.get_pod_status,
                self.toolbox.get_kubernetes_events,
                self.toolbox.restart_pod,
            ],
        )
        runner = Runner(agent=agent)
        prompt = (
            "请基于下面的在线诊断结构化数据完成分析。"
            "如果现有证据不足，请主动调用工具补充证据；"
            "只有在证据充分且允许动作时才调用 restart_pod。"
            "最终必须输出约定 JSON。\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        result = await runner.run(messages=prompt)
        return str(result)

    @staticmethod
    def _parse_llm_output(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM output is not a JSON object.")
        return parsed

    def _fallback_reasoning(self, payload: dict[str, Any], error_message: str) -> dict[str, Any]:
        diagnosis = payload["diagnosis"]
        trigger_analysis = payload["trigger_analysis"]
        evidence_bundle = payload["evidence_bundle"]
        root_cause = diagnosis.get("suspected_root_cause_service") or "unknown"
        abnormal_services = diagnosis.get("abnormal_services") or []
        missing_metrics = evidence_bundle["data_quality"].get("missing_trigger_metrics", [])
        top_breaches = trigger_analysis.get("breaches", [])[:3]
        breach_text = "；".join(
            f"{item['feature_name']}={item['observed_value']}"
            for item in top_breaches
        ) or "暂无明确超阈值证据"

        return {
            "status": "fallback",
            "provider": "rule_based_fallback",
            "tool_mode": "disabled",
            "incident_overview": (
                f"当前在线窗口主要表现为 {', '.join(abnormal_services) if abnormal_services else '局部服务'} "
                f"出现异常波动，触发证据集中在 {breach_text}。"
            ),
            "root_cause_hypothesis": (
                f"综合规则触发、检测证据和候选得分，当前最可能的根因服务是 {root_cause}。"
            ),
            "evidence_summary": [
                f"触发原因：{trigger_analysis.get('reason', 'unknown')}",
                f"候选根因排序：{diagnosis.get('candidate_scores', {})}",
            ],
            "missing_observations": missing_metrics,
            "operator_actions": [
                f"优先检查 {root_cause} 的最近变更、重启、依赖调用和资源使用情况。",
                "结合 Prometheus 图表继续核对异常指标是否持续上升，以及上下游服务是否同步异常。",
            ],
            "report_explanation": (
                f"当前在线诊断由规则触发进入深度分析，候选排序认为 {root_cause} 最可疑。"
                "不过仍建议结合缺失指标和上下游观测继续人工复核。"
            ),
            "error": error_message,
        }

    @staticmethod
    def _build_service_snapshots(latest_row: dict[str, Any]) -> dict[str, dict[str, float]]:
        snapshots: dict[str, dict[str, float]] = {}
        for feature_name, value in latest_row.items():
            if feature_name == "timestamp" or "_" not in feature_name:
                continue
            if value is None:
                continue
            service, metric = feature_name.split("_", 1)
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            snapshots.setdefault(service, {})[metric] = numeric_value
        return snapshots
