"""Toolbox for the online VeADK agent."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from benchmark.prometheus_client import PrometheusClient


class OnlineToolbox:
    """Runtime tools exposed to the online VeADK agent."""

    def __init__(
        self,
        prometheus_url: str,
        namespace: str = "online-boutique",
        allow_actions: bool = False,
    ) -> None:
        self.prometheus_url = prometheus_url.rstrip("/")
        self.namespace = namespace
        self.allow_actions = allow_actions
        self.prom_client = PrometheusClient(self.prometheus_url)
        self.call_history: list[dict[str, Any]] = []

    def reset_call_history(self) -> None:
        """Clear tool call history before a new reasoning round."""

        self.call_history = []

    def get_call_history(self) -> list[dict[str, Any]]:
        """Return a copy of tool call history for report rendering."""

        return list(self.call_history)

    def execute_promql(
        self,
        query: str,
        minutes: int = 10,
        step_seconds: int = 15,
    ) -> dict[str, Any]:
        """Execute a PromQL query and return a compact summary."""

        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=max(1, minutes))
        series = self.prom_client.query_range(
            query=query,
            start=start,
            end=end,
            step=max(1, step_seconds),
        )
        if series is None or series.empty:
            result = {
                "status": "empty",
                "query": query,
                "message": "Prometheus returned no data for this query window.",
            }
            return self._record_call(
                tool_name="execute_promql",
                arguments={
                    "query": query,
                    "minutes": minutes,
                    "step_seconds": step_seconds,
                },
                result=result,
            )

        values = [float(value) for value in series.tolist()]
        preview_count = min(5, len(values))
        result = {
            "status": "ok",
            "query": query,
            "window_minutes": minutes,
            "point_count": len(values),
            "start_time": str(series.index[0]),
            "end_time": str(series.index[-1]),
            "latest_value": round(values[-1], 6),
            "min_value": round(min(values), 6),
            "max_value": round(max(values), 6),
            "avg_value": round(sum(values) / len(values), 6),
            "preview": [
                {
                    "timestamp": str(series.index[idx]),
                    "value": round(values[idx], 6),
                }
                for idx in range(preview_count)
            ],
        }
        return self._record_call(
            tool_name="execute_promql",
            arguments={
                "query": query,
                "minutes": minutes,
                "step_seconds": step_seconds,
            },
            result=result,
        )

    def get_service_logs(
        self,
        service_name: str,
        tail_lines: int = 50,
    ) -> dict[str, Any]:
        """Fetch recent Kubernetes logs for one deployment or matching pod."""

        deployment_ref = f"deployment/{service_name}"
        cmd = [
            "kubectl",
            "logs",
            deployment_ref,
            "-n",
            self.namespace,
            "--tail",
            str(max(1, tail_lines)),
            "--all-containers=true",
        ]
        run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if run.returncode == 0 and run.stdout.strip():
            result = self._format_logs_result(service_name, cmd, run.stdout)
            return self._record_call(
                tool_name="get_service_logs",
                arguments={"service_name": service_name, "tail_lines": tail_lines},
                result=result,
            )

        pod_name = self._resolve_first_pod(service_name)
        if not pod_name:
            result = {
                "status": "error",
                "service_name": service_name,
                "message": run.stderr.strip() or "No matching deployment or pod found.",
                "command": " ".join(cmd),
            }
            return self._record_call(
                tool_name="get_service_logs",
                arguments={"service_name": service_name, "tail_lines": tail_lines},
                result=result,
            )

        pod_cmd = [
            "kubectl",
            "logs",
            pod_name,
            "-n",
            self.namespace,
            "--tail",
            str(max(1, tail_lines)),
            "--all-containers=true",
        ]
        pod_run = subprocess.run(pod_cmd, capture_output=True, text=True, encoding="utf-8")
        if pod_run.returncode != 0:
            result = {
                "status": "error",
                "service_name": service_name,
                "message": pod_run.stderr.strip() or "Failed to fetch logs from matching pod.",
                "command": " ".join(pod_cmd),
            }
            return self._record_call(
                tool_name="get_service_logs",
                arguments={"service_name": service_name, "tail_lines": tail_lines},
                result=result,
            )

        result = self._format_logs_result(service_name, pod_cmd, pod_run.stdout)
        return self._record_call(
            tool_name="get_service_logs",
            arguments={"service_name": service_name, "tail_lines": tail_lines},
            result=result,
        )


    def get_pod_status(self, service_name: str) -> dict[str, Any]:
        """Return current Pod status and container termination details for a service."""

        cmd = [
            "kubectl", "get", "pods", "-n", self.namespace,
            "-l", f"app={service_name}", "-o", "json",
        ]
        run = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if run.returncode != 0:
            result = {
                "status": "error",
                "service_name": service_name,
                "message": run.stderr.strip() or "Failed to query Pod status.",
                "command": " ".join(cmd),
            }
            return self._record_call("get_pod_status", {"service_name": service_name}, result)

        try:
            payload = json.loads(run.stdout)
        except json.JSONDecodeError as exc:
            result = {
                "status": "error",
                "service_name": service_name,
                "message": f"Invalid kubectl JSON: {exc}",
            }
            return self._record_call("get_pod_status", {"service_name": service_name}, result)

        pods: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            metadata = item.get("metadata", {})
            status = item.get("status", {})
            containers: list[dict[str, Any]] = []
            for container in status.get("containerStatuses", []) or []:
                last_state = container.get("lastState", {}) or {}
                terminated = last_state.get("terminated", {}) or {}
                containers.append({
                    "name": container.get("name"),
                    "ready": container.get("ready"),
                    "restart_count": container.get("restartCount", 0),
                    "last_termination_reason": terminated.get("reason"),
                    "last_exit_code": terminated.get("exitCode"),
                    "last_finished_at": terminated.get("finishedAt"),
                })
            pods.append({
                "name": metadata.get("name"),
                "uid": metadata.get("uid"),
                "creation_timestamp": metadata.get("creationTimestamp"),
                "deletion_timestamp": metadata.get("deletionTimestamp"),
                "phase": status.get("phase"),
                "pod_ip": status.get("podIP"),
                "containers": containers,
            })

        result = {
            "status": "ok",
            "service_name": service_name,
            "pod_count": len(pods),
            "pods": pods,
            "command": " ".join(cmd),
        }
        return self._record_call("get_pod_status", {"service_name": service_name}, result)

    def get_kubernetes_events(
        self,
        service_name: str = "",
        limit: int = 30,
    ) -> dict[str, Any]:
        """Return recent namespace Events, optionally filtered to one service."""

        cmd = [
            "kubectl", "get", "events", "-n", self.namespace,
            "--sort-by=.metadata.creationTimestamp", "-o", "json",
        ]
        run = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if run.returncode != 0:
            result = {
                "status": "error",
                "service_name": service_name,
                "message": run.stderr.strip() or "Failed to query Kubernetes Events.",
                "command": " ".join(cmd),
            }
            return self._record_call(
                "get_kubernetes_events",
                {"service_name": service_name, "limit": limit},
                result,
            )

        try:
            payload = json.loads(run.stdout)
        except json.JSONDecodeError as exc:
            result = {
                "status": "error",
                "service_name": service_name,
                "message": f"Invalid kubectl JSON: {exc}",
            }
            return self._record_call(
                "get_kubernetes_events",
                {"service_name": service_name, "limit": limit},
                result,
            )

        selected: list[dict[str, Any]] = []
        service_lower = service_name.lower()
        for item in payload.get("items", []):
            metadata = item.get("metadata", {})
            involved = item.get("involvedObject", {})
            message = str(item.get("message") or "")
            object_name = str(involved.get("name") or "")
            if service_lower and service_lower not in object_name.lower() and service_lower not in message.lower():
                continue
            selected.append({
                "timestamp": item.get("eventTime")
                or item.get("lastTimestamp")
                or item.get("firstTimestamp")
                or metadata.get("creationTimestamp"),
                "type": item.get("type"),
                "reason": item.get("reason"),
                "object_kind": involved.get("kind"),
                "object_name": object_name,
                "message": message,
                "count": item.get("count", 1),
            })

        selected = selected[-max(1, limit):]
        result = {
            "status": "ok",
            "service_name": service_name,
            "event_count": len(selected),
            "events": selected,
            "command": " ".join(cmd),
        }
        return self._record_call(
            "get_kubernetes_events",
            {"service_name": service_name, "limit": limit},
            result,
        )

    def restart_pod(self, service_name: str) -> dict[str, Any]:
        """Restart one deployment when action execution is allowed."""

        if not self.allow_actions:
            result = {
                "status": "blocked",
                "service_name": service_name,
                "message": (
                    "Restart action is disabled. Re-run online monitor with --allow-actions "
                    "if you want the agent to execute rollout restarts."
                ),
            }
            return self._record_call(
                tool_name="restart_pod",
                arguments={"service_name": service_name},
                result=result,
            )

        cmd = [
            "kubectl",
            "rollout",
            "restart",
            f"deployment/{service_name}",
            "-n",
            self.namespace,
        ]
        run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if run.returncode != 0:
            result = {
                "status": "error",
                "service_name": service_name,
                "message": run.stderr.strip() or "Rollout restart failed.",
                "command": " ".join(cmd),
            }
            return self._record_call(
                tool_name="restart_pod",
                arguments={"service_name": service_name},
                result=result,
            )

        result = {
            "status": "ok",
            "service_name": service_name,
            "message": run.stdout.strip() or f"Triggered rollout restart for {service_name}.",
            "command": " ".join(cmd),
        }
        return self._record_call(
            tool_name="restart_pod",
            arguments={"service_name": service_name},
            result=result,
        )

    def _resolve_first_pod(self, service_name: str) -> str | None:
        cmd = [
            "kubectl",
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            f"app={service_name}",
            "-o",
            "json",
        ]
        run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if run.returncode != 0 or not run.stdout.strip():
            return None

        try:
            payload = json.loads(run.stdout)
        except json.JSONDecodeError:
            return None

        items = payload.get("items", [])
        if not items:
            return None
        return str(items[0].get("metadata", {}).get("name") or "")

    @staticmethod
    def _format_logs_result(service_name: str, command: list[str], output: str) -> dict[str, Any]:
        lines = [line for line in output.splitlines() if line.strip()]
        preview = lines[-20:] if len(lines) > 20 else lines
        return {
            "status": "ok",
            "service_name": service_name,
            "line_count": len(lines),
            "command": " ".join(command),
            "log_excerpt": "\n".join(preview),
        }

    def _record_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Store a compact trace of what the agent actually called and observed."""

        self.call_history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_name": tool_name,
                "arguments": arguments,
                "result_summary": self._summarize_result(tool_name, result),
            }
        )
        return result

    @staticmethod
    def _summarize_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "execute_promql":
            return {
                "status": result.get("status"),
                "query": result.get("query"),
                "point_count": result.get("point_count"),
                "latest_value": result.get("latest_value"),
                "min_value": result.get("min_value"),
                "max_value": result.get("max_value"),
                "avg_value": result.get("avg_value"),
                "message": result.get("message"),
            }

        if tool_name == "get_pod_status":
            return {
                "status": result.get("status"),
                "service_name": result.get("service_name"),
                "pod_count": result.get("pod_count"),
                "pods": result.get("pods"),
                "message": result.get("message"),
            }

        if tool_name == "get_kubernetes_events":
            return {
                "status": result.get("status"),
                "service_name": result.get("service_name"),
                "event_count": result.get("event_count"),
                "events": result.get("events"),
                "message": result.get("message"),
            }

        if tool_name == "get_service_logs":
            return {
                "status": result.get("status"),
                "service_name": result.get("service_name"),
                "line_count": result.get("line_count"),
                "message": result.get("message"),
                "log_excerpt": result.get("log_excerpt"),
            }

        if tool_name == "restart_pod":
            return {
                "status": result.get("status"),
                "service_name": result.get("service_name"),
                "message": result.get("message"),
            }

        return {"status": result.get("status"), "message": result.get("message")}


def fetch_instant_prometheus_json(prometheus_url: str, query: str) -> dict[str, Any]:
    """Helper for direct instant Prometheus queries when needed by report/debug flows."""

    response = requests.get(
        f"{prometheus_url.rstrip('/')}/api/v1/query",
        params={"query": query},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()
