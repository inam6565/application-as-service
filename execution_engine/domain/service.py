#execution_engine\domain\service.py

"""Domain service - manages applications and deployments."""

from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
import re

from execution_engine.domain.models import (
    Application, ApplicationTemplate, Deployment, DeploymentStepExecution,
    ApplicationStatus, DeploymentStatus, StepStatus, ResourceLimits
)
from execution_engine.infrastructure.postgres.domain_repository import (
    ApplicationRepository, ApplicationTemplateRepository, DeploymentRepository
)
from execution_engine.core.errors import ExecutionValidationError


class DomainService:
    """Domain service for application lifecycle."""
    
    def __init__(
        self,
        template_repo: ApplicationTemplateRepository,
        app_repo: ApplicationRepository,
        deployment_repo: DeploymentRepository,
    ):
        self._template_repo = template_repo
        self._app_repo = app_repo
        self._deployment_repo = deployment_repo
    
    # ============================================
    # TEMPLATES
    # ============================================
    
    def register_template(self, template: ApplicationTemplate) -> None:
        """Register a new application template."""
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
        self._validate_inputs(template, user_inputs)
        
        # Create application
        application = Application(
            application_id=uuid4(),
            tenant_id=tenant_id,
            template_id=template.template_id,
            template_version=template.version,
            name=name,
            description=description,
            user_inputs=user_inputs,
            status=ApplicationStatus.CREATING,
            resource_limits=template.default_resources,
        )
        
        self._app_repo.create(application)
        
        print(f"[domain_service] created application {application.application_id} from template {template_id}")
        
        return application
    
    def get_application(self, application_id: UUID) -> Optional[Application]:
        """Get application by ID."""
        return self._app_repo.get(application_id)
    
    def list_applications(self, tenant_id: UUID) -> List[Application]:
        """List tenant's applications."""
        return self._app_repo.list_by_tenant(tenant_id)
    
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
        
        # Resolve configuration
        resolved_config = self._resolve_config(template, application.user_inputs, application.application_id)
        
        # Create deployment
        deployment = Deployment(
            deployment_id=uuid4(),
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
        
        print(f"[domain_service] created deployment {deployment.deployment_id} for app {application_id}")
        
        return deployment
    
    def get_deployment(self, deployment_id: UUID) -> Optional[Deployment]:
        """Get deployment by ID."""
        return self._deployment_repo.get(deployment_id)
    
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
    
    # ============================================
    # HELPERS
    # ============================================
    
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
    ) -> Dict[str, Any]:
        """
        Resolve template variables with user inputs.
        
        Variables:
        - {{field_name}} - user input
        - {{application_id}} - generated ID
        - {{application_id_short}} - first 8 chars
        """
        import json
        
        # Create variable map
        variables = {
            "application_id": str(application_id),
            "application_id_short": str(application_id)[:8],
            **user_inputs,
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