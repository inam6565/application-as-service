#tests\test_integration.py

"""Integration test - full workflow."""

import pytest
from uuid import uuid4
import time

from execution_engine.core.models import Execution, ExecutionState


class TestIntegrationWorkflow:
    """Test complete execution workflow."""
    
    def test_complete_execution_lifecycle(self, service):
        """Test: register -> queue -> claim -> start -> complete."""
        
        # 1. Create execution
        execution = Execution(
            execution_id=uuid4(),
            tenant_id=uuid4(),
            application_id=uuid4(),
            runtime_type="docker",
            spec={"image": "nginx:alpine"}
        )
        
        # 2. Register
        service.register_execution(execution)
        
        # 3. Queue
        service.queue_execution(execution.execution_id)
        
        # 4. Claim
        claimed = service.claim_execution(
            execution.execution_id,
            worker_id="worker-1",
            lease_seconds=30
        )
        assert claimed is True
        
        # 5. Start
        service.start_execution(execution.execution_id, "worker-1")
        
        # 6. Renew lease
        service.renew_execution_lease(
            execution.execution_id,
            worker_id="worker-1",
            lease_seconds=30
        )
        
        # 7. Complete
        service.complete_execution(
            execution.execution_id,
            worker_id="worker-1"
        )
        
        # Verify final state
        final_execution = service._require_execution(execution.execution_id)
        assert final_execution.state == ExecutionState.COMPLETED
        assert final_execution.lease_owner is None
    
    def test_lease_expiration_recovery(self, service, repository):
        """Test recovering from expired lease."""
        
        # Create and start execution with short lease
        execution = Execution(
            execution_id=uuid4(),
            tenant_id=uuid4(),
            application_id=uuid4(),
            runtime_type="docker",
            spec={"image": "nginx"}
        )
        
        service.register_execution(execution)
        service.queue_execution(execution.execution_id)
        service.claim_execution(execution.execution_id, "worker-1", lease_seconds=1)
        service.start_execution(execution.execution_id, "worker-1")
        
        # Wait for lease to expire
        time.sleep(2)
        
        # Another worker should be able to claim
        recoverable = repository.list_recoverable()
        
        assert len(recoverable) == 1
        assert recoverable[0].execution_id == execution.execution_id