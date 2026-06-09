"""VeADK agent entrypoint for offline diagnosis."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import yaml

def load_local_model_settings() -> dict[str, str]:
    """Load VeADK model settings from the local config file and force env sync."""

    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

    agent_config = ((payload.get("model") or {}).get("agent") or {})
    api_key = agent_config.get("api_key")
    api_base = agent_config.get("api_base")
    provider = agent_config.get("provider")
    model_name = agent_config.get("name")

    resolved: dict[str, str] = {}

    if api_key:
        resolved["MODEL_AGENT_API_KEY"] = str(api_key)
        os.environ["MODEL_AGENT_API_KEY"] = str(api_key)
    if api_base:
        resolved["MODEL_AGENT_API_BASE"] = str(api_base)
        os.environ["MODEL_AGENT_API_BASE"] = str(api_base)
    if provider:
        resolved["MODEL_AGENT_PROVIDER"] = str(provider)
        os.environ["MODEL_AGENT_PROVIDER"] = str(provider)
    if model_name:
        resolved["MODEL_AGENT_MODEL"] = str(model_name)
        os.environ["MODEL_AGENT_MODEL"] = str(model_name)

    return resolved


def patch_veadk_default_model_constants(resolved: dict[str, str]) -> None:
    """Patch VeADK modules that still read hard-coded default model constants."""

    if not resolved:
        return

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

    # Some VeADK submodules import these defaults by value at module import time.
    # Import them after patching `veadk.consts`, then patch the module globals too.
    try:
        import veadk.memory.short_term_memory_processor as short_term_memory_processor

        if model_name:
            short_term_memory_processor.DEFAULT_MODEL_AGENT_NAME = model_name
        if provider:
            short_term_memory_processor.DEFAULT_MODEL_AGENT_PROVIDER = provider
        if api_base:
            short_term_memory_processor.DEFAULT_MODEL_AGENT_API_BASE = api_base
    except Exception:
        pass


# Load model settings before importing VeADK, because VeADK/LiteLLM may
# initialize model-related configuration during import time.
_resolved_model_settings = load_local_model_settings()
patch_veadk_default_model_constants(_resolved_model_settings)

# Keep the terminal output clean. VeADK internal logs will be written to file.
os.environ.setdefault("LOGGING_LEVEL", "ERROR")

from veadk import Agent, Runner
from veadk.utils.logger import logger as veadk_logger

from .prompts import DEFAULT_USER_PROMPT, SYSTEM_PROMPT, WELCOME_TEXT
from .tools import (
    continue_with_ranked_window_tool,
    detect_anomaly_tool,
    diagnose_root_cause_tool,
    find_anomalous_windows_tool,
    inspect_current_state_tool,
    load_window_tool,
    run_full_offline_diagnosis_tool,
    show_ranked_windows_tool,
    show_tool_history_tool,
    summarize_dataset_tool,
    write_report_tool,
)

LOG_DIR = Path(__file__).resolve().parents[1] / "output" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
veadk_logger.add(
    LOG_DIR / "veadk_agent.log",
    level="DEBUG",
    encoding="utf-8",
    enqueue=True,
)


def build_agent() -> Agent:
    """Build the VeADK offline diagnosis agent."""

    return Agent(
        name="aiops_offline_diagnosis_agent",
        instruction=SYSTEM_PROMPT,
        tools=[
            summarize_dataset_tool,
            inspect_current_state_tool,
            find_anomalous_windows_tool,
            show_ranked_windows_tool,
            continue_with_ranked_window_tool,
            run_full_offline_diagnosis_tool,
            load_window_tool,
            detect_anomaly_tool,
            diagnose_root_cause_tool,
            write_report_tool,
            show_tool_history_tool,
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive VeADK offline diagnosis agent")
    parser.add_argument(
        "--prompt",
        help="Run one single prompt instead of interactive chat.",
    )
    return parser


async def run_once(prompt: str = DEFAULT_USER_PROMPT) -> str:
    """Run one local request against the VeADK agent."""

    agent = build_agent()
    runner = Runner(agent=agent)
    result = await runner.run(messages=prompt)
    return str(result)


async def interactive_chat() -> None:
    """Start a simple command-line chat loop."""

    print(WELCOME_TEXT)
    agent = build_agent()
    runner = Runner(agent=agent)

    while True:
        user_input = input("\n你> ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("已退出离线智能运维 Agent。")
            return

        result = await runner.run(messages=user_input)
        print(f"\nAgent> {result}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.prompt:
        output = asyncio.run(run_once(args.prompt))
        print(output)
        return

    asyncio.run(interactive_chat())


if __name__ == "__main__":
    main()
