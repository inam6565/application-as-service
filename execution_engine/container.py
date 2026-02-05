#execution_engine\container.py

"""Dependency injection container - wires all services together."""

from execution_engine.infrastructure.postgres.repository import PostgresExecutionRepository
from execution_engine.infrastructure.postgres.domain_repository import (
    ApplicationTemplateRepository,
    ApplicationRepository,
    DeploymentRepository,
)
from execution_engine.infrastructure.postgres.node_repository import NodeRepository
from execution_engine.infrastructure.postgres.config import settings

from execution_engine.core.service import ExecutionService
from execution_engine.core.events import MultiEventEmitter, PrintEventEmitter

from execution_engine.domain.service import DomainService
from execution_engine.node_manager.service import NodeManagerService


# ============================================
# REPOSITORIES
# ============================================

# Execution Engine
execution_repository = PostgresExecutionRepository()

# Domain
template_repository = ApplicationTemplateRepository()
application_repository = ApplicationRepository()
deployment_repository = DeploymentRepository()

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
)

# Node Manager Service
node_manager_service = NodeManagerService(
    node_repo=node_repository,
)