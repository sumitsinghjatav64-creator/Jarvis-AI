import asyncio
import subprocess
from typing import Any, Dict
from core.models import SubTask, ExecutionResult, WorkerType
from specialists.base import BaseSpecialist

class OSWorker(BaseSpecialist):
    def __init__(self, name: str = "OSWorker"):
        super().__init__(name)

    async def execute(self, task: SubTask) -> ExecutionResult:
        """
        Executes a shell command or native system action.
        """
        command = task.input_data.get("command")
        cwd = task.input_data.get("cwd", None)
        
        if not command:
            return ExecutionResult(
                success=False,
                output="",
                error="No command provided to OSWorker"
            )
        
        try:
            # Running command non-interactively using asyncio subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            stdout, stderr = await process.communicate()
            
            success = process.returncode == 0
            output = stdout.decode().strip()
            error = stderr.decode().strip() if not success else None
            
            return ExecutionResult(
                success=success,
                output=output,
                error=error,
                metadata={"returncode": process.returncode}
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=f"OSWorker execution failed: {str(e)}"
            )

    async def rollback(self, task: SubTask) -> bool:
        # Implement specific rollback command if provided
        rollback_cmd = task.input_data.get("rollback_command")
        if rollback_cmd:
            process = await asyncio.create_subprocess_shell(rollback_cmd)
            await process.communicate()
            return process.returncode == 0
        return False
