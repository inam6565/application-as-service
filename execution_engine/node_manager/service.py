"""Node manager service."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

from execution_engine.node_manager.models import (
    InfrastructureNode, NodeStatus, NodeHealthStatus
)
from execution_engine.infrastructure.postgres.node_repository import NodeRepository
from execution_engine.core.errors import ExecutionValidationError


class NodeManagerService:
    """Service for managing infrastructure nodes."""
    
    def __init__(self, node_repo: NodeRepository):
        self._node_repo = node_repo
    
    # ============================================
    # NODE REGISTRATION
    # ============================================
    
    def register_node(self, node: InfrastructureNode) -> None:
        """Register a new infrastructure node."""
        # Validate node
        if not node.runtime_agent_url:
            raise ExecutionValidationError("runtime_agent_url required")
        
        if not node.internal_ip:
            raise ExecutionValidationError("internal_ip required")
        
        # Set initial status
        node.status = NodeStatus.READY
        node.health_status = NodeHealthStatus.HEALTHY
        node.last_heartbeat_at = datetime.now(timezone.utc)
        
        self._node_repo.create(node)
        
        print(f"[node_manager] registered node {node.node_id} ({node.node_name})")
    
    def get_node(self, node_id: UUID) -> Optional[InfrastructureNode]:
        """Get node by ID."""
        return self._node_repo.get(node_id)
    
    def get_node_by_name(self, node_name: str) -> Optional[InfrastructureNode]:
        """Get node by name."""
        return self._node_repo.get_by_name(node_name)
    
    # ============================================
    # NODE SELECTION
    # ============================================
    
    def select_node(
        self,
        runtime_type: str,
        required_cpu: float,
        required_memory: int,
        required_storage: int,
    ) -> Optional[InfrastructureNode]:
        """
        Select best node for deployment.
        
        Strategy: Least loaded node with sufficient capacity.
        """
        available_nodes = self._node_repo.list_available(runtime_type=runtime_type)
        #print(f"[node_manager] available nodes {available_nodes}")
        # Filter by capacity
        suitable_nodes = [
            node for node in available_nodes
            if node.can_accommodate(required_cpu, required_memory, required_storage)
        ]
        #print(f"[node_manager] suitable nodes {suitable_nodes}")
        if not suitable_nodes:
            print(f"[node_manager] no suitable nodes found for {runtime_type}")
            return None
        
        # Select least loaded
        selected = min(suitable_nodes, key=lambda n: n.active_containers)
        
        print(f"[node_manager] selected node {selected.node_id} ({selected.node_name})")
        
        return selected
    
    def list_available_nodes(self, runtime_type: Optional[str] = None) -> List[InfrastructureNode]:
        """List all available nodes."""
        return self._node_repo.list_available(runtime_type=runtime_type)
    
    # ============================================
    # CAPACITY MANAGEMENT
    # ============================================
    
    def update_capacity(
        self,
        node_id: UUID,
        available_cpu: float,
        available_memory: int,
        available_storage: int,
        active_containers: int,
    ) -> None:
        """Update node capacity metrics."""
        node = self._node_repo.get(node_id)
        if not node:
            raise ExecutionValidationError(f"Node {node_id} not found")
        
        node.update_capacity(
            available_cpu=available_cpu,
            available_memory=available_memory,
            available_storage=available_storage,
            active_containers=active_containers,
        )
        
        # Update status based on capacity
        if active_containers >= node.max_containers:
            node.status = NodeStatus.FULL
        elif node.available_cpu < 0.5:  # Less than 0.5 CPU cores available
            node.status = NodeStatus.FULL
        else:
            node.status = NodeStatus.READY
        
        self._node_repo.update(node)
    
    def report_heartbeat(
        self,
        node_id: UUID,
        health_status: NodeHealthStatus,
    ) -> None:
        """Update node heartbeat and health status."""
        node = self._node_repo.get(node_id)
        if not node:
            raise ExecutionValidationError(f"Node {node_id} not found")
        
        node.health_status = health_status
        node.last_heartbeat_at = datetime.now(timezone.utc)
        
        self._node_repo.update(node)
    
    def check_stale_nodes(self, stale_threshold_minutes: int = 5) -> List[InfrastructureNode]:
        """
        Find nodes that haven't sent heartbeat recently.
        
        Returns list of potentially offline nodes.
        """
        all_nodes = self._node_repo.list_available()
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_threshold_minutes)
        
        stale_nodes = [
            node for node in all_nodes
            if node.last_heartbeat_at and node.last_heartbeat_at < stale_cutoff
        ]
        
        # Mark as offline
        for node in stale_nodes:
            node.status = NodeStatus.OFFLINE
            node.health_status = NodeHealthStatus.UNHEALTHY
            self._node_repo.update(node)
        
        return stale_nodes