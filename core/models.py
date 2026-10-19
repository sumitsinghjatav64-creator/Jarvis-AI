from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"

class WorkerType(str, Enum):
    OS = "os"
    VISION = "vision"
    IOT = "iot"
    MEMORY = "memory"
    PLANNER = "planner"

class ExecutionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    success: bool
    output: Any
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SubTask(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    task_id: str
    description: str
    worker_type: WorkerType
    input_data: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = Field(default_factory=list)
    result: Optional[ExecutionResult] = None

class TaskPlan(BaseModel):
    plan_id: str
    description: str
    subtasks: List[SubTask]
    created_at: datetime = Field(default_factory=datetime.now)
    status: TaskStatus = TaskStatus.PENDING

class IoTCommand(BaseModel):
    device_id: str
    action: str  # e.g., "set_state"
    params: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None

class AgentMessage(BaseModel):
    sender: str
    receiver: str
    content: Union[str, Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.now)

class TaskContext(BaseModel):
    plan_id: str
    current_subtask_id: Optional[str] = None
    history: List[AgentMessage] = Field(default_factory=list)
    global_state: Dict[str, Any] = Field(default_factory=dict)
