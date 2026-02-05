"""Domain repository implementations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from execution_engine.domain.models import (
    Application, ApplicationTemplate, Deployment, DeploymentStepExecution,
    DeployedResource, Domain, ProvisionedDatabase
)
from execution_engine.infrastructure.postgres.database import SessionLocal
from execution_engine.infrastructure.postgres.models import (
    ApplicationORM, ApplicationTemplateORM, DeploymentORM,
    DeploymentStepExecutionORM, DeployedResourceORM, DomainORM,
    ProvisionedDatabaseORM
)
from execution_engine.core.errors import ExecutionConcurrencyError


# ============================================
# MAPPING FUNCTIONS
# ============================================

def template_to_orm(template: ApplicationTemplate) -> ApplicationTemplateORM:
    """Convert template domain model to ORM."""
    return ApplicationTemplateORM(
        template_id=template.template_id,
        name=template.name,
        description=template.description,
        version=template.version,
        category=template.category,
        icon_url=template.icon_url,
        deployment_steps=[{
            "step_id": step.step_id,
            "step_name": step.step_name,
            "step_type": step.step_type,
            "order": step.order,
            "depends_on": step.depends_on,
            "spec_template": step.spec_template,
            "health_check": {
                "type": step.health_check.type,
                "path": step.health_check.path,
                "port": step.health_check.port,
                "command": step.health_check.command,
                "interval_seconds": step.health_check.interval_seconds,
                "timeout_seconds": step.health_check.timeout_seconds,
                "retries": step.health_check.retries,
                "initial_delay_seconds": step.health_check.initial_delay_seconds,
            } if step.health_check else None,
            "timeout_seconds": step.timeout_seconds,
            "retry_on_failure": step.retry_on_failure,
            "max_retries": step.max_retries,
            "cleanup_on_failure": step.cleanup_on_failure,
        } for step in template.deployment_steps],
        database_required=template.database_required,
        database_type=template.database_type,
        required_inputs=[{
            "field_name": field.field_name,
            "field_type": field.field_type,
            "label": field.label,
            "description": field.description,
            "required": field.required,
            "default_value": field.default_value,
            "validation_regex": field.validation_regex,
            "options": field.options,
            "min_value": field.min_value,
            "max_value": field.max_value,
            "placeholder": field.placeholder,
        } for field in template.required_inputs],
        default_resources={
            "cpu": template.default_resources.cpu,
            "memory": template.default_resources.memory,
            "storage": template.default_resources.storage,
        } if template.default_resources else None,
        created_at=template.created_at,
        updated_at=template.updated_at,
        is_active=template.is_active,
    )


def application_to_orm(app: Application) -> ApplicationORM:
    """Convert application domain model to ORM."""
    return ApplicationORM(
        application_id=app.application_id,
        tenant_id=app.tenant_id,
        template_id=app.template_id,
        template_version=app.template_version,
        name=app.name,
        description=app.description,
        user_inputs=app.user_inputs,
        current_deployment_id=app.current_deployment_id,
        status=app.status,
        health_status=app.health_status,
        domain=app.domain,
        public_url=app.public_url,
        ssl_enabled=app.ssl_enabled,
        resource_limits={
            "cpu": app.resource_limits.cpu,
            "memory": app.resource_limits.memory,
            "storage": app.resource_limits.storage,
        } if app.resource_limits else None,
        created_at=app.created_at,
        updated_at=app.updated_at,
        deleted_at=app.deleted_at,
    )


def deployment_to_orm(deployment: Deployment) -> DeploymentORM:
    """Convert deployment domain model to ORM."""
    return DeploymentORM(
        deployment_id=deployment.deployment_id,
        application_id=deployment.application_id,
        tenant_id=deployment.tenant_id,
        template_id=deployment.template_id,
        template_version=deployment.template_version,
        resolved_config=deployment.resolved_config,
        status=deployment.status,
        current_step_index=deployment.current_step_index,
        total_steps=deployment.total_steps,
        public_url=deployment.public_url,
        internal_endpoints=deployment.internal_endpoints,
        error_message=deployment.error_message,
        rollback_on_failure=deployment.rollback_on_failure,
        created_at=deployment.created_at,
        started_at=deployment.started_at,
        completed_at=deployment.completed_at,
        metadata=deployment.metadata,
    )


# ============================================
# TEMPLATE REPOSITORY
# ============================================

class ApplicationTemplateRepository:
    """Repository for application templates."""
    
    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal
    
    def _get_session(self):
        return self._session_factory()
    
    def create(self, template: ApplicationTemplate) -> None:
        """Create a new template."""
        session = self._get_session()
        try:
            orm = template_to_orm(template)
            session.add(orm)
            session.commit()
            print(f"[template_repo] created template {template.template_id}")
        except IntegrityError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Template {template.template_id} already exists") from e
        finally:
            session.close()
    
    def get(self, template_id: str) -> Optional[ApplicationTemplate]:
        """Get template by ID."""
        session = self._get_session()
        try:
            orm = session.get(ApplicationTemplateORM, template_id)
            if not orm:
                return None
            
            # Convert ORM to domain (simplified - you'd want proper conversion)
            from execution_engine.domain.models import (
                ApplicationTemplate, DeploymentStepDefinition,
                TemplateInputField, ResourceLimits, HealthCheckDefinition
            )
            
            return ApplicationTemplate(
                template_id=orm.template_id,
                name=orm.name,
                description=orm.description,
                version=orm.version,
                category=orm.category,
                icon_url=orm.icon_url,
                deployment_steps=[
                    DeploymentStepDefinition(
                        step_id=step["step_id"],
                        step_name=step["step_name"],
                        step_type=step["step_type"],
                        order=step["order"],
                        depends_on=step.get("depends_on", []),
                        spec_template=step.get("spec_template", {}),
                        health_check=HealthCheckDefinition(**step["health_check"]) if step.get("health_check") else None,
                        timeout_seconds=step.get("timeout_seconds", 300),
                        retry_on_failure=step.get("retry_on_failure", True),
                        max_retries=step.get("max_retries", 3),
                        cleanup_on_failure=step.get("cleanup_on_failure", True),
                    )
                    for step in orm.deployment_steps
                ],
                database_required=orm.database_required,
                database_type=orm.database_type,
                required_inputs=[
                    TemplateInputField(**field)
                    for field in orm.required_inputs
                ],
                default_resources=ResourceLimits(**orm.default_resources) if orm.default_resources else None,
                created_at=orm.created_at,
                updated_at=orm.updated_at,
                is_active=orm.is_active,
            )
        finally:
            session.close()
    
    def list_active(self, category: Optional[str] = None) -> List[ApplicationTemplate]:
        """List active templates."""
        session = self._get_session()
        try:
            query = session.query(ApplicationTemplateORM).filter(
                ApplicationTemplateORM.is_active == True
            )
            
            if category:
                query = query.filter(ApplicationTemplateORM.category == category)
            
            orms = query.all()
            
            # Convert each ORM to domain model
            templates = []
            for orm in orms:
                template = self.get(orm.template_id)  # Reuse get() for conversion
                if template:
                    templates.append(template)
            
            return templates
        finally:
            session.close()


# ============================================
# APPLICATION REPOSITORY
# ============================================

class ApplicationRepository:
    """Repository for applications."""
    
    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal
    
    def _get_session(self):
        return self._session_factory()
    
    def create(self, application: Application) -> None:
        """Create a new application."""
        session = self._get_session()
        try:
            orm = application_to_orm(application)
            session.add(orm)
            session.commit()
            print(f"[app_repo] created application {application.application_id}")
        except SQLAlchemyError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Failed to create application: {e}") from e
        finally:
            session.close()
    
    def get(self, application_id: UUID) -> Optional[Application]:
        """Get application by ID."""
        session = self._get_session()
        try:
            orm = session.get(ApplicationORM, application_id)
            if not orm:
                return None
            
            from execution_engine.domain.models import Application, ResourceLimits
            
            return Application(
                application_id=orm.application_id,
                tenant_id=orm.tenant_id,
                template_id=orm.template_id,
                template_version=orm.template_version,
                name=orm.name,
                description=orm.description,
                user_inputs=orm.user_inputs,
                current_deployment_id=orm.current_deployment_id,
                status=orm.status,
                health_status=orm.health_status,
                domain=orm.domain,
                public_url=orm.public_url,
                ssl_enabled=orm.ssl_enabled,
                resource_limits=ResourceLimits(**orm.resource_limits) if orm.resource_limits else None,
                created_at=orm.created_at,
                updated_at=orm.updated_at,
                deleted_at=orm.deleted_at,
            )
        finally:
            session.close()
    
    def update(self, application: Application) -> None:
        """Update application."""
        session = self._get_session()
        try:
            orm = session.get(ApplicationORM, application.application_id)
            if not orm:
                raise ExecutionConcurrencyError(f"Application {application.application_id} not found")
            
            # Update fields
            orm.status = application.status
            orm.health_status = application.health_status
            orm.current_deployment_id = application.current_deployment_id
            orm.public_url = application.public_url
            orm.domain = application.domain
            orm.ssl_enabled = application.ssl_enabled
            orm.deleted_at = application.deleted_at
            
            session.commit()
            print(f"[app_repo] updated application {application.application_id}")
        except SQLAlchemyError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Failed to update application: {e}") from e
        finally:
            session.close()
    
    def list_by_tenant(self, tenant_id: UUID, include_deleted: bool = False) -> List[Application]:
        """List applications by tenant."""
        session = self._get_session()
        try:
            query = session.query(ApplicationORM).filter(
                ApplicationORM.tenant_id == tenant_id
            )
            
            if not include_deleted:
                query = query.filter(ApplicationORM.deleted_at.is_(None))
            
            query = query.order_by(ApplicationORM.created_at.desc())
            
            orms = query.all()
            return [self.get(orm.application_id) for orm in orms if self.get(orm.application_id)]
        finally:
            session.close()


# ============================================
# DEPLOYMENT REPOSITORY
# ============================================

class DeploymentRepository:
    """Repository for deployments."""
    
    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal
    
    def _get_session(self):
        return self._session_factory()
    
    def create(self, deployment: Deployment) -> None:
        """Create a new deployment."""
        session = self._get_session()
        try:
            orm = deployment_to_orm(deployment)
            session.add(orm)
            session.commit()
            print(f"[deployment_repo] created deployment {deployment.deployment_id}")
        except SQLAlchemyError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Failed to create deployment: {e}") from e
        finally:
            session.close()
    
    def get(self, deployment_id: UUID) -> Optional[Deployment]:
        """Get deployment by ID."""
        session = self._get_session()
        try:
            orm = session.get(DeploymentORM, deployment_id)
            if not orm:
                return None
            
            from execution_engine.domain.models import Deployment
            
            return Deployment(
                deployment_id=orm.deployment_id,
                application_id=orm.application_id,
                tenant_id=orm.tenant_id,
                template_id=orm.template_id,
                template_version=orm.template_version,
                resolved_config=orm.resolved_config,
                status=orm.status,
                current_step_index=orm.current_step_index,
                total_steps=orm.total_steps,
                public_url=orm.public_url,
                internal_endpoints=orm.internal_endpoints,
                error_message=orm.error_message,
                rollback_on_failure=orm.rollback_on_failure,
                created_at=orm.created_at,
                started_at=orm.started_at,
                completed_at=orm.completed_at,
                metadata=orm.metadata,
            )
        finally:
            session.close()
    
    def update(self, deployment: Deployment) -> None:
        """Update deployment."""
        session = self._get_session()
        try:
            orm = session.get(DeploymentORM, deployment.deployment_id)
            if not orm:
                raise ExecutionConcurrencyError(f"Deployment {deployment.deployment_id} not found")
            
            orm.status = deployment.status
            orm.current_step_index = deployment.current_step_index
            orm.public_url = deployment.public_url
            orm.internal_endpoints = deployment.internal_endpoints
            orm.error_message = deployment.error_message
            orm.started_at = deployment.started_at
            orm.completed_at = deployment.completed_at
            
            session.commit()
            print(f"[deployment_repo] updated deployment {deployment.deployment_id}")
        except SQLAlchemyError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Failed to update deployment: {e}") from e
        finally:
            session.close()