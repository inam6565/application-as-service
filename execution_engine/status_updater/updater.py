# execution_engine/status_updater/updater.py
"""
Status Updater Service - Background process that monitors deployments
and updates their status based on execution states.

This runs as a separate process and polls the database every 5 seconds.
"""

import time
import logging
import signal
import sys
import threading
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from execution_engine.domain.models import DeploymentStatus, ApplicationStatus, StepStatus
from execution_engine.core.models import ExecutionState
from execution_engine.container import (
    domain_service,
    execution_service,
    deployment_repository,
    step_execution_repository,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StatusUpdater:
    """
    Background service that monitors deployments and updates their status.
    
    Architecture:
    - Runs as separate process (not thread)
    - Polls database every 5 seconds
    - No in-memory state (crash-safe)
    - Single source of truth: PostgreSQL
    """
    
    def __init__(self, poll_interval: int = 5):
        """
        Initialize status updater.
        
        Args:
            poll_interval: How often to poll database (seconds)
        """
        self.poll_interval = poll_interval
        self._stop_requested = False
        
        logger.info("Status Updater initialized")
        logger.info(f"Poll interval: {poll_interval}s")
    
    def start(self):
        """Start the status updater loop."""
        logger.info("=" * 80)
        logger.info("🔄 STATUS UPDATER STARTED")
        logger.info("=" * 80)
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 80)
        logger.info("")
        
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Main loop
        while not self._stop_requested:
            try:
                self._update_cycle()
            except Exception as e:
                logger.error(f"Error in update cycle: {e}", exc_info=True)
            
            # Wait before next cycle
            if not self._stop_requested:
                time.sleep(self.poll_interval)
        
        logger.info("Status Updater stopped")

    def stop(self):
        """Request graceful shutdown."""
        self._stop_requested = True
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, stopping...")
        self._stop_requested = True
    
    def _update_cycle(self):
        """
        Single update cycle.
        
        1. Find all deployments in DEPLOYING state
        2. For each deployment, check execution states
        3. Update deployment status accordingly
        4. Update application status
        """
        # Find deployments that need checking
        deployments_to_check = self._find_active_deployments()
        
        if not deployments_to_check:
            logger.debug("No active deployments to check")
            return
        
        logger.info(f"Checking {len(deployments_to_check)} active deployment(s)")
        
        for deployment_id in deployments_to_check:
            try:
                self._update_deployment(deployment_id)
            except Exception as e:
                logger.error(f"Error updating deployment {deployment_id}: {e}")
    
    def _find_active_deployments(self) -> List[UUID]:
        """
        Find deployments that are actively deploying.
        
        Returns:
            List of deployment IDs in DEPLOYING state
        """
        deployments = domain_service.list_deployments_by_status(
            DeploymentStatus.DEPLOYING,
            limit=100,
        )
        return [deployment.deployment_id for deployment in deployments]
    
    def _update_deployment(self, deployment_id: UUID):
        """
        Update a single deployment's status.
        
        Logic:
        1. Get all executions for this deployment
        2. Check their states
        3. If all COMPLETED → deployment RUNNING
        4. If any FAILED → deployment FAILED
        5. Otherwise → still DEPLOYING
        
        Args:
            deployment_id: Deployment to update
        """
        logger.info(f"[{deployment_id}] Checking deployment status")
        
        # Get deployment
        deployment = domain_service.get_deployment(deployment_id)
        if not deployment:
            logger.warning(f"[{deployment_id}] Deployment not found")
            return
        
        # Get all executions for this deployment
        executions = self._get_deployment_executions(deployment_id)
        
        if not executions:
            logger.debug(f"[{deployment_id}] No executions yet")
            return
        
        # Count execution states
        total = len(executions)
        completed = sum(1 for e in executions if e.state == ExecutionState.COMPLETED)
        failed = sum(1 for e in executions if e.state == ExecutionState.FAILED)
        
        logger.info(
            f"[{deployment_id}] Executions: {completed}/{total} completed, "
            f"{failed}/{total} failed"
        )
        
        # Determine new status
        new_status = None
        
        if failed > 0:
            # Any failure means deployment failed
            new_status = DeploymentStatus.FAILED
            logger.info(f"[{deployment_id}] → FAILED (has failed executions)")
        
        elif completed == total:
            # All completed means success
            new_status = DeploymentStatus.RUNNING
            logger.info(f"[{deployment_id}] → RUNNING (all executions completed)")
        
        else:
            # Still in progress
            logger.debug(f"[{deployment_id}] Still deploying ({completed}/{total})")
        
        # Update deployment status if changed
        if new_status and new_status != deployment.status:
            self._sync_step_statuses(deployment_id, executions)
            self._apply_deployment_status(deployment, new_status, executions)
        else:
            self._sync_step_statuses(deployment_id, executions)
    
    def _get_deployment_executions(self, deployment_id: UUID) -> List:
        """
        Get all executions for a deployment.
        
        Args:
            deployment_id: Deployment ID
            
        Returns:
            List of executions
        """
        return execution_service.list_deployment_executions(deployment_id, limit=100)
    
    def _apply_deployment_status(self, deployment, new_status: DeploymentStatus, executions: List):
        """
        Apply new status to deployment and update application.
        
        Args:
            deployment: Deployment object
            new_status: New status to apply
            executions: List of executions
        """
        deployment_id = deployment.deployment_id
        
        logger.info(f"[{deployment_id}] Updating status: {deployment.status.value} → {new_status.value}")
        
        # Update deployment
        deployment.status = new_status
        
        if new_status == DeploymentStatus.RUNNING:
            deployment.completed_at = datetime.now(timezone.utc)
            deployment.current_step_index = deployment.total_steps
        
        elif new_status == DeploymentStatus.FAILED:
            deployment.completed_at = datetime.now(timezone.utc)
            # Collect error messages
            errors = [e.error_message for e in executions if e.error_message]
            deployment.error_message = "; ".join(errors) if errors else "Deployment failed"
        
        deployment_repository.update(deployment)
        
        logger.info(f"[{deployment_id}] ✅ Deployment status updated")
        
        # Update application status
        self._update_application_status(deployment, new_status)
    
    def _update_application_status(self, deployment, deployment_status: DeploymentStatus):
        """
        Update application status based on deployment status.
        
        Args:
            deployment: Deployment object
            deployment_status: New deployment status
        """
        application_id = deployment.application_id
        application = domain_service.get_application(application_id)
        
        if not application:
            logger.warning(f"Application {application_id} not found")
            return
        
        # Map deployment status to application status
        if deployment_status == DeploymentStatus.RUNNING:
            new_app_status = ApplicationStatus.RUNNING
        elif deployment_status == DeploymentStatus.FAILED:
            new_app_status = ApplicationStatus.FAILED
        else:
            # Other statuses don't change app status
            return
        
        # Update application
        if application.status != new_app_status:
            logger.info(
                f"[app:{application_id}] Updating status: "
                f"{application.status.value} → {new_app_status.value}"
            )
            
            domain_service.set_application_status(application_id, new_app_status)
            
            logger.info(f"[app:{application_id}] ✅ Application status updated")

    def _sync_step_statuses(self, deployment_id: UUID, executions: List) -> None:
        """Reflect async execution state onto linked deployment step records."""
        execution_by_id = {
            execution.execution_id: execution
            for execution in executions
        }
        steps = step_execution_repository.list_by_deployment(deployment_id)
        now = datetime.now(timezone.utc)

        for step in steps:
            if not step.execution_id:
                continue

            execution = execution_by_id.get(step.execution_id)
            if not execution:
                continue

            if execution.state == ExecutionState.COMPLETED and step.status != StepStatus.COMPLETED:
                step.status = StepStatus.COMPLETED
                step.result = execution.deployment_result or step.result
                step.completed_at = now
            elif execution.state == ExecutionState.FAILED and step.status != StepStatus.FAILED:
                step.status = StepStatus.FAILED
                step.error_message = execution.error_message
                step.completed_at = now
            else:
                continue

            if step.started_at:
                started_at = step.started_at.replace(tzinfo=timezone.utc) if step.started_at.tzinfo is None else step.started_at
                step.duration_seconds = (now - started_at).total_seconds()
            step_execution_repository.update(step)


def main():
    """Main entry point."""
    updater = StatusUpdater(poll_interval=5)
    
    try:
        updater.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
