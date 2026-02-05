#execution_engine\node_manager\models.py

"""Infrastructure node models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID


class NodeType(Enum):
    """Infrastructure node type."""
    APP_NODE = "APP_NODE"
    DB_NODE = "DB_NODE"
    EDGE_NODE = "EDGE_NODE"


class NodeStatus(Enum):
    """Node status."""
    READY = "READY"
    FULL = "FULL"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class NodeHealthStatus(Enum):
    """Node health status."""
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class InfrastructureNode:
    """Infrastructure node (server/VM running containers)."""
    node_id: UUID
    node_name: str
    node_type: NodeType
    
    internal_ip: str
    runtime_agent_url: str
    public_ip: Optional[str] = None
    
    
    supported_runtimes: List[str] = field(default_factory=lambda: ["docker"])
    
    total_cpu: float = 0.0  # cores
    total_memory: int = 0  # MB
    total_storage: int = 0  # GB
    
    available_cpu: float = 0.0
    available_memory: int = 0
    available_storage: int = 0
    
    max_containers: int = 50
    active_containers: int = 0
    
    status: NodeStatus = NodeStatus.READY
    health_status: NodeHealthStatus = NodeHealthStatus.UNKNOWN
    
    last_heartbeat_at: Optional[datetime] = None
    
    labels: Dict[str, str] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def update_capacity(
        self,
        available_cpu: float,
        available_memory: int,
        available_storage: int,
        active_containers: int
    ) -> None:
        """Update node capacity metrics."""
        self.available_cpu = available_cpu
        self.available_memory = available_memory
        self.available_storage = available_storage
        self.active_containers = active_containers
    
    def can_accommodate(
        self,
        required_cpu: float,
        required_memory: int,
        required_storage: int
    ) -> bool:
        """Check if node can accommodate resource requirements."""
        return (
            self.available_cpu >= required_cpu and
            self.available_memory >= required_memory and
            self.available_storage >= required_storage and
            self.active_containers < self.max_containers
        )
    
    def is_available(self) -> bool:
        """Check if node is available for deployments."""
        return (
            self.status == NodeStatus.READY and
            self.health_status == NodeHealthStatus.HEALTHY
        )