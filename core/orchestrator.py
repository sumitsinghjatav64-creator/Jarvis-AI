import asyncio
import json
import os
import platform
import uuid
from typing import Any, Dict, List, Optional, Set

from core.models import SubTask, TaskPlan, ExecutionResult, TaskStatus, WorkerType, TaskContext
from core.memory import MemoryWorker
from specialists.base import BaseSpecialist
from specialists.os_worker import OSWorker
from specialists.iot_worker import IoTWorker
from specialists.vision_worker import VisionWorker

# Optional Microsoft Agent Framework (MAF) import with graceful fallback
try:
    from agent_framework import Agent
    from agent_framework.openai import OpenAIChatClient
    _HAS_MAF = True
except ImportError:
    _HAS_MAF = False

_PLANNER_INSTRUCTIONS = """You are the JARVIS Orchestrator Planner.
Break down the user's request into a JSON array of subtasks.
Allowed worker_type values:
- "os"     : allowlisted read-only diagnostics only. Supported requests: tasklist, whoami, hostname, ps aux, uname -a. No shell, interpreter, file writes, or chained commands.
- "iot"    : smart home devices/lights (input_data: {"device_id": "light_living_room", "action": "set_state", "params": {"state": "ON"|"OFF"}})
- "vision" : screen/camera analysis (input_data: {"angle": "screen"|"camera", "prompt": "<question>"})
             OR UI clicking (input_data: {"action": "click", "target_element": "<element description>"})

Return ONLY a valid JSON array matching this exact structure:
[
  {
    "description": "Short task summary",
    "worker_type": "os",
    "input_data": {"command": "tasklist"},
    "dependencies": []
  }
]"""


