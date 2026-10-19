import asyncio
import json
from typing import Any, Dict, List, Optional
from core.models import SubTask, ExecutionResult, IoTCommand, WorkerType
from specialists.base import BaseSpecialist
from config.settings import settings

class IoTWorker(BaseSpecialist):
    def __init__(self, name: str = "IoTWorker"):
        super().__init__(name)
        self.broker = settings.MQTT_BROKER
        self.port = settings.MQTT_PORT
        self.allowlist = {"light", "switch", "plug", "thermostat", "relay", "lamp"}
        self.device_states: Dict[str, Dict[str, Any]] = {}  # Mock state cache for pre-flight validation

    async def validate_preconditions(self, task: SubTask) -> bool:
        device_id = task.input_data.get("device_id")
        action = task.input_data.get("action")
        
        if not device_id or not action:
            return False
            
        # Check allowlist based on device type prefix
        device_type = device_id.split("_")[0].lower()
        if device_type not in self.allowlist:
            print(f"[IoT Safety Guard] Device type '{device_type}' not in allowlist: {self.allowlist}")
            return False
            
        return True

    async def get_device_state(self, device_id: str) -> Dict[str, Any]:
        """Pre-flight state validation hook"""
        await asyncio.sleep(0.1)
        return self.device_states.get(device_id, {"state": "OFF", "reachable": True})

    async def set_state(self, command: IoTCommand) -> ExecutionResult:
        """Idempotent state control"""
        current_state = await self.get_device_state(command.device_id)
        
        target_state = command.params.get("state")
        if current_state.get("state") == target_state:
            return ExecutionResult(
                success=True,
                output=f"Device {command.device_id} is already in state {target_state}. Idempotent skip.",
                metadata={"idempotent_skip": True, "device_id": command.device_id}
            )
            
        # Simulate dispatching command to broker / hardware gateway
        print(f"[IoT Gateway -> MQTT {self.broker}:{self.port}] Dispatching command to {command.device_id}: {command.action} -> {target_state}")
        await asyncio.sleep(0.2)
        
        # Update mock cache
        self.device_states[command.device_id] = {"state": target_state, "reachable": True}
        
        return ExecutionResult(
            success=True,
            output=f"Successfully set {command.device_id} state to {target_state}",
            metadata={"device_id": command.device_id, "target_state": target_state}
        )

    async def execute(self, task: SubTask) -> ExecutionResult:
        if not await self.validate_preconditions(task):
            return ExecutionResult(
                success=False,
                output="",
                error="IoT Pre-flight validation failed or device not allowed by safety guard."
            )
            
        device_id = task.input_data.get("device_id")
        action = task.input_data.get("action", "set_state")
        params = task.input_data.get("params", {})
        
        cmd = IoTCommand(
            device_id=device_id,
            action=action,
            params=params,
            idempotency_key=task.input_data.get("idempotency_key")
        )
        
        if action == "set_state":
            return await self.set_state(cmd)
        elif action == "get_state":
            state = await self.get_device_state(device_id)
            return ExecutionResult(success=True, output=state, metadata={"device_id": device_id})
        else:
            return ExecutionResult(success=False, output="", error=f"Unknown IoT action: {action}")
