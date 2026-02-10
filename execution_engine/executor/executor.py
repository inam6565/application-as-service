# execution_engine/executor/executor.py
"""Executor - claims and executes container deployments."""

import threading
import time
from datetime import datetime
from uuid import UUID
import logging
from typing import Dict, Any

from execution_engine.executor.slots import SlotManager
from execution_engine.executor.runtime_executor import RuntimeExecutor
from execution_engine.core.models import ExecutionState
from execution_engine.core.errors import ExecutionLeaseError

logger = logging.getLogger(__name__)


class Executor:
    """
    Executor - claims executions and runs them via Runtime Agent.
    """
    
    def __init__(
        self,
        *,
        executor_id: str,
        service,
        repository,
        poll_interval: float = 2.0,
        max_slots: int = 2,
        lease_seconds: int = 30,
    ):
        self.executor_id = executor_id
        self.service = service
        self.repo = repository
        self.poll_interval = poll_interval
        self.lease_seconds = lease_seconds

        self.slots = SlotManager(max_slots)
        self._stop_event = threading.Event()
        self._thread = None

        # Runtime executor
        self.runtime_executor = RuntimeExecutor()
        
        # Track running executions: {execution_id: thread}
        self._running: Dict[UUID, threading.Thread] = {}

    def start(self):
        """Start executor main loop."""
        logger.info(f"[executor {self.executor_id}] 🚀 Starting executor")
        logger.info(f"[executor] Max slots: {self.slots.total_slots()}")
        logger.info(f"[executor] Poll interval: {self.poll_interval}s")
        logger.info(f"[executor] Lease duration: {self.lease_seconds}s")
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop executor."""
        logger.info(f"[executor {self.executor_id}] Stopping executor")
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def _run_loop(self):
        """Main execution loop."""
        while not self._stop_event.is_set():
            try:
                self._renew_running_leases()
                self._claim_and_execute()
            except Exception as e:
                logger.error(f"[executor] Error in main loop: {e}", exc_info=True)
            
            time.sleep(self.poll_interval)

    def _renew_running_leases(self):
        """Renew leases for running executions."""
        for execution_id in list(self._running.keys()):
            try:
                self.service.renew_execution_lease(
                    execution_id=execution_id,
                    worker_id=self.executor_id,
                    lease_seconds=self.lease_seconds,
                )
            except ExecutionLeaseError:
                logger.warning(f"[executor] Lost lease for {execution_id}")
                self._handle_lost_execution(execution_id)
            except Exception as e:
                logger.error(f"[executor] Error renewing lease for {execution_id}: {e}")

    def _handle_lost_execution(self, execution_id: UUID):
        """Handle lost execution lease."""
        slot = self.slots.find_slot_by_execution(execution_id)
        if slot:
            slot.release()
        self._running.pop(execution_id, None)

    def _claim_and_execute(self):
        """Claim and execute available work."""
        # Check if we have free slots
        slot = self.slots.acquire_free_slot()
        if not slot:
            return

        # Try to claim queued execution
        queued = self.repo.list_by_state(
            state=ExecutionState.QUEUED,
            limit=1,
        )

        for execution in queued:
            logger.info(f"[executor] Found queued execution: {execution.execution_id}")
            
            # Try to claim
            claimed = self.service.claim_execution(
                execution_id=execution.execution_id,
                worker_id=self.executor_id,
                lease_seconds=self.lease_seconds,
            )

            if not claimed:
                logger.info(f"[executor] Failed to claim {execution.execution_id}")
                continue

            # Start execution
            try:
                self.service.start_execution(
                    execution.execution_id,
                    worker_id=self.executor_id,
                )
            except ExecutionLeaseError as e:
                logger.error(f"[executor] Failed to start {execution.execution_id}: {e}")
                slot.release()
                return
            except Exception as e:
                logger.error(f"[executor] Error starting {execution.execution_id}: {e}")
                slot.release()
                return

            # Bind to slot
            slot.bind(execution.execution_id)
            
            # Execute in background thread
            thread = threading.Thread(
                target=self._execute_in_thread,
                args=(execution.execution_id,),
                daemon=True
            )
            thread.start()
            self._running[execution.execution_id] = thread
            
            logger.info(f"[executor] ✅ Started execution {execution.execution_id} in slot {slot.slot_id}")
            return

        # If no queued work, try recovery
        recoverable = self.repo.list_recoverable(limit=1)

        for execution in recoverable:
            logger.info(f"[executor] Found recoverable execution: {execution.execution_id}")
            
            claimed = self.service.claim_execution(
                execution_id=execution.execution_id,
                worker_id=self.executor_id,
                lease_seconds=self.lease_seconds,
            )

            if not claimed:
                continue

            slot.bind(execution.execution_id)
            
            thread = threading.Thread(
                target=self._execute_in_thread,
                args=(execution.execution_id,),
                daemon=True
            )
            thread.start()
            self._running[execution.execution_id] = thread
            
            logger.info(f"[executor] ✅ Recovered execution {execution.execution_id}")
            return

        # No work available
        slot.release()

    def _execute_in_thread(self, execution_id: UUID):
        """Execute deployment in background thread."""
        try:
            logger.info(f"[executor] [{execution_id}] Starting execution")
            
            # Get execution
            execution = self.repo.get(execution_id)
            if not execution:
                logger.error(f"[executor] [{execution_id}] Execution not found")
                return
            
            # Execute via runtime executor
            result = self.runtime_executor.execute_deployment(
                execution_id=execution_id,
                spec=execution.spec
            )
            
            logger.info(f"[executor] [{execution_id}] Deployment completed, updating result...")
            
            # Get fresh execution
            fresh_execution = self.repo.get(execution_id)
            if not fresh_execution:
                raise RuntimeError("Execution disappeared during update")
            
            # Update with deployment result
            fresh_execution.deployment_result = result
            fresh_execution.version += 1
            
            # Save the updated result
            try:
                self.repo.update(fresh_execution)
                logger.info(f"[executor] [{execution_id}] Result saved successfully")
            except Exception as update_error:
                logger.error(f"[executor] [{execution_id}] Failed to save result: {update_error}")
            
            # ✅ ADD: Update deployed resource with container ID
            self._update_deployed_resource(execution_id, result)
            
            # Complete execution
            self.service.complete_execution(
                execution_id=execution_id,
                worker_id=self.executor_id,
            )
            
            logger.info(f"[executor] [{execution_id}] ✅ Completed successfully")
            
        except Exception as e:
            logger.error(f"[executor] [{execution_id}] ❌ Failed: {e}", exc_info=True)
            
            # Fail execution
            try:
                self.service.fail_execution(
                    execution_id=execution_id,
                    worker_id=self.executor_id,
                    reason=str(e)
                )
            except Exception as fail_error:
                logger.error(f"[executor] [{execution_id}] Failed to mark as failed: {fail_error}")
        
        finally:
            # Release slot
            slot = self.slots.find_slot_by_execution(execution_id)
            if slot:
                slot.release()
            
            # Remove from running
            self._running.pop(execution_id, None)


    # execution_engine/executor/executor.py

    def _update_deployed_resource(self, execution_id: UUID, deployment_result: Dict[str, Any]):
        """
        Update deployed resource with container details.
        
        Args:
            execution_id: Execution ID
            deployment_result: Deployment result from runtime agent
        """
        try:
            from execution_engine.infrastructure.postgres.database import engine
            from sqlalchemy import text
            import json
            
            container_id = deployment_result.get('container_id')
            if not container_id:
                logger.warning(f"[executor] No container_id in deployment result")
                return
            
            logger.info(f"[executor] Updating deployed resource for execution {execution_id}")
            logger.info(f"[executor] Container ID: {container_id}")
            
            # Find resource by execution_id in spec
            with engine.connect() as conn:
                # ✅ STEP 1: Get the current spec
                result = conn.execute(
                    text("""
                        SELECT resource_id, spec
                        FROM deployed_resources
                        WHERE spec->>'execution_id' = :execution_id
                    """),
                    {'execution_id': str(execution_id)}
                )
                
                row = result.fetchone()
                
                if not row:
                    logger.warning(f"[executor] No deployed resource found for execution {execution_id}")
                    return
                
                resource_id = row[0]
                current_spec = row[1]
                
                logger.info(f"[executor] Found resource {resource_id}")
                
                # ✅ STEP 2: Merge deployment_result into spec (in Python, not SQL)
                if isinstance(current_spec, str):
                    current_spec = json.loads(current_spec)
                
                current_spec['deployment_result'] = deployment_result
                
                # ✅ STEP 3: Update with merged spec (NO jsonb_set!)
                conn.execute(
                    text("""
                        UPDATE deployed_resources
                        SET external_id = :container_id,
                            status = 'running',
                            health_status = 'STARTING',
                            spec = :spec_json
                        WHERE resource_id = :resource_id
                    """),
                    {
                        'container_id': container_id,
                        'spec_json': json.dumps(current_spec),
                        'resource_id': resource_id
                    }
                )
                
                conn.commit()
                logger.info(f"[executor] ✅ Updated deployed resource {resource_id} with container {container_id}")
                logger.info(f"[executor] Status: running, Health: STARTING")
            
        except Exception as e:
            logger.error(f"[executor] ❌ Error updating deployed resource: {e}", exc_info=True)