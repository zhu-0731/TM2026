"""Report generation for offline diagnosis runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DiagnosisResult, DiagnosticWindow, StructuredReport


class ReportWriter:
    """Write structured JSON and richer Markdown reports."""

    def write(
        self,
        window: DiagnosticWindow,
        diagnosis: DiagnosisResult,
        output_dir: str | Path,
        agent_context: dict[str, Any] | None = None,
    ) -> StructuredReport:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        report = StructuredReport(
            mode="offline",
            dataset_name=window.dataset_name,
            split=window.split,
            start_time=window.start_time,
            end_time=window.end_time,
            start_index=window.start_index,
            end_index=window.end_index,
            is_anomaly=diagnosis.is_anomaly,
            abnormal_services=diagnosis.abnormal_services,
            suspected_root_cause_service=diagnosis.suspected_root_cause_service,
            incident_ids=diagnosis.incident_ids,
            evidence=[
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
            candidate_scores=diagnosis.candidate_scores,
            summary=diagnosis.summary,
            agent_context=agent_context or {},
        )

        stem = f"{window.split}_{window.start_index}_{window.end_index}"
        json_path = output_path / f"{stem}.json"
        md_path = output_path / f"{stem}.md"
        json_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(self._render_markdown(report), encoding="utf-8")
        return report

    @classmethod
    def _render_markdown(cls, report: StructuredReport) -> str:
        root_cause_score = cls._root_cause_score(report)
        confidence = cls._confidence_level(root_cause_score, len(report.evidence))
        severity = cls._severity_level(report)
        incident_lines = "、".join(report.incident_ids) if report.incident_ids else "无"
        abnormal_services = "、".join(report.abnormal_services) if report.abnormal_services else "无"
        evidence_lines = cls._render_evidence(report.evidence)
        candidate_lines = cls._render_candidates(report.candidate_scores)
        impact_lines = cls._render_impact(report)
        actions_lines = cls._render_actions(report)
        agent_overview_lines = cls._render_agent_overview(report.agent_context)
        tool_trace_lines = cls._render_tool_trace(report.agent_context.get("tool_trace", []))
        explanation_lines = cls._render_explanation(report)

        return (
            "# AIOps 离线诊断报告\n\n"
            "## 一、事件概览\n\n"
            f"- 分析模式：`{report.mode}`\n"
            f"- 是否检测到异常：`{report.is_anomaly}`\n"
            f"- 事件严重度：`{severity}`\n"
            f"- 根因置信度：`{confidence}`\n"
            f"- 推测根因服务：`{report.suspected_root_cause_service or '无'}`\n"
            f"- 根因服务总评分：`{root_cause_score}`\n"
            f"- 窗口内事件 ID：`{incident_lines}`\n\n"
            "## 二、窗口与数据范围\n\n"
            f"- 数据集：`{report.dataset_name}`\n"
            f"- 数据分片：`{report.split}`\n"
            f"- 时间窗口：`{report.start_time}` -> `{report.end_time}`\n"
            f"- 行号范围：`{report.start_index}` -> `{report.end_index}`\n\n"
            "## 三、Agent 分析过程\n\n"
            f"{agent_overview_lines}\n\n"
            "## 四、执行摘要\n\n"
            f"{report.summary}\n\n"
            "## 五、影响面分析\n\n"
            f"- 异常服务列表：`{abnormal_services}`\n"
            f"{impact_lines}\n\n"
            "## 六、关键证据\n\n"
            f"{evidence_lines}\n\n"
            "## 七、候选根因排序\n\n"
            f"{candidate_lines}\n\n"
            "## 八、Agent 工具调用轨迹\n\n"
            f"{tool_trace_lines}\n\n"
            "## 九、报告解释\n\n"
            f"{explanation_lines}\n\n"
            "## 十、处置建议\n\n"
            f"{actions_lines}\n\n"
            "## 十一、方法说明\n\n"
            "- “证据分”表示单个指标相对训练集基线的偏离程度，主要依据 z-score 计算。\n"
            "- “服务总评分”表示服务汇总多条异常证据并结合依赖关系修正后的排序结果。\n"
            "- “Agent 工具调用轨迹”展示了离线 Agent 在这次分析过程中实际调用过的工具与关键结果摘要。\n"
            "- 离线回放适合验证模型/规则是否能在历史窗口中识别异常与根因，不代表实时告警能力。\n"
        )

    @staticmethod
    def _root_cause_score(report: StructuredReport) -> float | str:
        if not report.suspected_root_cause_service:
            return "无"
        return report.candidate_scores.get(report.suspected_root_cause_service, "无")

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
    def _severity_level(report: StructuredReport) -> str:
        abnormal_count = len(report.abnormal_services)
        if abnormal_count >= 6:
            return "高"
        if abnormal_count >= 3:
            return "中"
        return "低"

    @staticmethod
    def _render_impact(report: StructuredReport) -> str:
        abnormal_count = len(report.abnormal_services)
        evidence_count = len(report.evidence)
        return (
            f"- 受影响服务数量：`{abnormal_count}`\n"
            f"- 直接支撑当前结论的证据数量：`{evidence_count}`"
        )

    @staticmethod
    def _render_evidence(evidence: list[dict[str, Any]]) -> str:
        if not evidence:
            return "1. 当前没有记录到可用于支撑结论的关键指标证据。"

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
            return "1. 当前没有可用的候选服务评分。"

        return "\n".join(
            [
                f"{idx + 1}. `{service}`：服务总评分 `{score}`{'，当前排序第一' if idx == 0 else ''}"
                for idx, (service, score) in enumerate(candidate_scores.items())
            ]
        )

    @staticmethod
    def _render_actions(report: StructuredReport) -> str:
        root_cause = report.suspected_root_cause_service or "目标服务"
        if not report.is_anomaly:
            return "- 当前窗口没有显著异常，无需升级处置，建议继续观察后续窗口。"

        return "\n".join(
            [
                f"- 优先复核 `{root_cause}` 在该时间窗口附近的资源波动、错误率、重启和下游调用情况。",
                f"- 对 `{root_cause}` 的最近配置变更、发布记录和依赖健康状态做交叉核对。",
                "- 建议结合关键证据、候选根因排序与上下游依赖状态，形成可执行的复核与处置闭环。",
            ]
        )

    @staticmethod
    def _render_agent_overview(agent_context: dict[str, Any]) -> str:
        tool_count = agent_context.get("tool_call_count", 0)
        dataset_root = agent_context.get("dataset_root", "未知")
        scan_result_count = agent_context.get("scan_result_count", 0)
        selected_window = agent_context.get("selected_window")
        lines = [
            f"- 数据集根目录：`{dataset_root}`",
            f"- 本次写报告前累计工具调用次数：`{tool_count}`",
            f"- 最近一次异常窗口扫描结果数量：`{scan_result_count}`",
        ]
        if selected_window:
            lines.append(
                f"- 当前分析窗口来源：排名 `#{selected_window.get('rank', '未知')}` 的候选异常窗口"
            )
            lines.append(
                f"- 候选窗口分数：`{selected_window.get('anomaly_score', '未知')}`"
            )
        else:
            lines.append("- 当前分析窗口来源：手动指定窗口或直接加载窗口。")
        return "\n".join(lines)

    @staticmethod
    def _render_tool_trace(tool_trace: list[dict[str, Any]]) -> str:
        if not tool_trace:
            return "1. 本次离线分析没有记录到可展示的工具调用轨迹。"

        lines: list[str] = []
        for idx, item in enumerate(tool_trace, start=1):
            lines.append(
                f"{idx}. 工具：`{item.get('tool_name', 'unknown_tool')}`\n"
                f"   调用时间：`{item.get('timestamp', 'unknown')}`\n"
                f"   调用参数：`{json.dumps(item.get('arguments', {}), ensure_ascii=False)}`\n"
                f"   结果摘要：`{json.dumps(item.get('result_summary', {}), ensure_ascii=False)}`"
            )
        return "\n".join(lines)

    @staticmethod
    def _render_explanation(report: StructuredReport) -> str:
        root_cause = report.suspected_root_cause_service or "未知服务"
        abnormal_services = "、".join(report.abnormal_services) if report.abnormal_services else "无"
        evidence_count = len(report.evidence)
        return (
            f"本次离线回放窗口中，系统识别到 `{abnormal_services}` 出现异常迹象，"
            f"最终将 `{root_cause}` 排在候选根因首位。当前结论主要由 `{evidence_count}` 条关键证据支撑，"
            "结论适合用于历史复盘、故障机理分析以及后续运维处置决策。"
        )
