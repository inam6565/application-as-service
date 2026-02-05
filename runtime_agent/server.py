# execution_engine/runtime_agent/server.py
"""
Runtime Agent - Runs on compute nodes.
Receives deployment requests and manages Docker containers.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from uuid import UUID
import docker
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Runtime Agent",
    description="Container runtime agent for execution engine",
    version="1.0.0"
)

# Docker client (connects to local Docker daemon)
try:
    docker_client = docker.from_env()
    logger.info("✅ Connected to Docker daemon")
except Exception as e:
    logger.error(f"❌ Failed to connect to Docker: {e}")
    docker_client = None


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ContainerSpec(BaseModel):
    """Container specification."""
    image: str = Field(..., description="Docker image (e.g., 'nginx:alpine')")
    name: str = Field(..., description="Container name")
    ports: Dict[str, int] = Field(default_factory=dict, description="Port mappings {'80/tcp': 8080}")
    environment: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    volumes: List[str] = Field(default_factory=list, description="Volume mounts")
    restart_policy: str = Field(default="always", description="Restart policy")
    labels: Dict[str, str] = Field(default_factory=dict, description="Container labels")


class DeployRequest(BaseModel):
    """Deploy container request."""
    execution_id: UUID
    container_spec: ContainerSpec


class DeployResponse(BaseModel):
    """Deploy container response."""
    container_id: str
    container_name: str
    status: str
    internal_ip: Optional[str]
    ports: Dict[str, int]


class ContainerStatusResponse(BaseModel):
    """Container status response."""
    container_id: str
    status: str  # "running", "exited", "paused", etc.
    running: bool
    exit_code: Optional[int]


class NodeInfoResponse(BaseModel):
    """Node information response."""
    docker_version: str
    containers_running: int
    containers_total: int
    images_count: int
    memory_total: int  # bytes
    cpu_count: int


# ============================================
# ENDPOINTS
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if docker_client is None:
        raise HTTPException(status_code=503, detail="Docker not available")
    
    return {
        "status": "healthy",
        "docker_connected": True
    }


@app.get("/info", response_model=NodeInfoResponse)
async def get_node_info():
    """Get node information."""
    if docker_client is None:
        raise HTTPException(status_code=503, detail="Docker not available")
    
    try:
        info = docker_client.info()
        
        return NodeInfoResponse(
            docker_version=info.get("ServerVersion", "unknown"),
            containers_running=info.get("ContainersRunning", 0),
            containers_total=info.get("Containers", 0),
            images_count=info.get("Images", 0),
            memory_total=info.get("MemTotal", 0),
            cpu_count=info.get("NCPU", 0),
        )
    except Exception as e:
        logger.error(f"Failed to get node info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/deploy", response_model=DeployResponse)
async def deploy_container(request: DeployRequest):
    """
    Deploy a container.
    
    Steps:
    1. Pull image if not present
    2. Create container with spec
    3. Start container
    4. Return container details
    """
    if docker_client is None:
        raise HTTPException(status_code=503, detail="Docker not available")
    
    spec = request.container_spec
    
    try:
        logger.info(f"[{request.execution_id}] Starting deployment: {spec.name}")
        
        # Step 1: Pull image
        logger.info(f"[{request.execution_id}] Pulling image: {spec.image}")
        try:
            docker_client.images.pull(spec.image)
            logger.info(f"[{request.execution_id}] ✅ Image pulled")
        except docker.errors.ImageNotFound:
            raise HTTPException(status_code=404, detail=f"Image not found: {spec.image}")
        
        # Step 2: Prepare container config
        container_config = {
            "image": spec.image,
            "name": spec.name,
            "detach": True,
            "labels": {
                **spec.labels,
                "managed_by": "execution_engine",
                "execution_id": str(request.execution_id),
            }
        }
        
        # Add environment variables
        if spec.environment:
            container_config["environment"] = spec.environment
        
        # Add port mappings
        if spec.ports:
            container_config["ports"] = spec.ports
        
        # Add volumes
        if spec.volumes:
            container_config["volumes"] = spec.volumes
        
        # Add restart policy
        if spec.restart_policy:
            container_config["restart_policy"] = {"Name": spec.restart_policy}
        
        # Step 3: Create container
        logger.info(f"[{request.execution_id}] Creating container: {spec.name}")
        container = docker_client.containers.create(**container_config)
        logger.info(f"[{request.execution_id}] ✅ Container created: {container.id[:12]}")
        
        # Step 4: Start container
        logger.info(f"[{request.execution_id}] Starting container")
        container.start()
        
        # Step 5: Get container details
        container.reload()
        
        # Get internal IP
        internal_ip = None
        networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
        if networks:
            first_network = list(networks.values())[0]
            internal_ip = first_network.get('IPAddress')
        
        logger.info(f"[{request.execution_id}] ✅ Container started successfully")
        
        return DeployResponse(
            container_id=container.id,
            container_name=container.name,
            status=container.status,
            internal_ip=internal_ip,
            ports=spec.ports,
        )
        
    except docker.errors.APIError as e:
        logger.error(f"[{request.execution_id}] Docker API error: {e}")
        raise HTTPException(status_code=500, detail=f"Docker error: {str(e)}")
    except Exception as e:
        logger.error(f"[{request.execution_id}] Deployment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/containers/{container_id}/status", response_model=ContainerStatusResponse)
async def get_container_status(container_id: str):
    """Get container status."""
    if docker_client is None:
        raise HTTPException(status_code=503, detail="Docker not available")
    
    try:
        container = docker_client.containers.get(container_id)
        
        return ContainerStatusResponse(
            container_id=container.id,
            status=container.status,
            running=container.status == "running",
            exit_code=container.attrs.get('State', {}).get('ExitCode'),
        )
        
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except Exception as e:
        logger.error(f"Failed to get container status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/containers/{container_id}/stop")
async def stop_container(container_id: str):
    """Stop a container."""
    if docker_client is None:
        raise HTTPException(status_code=503, detail="Docker not available")
    
    try:
        container = docker_client.containers.get(container_id)
        container.stop(timeout=10)
        
        return {"status": "stopped", "container_id": container_id}
        
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except Exception as e:
        logger.error(f"Failed to stop container: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/containers/{container_id}")
async def remove_container(container_id: str, force: bool = False):
    """Remove a container."""
    if docker_client is None:
        raise HTTPException(status_code=503, detail="Docker not available")
    
    try:
        container = docker_client.containers.get(container_id)
        container.remove(force=force)
        
        return {"status": "removed", "container_id": container_id}
        
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except Exception as e:
        logger.error(f"Failed to remove container: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting Runtime Agent...")
    logger.info("📍 Listening on 0.0.0.0:9000")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        log_level="info"
    )