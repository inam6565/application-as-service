#execution_engine\domain\service.py

"""Domain service - manages applications and deployments."""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
import re

from execution_engine.domain.models import (
    Application, ApplicationTemplate, Deployment, DeploymentStepExecution,
    ApplicationStatus, DeploymentStatus, StepStatus, ResourceLimits, DeployedResource
)
from execution_engine.infrastructure.postgres.domain_repository import (
    ApplicationRepository, ApplicationTemplateRepository, DeploymentRepository,
    DeployedResourceRepository, DeploymentStepExecutionRepository
)
from execution_engine.infrastructure.postgres.config import settings as database_settings
from execution_engine.core.errors import ExecutionValidationError

logger = logging.getLogger(__name__)


class DomainService:
    """Domain service for application lifecycle."""
    
    def __init__(
        self,
        template_repo: ApplicationTemplateRepository,
        app_repo: ApplicationRepository,
        deployment_repo: DeploymentRepository,
        resource_repo: DeployedResourceRepository = None,
        step_repo: DeploymentStepExecutionRepository = None,
    ):
        self._template_repo = template_repo
        self._app_repo = app_repo
        self._deployment_repo = deployment_repo
        self._resource_repo = resource_repo or DeployedResourceRepository()
        self._step_repo = step_repo or DeploymentStepExecutionRepository()
    
    # ============================================
    # TEMPLATES
    # ============================================
    
    def register_template(self, template: ApplicationTemplate) -> None:
        """Register a new application template."""
        existing = self._template_repo.get(template.template_id)
        if existing:
            self._template_repo.update(template)
            return
        self._template_repo.create(template)
    
    def get_template(self, template_id: str) -> Optional[ApplicationTemplate]:
        """Get template by ID."""
        return self._template_repo.get(template_id)
    
    def list_templates(self, category: Optional[str] = None) -> List[ApplicationTemplate]:
        """List available templates."""
        return self._template_repo.list_active(category=category)
    
    # ============================================
    # APPLICATIONS
    # ============================================
    
    def create_application(
        self,
        tenant_id: UUID,
        template_id: str,
        name: str,
        user_inputs: Dict[str, Any],
        description: Optional[str] = None,
    ) -> Application:
        """
        Create a new application from template.
        
        Validates user inputs against template requirements.
        """
        # Get template
        template = self._template_repo.get(template_id)
        if not template:
            raise ExecutionValidationError(f"Template {template_id} not found")
        
        # Validate inputs
        resolved_inputs = self._apply_default_inputs(template, user_inputs)
        self._validate_inputs(template, resolved_inputs)
        
        # Create application
        application = Application(
            application_id=uuid4(),
            tenant_id=tenant_id,
            template_id=template.template_id,
            template_version=template.version,
            name=name,
            description=description,
            user_inputs=resolved_inputs,
            status=ApplicationStatus.CREATING,
            resource_limits=template.default_resources,
        )
        
        self._app_repo.create(application)
        
        logger.info(
            "[domain_service] created application %s from template %s",
            application.application_id,
            template_id,
        )
        
        return application
    
    def get_application(self, application_id: UUID) -> Optional[Application]:
        """Get application by ID."""
        return self._app_repo.get(application_id)
    
    def list_applications(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Application]:
        """List tenant's applications."""
        return self._app_repo.list_by_tenant(tenant_id, limit=limit, offset=offset)
    
    def update_application_status(
        self,
        application_id: UUID,
        status: ApplicationStatus,
        public_url: Optional[str] = None,
    ) -> None:
        """Update application status."""
        application = self._app_repo.get(application_id)
        if not application:
            raise ExecutionValidationError(f"Application {application_id} not found")
        
        application.status = status
        if public_url:
            application.public_url = public_url
        
        self._app_repo.update(application)

    def set_application_status(
        self,
        application_id: UUID,
        status: ApplicationStatus,
        public_url: Optional[str] = None,
    ) -> None:
        """Set application status through the public service boundary."""
        self.update_application_status(application_id, status, public_url=public_url)
    
    def delete_application(self, application_id: UUID) -> None:
        """Soft delete application."""
        application = self._app_repo.get(application_id)
        if not application:
            raise ExecutionValidationError(f"Application {application_id} not found")
        
        application.status = ApplicationStatus.DELETED
        application.deleted_at = datetime.now(timezone.utc)
        
        self._app_repo.update(application)
    
    # ============================================
    # DEPLOYMENTS
    # ============================================
    
    def create_deployment(self, application_id: UUID) -> Deployment:
        """
        Create a new deployment for an application.
        
        Resolves template variables with user inputs.
        """
        # Get application
        application = self._app_repo.get(application_id)
        if not application:
            raise ExecutionValidationError(f"Application {application_id} not found")
        
        # Get template
        template = self._template_repo.get(application.template_id)
        if not template:
            raise ExecutionValidationError(f"Template {application.template_id} not found")
        
        deployment_id = uuid4()

        # Resolve configuration
        resolved_config = self._resolve_config(
            template,
            application.user_inputs,
            application.application_id,
            deployment_id,
        )
        
        # Create deployment
        deployment = Deployment(
            deployment_id=deployment_id,
            application_id=application.application_id,
            tenant_id=application.tenant_id,
            template_id=template.template_id,
            template_version=template.version,
            resolved_config=resolved_config,
            status=DeploymentStatus.PENDING,
            total_steps=len(template.deployment_steps),
        )
        
        self._deployment_repo.create(deployment)
        
        # Update application
        application.current_deployment_id = deployment.deployment_id
        application.status = ApplicationStatus.CREATING
        self._app_repo.update(application)
        
        logger.info(
            "[domain_service] created deployment %s for app %s",
            deployment.deployment_id,
            application_id,
        )
        
        return deployment
    
    def get_deployment(self, deployment_id: UUID) -> Optional[Deployment]:
        """Get deployment by ID."""
        return self._deployment_repo.get(deployment_id)

    def list_application_deployments(
        self,
        application_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Deployment]:
        """List deployments for an application."""
        return self._deployment_repo.list_by_application(
            application_id=application_id,
            limit=limit,
            offset=offset,
        )

    def list_deployments_by_status(
        self,
        status: DeploymentStatus,
        limit: int = 100,
    ) -> List[Deployment]:
        """List deployments by status."""
        return self._deployment_repo.list_by_status(status=status, limit=limit)

    def list_deployment_resources(self, deployment_id: UUID) -> List[DeployedResource]:
        """List deployed resources for a deployment."""
        return self._resource_repo.list_by_deployment(deployment_id)

    def get_deployment_resource(self, resource_id: UUID) -> Optional[DeployedResource]:
        """Get a deployed resource by ID."""
        return self._resource_repo.get(resource_id)

    def update_deployment_resource(self, resource: DeployedResource) -> None:
        """Update a deployed resource."""
        self._resource_repo.update(resource)

    def list_deployment_steps(self, deployment_id: UUID) -> List[DeploymentStepExecution]:
        """List deployment step executions."""
        return self._step_repo.list_by_deployment(deployment_id)
    
    def update_deployment_status(
        self,
        deployment_id: UUID,
        status: DeploymentStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Update deployment status."""
        deployment = self._deployment_repo.get(deployment_id)
        if not deployment:
            raise ExecutionValidationError(f"Deployment {deployment_id} not found")
        
        deployment.status = status
        if error_message:
            deployment.error_message = error_message
        
        if status == DeploymentStatus.RUNNING:
            deployment.completed_at = datetime.now(timezone.utc)
        
        self._deployment_repo.update(deployment)

    def update_deployment_metadata(
        self,
        deployment_id: UUID,
        metadata_updates: Dict[str, Any],
    ) -> None:
        """Merge metadata into a deployment record."""
        deployment = self._deployment_repo.get(deployment_id)
        if not deployment:
            raise ExecutionValidationError(f"Deployment {deployment_id} not found")

        deployment.metadata = {
            **(deployment.metadata or {}),
            **metadata_updates,
        }
        self._deployment_repo.update(deployment)
    
    # ============================================
    # HELPERS
    # ============================================

    def _apply_default_inputs(
        self,
        template: ApplicationTemplate,
        user_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge template defaults with caller-provided inputs."""
        resolved = dict(user_inputs)
        for field in template.required_inputs:
            value = resolved.get(field.field_name)
            if (value is None or value == "") and field.default_value is not None:
                resolved[field.field_name] = field.default_value
        return resolved
    
    def _validate_inputs(self, template: ApplicationTemplate, user_inputs: Dict[str, Any]) -> None:
        """Validate user inputs against template requirements."""
        for field in template.required_inputs:
            if field.required and field.field_name not in user_inputs:
                raise ExecutionValidationError(f"Required field '{field.field_name}' missing")
            
            value = user_inputs.get(field.field_name)
            
            # Type validation
            if value is not None and field.field_type == "integer":
                try:
                    int(value)
                except ValueError:
                    raise ExecutionValidationError(f"Field '{field.field_name}' must be integer")
            
            # Regex validation
            if value and field.validation_regex:
                if not re.match(field.validation_regex, str(value)):
                    raise ExecutionValidationError(
                        f"Field '{field.field_name}' does not match required format"
                    )
            
            # Min/max validation
            if value and field.min_value is not None:
                if int(value) < field.min_value:
                    raise ExecutionValidationError(
                        f"Field '{field.field_name}' must be >= {field.min_value}"
                    )
            
            if value and field.max_value is not None:
                if int(value) > field.max_value:
                    raise ExecutionValidationError(
                        f"Field '{field.field_name}' must be <= {field.max_value}"
                    )
    
    def _resolve_config(
        self,
        template: ApplicationTemplate,
        user_inputs: Dict[str, Any],
        application_id: UUID,
        deployment_id: UUID,
    ) -> Dict[str, Any]:
        """
        Resolve template variables with user inputs.
        
        Variables:
        - {{field_name}} - user input
        - {{application_id}} - generated ID
        - {{application_id_short}} - first 8 chars
        - {{deployment_id}} - generated deployment ID
        - {{deployment_id_short}} - first 8 chars
        """
        import json

        db_host = getattr(database_settings, "mysql_host", "localhost")
        db_port = getattr(database_settings, "mysql_port", 3306)
        db_user = getattr(database_settings, "mysql_root_user", "root")
        db_password = getattr(database_settings, "mysql_root_password", "")
        db_name = f"wp_{str(application_id)[:8]}_{str(deployment_id)[:8]}"
        
        # Create variable map
        variables = {
            **user_inputs,
            "application_id": str(application_id),
            "application_id_short": str(application_id)[:8],
            "deployment_id": str(deployment_id),
            "deployment_id_short": str(deployment_id)[:8],
            "db_host": db_host,
            "db_port": db_port,
            "db_name": db_name,
            "db_user": db_user,
            "db_password": db_password,
        }
        
        # Serialize template to JSON
        config_str = json.dumps({
            "steps": [{
                "step_id": step.step_id,
                "step_name": step.step_name,
                "step_type": step.step_type,
                "order": step.order,
                "depends_on": step.depends_on,
                "spec_template": step.spec_template,
            } for step in template.deployment_steps]
        })
        
        # Replace variables
        for key, value in variables.items():
            config_str = config_str.replace(f"{{{{{key}}}}}", str(value))
        
        # Parse back to dict
        resolved = json.loads(config_str)
        
        return resolved
