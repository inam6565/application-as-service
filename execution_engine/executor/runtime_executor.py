# execution_engine/executor/runtime_executor.py
"""Runtime executor - executes deployments via Runtime Agent."""

import logging
from uuid import UUID
from typing import Dict, Any, Optional

from runtime_agent.client import RuntimeAgentClient, DeploymentResult
from execution_engine.core.errors import ExecutionValidationError

logger = logging.getLogger(__name__)


class RuntimeExecutor:
    """
    Executes container deployments by calling Runtime Agent.
    
    This replaces the mock executor that just sleeps.
    """
    
    def __init__(self):
        """Initialize runtime executor."""
        self._agent_clients: Dict[str, RuntimeAgentClient] = {}
    
    def execute_deployment(
        self,
        execution_id: UUID,
        spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a container deployment.
        
        Args:
            execution_id: Execution ID
            spec: Execution spec containing:
                - node_id: Target node ID
                - container_spec: Container specification
                
        Returns:
            Deployment result dict
            
        Raises:
            RuntimeError: If deployment fails
        """
        logger.info(f"[{execution_id}] Starting deployment execution")
        
        # Extract spec
        node_id = spec.get('node_id')
        container_spec = spec.get('container_spec')
        
        if not node_id:
            raise ExecutionValidationError("node_id required in spec")
        
        if not container_spec:
            raise ExecutionValidationError("container_spec required in spec")
        
        # Get runtime agent URL from node manager
        # For now, we'll expect it in the spec
        agent_url = spec.get('agent_url')
        if not agent_url:
            raise ExecutionValidationError("agent_url required in spec")
        
        # Get or create agent client
        agent_client = self._get_agent_client(agent_url)
        
        # Check agent health
        if not agent_client.health_check():
            raise RuntimeError(f"Runtime agent at {agent_url} is not healthy")
        
        # Deploy container
        try:
            result = agent_client.deploy_container(
                execution_id=execution_id,
                container_spec=container_spec
            )
            
            logger.info(f"[{execution_id}] ✅ Deployment successful")
            
            # Return result as dict
            return {
                "container_id": result.container_id,
                "container_name": result.container_name,
                "status": result.status,
                "internal_ip": result.internal_ip,
                "ports": result.ports,
                "node_id": node_id,
                "agent_url": agent_url,
            }
            
        except Exception as e:
            logger.error(f"[{execution_id}] ❌ Deployment failed: {e}")
            raise
    
    def _get_agent_client(self, agent_url: str) -> RuntimeAgentClient:
        """Get or create agent client for given URL."""
        if agent_url not in self._agent_clients:
            self._agent_clients[agent_url] = RuntimeAgentClient(agent_url)
        
        return self._agent_clients[agent_url]