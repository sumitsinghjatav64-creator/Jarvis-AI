import asyncio
import uuid
from typing import Any, Dict, List, Optional, Set
from core.models import SubTask, TaskPlan, ExecutionResult, TaskStatus, WorkerType, TaskContext
from core.memory import MemoryWorker
from specialists.base import BaseSpecialist
from specialists.os_worker import OSWorker
from specialists.iot_worker import IoTWorker
from specialists.vision_worker import VisionWorker

class Orchestrator:
    """Host Planner and Orchestrator implementing Perceive -> Plan -> Act -> Reflect."""
    def __init__(self):
        self.memory = MemoryWorker()
        self.workers: Dict[WorkerType, BaseSpecialist] = {
            WorkerType.OS: OSWorker(),
            WorkerType.IOT: IoTWorker(),
            WorkerType.VISION: VisionWorker()
        }

    async def perceive(self, prompt: str) -> Dict[str, Any]:
        print(f"\n[Orchestrator] PERCEIVE: Analyzing prompt -> '{prompt}'")
        past_actions = self.memory.get_past_subtasks(limit=3)
        return {"prompt": prompt, "relevant_history": past_actions, "system_state": "nominal"}

    async def plan(self, perception: Dict[str, Any]) -> TaskPlan:
        prompt = perception["prompt"]
        print(f"[Orchestrator] PLAN: Breaking down task into subgoals...")
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        subtasks: List[SubTask] = []
        prompt_lower = prompt.lower()
        
        if "light" in prompt_lower or "lamp" in prompt_lower or "iot" in prompt_lower or "switch" in prompt_lower:
            subtasks.append(SubTask(
                task_id=f"t_{uuid.uuid4().hex[:6]}",
                description="Verify and set IoT device state",
                worker_type=WorkerType.IOT,
                input_data={
                    "device_id": "light_living_room",
                    "action": "set_state",
                    "params": {"state": "ON" if "on" in prompt_lower else "OFF"}
                }
            ))

        if "command" in prompt_lower or "run" in prompt_lower or "status" in prompt_lower or "process" in prompt_lower or "check" in prompt_lower or "echo" in prompt_lower or "powershell" in prompt_lower or "cli" in prompt_lower:
            cmd = "echo Jarvis OS Worker Active"
            if "process" in prompt_lower:
                cmd = "tasklist" if os_is_windows() else "ps aux"
            elif "echo" in prompt_lower:
                parts = prompt.split("echo")
                if len(parts) > 1:
                    cmd = f"echo {parts[1].strip()}"
            subtasks.append(SubTask(
                task_id=f"t_{uuid.uuid4().hex[:6]}",
                description=f"Execute system command: {cmd}",
                worker_type=WorkerType.OS,
                input_data={"command": cmd}
            ))

        if not subtasks:
            subtasks.append(SubTask(
                task_id=f"t_{uuid.uuid4().hex[:6]}",
                description="Default system status check",
                worker_type=WorkerType.OS,
                input_data={"command": "echo Jarvis system operational"}
            ))

        return TaskPlan(plan_id=plan_id, description=prompt, subtasks=subtasks, status=TaskStatus.PENDING)

    async def act(self, plan: TaskPlan) -> List[ExecutionResult]:
        print(f"[Orchestrator] ACT: Executing plan {plan.plan_id}...")
        plan.status = TaskStatus.IN_PROGRESS
        results: List[ExecutionResult] = []
        completed_tasks: Set[str] = set()
        pending_subtasks = list(plan.subtasks)
        
        while pending_subtasks:
            executable = [t for t in pending_subtasks if all(dep in completed_tasks for dep in t.dependencies)]
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
        return {"plan": plan.model_dump(), "results": [r.model_dump() for r in results], "reflection": reflection}

def os_is_windows() -> bool:
    import platform
    return platform.system() == "Windows"
