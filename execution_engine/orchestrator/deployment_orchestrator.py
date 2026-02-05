"""Deployment orchestrator - coordinates multi-step deployments."""

from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone

from execution_engine.domain.service import DomainService
from execution_engine.domain.models import (
    DeploymentStatus, StepStatus, DeploymentStepExecution,
    DeployedResource, ResourceType
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
        
        This creates executions for each deployment step.
        """
        deployment = self._domain_service.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")
        
        print(f"[orchestrator] starting deployment {deployment_id}")
        
        # Get template
        template = self._domain_service.get_template(deployment.template_id)
        if not template:
            raise ValueError(f"Template {deployment.template_id} not found")
        
        # Update deployment status
        deployment.status = DeploymentStatus.DEPLOYING
        deployment.started_at = datetime.now(timezone.utc)
        self._deployment_repo.update(deployment)
        
        print(f"[orchestrator] deployment has {len(template.deployment_steps)} steps")
        
        # For MVP: Execute steps sequentially
        # Future: Support parallel execution with dependency graph
        
        for step_def in sorted(template.deployment_steps, key=lambda s: s.order):
            print(f"[orchestrator] processing step {step_def.order}: {step_def.step_id}")
            
            try:
                self._execute_step(deployment, step_def)
            except Exception as e:
                print(f"[orchestrator] step {step_def.step_id} failed: {e}")
                
                # Mark deployment as failed
                deployment.status = DeploymentStatus.FAILED
                deployment.error_message = str(e)
                deployment.completed_at = datetime.now(timezone.utc)
                self._deployment_repo.update(deployment)
                
                raise
        
        # All steps completed
        deployment.status = DeploymentStatus.RUNNING
        deployment.completed_at = datetime.now(timezone.utc)
        self._deployment_repo.update(deployment)
        
        print(f"[orchestrator] deployment {deployment_id} completed successfully")
    
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
        
        This creates an Execution and processes it through the execution engine.
        """
        spec = step_config["spec_template"]
        
        print(f"[orchestrator] deploying container: {spec['name']}")
        
        # Parse resource requirements
        resources = spec.get("resources", {})
        cpu = float(resources.get("cpu", "0.5"))
        memory_str = resources.get("memory", "512Mi")
        
        # Convert memory to MB
        memory_mb = self._parse_memory(memory_str)
        
        # Select node
        node = self._node_manager_service.select_node(
            runtime_type="docker",
            required_cpu=cpu,
            required_memory=memory_mb,
            required_storage=1,  # 1GB default
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
                "container_spec": spec,
            },
        )
        
        # Register and queue execution
        self._execution_service.register_execution(execution)
        self._execution_service.queue_execution(execution.execution_id)
        
        print(f"[orchestrator] created execution {execution.execution_id}")
        
        # For MVP: Return immediately with execution ID
        # In production: Wait for execution to complete or use async callbacks
        
        result = {
            "execution_id": str(execution.execution_id),
            "node_id": str(node.node_id),
            "node_name": node.node_name,
            "container_name": spec["name"],
            "status": "queued"
        }
        
        print(f"[orchestrator] container deployment queued: {result}")
        
        return result
    
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