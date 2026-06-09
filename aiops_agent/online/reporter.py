"""Online diagnosis report output."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aiops_agent.offline.models import DiagnosisResult, DiagnosticWindow


class OnlineReportWriter:
    """Write online diagnosis reports with trigger, evidence, and LLM explanations."""

    def write(
        self,
        window: DiagnosticWindow,
        diagnosis: DiagnosisResult,
        trigger_context: dict[str, Any],
        trigger_analysis: dict[str, Any],
        evidence_bundle: dict[str, Any],
        llm_reasoning: dict[str, Any] | None,
        output_dir: str | Path,
    ) -> dict[str, Any]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"online_{timestamp}"

        report = {
            "mode": "online",
            "dataset_name": window.dataset_name,
            "split": window.split,
            "start_time": window.start_time,
            "end_time": window.end_time,
            "start_index": window.start_index,
            "end_index": window.end_index,
            "is_anomaly": diagnosis.is_anomaly,
            "abnormal_services": diagnosis.abnormal_services,
            "suspected_root_cause_service": diagnosis.suspected_root_cause_service,
            "incident_ids": diagnosis.incident_ids,
            "candidate_scores": diagnosis.candidate_scores,
            "summary": diagnosis.summary,
            "trigger_context": trigger_context,
            "trigger_analysis": trigger_analysis,
            "evidence_bundle": evidence_bundle,
            "llm_reasoning": llm_reasoning or {},
            "evidence": [
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
            ],
        }

        json_path = output_path / f"{stem}.json"
        md_path = output_path / f"{stem}.md"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(self._render_markdown(report), encoding="utf-8")

        return {
            "json_report": str(json_path),
            "markdown_report": str(md_path),
            "summary": report["summary"],
        }

    @classmethod
    def _render_markdown(cls, report: dict[str, Any]) -> str:
        llm_reasoning = report.get("llm_reasoning", {})
        trigger_metrics = report["trigger_context"].get("triggered_metrics", {})
        missing_metrics = report.get("evidence_bundle", {}).get("data_quality", {}).get("missing_trigger_metrics", [])
        candidate_scores = report.get("candidate_scores", {})
        tool_trace = llm_reasoning.get("agent_tool_trace", [])
        root_cause = report.get("suspected_root_cause_service")
        root_cause_score = candidate_scores.get(root_cause, "无") if root_cause else "无"
        confidence = cls._confidence_level(root_cause_score, len(report.get("evidence", [])))
        severity = cls._severity_level(report)
        abnormal_services = "、".join(report["abnormal_services"]) if report["abnormal_services"] else "无"

        trigger_lines = cls._render_trigger_metrics(trigger_metrics)
        breach_lines = cls._render_breaches(report.get("trigger_analysis", {}).get("breaches", []))
        lifecycle_lines = cls._render_lifecycle_evidence(
            report.get("evidence_bundle", {}).get("kubernetes_lifecycle_evidence", {})
        )
        runtime_k8s_lines = cls._render_runtime_kubernetes_evidence(
            report.get("evidence_bundle", {}).get("kubernetes_runtime_evidence", {})
        )
        evidence_lines = cls._render_evidence(report.get("evidence", []))
        candidate_lines = cls._render_candidates(candidate_scores)
        missing_lines = "\n".join([f"- `{item}`" for item in missing_metrics]) if missing_metrics else "- 无"
        llm_evidence_lines = cls._render_llm_list(llm_reasoning.get("evidence_summary"), fallback="- 暂无补充总结")
        llm_missing_lines = cls._render_llm_list(llm_reasoning.get("missing_observations"), fallback=missing_lines)
        llm_action_lines = cls._render_llm_list(llm_reasoning.get("operator_actions"), fallback="- 暂无额外建议")
        tool_trace_lines = cls._render_tool_trace(tool_trace)
        llm_overview = llm_reasoning.get("incident_overview") or "未生成事件概览。"
        llm_hypothesis = llm_reasoning.get("root_cause_hypothesis") or report["summary"]
        llm_explanation = llm_reasoning.get("report_explanation") or report["summary"]

        return (
            "# 在线智能运维诊断报告\n\n"
            "## 一、事件概览\n\n"
            f"- 分析模式：`在线巡检`\n"
            f"- 是否检测到异常：`{report['is_anomaly']}`\n"
            f"- 事件严重度：`{severity}`\n"
            f"- 根因置信度：`{confidence}`\n"
            f"- 推测根因服务：`{root_cause or '无'}`\n"
            f"- 根因服务总评分：`{root_cause_score}`\n"
            f"- 事件概述：{llm_overview}\n\n"
            "## 二、监测窗口与数据范围\n\n"
            f"- 时间窗口：`{report['start_time']}` -> `{report['end_time']}`\n"
            f"- 行号范围：`{report['start_index']}` -> `{report['end_index']}`\n"
            f"- 数据来源：`{report['dataset_name']}`\n"
            f"- 触发回看长度：`{report['trigger_context'].get('lookback_minutes', '未知')}` 分钟\n"
            f"- 采样步长：`{report['trigger_context'].get('step_seconds', '未知')}` 秒\n\n"
            "## 三、触发情况\n\n"
            f"- 触发时间：`{report['trigger_context'].get('trigger_time', '未知')}`\n"
            f"- 触发原因：{report['trigger_context'].get('trigger_reason', '未知')}\n"
            f"- 触发服务聚合分：`{report.get('trigger_analysis', {}).get('service_scores', {})}`\n"
            f"{trigger_lines}\n\n"
            "## 四、超阈值证据\n\n"
            f"{breach_lines}\n\n"
            "## 五、影响面与根因分析\n\n"
            f"- 异常服务列表：`{abnormal_services}`\n"
            f"- 当前规则诊断结论：{report['summary']}\n"
            f"- LLM 根因假设：{llm_hypothesis}\n\n"
            "## 六、Kubernetes 生命周期与运行证据\n\n"
            f"{lifecycle_lines}\n\n"
            f"{runtime_k8s_lines}\n\n"
            "## 七、关键指标证据\n\n"
            f"{evidence_lines}\n\n"
            "## 八、候选根因排序\n\n"
            f"{candidate_lines}\n\n"
            "## 九、数据完整性与缺失观测\n\n"
            f"- 触发指标总数：`{report.get('evidence_bundle', {}).get('data_quality', {}).get('trigger_metric_count', 0)}`\n"
            f"- 成功采集触发指标数：`{report.get('evidence_bundle', {}).get('data_quality', {}).get('available_trigger_metric_count', 0)}`\n"
            f"{llm_missing_lines}\n\n"
            "## 十、综合解释\n\n"
            f"{llm_explanation}\n\n"
            "## 十一、建议动作\n\n"
            f"{llm_action_lines}\n\n"
            "## 十二、Agent 工具调用轨迹\n\n"
            f"{tool_trace_lines}\n\n"
            "## 十三、补充说明\n\n"
            f"{llm_evidence_lines}\n\n"
            "## 十四、方法说明\n\n"
            "- 在线报告先通过规则层判断是否触发，再进入证据收集、候选根因排序和 LLM 综合解释。\n"
            "- “证据分”来自离线基线统计与在线窗口对比；“服务总评分”来自多证据汇总和依赖关系修正。\n"
            "- 如果 p95 / error_rate 等 HTTP 指标缺失，报告中的“缺失观测”会直接影响置信度，结论应结合人工复核使用。\n"
        )

    @staticmethod
    def _confidence_level(root_cause_score: float | str, evidence_count: int) -> str:
        if isinstance(root_cause_score, str):
            return "低"
        if root_cause_score >= 15 and evidence_count >= 2:
            return "高"
        if root_cause_score >= 8:
            return "中"
        return "低"

    @staticmethod
    def _severity_level(report: dict[str, Any]) -> str:
        """根据生命周期、容器状态和指标证据综合判断严重度。"""

        abnormal_count = len(report.get("abnormal_services", []))
        breach_count = len(report.get("trigger_analysis", {}).get("breaches", []))
        evidence_bundle = report.get("evidence_bundle", {})
        lifecycle = evidence_bundle.get("kubernetes_lifecycle_evidence", {}) or {}
        runtime = evidence_bundle.get("kubernetes_runtime_evidence", {}) or {}

        any_not_ready = False
        any_critical_reason = False
        for service_data in runtime.values():
            pod_status = service_data.get("pod_status", {}) or {}
            for pod in pod_status.get("pods", []) or []:
                for container in pod.get("containers", []) or []:
                    if not bool(container.get("ready", False)):
                        any_not_ready = True
                    reason = str(container.get("last_termination_reason") or "")
                    if reason in {"OOMKilled", "Error", "CrashLoopBackOff"}:
                        any_critical_reason = True

            events = service_data.get("events", {}) or {}
            for event in events.get("events", []) or []:
                reason = str(event.get("reason") or "")
                message = str(event.get("message") or "")
                if reason in {"Evicted", "BackOff", "FailedMount"}:
                    any_critical_reason = True
                if "CrashLoopBackOff" in message or "OOMKilled" in message:
                    any_critical_reason = True

        if any_critical_reason:
            return "高"

        # 单次 Pod 删除/重建且新 Pod 尚未完全 Ready，通常按“中”处理。
        if lifecycle.get("triggered") and any_not_ready:
            return "中"

        # 已自动恢复的生命周期事件通常不应仅因异常服务数量多而判为高。
        if lifecycle.get("triggered"):
            return "低" if breach_count == 0 else "中"

        if abnormal_count >= 6 or breach_count >= 3:
            return "高"
        if abnormal_count >= 3 or breach_count >= 2:
            return "中"
        return "低"

    @staticmethod
    def _render_trigger_metrics(trigger_metrics: dict[str, float]) -> str:
        if not trigger_metrics:
            return "- 本次触发没有记录到具体触发指标值。"
        return "\n".join([f"- `{metric}`：`{value}`" for metric, value in trigger_metrics.items()])

    @staticmethod
    def _render_breaches(breaches: list[dict[str, Any]]) -> str:
        if not breaches:
            return "1. 当前没有保留下来的超阈值明细。"
        return "\n".join(
            [
                f"{idx + 1}. `{item['feature_name']}`\n"
                f"   服务：`{item['service']}`\n"
                f"   观测值 / 阈值：`{item['observed_value']}` / `{item['threshold']}`\n"
                f"   超阈倍数：`{item['exceed_ratio']}`"
                for idx, item in enumerate(breaches)
            ]
        )

    @staticmethod
    def _render_lifecycle_evidence(lifecycle: dict[str, Any]) -> str:
        if not isinstance(lifecycle, dict) or not lifecycle.get("events"):
            return "1. 本轮没有检测到 Pod 删除或重建。"
        lines: list[str] = []
        for idx, event in enumerate(lifecycle.get("events", []), start=1):
            removed = ", ".join(
                pod.get("name", "unknown") for pod in event.get("removed_pods", [])
            ) or "无"
            added = ", ".join(
                pod.get("name", "unknown") for pod in event.get("added_pods", [])
            ) or "无"
            lines.append(
                f"{idx}. `{event.get('event_type', 'unknown')}`：服务 `{event.get('service', 'unknown')}`\n"
                f"   消失的 Pod：`{removed}`\n"
                f"   新出现的 Pod：`{added}`\n"
                f"   说明：{event.get('explanation', '')}"
            )
        return "\n".join(lines)

    @staticmethod
    def _render_runtime_kubernetes_evidence(evidence: dict[str, Any]) -> str:
        if not evidence:
            return "- 未采集额外 Pod 状态或 Kubernetes Event。"
        lines: list[str] = []
        for service, details in evidence.items():
            pod_status = details.get("pod_status", {})
            events = details.get("events", {})
            lines.append(
                f"- `{service}` 当前 Pod 数：`{pod_status.get('pod_count', '未知')}`；"
                f"相关 Event 数：`{events.get('event_count', '未知')}`"
            )
            for event in events.get("events", [])[-5:]:
                lines.append(
                    f"  - `{event.get('reason', 'Unknown')}`：{event.get('message', '')}"
                )
        return "\n".join(lines)

    @staticmethod
    def _render_evidence(evidence: list[dict[str, Any]]) -> str:
        if not evidence:
            return "1. 当前没有记录到关键异常证据。"
        return "\n".join(
            [
                f"{idx + 1}. `{item['feature_name']}`\n"
                f"   归属服务：`{item['service']}`\n"
                f"   指标类型：`{item['metric']}`\n"
                f"   观测值 / 基线均值：`{item['observed_value']}` / `{item['baseline_mean']}`\n"
                f"   基线标准差：`{item['baseline_std']}`\n"
                f"   证据分：`{item['score']}`\n"
                f"   解释：{item['reason']}"
                for idx, item in enumerate(evidence)
            ]
        )

    @staticmethod
    def _render_candidates(candidate_scores: dict[str, float]) -> str:
        if not candidate_scores:
            return "1. 当前没有候选根因服务评分。"
        return "\n".join(
            [
                f"{idx + 1}. `{service}`：服务总评分 `{score}`{'，当前排序第一' if idx == 0 else ''}"
                for idx, (service, score) in enumerate(candidate_scores.items())
            ]
        )

    @staticmethod
    def _render_llm_list(items: Any, fallback: str) -> str:
        if not isinstance(items, list) or not items:
            return fallback
        return "\n".join([f"- {item}" for item in items])

    @staticmethod
    def _render_tool_trace(tool_trace: list[dict[str, Any]]) -> str:
        if not tool_trace:
            return "1. 本次 Agent 未实际调用工具，或没有记录到可展示的工具轨迹。"

        lines: list[str] = []
        for idx, item in enumerate(tool_trace, start=1):
            tool_name = item.get("tool_name", "unknown_tool")
            arguments = item.get("arguments", {})
            summary = item.get("result_summary", {})
            timestamp = item.get("timestamp", "unknown")
            lines.append(
                f"{idx}. 工具：`{tool_name}`\n"
                f"   调用时间：`{timestamp}`\n"
                f"   调用参数：`{json.dumps(arguments, ensure_ascii=False)}`\n"
                f"   查询结果：`{json.dumps(summary, ensure_ascii=False)}`"
            )
        return "\n".join(lines)
