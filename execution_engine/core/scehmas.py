"""Pydantic schemas for validation and serialization."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict

from execution_engine.core.models import ExecutionState


# ============================================
# Base Schemas
# ============================================

class ExecutionBase(BaseModel):
    """Base execution schema."""
    
    tenant_id: UUID
    application_id: UUID
    deployment_id: Optional[UUID] = None
    step_execution_id: Optional[UUID] = None
    
    execution_type: str = "deploy"
    target_resource_id: Optional[UUID] = None
    
    runtime_type: str
    spec: Dict[str, Any]
    
    priority: int = Field(default=0, ge=0, le=100)
    max_retries: int = Field(default=3, ge=0, le=10)
    
    model_config = ConfigDict(from_attributes=True)


class ExecutionCreate(ExecutionBase):
    """Schema for creating a new execution."""
    pass


class ExecutionUpdate(BaseModel):
    """Schema for updating execution."""
    
    state: Optional[ExecutionState] = None
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    deployment_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class ExecutionResponse(ExecutionBase):
    """Schema for execution response."""
    
    execution_id: UUID
    state: ExecutionState
    
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    
    deployment_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int
    
    created_at: datetime
    queued_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    version: int
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# Service Request/Response Schemas
# ============================================

class ClaimExecutionRequest(BaseModel):
    """Request to claim an execution."""
    
    execution_id: UUID
    worker_id: str = Field(..., min_length=1, max_length=255)
    lease_seconds: int = Field(default=30, ge=5, le=300)


class ClaimExecutionResponse(BaseModel):
    """Response for claim attempt."""
    
    claimed: bool
    execution: Optional[ExecutionResponse] = None


class StartExecutionRequest(BaseModel):
    """Request to start an execution."""
    
    execution_id: UUID
    worker_id: str = Field(..., min_length=1, max_length=255)


class CompleteExecutionRequest(BaseModel):
    """Request to complete an execution."""
    
    execution_id: UUID
    worker_id: str = Field(..., min_length=1, max_length=255)
    deployment_result: Optional[Dict[str, Any]] = None


class FailExecutionRequest(BaseModel):
    """Request to fail an execution."""
    
    execution_id: UUID
    worker_id: str = Field(..., min_length=1, max_length=255)
    error_message: str


class RenewLeaseRequest(BaseModel):
    """Request to renew lease."""
    
    execution_id: UUID
    worker_id: str = Field(..., min_length=1, max_length=255)
    lease_seconds: int = Field(default=30, ge=5, le=300)


# ============================================
# Deployment Result Schema
# ============================================

class DeploymentResultSchema(BaseModel):
    """Schema for deployment result."""
    
    resource_id: Optional[UUID] = None
    resource_type: str
    external_id: str  # Container ID, DB name, etc.
    
    node_id: Optional[UUID] = None
    node_name: Optional[str] = None
    
    internal_ip: Optional[str] = None
    internal_port: Optional[int] = None
    public_url: Optional[str] = None
    
    status: str
    health_status: str = "unknown"
    
    deployed_at: datetime
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)