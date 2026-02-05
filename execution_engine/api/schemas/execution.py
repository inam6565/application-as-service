from uuid import UUID
from typing import Dict, Any
from pydantic import BaseModel


class ExecutionCreateRequest(BaseModel):
    tenant_id: UUID
    application_id: UUID
    runtime_type: str
    spec: Dict[str, Any]


class ExecutionResponse(BaseModel):
    execution_id: UUID
    tenant_id: UUID
    application_id: UUID
    runtime_type: str
    spec: Dict[str, Any]
    state: str
