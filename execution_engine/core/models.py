"""Core domain models (business logic)."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone  
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


class ExecutionState(Enum):
    """Execution state machine."""
    
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class Execution:
    """Execution domain model with state transitions."""
    
    # Identity
    execution_id: UUID
    tenant_id: UUID
    application_id: UUID
    deployment_id: Optional[UUID] = None
    step_execution_id: Optional[UUID] = None
    
    # Execution type
    execution_type: str = "deploy"
    target_resource_id: Optional[UUID] = None
    
    # Runtime
    runtime_type: str = "docker"
    spec: Dict[str, Any] = field(default_factory=dict)
    
    # State
    state: ExecutionState = ExecutionState.CREATED
    
    # Lifecycle timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    queued_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    # Lease management
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    
    # Results
    deployment_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # Retry
    retry_count: int = 0
    max_retries: int = 3
    
    # Priority
    priority: int = 0
    
    # Optimistic concurrency
    version: int = 0
    
    # -------------------------
    # STATE TRANSITIONS
    # -------------------------
    
    def queue(self) -> None:
        """Transition from CREATED to QUEUED."""
        if self.state != ExecutionState.CREATED:
            raise ValueError(f"Cannot queue from {self.state.value} state")
        
        self.state = ExecutionState.QUEUED
        self.queued_at = datetime.now(timezone.utc)
        self.version += 1
    
    def claim(self, worker_id: str, lease_seconds: int) -> None:
        """Claim execution (QUEUED -> CLAIMED)."""
        if self.state != ExecutionState.QUEUED:
            raise ValueError(f"Cannot claim from {self.state.value} state")
        
        self.state = ExecutionState.CLAIMED
        self.lease_owner = worker_id
        self.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        self.claimed_at = datetime.now(timezone.utc)
        self.version += 1
    
    def start(self) -> None:
        """Transition from CLAIMED to STARTED."""
        if self.state != ExecutionState.CLAIMED:
            raise ValueError(f"Cannot start from {self.state.value} state")
        
        self.state = ExecutionState.STARTED
        self.started_at = datetime.now(timezone.utc)
        self.version += 1
    
    def complete(self, deployment_result: Optional[Dict[str, Any]] = None) -> None:
        """Transition from STARTED to COMPLETED."""
        if self.state != ExecutionState.STARTED:
            raise ValueError(f"Cannot complete from {self.state.value} state")
        
        self.state = ExecutionState.COMPLETED
        self.finished_at = datetime.now(timezone.utc)
        self.deployment_result = deployment_result
        self.lease_owner = None
        self.lease_expires_at = None
        self.version += 1
    
    def fail(self, error_message: str) -> None:
        """Transition to FAILED state."""
        if self.state not in (ExecutionState.QUEUED, ExecutionState.CLAIMED, ExecutionState.STARTED):
            raise ValueError(f"Cannot fail from {self.state.value} state")
        
        self.state = ExecutionState.FAILED
        self.finished_at = datetime.now(timezone.utc)
        self.error_message = error_message
        self.lease_owner = None
        self.lease_expires_at = None
        self.version += 1
    
    def cancel(self) -> None:
        """Transition to CANCELLED state."""
        if self.state in (ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED):
            raise ValueError(f"Cannot cancel from {self.state.value} state")
        
        self.state = ExecutionState.CANCELLED
        self.finished_at = datetime.now(timezone.utc)
        self.lease_owner = None
        self.lease_expires_at = None
        self.version += 1
    
    def renew_lease(self, worker_id: str, lease_seconds: int) -> None:
        """Renew lease expiration."""
        if self.lease_owner != worker_id:
            raise ValueError(f"Execution leased by {self.lease_owner}, not {worker_id}")
        
        if not self.lease_expires_at or self.lease_expires_at <= datetime.now(timezone.utc):
            raise ValueError("Lease already expired")
        
        self.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        self.version += 1
    
    def is_lease_valid(self, worker_id: str) -> bool:
        """Check if lease is valid for given worker."""
        if self.lease_owner != worker_id:
            return False
        
        if not self.lease_expires_at:
            return False
        
        return self.lease_expires_at > datetime.now(timezone.utc)
    
    def can_retry(self) -> bool:
        """Check if execution can be retried."""
        return self.state == ExecutionState.FAILED and self.retry_count < self.max_retries