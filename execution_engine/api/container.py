"""FastAPI dependency providers."""

from execution_engine.container import (
    deployment_orchestrator,
    domain_service,
    execution_service,
    node_manager_service,
)


def get_execution_service():
    return execution_service


def get_domain_service():
    return domain_service


def get_node_manager_service():
    return node_manager_service


def get_deployment_orchestrator():
    return deployment_orchestrator
