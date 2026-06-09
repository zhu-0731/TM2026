"""Unified CLI entrypoint for the AIOps agent package."""

from __future__ import annotations

import argparse
import asyncio
import json

from aiops_agent.online.monitor import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_QUERIES_PATH,
    run_monitor_loop,
    run_monitor_once,
)

DEFAULT_OFFLINE_PROMPT = "请先总结数据集，再扫描 valid split 中最异常的窗口，并继续分析排名第一的窗口，最后生成完整报告。"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified AIOps agent launcher for offline and online modes."
    )
    parser.add_argument(
        "--mode",
        choices=["offline", "online"],
        default="offline",
        help="Select offline historical diagnosis or online realtime monitoring mode.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Run one single offline LLM diagnosis request instead of interactive chat.",
    )
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit in online mode.")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--namespace", default="online-boutique")
    parser.add_argument("--dataset-root", default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--queries-path", default=DEFAULT_QUERIES_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--interval-seconds", type=int, default=10)
    parser.add_argument("--lookback-minutes", type=int, default=10)
    parser.add_argument("--step-seconds", type=int, default=5)
    parser.add_argument("--cooldown-seconds", type=int, default=300)
    parser.add_argument(
        "--disable-llm",
        action="store_true",
        help="Disable LLM reasoning in online mode and keep rule-only explanations.",
    )
    parser.add_argument(
        "--allow-actions",
        action="store_true",
        help="Allow the online agent to execute action tools such as restart_pod.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "offline":
        from aiops_agent.veadk_app.agent import interactive_chat, run_once

        if args.prompt is not None:
            output = asyncio.run(run_once(args.prompt or DEFAULT_OFFLINE_PROMPT))
            print(output)
            return

        asyncio.run(interactive_chat())
        return

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
