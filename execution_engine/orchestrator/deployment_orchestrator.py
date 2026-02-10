# execution_engine/orchestrator/deployment_orchestrator.py
"""Deployment orchestrator - coordinates multi-step deployments."""

import time
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone

from execution_engine.domain.service import DomainService
from execution_engine.domain.models import (
    DeploymentStatus, StepStatus, DeploymentStepExecution,
    DeployedResource, ResourceType, ApplicationStatus
)
from execution_engine.core.service import ExecutionService
from execution_engine.core.models import Execution, ExecutionState
from execution_engine.node_manager.service import NodeManagerService
from execution_engine.infrastructure.postgres.domain_repository import DeploymentRepository


class DeploymentOrchestrator:
    """
    Orchestrates multi-step application deployments.
    
    Flow:
    1. Get deployment from domain service
    2. For each step in order:
       a. Check dependencies completed
       b. Select infrastructure node
       c. Create execution
       d. Wait for execution to complete
       e. Store step result
    3. Mark deployment as complete
    """
    
    def __init__(
        self,
        domain_service: DomainService,
        execution_service: ExecutionService,
        node_manager_service: NodeManagerService,
        deployment_repo: DeploymentRepository,
    ):
        self._domain_service = domain_service
        self._execution_service = execution_service
        self._node_manager_service = node_manager_service
        self._deployment_repo = deployment_repo
    
    def start_deployment(self, deployment_id: UUID) -> None:
        """
        Start a deployment workflow.
        
        ✅ ASYNC VERSION:
        - Creates executions for all steps
        - Queues them
        - Returns immediately
        - Status updater handles completion
        """
        deployment = self._domain_service.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")
        
        print(f"[orchestrator] starting deployment {deployment_id}")
        
        # Get template
        template = self._domain_service.get_template(deployment.template_id)
        if not template:
            raise ValueError(f"Template {deployment.template_id} not found")
        
        # ✅ Update deployment status to DEPLOYING
        deployment.status = DeploymentStatus.DEPLOYING
        deployment.started_at = datetime.now(timezone.utc)
        self._deployment_repo.update(deployment)
        
        print(f"[orchestrator] deployment has {len(template.deployment_steps)} steps")
        
        try:
            # Execute steps sequentially (create executions)
            for step_def in sorted(template.deployment_steps, key=lambda s: s.order):
                print(f"[orchestrator] processing step {step_def.order}: {step_def.step_id}")
                
                try:
                    self._execute_step(deployment, step_def)
                except Exception as e:
                    print(f"[orchestrator] step {step_def.step_id} failed: {e}")
                    raise
            
            # ✅ REMOVE ALL STATUS UPDATES HERE
            # Status updater will handle them!
            
            print(f"[orchestrator] all executions queued, status updater will monitor")
            
        except Exception as e:
            print(f"[orchestrator] deployment {deployment_id} failed during orchestration: {e}")
            
            # ✅ Only mark as FAILED if orchestration itself fails
            # (not execution failures - status updater handles those)
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = f"Orchestration error: {str(e)}"
            deployment.completed_at = datetime.now(timezone.utc)
            self._deployment_repo.update(deployment)
            
            raise
  
    def _execute_step(self, deployment, step_def) -> Dict[str, Any]:
        """
        Execute a single deployment step.
        
        Returns step result data.
        """
        print(f"[orchestrator] executing step: {step_def.step_id}")
        
        # Get step configuration from resolved config
        step_config = None
        for step in deployment.resolved_config.get("steps", []):
            if step["step_id"] == step_def.step_id:
                step_config = step
                break
        
        if not step_config:
            raise ValueError(f"Step {step_def.step_id} not found in resolved config")
        
        # Handle different step types
        if step_def.step_type == "volume":
            return self._execute_volume_step(deployment, step_def, step_config)
        
        elif step_def.step_type == "database":
            return self._execute_database_step(deployment, step_def, step_config)
        
        elif step_def.step_type == "container":
            return self._execute_container_step(deployment, step_def, step_config)
        
        else:
            raise ValueError(f"Unknown step type: {step_def.step_type}")
    
    def _execute_volume_step(self, deployment, step_def, step_config) -> Dict[str, Any]:
        """Execute volume creation step (simplified for MVP)."""
        print(f"[orchestrator] creating volume: {step_config['spec_template']['volume_name']}")
        
        # For MVP: Just return success
        # In production: Create actual volume via Runtime Agent
        
        result = {
            "volume_name": step_config["spec_template"]["volume_name"],
            "status": "created"
        }
        
        print(f"[orchestrator] volume created: {result}")
        
        return result
    
    def _execute_database_step(self, deployment, step_def, step_config) -> Dict[str, Any]:
        """Execute database provisioning step (simplified for MVP)."""
        spec = step_config["spec_template"]
        
        print(f"[orchestrator] provisioning database: {spec['db_name']}")
        
        # For MVP: Simulate DB provisioning
        # In production: Call database provisioning service
        
        # Simulated DB connection details
        result = {
            "db_type": spec["db_type"],
            "db_name": spec["db_name"],
            "db_user": spec["db_user"],
            "db_host": "mysql-server.local",  # From user input or platform DB server
            "db_port": 3306,
            "status": "ready"
        }
        
        print(f"[orchestrator] database provisioned: {result}")
        
        return result
    
    def _execute_container_step(self, deployment, step_def, step_config) -> Dict[str, Any]:
        """
        Execute container deployment step.
        
        Creates execution and tracks deployed resource.
        """
        spec = step_config["spec_template"]
        
        print(f"[orchestrator] deploying container: {spec['name']}")
        
        # Parse resource requirements
        resources = spec.get("resources", {})
        cpu = float(resources.get("cpu", "0.5"))
        memory_str = resources.get("memory", "512Mi")
        memory_mb = self._parse_memory(memory_str)
        
        # Select node
        node = self._node_manager_service.select_node(
            runtime_type="docker",
            required_cpu=cpu,
            required_memory=memory_mb,
            required_storage=1,
        )
        
        if not node:
            raise RuntimeError("No suitable infrastructure node available")
        
        print(f"[orchestrator] selected node: {node.node_name}")
        
        # Create execution
        execution = Execution(
            execution_id=uuid4(),
            tenant_id=deployment.tenant_id,
            application_id=deployment.application_id,
            deployment_id=deployment.deployment_id,
            execution_type="deploy",
            runtime_type="docker",
            spec={
                "node_id": str(node.node_id),
                "agent_url": node.runtime_agent_url,
                "container_spec": spec,
            },
        )
        
        # Register and queue execution
        self._execution_service.register_execution(execution)
        self._execution_service.queue_execution(execution.execution_id)
        
        print(f"[orchestrator] created execution {execution.execution_id}")
        
        # ✅ ADD: Track as deployed resource
        from execution_engine.domain.models import DeployedResource, ResourceType, HealthStatus
        from execution_engine.infrastructure.postgres.domain_repository import DeployedResourceRepository
        
        # Convert health check to dict
        health_check_dict = None
        if step_def.health_check:
            health_check_dict = {
                'type': step_def.health_check.type,
                'path': step_def.health_check.path,
                'port': step_def.health_check.port,
                'command': step_def.health_check.command,
                'interval_seconds': step_def.health_check.interval_seconds,
                'timeout_seconds': step_def.health_check.timeout_seconds,
                'retries': step_def.health_check.retries,
                'initial_delay_seconds': step_def.health_check.initial_delay_seconds,
            }
        
        deployed_resource = DeployedResource(
            resource_id=uuid4(),
            deployment_id=deployment.deployment_id,
            resource_type=ResourceType.CONTAINER,
            external_id="pending",  # Will be updated when execution completes
            node_id=node.node_id,
            name=spec["name"],
            spec={
                **step_config,
                'execution_id': str(execution.execution_id),
                'health_check': health_check_dict,
            },
            status="pending",
            health_status=HealthStatus.UNKNOWN,
        )
        
        resource_repo = DeployedResourceRepository()
        resource_repo.create(deployed_resource)
        
        print(f"[orchestrator] tracked deployed resource {deployed_resource.resource_id}")
        
        # Return result
        result = {
            'execution_id': str(execution.execution_id),
            'resource_id': str(deployed_resource.resource_id),
            'node_id': str(node.node_id),
            'node_name': node.node_name,
            'container_name': spec["name"],
            'status': "queued",
        }
        
        print(f"[orchestrator] container deployment queued: {result}")
        
        return result
   
    def _wait_for_execution(
        self,
        execution_id: UUID,
        timeout_seconds: int = 300,
    ) -> Dict[str, Any]:
        """
        Wait for execution to complete.
        
        Polls execution status every 2 seconds until:
        - Execution completes (returns result)
        - Execution fails (raises error)
        - Timeout (raises error)
        
        Args:
            execution_id: Execution to wait for
            timeout_seconds: Maximum time to wait
            
        Returns:
            Execution result dictionary
            
        Raises:
            RuntimeError: If execution fails or times out
        """
        start_time = datetime.now(timezone.utc)
        poll_interval = 2  # seconds
        
        while True:
            # Get current execution state
            execution = self._execution_service._repo.get(execution_id)
            
            if not execution:
                raise RuntimeError(f"Execution {execution_id} not found")
            
            # Check if completed
            if execution.state == ExecutionState.COMPLETED:
                print(f"[orchestrator] execution {execution_id} completed successfully")
                
                result = {
                    "execution_id": str(execution.execution_id),
                    "status": "completed",
                    "deployment_result": execution.deployment_result or {},
                }
                
                return result
            
            # Check if failed
            if execution.state == ExecutionState.FAILED:
                error_msg = execution.error_message or "Unknown error"
                print(f"[orchestrator] execution {execution_id} failed: {error_msg}")
                raise RuntimeError(f"Execution failed: {error_msg}")
            
            # Check timeout
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > timeout_seconds:
                raise RuntimeError(f"Execution timeout after {timeout_seconds}s (current state: {execution.state.value})")
            
            # Log progress
            if elapsed % 10 == 0:  # Log every 10 seconds
                print(f"[orchestrator] execution {execution_id} still running (state: {execution.state.value}, elapsed: {int(elapsed)}s)")
            
            # Wait before next poll
            time.sleep(poll_interval)
    
    def _parse_memory(self, memory_str: str) -> int:
        """Parse memory string (e.g., '512Mi', '1Gi') to MB."""
        memory_str = memory_str.strip()
        
        if memory_str.endswith("Gi"):
            return int(float(memory_str[:-2]) * 1024)
        elif memory_str.endswith("Mi"):
            return int(float(memory_str[:-2]))
        elif memory_str.endswith("G"):
            return int(float(memory_str[:-1]) * 1024)
        elif memory_str.endswith("M"):
            return int(float(memory_str[:-1]))
        else:
            # Assume MB
            return int(memory_str)