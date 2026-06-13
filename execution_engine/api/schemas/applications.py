"""API schemas for application deployment flows."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TemplateInputResponse(BaseModel):
    field_name: str
    field_type: str
    label: str
    description: str
    required: bool
    default_value: Optional[Any] = None
    options: Optional[List[str]] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    placeholder: Optional[str] = None


class TemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str
    version: str
    category: str
    icon_url: Optional[str] = None
    database_required: bool
    database_type: Optional[str] = None
    required_inputs: List[TemplateInputResponse]
    step_count: int


class ApplicationCreateRequest(BaseModel):
    tenant_id: UUID
    template_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    user_inputs: Dict[str, Any] = Field(default_factory=dict)
    deploy: bool = False


class ApplicationResponse(BaseModel):
    application_id: UUID
    tenant_id: UUID
    template_id: str
    template_version: str
    name: str
    description: Optional[str] = None
    status: str
    health_status: str
    current_deployment_id: Optional[UUID] = None
    public_url: Optional[str] = None
    user_inputs: Dict[str, Any]


class DeploymentCreateResponse(BaseModel):
    application: ApplicationResponse
    deployment_id: UUID
    status: str


class DeploymentResponse(BaseModel):
    deployment_id: UUID
    application_id: UUID
    tenant_id: UUID
    template_id: str
    template_version: str
    status: str
    current_step_index: int
    total_steps: int
    public_url: Optional[str] = None
    error_message: Optional[str] = None


class ResourceResponse(BaseModel):
    resource_id: UUID
    deployment_id: UUID
    resource_type: str
    external_id: str
    node_id: UUID
    name: str
    status: str
    health_status: str
    consecutive_health_failures: int
    spec: Dict[str, Any]


class DeploymentStepResponse(BaseModel):
    step_execution_id: UUID
    deployment_id: UUID
    step_id: str
    step_name: str
    execution_id: Optional[UUID] = None
    status: str
    result: Dict[str, Any]
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
