"""Event models for execution engine."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Any, Dict, Optional


@dataclass
class ExecutionEvent:
    """Base execution event."""
    
    event_type: str
    execution_id: UUID
    timestamp: datetime
    metadata: Dict[str, Any]
    
    @staticmethod
    def execution_registered(execution):
        """Execution registered event."""
        return ExecutionEvent(
            event_type="execution.registered",
            execution_id=execution.execution_id,
            timestamp=datetime.utcnow(),
            metadata={
                "tenant_id": str(execution.tenant_id),
                "application_id": str(execution.application_id),
                "runtime_type": execution.runtime_type,
            }
        )
    
    @staticmethod
    def execution_queued(execution):
        """Execution queued event."""
        return ExecutionEvent(
            event_type="execution.queued",
            execution_id=execution.execution_id,
            timestamp=datetime.utcnow(),
            metadata={
                "state": execution.state.value,
            }
        )
    
    @staticmethod
    def execution_claimed(execution):
        """Execution claimed event (NEW)."""
        return ExecutionEvent(
            event_type="execution.claimed",
            execution_id=execution.execution_id,
            timestamp=datetime.utcnow(),
            metadata={
                "lease_owner": execution.lease_owner,
                "lease_expires_at": execution.lease_expires_at.isoformat() if execution.lease_expires_at else None,
            }
        )
    
    @staticmethod
    def execution_started(execution):
        """Execution started event."""
        return ExecutionEvent(
            event_type="execution.started",
            execution_id=execution.execution_id,
            timestamp=datetime.utcnow(),
            metadata={
                "lease_owner": execution.lease_owner,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
            }
        )
    
    @staticmethod
    def execution_completed(execution):
        """Execution completed event."""
        return ExecutionEvent(
            event_type="execution.completed",
            execution_id=execution.execution_id,
            timestamp=datetime.utcnow(),
            metadata={
                "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
                "deployment_result": execution.deployment_result,
            }
        )
    
    @staticmethod
    def execution_failed(execution, reason: str):
        """Execution failed event."""
        return ExecutionEvent(
            event_type="execution.failed",
            execution_id=execution.execution_id,
            timestamp=datetime.utcnow(),
            metadata={
                "error_message": reason,
                "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            }
        )
    
    @staticmethod
    def execution_cancelled(execution):
        """Execution cancelled event."""
        return ExecutionEvent(
            event_type="execution.cancelled",
            execution_id=execution.execution_id,
            timestamp=datetime.utcnow(),
            metadata={
                "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            }
        )