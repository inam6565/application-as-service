"""Node manager repository."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from execution_engine.node_manager.models import InfrastructureNode, NodeStatus, NodeHealthStatus
from execution_engine.infrastructure.postgres.database import SessionLocal
from execution_engine.infrastructure.postgres.models import InfrastructureNodeORM
from execution_engine.core.errors import ExecutionConcurrencyError


def node_to_orm(node: InfrastructureNode) -> InfrastructureNodeORM:
    """Convert node domain model to ORM."""
    return InfrastructureNodeORM(
        node_id=node.node_id,
        node_name=node.node_name,
        node_type=node.node_type,
        internal_ip=node.internal_ip,
        public_ip=node.public_ip,
        runtime_agent_url=node.runtime_agent_url,
        supported_runtimes=node.supported_runtimes,
        total_cpu=node.total_cpu,
        total_memory=node.total_memory,
        total_storage=node.total_storage,
        available_cpu=node.available_cpu,
        available_memory=node.available_memory,
        available_storage=node.available_storage,
        max_containers=node.max_containers,
        active_containers=node.active_containers,
        status=node.status,
        health_status=node.health_status,
        last_heartbeat_at=node.last_heartbeat_at,
        labels=node.labels,
        created_at=node.created_at,
        registered_at=node.registered_at,
    )


def orm_to_node(orm: InfrastructureNodeORM) -> InfrastructureNode:
    """Convert ORM to node domain model."""
    return InfrastructureNode(
        node_id=orm.node_id,
        node_name=orm.node_name,
        node_type=orm.node_type,
        internal_ip=orm.internal_ip,
        public_ip=orm.public_ip,
        runtime_agent_url=orm.runtime_agent_url,
        supported_runtimes=orm.supported_runtimes,
        total_cpu=orm.total_cpu,
        total_memory=orm.total_memory,
        total_storage=orm.total_storage,
        available_cpu=orm.available_cpu,
        available_memory=orm.available_memory,
        available_storage=orm.available_storage,
        max_containers=orm.max_containers,
        active_containers=orm.active_containers,
        status=orm.status,
        health_status=orm.health_status,
        last_heartbeat_at=orm.last_heartbeat_at,
        labels=orm.labels,
        created_at=orm.created_at,
        registered_at=orm.registered_at,
    )


class NodeRepository:
    """Repository for infrastructure nodes."""
    
    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal
    
    def _get_session(self):
        return self._session_factory()
    
    def create(self, node: InfrastructureNode) -> None:
        """Register a new node."""
        session = self._get_session()
        try:
            orm = node_to_orm(node)
            session.add(orm)
            session.commit()
            print(f"[node_repo] registered node {node.node_id} ({node.node_name})")
        except IntegrityError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Node {node.node_name} already exists") from e
        finally:
            session.close()
    
    def get(self, node_id: UUID) -> Optional[InfrastructureNode]:
        """Get node by ID."""
        session = self._get_session()
        try:
            orm = session.get(InfrastructureNodeORM, node_id)
            if not orm:
                return None
            return orm_to_node(orm)
        finally:
            session.close()
    
    def get_by_name(self, node_name: str) -> Optional[InfrastructureNode]:
        """Get node by name."""
        session = self._get_session()
        try:
            orm = session.query(InfrastructureNodeORM).filter(
                InfrastructureNodeORM.node_name == node_name
            ).first()
            if not orm:
                return None
            return orm_to_node(orm)
        finally:
            session.close()
    
    def update(self, node: InfrastructureNode) -> None:
        """Update node."""
        session = self._get_session()
        try:
            orm = session.get(InfrastructureNodeORM, node.node_id)
            if not orm:
                raise ExecutionConcurrencyError(f"Node {node.node_id} not found")
            
            # Update capacity fields
            orm.available_cpu = node.available_cpu
            orm.available_memory = node.available_memory
            orm.available_storage = node.available_storage
            orm.active_containers = node.active_containers
            orm.status = node.status
            orm.health_status = node.health_status
            orm.last_heartbeat_at = node.last_heartbeat_at
            
            session.commit()
            print(f"[node_repo] updated node {node.node_id}")
        except SQLAlchemyError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Failed to update node: {e}") from e
        finally:
            session.close()
    
    def list_available(self, runtime_type: str = "docker") -> List[InfrastructureNode]:
        """
        List available nodes for deployment.
        
        Filters by status, health, and supported runtime.
        Accepts HEALTHY or UNKNOWN health status (for newly registered nodes).
        """
        session = self._get_session()
        try:
            # Query for available nodes - accept HEALTHY or UNKNOWN
            query = session.query(InfrastructureNodeORM).filter(
                InfrastructureNodeORM.status == NodeStatus.READY,
                InfrastructureNodeORM.health_status.in_([
                    NodeHealthStatus.HEALTHY,
                    NodeHealthStatus.UNKNOWN  # Accept newly registered nodes
                ])
            )
            
            orms = query.order_by(
                InfrastructureNodeORM.active_containers.asc()  # Least loaded first
            ).all()
            
            # Convert to domain models
            nodes = [orm_to_node(orm) for orm in orms]
            
            # Filter by runtime support (in Python - simpler than JSON SQL)
            if runtime_type:
                nodes = [
                    node for node in nodes
                    if runtime_type in node.supported_runtimes
                ]
            
            print(f"[node_repo] found {len(nodes)} available nodes for runtime '{runtime_type}'")
            
            return nodes
        finally:
            session.close()                
    def update_heartbeat(self, node_id: UUID) -> None:
        """Update node heartbeat timestamp."""
        session = self._get_session()
        try:
            orm = session.get(InfrastructureNodeORM, node_id)
            if not orm:
                raise ExecutionConcurrencyError(f"Node {node_id} not found")
            
            orm.last_heartbeat_at = datetime.now(timezone.utc)
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Failed to update heartbeat: {e}") from e
        finally:
            session.close()