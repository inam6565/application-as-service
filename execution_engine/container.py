# execution_engine/container.py
"""Dependency injection container - wires all services together."""

from execution_engine.infrastructure.postgres.repository import PostgresExecutionRepository
from execution_engine.infrastructure.postgres.domain_repository import (
    ApplicationTemplateRepository,
    ApplicationRepository,
    DeploymentRepository,
    DeployedResourceRepository,
    DeploymentStepExecutionRepository,
)
from execution_engine.infrastructure.postgres.node_repository import NodeRepository

from execution_engine.core.service import ExecutionService
from execution_engine.core.events import MultiEventEmitter, PrintEventEmitter

from execution_engine.domain.service import DomainService
from execution_engine.node_manager.service import NodeManagerService
from execution_engine.orchestrator.deployment_orchestrator import DeploymentOrchestrator


# ============================================
# REPOSITORIES
# ============================================

# Execution Engine
execution_repository = PostgresExecutionRepository()

# Domain
template_repository = ApplicationTemplateRepository()
application_repository = ApplicationRepository()
deployment_repository = DeploymentRepository()
resource_repository = DeployedResourceRepository()
step_execution_repository = DeploymentStepExecutionRepository()

# Node Manager
node_repository = NodeRepository()


# ============================================
# EVENTS
# ============================================

emitters = MultiEventEmitter([
    PrintEventEmitter()
])


# ============================================
# SERVICES
# ============================================

# Execution Service
execution_service = ExecutionService(
    repository=execution_repository,
    event_emitters=emitters,
)

# Domain Service
domain_service = DomainService(
    template_repo=template_repository,
    app_repo=application_repository,
    deployment_repo=deployment_repository,
    resource_repo=resource_repository,
    step_repo=step_execution_repository,
)

# Node Manager Service
node_manager_service = NodeManagerService(
    node_repo=node_repository,
)

deployment_orchestrator = DeploymentOrchestrator(
    domain_service=domain_service,
    execution_service=execution_service,
    node_manager_service=node_manager_service,
    deployment_repo=deployment_repository,
    resource_repo=resource_repository,
    step_repo=step_execution_repository,
)


# ============================================
# EXPORTS (for easy importing)
# ============================================

__all__ = [
    # Repositories
    'execution_repository',
    'template_repository',
    'application_repository',
    'deployment_repository',
    'resource_repository',
    'step_execution_repository',
    'node_repository',
    
    # Services
    'execution_service',
    'domain_service',
    'node_manager_service',
    'deployment_orchestrator',
    
    # Events
    'emitters',
]
