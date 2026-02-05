from fastapi import APIRouter, Depends, HTTPException
from uuid import uuid4
from uuid import UUID

from execution_engine.api.schemas.execution import (
    ExecutionCreateRequest,
    ExecutionResponse,
)
from execution_engine.core.models import Execution
from execution_engine.api.container import get_execution_service

router = APIRouter(prefix="/executions", tags=["executions"])


@router.post("/", response_model=ExecutionResponse)
def create_execution(
    request: ExecutionCreateRequest,
    service=Depends(get_execution_service),
):
    execution = Execution(
        execution_id=uuid4(),
        tenant_id=request.tenant_id,
        application_id=request.application_id,
        runtime_type=request.runtime_type,
        spec=request.spec,
    )

    service.register_execution(execution)

    return ExecutionResponse(
        execution_id=execution.execution_id,
        tenant_id=execution.tenant_id,
        application_id=execution.application_id,
        runtime_type=execution.runtime_type,
        spec=execution.spec,
        state=execution.state.value,
    )


@router.get("/{execution_id}", response_model=ExecutionResponse)
def get_execution(
    execution_id: UUID,
    service=Depends(get_execution_service),
):
    execution = service._repo.get(execution_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return ExecutionResponse(
        execution_id=execution.execution_id,
        tenant_id=execution.tenant_id,
        application_id=execution.application_id,
        runtime_type=execution.runtime_type,
        spec=execution.spec,
        state=execution.state.value,
    )

@router.post("/{execution_id}/queue")
def queue_execution(
    execution_id: UUID,
    service=Depends(get_execution_service),
):
    try:
        service.queue_execution(execution_id)
        return {"status": "queued"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
