import asyncio
from core.orchestrator import Orchestrator

_orch = None

def _get_orch() -> Orchestrator:
    global _orch
    if _orch is None:
        _orch = Orchestrator()
    return _orch

def run_orchestrator(parameters: dict, **kwargs) -> str:
    prompt = (parameters.get("task") or "").strip()
    if not prompt:
        return "Please provide a task description for the orchestrator."
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
        res = _safe_run_coro(_get_orch().run_workflow(prompt))
        outputs = [
            f"[{r.get('success')}] {r.get('output') or r.get('error')}"
            for r in res.get("results", [])
        ]
        return "Workflow complete:\n" + "\n".join(outputs)
    except Exception as e:
        return f"Orchestrator failed: {e}"

TOOL = {
    "name": "multi_agent_orchestrator",
    "description": (
        "Executes complex multi-step OS, IoT, or Vision workflows using the "
        "Perceive-Plan-Act-Reflect agent orchestrator."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "The full natural-language goal to plan and execute.",
            }
        },
        "required": ["task"],
    },
    "handler": run_orchestrator,
}