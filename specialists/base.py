from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict
from core.models import SubTask, ExecutionResult

class BaseSpecialist(ABC):
    """
    Abstract Base Class for all specialized workers.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, task: SubTask) -> ExecutionResult:
        """
        Execute the given subtask.
        
        Args:
            task: The SubTask to execute.
            
        Returns:
            ExecutionResult: The result of the task execution.
        """
        pass

    async def validate_preconditions(self, task: SubTask) -> bool:
        """
        Optional: Check if preconditions for the task are met.
        
        Args:
            task: The SubTask to validate.
            
        Returns:
            bool: True if preconditions are met, False otherwise.
        """
        return True

    async def rollback(self, task: SubTask) -> bool:
        """
        Optional: Rollback the effects of the task if it failed or if requested.
        
        Args:
            task: The SubTask to rollback.
            
        Returns:
            bool: True if rollback was successful, False otherwise.
        """
        return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
