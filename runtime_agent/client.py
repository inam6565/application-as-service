# execution_engine/runtime_agent/client.py
"""Runtime Agent client for making deployment requests."""

import requests
from typing import Dict, Any, Optional
from uuid import UUID
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    """Result from container deployment."""
    container_id: str
    container_name: str
    status: str
    internal_ip: Optional[str]
    ports: Dict[str, int]


class RuntimeAgentClient:
    """Client for communicating with Runtime Agent."""
    
    def __init__(self, agent_url: str, timeout: int = 30):
        """
        Initialize client.
        
        Args:
            agent_url: Base URL of runtime agent (e.g., "http://10.0.1.10:9000")
            timeout: Request timeout in seconds
        """
        self.base_url = agent_url.rstrip('/')
        self.timeout = timeout
    
    def health_check(self) -> bool:
        """
        Check if agent is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_node_info(self) -> Optional[Dict[str, Any]]:
        """
        Get node information.
        
        Returns:
            Node info dict or None if failed
        """
        try:
            response = requests.get(
                f"{self.base_url}/info",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get node info: {e}")
            return None
    
    def deploy_container(
        self,
        execution_id: UUID,
        container_spec: Dict[str, Any]
    ) -> DeploymentResult:
        """
        Deploy a container.
        
        Args:
            execution_id: Execution ID for tracking
            container_spec: Container specification
            
        Returns:
            DeploymentResult
            
        Raises:
            RuntimeError: If deployment fails
        """
        try:
            logger.info(f"[{execution_id}] Deploying container to {self.base_url}")
            
            # Prepare request
            payload = {
                "execution_id": str(execution_id),
                "container_spec": container_spec
            }
            
            # Make request
            response = requests.post(
                f"{self.base_url}/deploy",
                json=payload,
                timeout=self.timeout
            )
            
            # Check response
            if response.status_code != 200:
                error_detail = response.json().get('detail', response.text)
                raise RuntimeError(f"Deployment failed: {error_detail}")
            
            # Parse response
            data = response.json()
            
            logger.info(f"[{execution_id}] ✅ Container deployed: {data['container_id'][:12]}")
            
            return DeploymentResult(
                container_id=data['container_id'],
                container_name=data['container_name'],
                status=data['status'],
                internal_ip=data.get('internal_ip'),
                ports=data.get('ports', {}),
            )
            
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Deployment timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to runtime agent at {self.base_url}")
        except Exception as e:
            logger.error(f"[{execution_id}] Deployment error: {e}")
            raise RuntimeError(f"Deployment failed: {str(e)}")
    
    def get_container_status(self, container_id: str) -> Optional[Dict[str, Any]]:
        """
        Get container status.
        
        Args:
            container_id: Container ID
            
        Returns:
            Status dict or None if failed
        """
        try:
            response = requests.get(
                f"{self.base_url}/containers/{container_id}/status",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get container status: {e}")
            return None
    
    def stop_container(self, container_id: str) -> bool:
        """
        Stop a container.
        
        Args:
            container_id: Container ID
            
        Returns:
            True if stopped, False otherwise
        """
        try:
            response = requests.post(
                f"{self.base_url}/containers/{container_id}/stop",
                timeout=30
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to stop container: {e}")
            return False
    
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """
        Remove a container.
        
        Args:
            container_id: Container ID
            force: Force removal even if running
            
        Returns:
            True if removed, False otherwise
        """
        try:
            response = requests.delete(
                f"{self.base_url}/containers/{container_id}",
                params={"force": force},
                timeout=30
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to remove container: {e}")
            return False