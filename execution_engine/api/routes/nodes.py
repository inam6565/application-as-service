# execution_engine/api/routes/nodes.py
"""Node management API routes."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4

from execution_engine.node_manager.models import (
    InfrastructureNode, NodeType, NodeStatus, NodeHealthStatus
)
from execution_engine.container import node_manager_service

router = APIRouter(prefix="/nodes", tags=["nodes"])


class RegisterNodeRequest(BaseModel):
    """Register node request."""
    node_name: str = Field(..., min_length=1, max_length=255)
    node_type: str = Field(default="APP_NODE")
    internal_ip: str
    public_ip: Optional[str] = None
    runtime_agent_url: str
    supported_runtimes: List[str] = Field(default=["docker"])
    total_cpu: float = Field(..., gt=0)
    total_memory: int = Field(..., gt=0)
    total_storage: int = Field(..., gt=0)
    max_containers: int = Field(default=50, gt=0)


class NodeResponse(BaseModel):
    """Node response."""
    node_id: UUID
    node_name: str
    node_type: str
    internal_ip: str
    public_ip: Optional[str]
    runtime_agent_url: str
    status: str
    health_status: str
    available_cpu: float
    available_memory: int
    available_storage: int
    active_containers: int
    max_containers: int


@router.post("/register", response_model=NodeResponse)
async def register_node(request: RegisterNodeRequest):
    """
    Register a new infrastructure node.
    
    This endpoint is called to add a compute node to the platform.
    """
    try:
        # Create node
        node = InfrastructureNode(
            node_id=uuid4(),
            node_name=request.node_name,
            node_type=NodeType[request.node_type],
            internal_ip=request.internal_ip,
            public_ip=request.public_ip,
            runtime_agent_url=request.runtime_agent_url,
            supported_runtimes=request.supported_runtimes,
            total_cpu=request.total_cpu,
            total_memory=request.total_memory,
            total_storage=request.total_storage,
            available_cpu=request.total_cpu,  # Initially fully available
            available_memory=request.total_memory,
            available_storage=request.total_storage,
            max_containers=request.max_containers,
            active_containers=0,
        )
        
        # Register
        node_manager_service.register_node(node)
        
        return NodeResponse(
            node_id=node.node_id,
            node_name=node.node_name,
            node_type=node.node_type.value,
            internal_ip=node.internal_ip,
            public_ip=node.public_ip,
            runtime_agent_url=node.runtime_agent_url,
            status=node.status.value,
            health_status=node.health_status.value,
            available_cpu=node.available_cpu,
            available_memory=node.available_memory,
            available_storage=node.available_storage,
            active_containers=node.active_containers,
            max_containers=node.max_containers,
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[NodeResponse])
async def list_nodes():
    """List all registered nodes."""
    nodes = node_manager_service.list_available_nodes()
    
    return [
        NodeResponse(
            node_id=node.node_id,
            node_name=node.node_name,
            node_type=node.node_type.value,
            internal_ip=node.internal_ip,
            public_ip=node.public_ip,
            runtime_agent_url=node.runtime_agent_url,
            status=node.status.value,
            health_status=node.health_status.value,
            available_cpu=node.available_cpu,
            available_memory=node.available_memory,
            available_storage=node.available_storage,
            active_containers=node.active_containers,
            max_containers=node.max_containers,
        )
        for node in nodes
    ]


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(node_id: UUID):
    """Get node details."""
    node = node_manager_service.get_node(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return NodeResponse(
        node_id=node.node_id,
        node_name=node.node_name,
        node_type=node.node_type.value,
        internal_ip=node.internal_ip,
        public_ip=node.public_ip,
        runtime_agent_url=node.runtime_agent_url,
        status=node.status.value,
        health_status=node.health_status.value,
        available_cpu=node.available_cpu,
        available_memory=node.available_memory,
        available_storage=node.available_storage,
        active_containers=node.active_containers,
        max_containers=node.max_containers,
    )