class Orchestrator:
    """Host Planner and Orchestrator implementing Perceive -> Plan -> Act -> Reflect."""

    def __init__(self):
        self.memory = MemoryWorker()
        self.workers: Dict[WorkerType, BaseSpecialist] = {
            WorkerType.OS: OSWorker(),
            WorkerType.IOT: IoTWorker(),
            WorkerType.VISION: VisionWorker(),
        }

    async def perceive(self, prompt: str) -> Dict[str, Any]:
        print(f"\n[Orchestrator] PERCEIVE: Analyzing prompt -> '{prompt}'")
        past_actions = self.memory.get_past_subtasks(limit=3)
        return {
            "prompt": prompt,
            "relevant_history": past_actions,
            "system_state": "nominal",
        }

    async def _plan_with_llm(self, prompt: str) -> Optional[List[Dict[str, Any]]]:
        """Attempts dynamic planning via Microsoft Agent Framework or JARVIS Gemini ladder."""
        # 1. Try Microsoft Agent Framework if installed and OpenAI/Local endpoint is configured
        if _HAS_MAF and (os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")):
            try:
                print("[Orchestrator] Using Microsoft Agent Framework (MAF) Planner...")
                planner = Agent(
                    client=OpenAIChatClient(),
                    instructions=_PLANNER_INSTRUCTIONS,
                )
                res = await planner.run(prompt)
                raw_text = getattr(res, "text", None) or (
                    res.messages[0].text if getattr(res, "messages", None) else str(res)
                )
                if "[" in raw_text and "]" in raw_text:
                    raw_text = raw_text[raw_text.find("[") : raw_text.rfind("]") + 1]
                return json.loads(raw_text)
            except Exception as e:
                print(f"[Orchestrator] MAF Planner fallback triggered: {e}")

        # 2. Fallback to JARVIS built-in Gemini / Local LLM client (core/gemini.py)
        try:
            from core import gemini
            print("[Orchestrator] Using JARVIS Gemini Planner...")
            full_prompt = (
                f"{_PLANNER_INSTRUCTIONS}\n\n"
                f"User request: {prompt}\n\n"
                "CRITICAL: Output ONLY the raw JSON array starting with '[' and ending with ']'. "
                "Do not include markdown codeblocks (```json), explanations, or trailing commentary."
            )
            raw = await asyncio.to_thread(gemini.text, full_prompt, gemini.FAST)
            if raw and "[" in raw and "]" in raw:
                clean_json = raw[raw.find("[") : raw.rfind("]") + 1]
                parsed = json.loads(clean_json)
                if isinstance(parsed, list) and parsed:
                    return parsed
        except Exception as e:
            print(f"[Orchestrator] Gemini Planner fallback triggered: {e}")

        return None

    async def plan(self, perception: Dict[str, Any]) -> TaskPlan:
        prompt = perception["prompt"]
        print("[Orchestrator] PLAN: Breaking down task into subgoals...")
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        subtasks: List[SubTask] = []

        # Try dynamic AI planning first
        llm_tasks = await self._plan_with_llm(prompt)
        if llm_tasks:
            for item in llm_tasks:
                if not isinstance(item, dict):
                    continue
                w_str = str(item.get("worker_type", "os")).lower().strip()
                w_map = {
                    "os": WorkerType.OS,
                    "iot": WorkerType.IOT,
                    "vision": WorkerType.VISION,
                }
                subtasks.append(
                    SubTask(
                        task_id=str(item.get("task_id") or f"t_{uuid.uuid4().hex[:6]}"),
                        description=str(item.get("description") or "Execute subtask"),
                        worker_type=w_map.get(w_str, WorkerType.OS),
                        input_data=item.get("input_data") if isinstance(item.get("input_data"), dict) else {},
                        dependencies=item.get("dependencies") if isinstance(item.get("dependencies"), list) else [],
                    )
                )

        # Fallback to deterministic rule-based planning if LLM returned nothing
        if not subtasks:
            prompt_lower = prompt.lower()

            if any(k in prompt_lower for k in ("light", "lamp", "iot", "switch")):
                subtasks.append(
                    SubTask(
                        task_id=f"t_{uuid.uuid4().hex[:6]}",
                        description="Verify and set IoT device state",
                        worker_type=WorkerType.IOT,
                        input_data={
                            "device_id": "light_living_room",
                            "action": "set_state",
                            "params": {"state": "ON" if "on" in prompt_lower else "OFF"},
                        },
                    )
                )

            if any(k in prompt_lower for k in ("command", "run", "status", "process", "check", "echo", "powershell", "cli")):
                cmd = "echo Jarvis OS Worker Active"
                if "process" in prompt_lower:
                    cmd = "tasklist" if os_is_windows() else "ps aux"
                elif "echo" in prompt_lower:
                    parts = prompt.split("echo")
                    if len(parts) > 1:
                        cmd = f"echo {parts[1].strip()}"
                subtasks.append(
                    SubTask(
                        task_id=f"t_{uuid.uuid4().hex[:6]}",
                        description=f"Execute system command: {cmd}",
                        worker_type=WorkerType.OS,
                        input_data={"command": cmd},
                    )
                )

            if not subtasks:
                subtasks.append(
                    SubTask(
                        task_id=f"t_{uuid.uuid4().hex[:6]}",
                        description="Default system status check",
                        worker_type=WorkerType.OS,
                        input_data={"command": "echo Jarvis system operational"},
                    )
                )

        return TaskPlan(
            plan_id=plan_id,
            description=prompt,
            subtasks=subtasks,
            status=TaskStatus.PENDING,
        )

    async def act(self, plan: TaskPlan) -> List[ExecutionResult]:
        print(f"[Orchestrator] ACT: Executing plan {plan.plan_id}...")
        plan.status = TaskStatus.IN_PROGRESS
        results: List[ExecutionResult] = []
        completed_tasks: Set[str] = set()
        pending_subtasks = list(plan.subtasks)

        while pending_subtasks:
            executable = [
                t for t in pending_subtasks
                if all(dep in completed_tasks for dep in t.dependencies)
            ]
            if not executable:
                print("[Orchestrator] Error: Dependency deadlock detected.")
                break
            for task in executable:
                print(f"[Orchestrator] Dispatching SubTask [{task.task_id}] -> Worker: {task.worker_type.value}")
                task.status = TaskStatus.IN_PROGRESS
                worker = self.workers.get(task.worker_type)
                if not worker:
                    result = ExecutionResult(success=False, output="", error="No worker found")
                else:
                    if await worker.validate_preconditions(task):
                        result = await worker.execute(task)
                    else:
                        result = ExecutionResult(success=False, output="", error="Preconditions failed")
                task.result = result
                task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                self.memory.record_subtask(plan.plan_id, task)
                results.append(result)
                completed_tasks.add(task.task_id)
                pending_subtasks.remove(task)

        plan.status = TaskStatus.COMPLETED if all(r.success for r in results) else TaskStatus.FAILED
        return results

    async def reflect(self, plan: TaskPlan, results: List[ExecutionResult]) -> Dict[str, Any]:
        print(f"[Orchestrator] REFLECT: Evaluating plan {plan.plan_id}...")
        all_success = all(r.success for r in results)
        if not all_success:
            for task in plan.subtasks:
                if task.status == TaskStatus.FAILED:
                    worker = self.workers.get(task.worker_type)
                    if worker:
                        await worker.rollback(task)
        return {"plan_id": plan.plan_id, "success": all_success}

    async def run_workflow(self, prompt: str) -> Dict[str, Any]:
        perception = await self.perceive(prompt)
        plan = await self.plan(perception)
        results = await self.act(plan)
        reflection = await self.reflect(plan, results)
        return {
            "plan": plan.model_dump(),
            "results": [r.model_dump() for r in results],
            "reflection": reflection,
        }


def os_is_windows() -> bool:
    return platform.system() == "Windows"