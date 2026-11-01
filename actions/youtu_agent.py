"""Optional text-only Youtu-Agent bridge for JARVIS.

The agent runs with Youtu-Agent's BaseEnv and no tools, so it cannot access the
local shell, files, browser, or MCP servers. The task is sent to the configured
UTU model endpoint; credentials are read from the process environment only.
"""
from __future__ import annotations

import asyncio
import importlib
import os
from urllib.parse import urlsplit

_MAX_TASK_CHARS = 8_000
_ALLOWED_MODEL_TYPES = {"chat.completions", "responses"}


def _load_youtu_api() -> dict:
    """Import Youtu-Agent lazily so the optional dependency never breaks startup."""
    agents = importlib.import_module("utu.agents")
    agent_config = importlib.import_module("utu.config.agent_config")
    model_config = importlib.import_module("utu.config.model_config")

    return {
        "SimpleAgent": agents.SimpleAgent,
        "AgentConfig": agent_config.AgentConfig,
        "ContextManagerConfig": agent_config.ContextManagerConfig,
        "EnvConfig": agent_config.EnvConfig,
        "ProfileConfig": agent_config.ProfileConfig,
        "ModelConfigs": model_config.ModelConfigs,
        "ModelProviderConfig": model_config.ModelProviderConfig,
    }


def _settings_from_env() -> tuple[dict | None, str | None]:
    api_key = os.environ.get("UTU_LLM_API_KEY", "").strip()
    base_url = os.environ.get("UTU_LLM_BASE_URL", "").strip()
    model = os.environ.get("UTU_LLM_MODEL", "").strip()
    model_type = os.environ.get("UTU_LLM_TYPE", "chat.completions").strip().lower()

    missing = [
        name
        for name, value in (
            ("UTU_LLM_API_KEY", api_key),
            ("UTU_LLM_BASE_URL", base_url),
            ("UTU_LLM_MODEL", model),
        )
        if not value
    ]
    if missing:
        return None, "Configure these environment variables to use Youtu-Agent: " + ", ".join(missing)
    if model_type not in _ALLOWED_MODEL_TYPES:
        return None, "UTU_LLM_TYPE must be 'chat.completions' or 'responses'."

    parsed = urlsplit(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return None, "UTU_LLM_BASE_URL must be an absolute HTTP(S) endpoint."
    if parsed.username or parsed.password:
        return None, "Do not put credentials in UTU_LLM_BASE_URL; use UTU_LLM_API_KEY."
    if parsed.scheme != "https" and parsed.hostname.lower() not in {"localhost", "127.0.0.1", "::1"}:
        return None, "Use HTTPS for remote Youtu-Agent model endpoints; HTTP is allowed only on loopback."

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "model_type": model_type,
    }, None


def _build_agent_config(api: dict, settings: dict):
    model_provider = api["ModelProviderConfig"](
        type=settings["model_type"],
        model=settings["model"],
        base_url=settings["base_url"],
        api_key=settings["api_key"],
    )
    return api["AgentConfig"](
        agent=api["ProfileConfig"](
            name="JARVIS Youtu-Agent",
            instructions=(
                "Answer the user's task clearly and accurately. You have no tools: "
                "do not claim to browse, inspect local files, or perform actions."
            ),
        ),
        model=api["ModelConfigs"](model_provider=model_provider),
        env=api["EnvConfig"](name="base"),
        context_manager=api["ContextManagerConfig"](name="dummy"),
        toolkits={},
        enabled_skills=[],
        max_turns=8,
    )


async def _run_agent(api: dict, settings: dict, task: str) -> str:
    agent = api["SimpleAgent"](config=_build_agent_config(api, settings))
    async with agent:
        result = await agent.run(task, save=False, log_to_db=False)
    return str(getattr(result, "final_output", "") or "").strip()


def run_youtu_agent(parameters: dict, **_kwargs) -> str:
    """Run a text-only Youtu-Agent task using explicit environment configuration."""
    task = (parameters.get("task") or "").strip()
    if not task:
        return "Please provide a task for Youtu-Agent."
    if len(task) > _MAX_TASK_CHARS:
        return f"Task is too long for this action (maximum {_MAX_TASK_CHARS} characters)."

    settings, error = _settings_from_env()
    if error:
        return error
    if settings is None:
        return "Youtu-Agent configuration could not be resolved."

    try:
        api = _load_youtu_api()
    except ImportError:
        return (
            "Youtu-Agent is not installed in this Python environment. "
            "Install the optional dependency with `python -m pip install -r requirements-youtu.txt`."
        )

    try:
        def _safe_run_coro(coro):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, coro).result()
            return asyncio.run(coro)
        answer = _safe_run_coro(_run_agent(api, settings, task))
    except Exception as exc:
        # Provider errors can include request details; never echo credentials or prompts.
        return f"Youtu-Agent failed ({type(exc).__name__}). Check the configured model endpoint."
    return answer or "Youtu-Agent returned an empty response."


TOOL = {
    "name": "youtu_agent_text",
    "description": (
        "Run a text-only Youtu-Agent task when the user explicitly asks to use Youtu-Agent. "
        "The task is sent to the configured UTU model endpoint. It has no local, shell, "
        "browser, MCP, or file tools."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "A text-only task for Youtu-Agent (maximum 8000 characters).",
            }
        },
        "required": ["task"],
    },
    "handler": run_youtu_agent,
}
