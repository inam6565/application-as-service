# execution_engine/orchestrator/deployment_orchestrator.py
"""Deployment orchestrator - coordinates multi-step deployments."""

import time
import logging
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
from execution_engine.infrastructure.postgres.domain_repository import (
    DeploymentRepository,
    DeployedResourceRepository,
    DeploymentStepExecutionRepository,
)
from execution_engine.infrastructure.mysql.provisioner import MySQLProvisioner

logger = logging.getLogger(__name__)


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
        resource_repo: DeployedResourceRepository = None,
        step_repo: DeploymentStepExecutionRepository = None,
    ):
        self._domain_service = domain_service
        self._execution_service = execution_service
        self._node_manager_service = node_manager_service
        self._deployment_repo = deployment_repo
        self._resource_repo = resource_repo or DeployedResourceRepository()
        self._step_repo = step_repo or DeploymentStepExecutionRepository()
        self._mysql_provisioner = MySQLProvisioner()
    
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
        
        logger.info("[orchestrator] starting deployment %s", deployment_id)
        
        # Get template
        template = self._domain_service.get_template(deployment.template_id)
        if not template:
            raise ValueError(f"Template {deployment.template_id} not found")
        
        # ✅ Update deployment status to DEPLOYING
        deployment.status = DeploymentStatus.DEPLOYING
        deployment.started_at = datetime.now(timezone.utc)
        self._deployment_repo.update(deployment)
        
        logger.info("[orchestrator] deployment has %s steps", len(template.deployment_steps))
        
        try:
            step_results: Dict[str, Dict[str, Any]] = {}

            # Execute steps sequentially (create executions)
            for step_def in sorted(template.deployment_steps, key=lambda s: s.order):
                logger.info("[orchestrator] processing step %s: %s", step_def.order, step_def.step_id)
                
                step_execution = self._start_step(deployment, step_def)
                try:
                    result = self._execute_step(
                        deployment,
                        step_def,
                        step_results,
                        step_execution,
                    )
                    step_results[step_def.step_id] = result
                    if step_def.step_type != "container":
                        self._complete_step(step_execution, result)
                except Exception as e:
                    self._fail_step(step_execution, str(e))
                    logger.exception("[orchestrator] step %s failed: %s", step_def.step_id, e)
                    raise
            
            # ✅ REMOVE ALL STATUS UPDATES HERE
            # Status updater will handle them!
            
            logger.info("[orchestrator] all executions queued, status updater will monitor")
            
        except Exception as e:
            logger.exception("[orchestrator] deployment %s failed during orchestration: %s", deployment_id, e)
            
            # ✅ Only mark as FAILED if orchestration itself fails
            # (not execution failures - status updater handles those)
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = f"Orchestration error: {str(e)}"
            deployment.completed_at = datetime.now(timezone.utc)
            self._deployment_repo.update(deployment)
            
            raise

    def _start_step(self, deployment, step_def) -> DeploymentStepExecution:
        """Create or update a deployment step as running."""
        existing = self._step_repo.get_by_deployment_step(
            deployment.deployment_id,
            step_def.step_id,
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.status = StepStatus.RUNNING
            existing.error_message = None
            existing.started_at = existing.started_at or now
            self._step_repo.update(existing)
            return existing

        step_execution = DeploymentStepExecution(
            step_execution_id=uuid4(),
            deployment_id=deployment.deployment_id,
            step_id=step_def.step_id,
            step_name=step_def.step_name,
            status=StepStatus.RUNNING,
            started_at=now,
        )
        self._step_repo.create(step_execution)
        deployment.current_step_index = max(deployment.current_step_index, step_def.order - 1)
        self._deployment_repo.update(deployment)
        return step_execution

    def _complete_step(self, step_execution: DeploymentStepExecution, result: Dict[str, Any]) -> None:
        """Mark a synchronous deployment step complete."""
        now = datetime.now(timezone.utc)
        step_execution.status = StepStatus.COMPLETED
        step_execution.result = result
        step_execution.completed_at = now
        if step_execution.started_at:
            step_execution.duration_seconds = (now - self._as_utc(step_execution.started_at)).total_seconds()
        self._step_repo.update(step_execution)

    def _fail_step(self, step_execution: DeploymentStepExecution, error_message: str) -> None:
        """Mark a deployment step failed."""
        now = datetime.now(timezone.utc)
        step_execution.status = StepStatus.FAILED
        step_execution.error_message = error_message
        step_execution.completed_at = now
        if step_execution.started_at:
            step_execution.duration_seconds = (now - self._as_utc(step_execution.started_at)).total_seconds()
        self._step_repo.update(step_execution)

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
  
    def _execute_step(
        self,
        deployment,
        step_def,
        step_results: Dict[str, Dict[str, Any]],
        step_execution: DeploymentStepExecution,
    ) -> Dict[str, Any]:
        """
        Execute a single deployment step.
        
        Returns step result data.
        """
        logger.info("[orchestrator] executing step: %s", step_def.step_id)
        
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
            return self._execute_container_step(deployment, step_def, step_config, step_results, step_execution)
        
        else:
            raise ValueError(f"Unknown step type: {step_def.step_type}")
    
    def _execute_volume_step(self, deployment, step_def, step_config) -> Dict[str, Any]:
        """Execute volume creation step (simplified for MVP)."""
        logger.info("[orchestrator] creating volume: %s", step_config['spec_template']['volume_name'])
        
        # For MVP: Just return success
        # In production: Create actual volume via Runtime Agent
        
        result = {
            "volume_name": step_config["spec_template"]["volume_name"],
            "status": "created"
        }
        
        logger.info("[orchestrator] volume created: %s", result)
        
        return result
    
    def _execute_database_step(self, deployment, step_def, step_config) -> Dict[str, Any]:
        """Execute database provisioning step on the shared MySQL host."""
        spec = step_config["spec_template"]
        
        logger.info("[orchestrator] provisioning database: %s", spec["db_name"])

        db_details = self._mysql_provisioner.create_database(spec["db_name"])
        result = {
            "db_type": spec["db_type"],
            "db_name": db_details["db_name"],
            "db_user": spec["db_user"],
            "db_password": spec.get("db_password") or self._get_resolved_wordpress_db_password(deployment),
            "db_host": db_details["db_host"],
            "db_port": db_details["db_port"],
            "status": "ready",
        }

        self._domain_service.update_deployment_metadata(
            deployment.deployment_id,
            {
                "database": {
                    **{key: value for key, value in result.items() if key != "db_password"},
                    "provisioned_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        
        logger.info(
            "[orchestrator] database provisioned: %s",
            {key: value for key, value in result.items() if key != "db_password"},
        )
        
        return result
    
    def _execute_container_step(
        self,
        deployment,
        step_def,
        step_config,
        step_results: Dict[str, Dict[str, Any]],
        step_execution: DeploymentStepExecution,
    ) -> Dict[str, Any]:
        """
        Execute container deployment step.
        
        Creates execution and tracks deployed resource.
        """
        spec = dict(step_config["spec_template"])
        spec["ports"] = self._normalize_ports(spec.get("ports", {}))
        spec["env"] = dict(spec.get("env", {}))
        spec["labels"] = {
            **dict(spec.get("labels", {})),
            "application_id": str(deployment.application_id),
            "deployment_id": str(deployment.deployment_id),
        }
        self._inject_database_env(spec, step_results)
        step_config["spec_template"] = spec
        self._persist_resolved_step_config(deployment, step_config)
        
        logger.info("[orchestrator] deploying container: %s", spec['name'])
        
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
        
        logger.info("[orchestrator] selected node: %s", node.node_name)
        
        # Create execution
        execution = Execution(
            execution_id=uuid4(),
            tenant_id=deployment.tenant_id,
            application_id=deployment.application_id,
            deployment_id=deployment.deployment_id,
            step_execution_id=step_execution.step_execution_id,
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
        step_execution.execution_id = execution.execution_id
        step_execution.result = {"execution_id": str(execution.execution_id), "status": "queued"}
        self._step_repo.update(step_execution)
        
        logger.info("[orchestrator] created execution %s", execution.execution_id)
        
        from execution_engine.domain.models import DeployedResource, ResourceType, HealthStatus
        
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
        
        self._resource_repo.create(deployed_resource)
        
        logger.info("[orchestrator] tracked deployed resource %s", deployed_resource.resource_id)
        
        # Return result
        result = {
            'execution_id': str(execution.execution_id),
            'resource_id': str(deployed_resource.resource_id),
            'node_id': str(node.node_id),
            'node_name': node.node_name,
            'container_name': spec["name"],
            'status': "queued",
        }
        
        logger.info("[orchestrator] container deployment queued: %s", result)
        
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
            execution = self._execution_service.get_execution(execution_id)
            
            if not execution:
                raise RuntimeError(f"Execution {execution_id} not found")
            
            # Check if completed
            if execution.state == ExecutionState.COMPLETED:
                logger.info("[orchestrator] execution %s completed successfully", execution_id)
                
                result = {
                    "execution_id": str(execution.execution_id),
                    "status": "completed",
                    "deployment_result": execution.deployment_result or {},
                }
                
                return result
            
            # Check if failed
            if execution.state == ExecutionState.FAILED:
                error_msg = execution.error_message or "Unknown error"
                logger.info("[orchestrator] execution %s failed: %s", execution_id, error_msg)
                raise RuntimeError(f"Execution failed: {error_msg}")
            
            # Check timeout
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > timeout_seconds:
                raise RuntimeError(f"Execution timeout after {timeout_seconds}s (current state: {execution.state.value})")
            
            # Log progress
            if elapsed % 10 == 0:  # Log every 10 seconds
                logger.info(
                    "[orchestrator] execution %s still running (state: %s, elapsed: %ss)",
                    execution_id,
                    execution.state.value,
                    int(elapsed),
                )
            
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

    def _inject_database_env(
        self,
        spec: Dict[str, Any],
        step_results: Dict[str, Dict[str, Any]],
    ) -> None:
        """Inject provisioned database details into WordPress container env."""
        database = step_results.get("provision-database")
        if not database:
            return

        env = spec.setdefault("env", {})
        env["WORDPRESS_DB_HOST"] = f"{database['db_host']}:{database['db_port']}"
        env["WORDPRESS_DB_NAME"] = database["db_name"]
        env["WORDPRESS_DB_USER"] = database["db_user"]
        env["WORDPRESS_DB_PASSWORD"] = database["db_password"]

    def _persist_resolved_step_config(self, deployment, step_config: Dict[str, Any]) -> None:
        """Persist runtime-injected step values so execution/debug views match Docker payload."""
        for index, step in enumerate(deployment.resolved_config.get("steps", [])):
            if step.get("step_id") == step_config.get("step_id"):
                deployment.resolved_config["steps"][index] = step_config
                self._deployment_repo.update(deployment)
                return

    def _get_resolved_wordpress_db_password(self, deployment) -> str:
        """Read DB password from an older resolved WordPress container spec."""
        for step in deployment.resolved_config.get("steps", []):
            if step.get("step_id") == "deploy-wordpress":
                env = step.get("spec_template", {}).get("env", {})
                password = env.get("WORDPRESS_DB_PASSWORD")
                if password:
                    return password
        raise ValueError("WordPress database password missing from resolved deployment config")

    def _normalize_ports(self, ports: Dict[str, Any]) -> Dict[str, int]:
        """Normalize UI/template port values before sending them to the runtime agent."""
        normalized: Dict[str, int] = {}
        for container_port, host_port in ports.items():
            normalized[str(container_port)] = int(host_port)
        return normalized
