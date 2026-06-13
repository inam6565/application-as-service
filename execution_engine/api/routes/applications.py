"""Application deployment API routes."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from execution_engine.api.container import (
    get_deployment_orchestrator,
    get_domain_service,
    get_execution_service,
)
from execution_engine.domain.models import HealthStatus, ResourceType
from runtime_agent.client import RuntimeAgentClient
from execution_engine.api.schemas.applications import (
    ApplicationCreateRequest,
    ApplicationResponse,
    DeploymentCreateResponse,
    DeploymentResponse,
    DeploymentStepResponse,
    ResourceResponse,
    TemplateInputResponse,
    TemplateResponse,
)

router = APIRouter(tags=["applications"])


def template_to_response(template) -> TemplateResponse:
    return TemplateResponse(
        template_id=template.template_id,
        name=template.name,
        description=template.description,
        version=template.version,
        category=template.category,
        icon_url=template.icon_url,
        database_required=template.database_required,
        database_type=template.database_type,
        required_inputs=[
            TemplateInputResponse(
                field_name=field.field_name,
                field_type=field.field_type,
                label=field.label,
                description=field.description,
                required=field.required,
                default_value=field.default_value,
                options=field.options,
                min_value=field.min_value,
                max_value=field.max_value,
                placeholder=field.placeholder,
            )
            for field in template.required_inputs
        ],
        step_count=len(template.deployment_steps),
    )


def application_to_response(application) -> ApplicationResponse:
    return ApplicationResponse(
        application_id=application.application_id,
        tenant_id=application.tenant_id,
        template_id=application.template_id,
        template_version=application.template_version,
        name=application.name,
        description=application.description,
        status=application.status.value,
        health_status=application.health_status.value,
        current_deployment_id=application.current_deployment_id,
        public_url=application.public_url,
        user_inputs=application.user_inputs,
    )


def deployment_to_response(deployment) -> DeploymentResponse:
    return DeploymentResponse(
        deployment_id=deployment.deployment_id,
        application_id=deployment.application_id,
        tenant_id=deployment.tenant_id,
        template_id=deployment.template_id,
        template_version=deployment.template_version,
        status=deployment.status.value,
        current_step_index=deployment.current_step_index,
        total_steps=deployment.total_steps,
        public_url=deployment.public_url,
        error_message=deployment.error_message,
    )


def resource_to_response(resource) -> ResourceResponse:
    return ResourceResponse(
        resource_id=resource.resource_id,
        deployment_id=resource.deployment_id,
        resource_type=resource.resource_type.value,
        external_id=resource.external_id,
        node_id=resource.node_id,
        name=resource.name,
        status=resource.status,
        health_status=resource.health_status.value,
        consecutive_health_failures=resource.consecutive_health_failures,
        spec=resource.spec,
    )


def step_to_response(step) -> DeploymentStepResponse:
    return DeploymentStepResponse(
        step_execution_id=step.step_execution_id,
        deployment_id=step.deployment_id,
        step_id=step.step_id,
        step_name=step.step_name,
        execution_id=step.execution_id,
        status=step.status.value,
        result=step.result,
        error_message=step.error_message,
        started_at=step.started_at.isoformat() if step.started_at else None,
        completed_at=step.completed_at.isoformat() if step.completed_at else None,
        duration_seconds=step.duration_seconds,
    )


@router.get("/templates", response_model=List[TemplateResponse])
def list_templates(
    category: str | None = None,
    service=Depends(get_domain_service),
):
    templates = service.list_templates(category=category)
    return [template_to_response(template) for template in templates]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
def get_template(template_id: str, service=Depends(get_domain_service)):
    template = service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template_to_response(template)


@router.post("/applications", response_model=DeploymentCreateResponse | ApplicationResponse)
def create_application(
    request: ApplicationCreateRequest,
    service=Depends(get_domain_service),
    orchestrator=Depends(get_deployment_orchestrator),
):
    try:
        application = service.create_application(
            tenant_id=request.tenant_id,
            template_id=request.template_id,
            name=request.name,
            user_inputs=request.user_inputs,
            description=request.description,
        )
        if not request.deploy:
            return application_to_response(application)

        deployment = service.create_deployment(application.application_id)
        orchestrator.start_deployment(deployment.deployment_id)
        application = service.get_application(application.application_id)
        return DeploymentCreateResponse(
            application=application_to_response(application),
            deployment_id=deployment.deployment_id,
            status=deployment.status.value,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/applications", response_model=List[ApplicationResponse])
def list_applications(
    tenant_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service=Depends(get_domain_service),
):
    applications = service.list_applications(tenant_id, limit=limit, offset=offset)
    return [application_to_response(application) for application in applications]


@router.get("/applications/{application_id}", response_model=ApplicationResponse)
def get_application(application_id: UUID, service=Depends(get_domain_service)):
    application = service.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application_to_response(application)


@router.post("/applications/{application_id}/deploy", response_model=DeploymentResponse)
def deploy_application(
    application_id: UUID,
    service=Depends(get_domain_service),
    orchestrator=Depends(get_deployment_orchestrator),
):
    try:
        deployment = service.create_deployment(application_id)
        orchestrator.start_deployment(deployment.deployment_id)
        refreshed = service.get_deployment(deployment.deployment_id) or deployment
        return deployment_to_response(refreshed)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/applications/{application_id}/deployments", response_model=List[DeploymentResponse])
def list_application_deployments(
    application_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service=Depends(get_domain_service),
):
    deployments = service.list_application_deployments(application_id, limit=limit, offset=offset)
    return [deployment_to_response(deployment) for deployment in deployments]


@router.get("/deployments/{deployment_id}", response_model=DeploymentResponse)
def get_deployment(deployment_id: UUID, service=Depends(get_domain_service)):
    deployment = service.get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment_to_response(deployment)


@router.get("/deployments/{deployment_id}/executions")
def list_deployment_executions(
    deployment_id: UUID,
    execution_service=Depends(get_execution_service),
):
    executions = execution_service.list_deployment_executions(deployment_id, limit=100)
    return [
        {
            "execution_id": execution.execution_id,
            "state": execution.state.value,
            "runtime_type": execution.runtime_type,
            "error_message": execution.error_message,
            "deployment_result": execution.deployment_result,
            "retry_count": execution.retry_count,
        }
        for execution in executions
    ]


@router.get("/deployments/{deployment_id}/steps", response_model=List[DeploymentStepResponse])
def list_deployment_steps(
    deployment_id: UUID,
    service=Depends(get_domain_service),
):
    return [step_to_response(step) for step in service.list_deployment_steps(deployment_id)]


@router.get("/deployments/{deployment_id}/resources", response_model=List[ResourceResponse])
def list_deployment_resources(
    deployment_id: UUID,
    service=Depends(get_domain_service),
):
    resources = service.list_deployment_resources(deployment_id)
    return [resource_to_response(resource) for resource in resources]


@router.post("/deployments/{deployment_id}/cleanup")
def cleanup_deployment(
    deployment_id: UUID,
    service=Depends(get_domain_service),
):
    resources = service.list_deployment_resources(deployment_id)
    cleaned = []
    errors = []

    for resource in resources:
        if resource.resource_type != ResourceType.CONTAINER or resource.external_id == "pending":
            continue

        agent_url = (
            resource.spec.get("deployment_result", {}).get("agent_url")
            or resource.spec.get("spec_template", {}).get("agent_url")
        )
        if not agent_url:
            errors.append({"resource_id": str(resource.resource_id), "error": "Missing runtime agent URL"})
            continue

        try:
            client = RuntimeAgentClient(agent_url)
            removed = client.remove_container(resource.external_id, force=True)
            if removed:
                resource.status = "removed"
                resource.health_status = HealthStatus.UNKNOWN
                service.update_deployment_resource(resource)
                cleaned.append(str(resource.resource_id))
            else:
                errors.append({"resource_id": str(resource.resource_id), "error": "Runtime agent remove failed"})
        except Exception as exc:
            errors.append({"resource_id": str(resource.resource_id), "error": str(exc)})

    return {"deployment_id": deployment_id, "cleaned": cleaned, "errors": errors}
