# test_retry_logic.py
"""Test retry logic with simulated transient failures."""

import time
from uuid import uuid4
from datetime import datetime, timezone

from execution_engine.container import (
    execution_service,
    execution_repository,
    node_manager_service,
)
from execution_engine.core.models import Execution, ExecutionState
from execution_engine.node_manager.models import InfrastructureNode, NodeType


def main():
    print("=" * 80)
    print("🔄 RETRY LOGIC TEST")
    print("=" * 80)
    print()
    
    # Register node
    print("1️⃣  Registering node...")
    node = InfrastructureNode(
        node_id=uuid4(),
        node_name="test-node-retry",
        node_type=NodeType.APP_NODE,
        internal_ip="10.0.1.50",
        public_ip="203.0.113.50",
        runtime_agent_url="http://10.0.1.50:9000",  # Fake URL = connection error
        supported_runtimes=["docker"],
        total_cpu=4.0,
        total_memory=8192,
        total_storage=100,
        available_cpu=4.0,
        available_memory=8192,
        available_storage=100,
        max_containers=20,
    )
    
    try:
        node_manager_service.register_node(node)
        print(f"✅ Node registered: {node.node_name}")
    except Exception as e:
        print(f"⚠️  Node already exists: {e}")
    
    print()
    
    # Create execution with invalid agent URL (will fail with connection error)
    print("2️⃣  Creating execution with unreachable node...")
    execution = Execution(
        execution_id=uuid4(),
        tenant_id=uuid4(),
        application_id=uuid4(),
        runtime_type="docker",
        spec={
            "node_id": str(node.node_id),
            "agent_url": "http://10.0.1.50:9000",  # Unreachable
            "container_spec": {
                "image": "nginx:alpine",
                "name": "test-retry-container",
                "ports": {"80/tcp": 9090},
            }
        },
        max_retries=3,
    )
    
    execution_service.register_execution(execution)
    execution_service.queue_execution(execution.execution_id)
    
    print(f"✅ Execution created: {execution.execution_id}")
    print(f"   Max retries: {execution.max_retries}")
    print()
    
    # Wait for executor to pick it up and fail
    print("3️⃣  Waiting for executor to fail (connection error)...")
    print("   Expected: Executor will fail with 'Connection refused' error")
    print()
    
    time.sleep(10)  # Give executor time to fail
    
    # Check execution state
    failed_exec = execution_repository.get(execution.execution_id)
    
    if not failed_exec:
        print("❌ Execution not found!")
        return
    
    print(f"📊 Execution status:")
    print(f"   State: {failed_exec.state.value}")
    print(f"   Error: {failed_exec.error_message}")
    print(f"   Retry count: {failed_exec.retry_count}/{failed_exec.max_retries}")
    print()
    
    if failed_exec.state != ExecutionState.FAILED:
        print("⚠️  Execution not failed yet, wait longer...")
        return
    
    # Check if error is transient
    print("4️⃣  Checking error type...")
    is_transient = failed_exec.is_transient_error()
    can_retry = failed_exec.can_retry()
    delay = failed_exec.calculate_retry_delay()
    
    print(f"   Transient error: {is_transient}")
    print(f"   Can retry: {can_retry}")
    print(f"   Retry delay: {delay}s")
    print()
    
    if not is_transient:
        print("❌ Error is not transient, should not retry")
        return
    
    if not can_retry:
        print("❌ Cannot retry (max retries reached or wrong state)")
        return
    
    print("✅ Error is transient and retryable!")
    print()
    
    # Now test retry worker
    print("5️⃣  Testing retry worker...")
    print(f"   Waiting {delay}s for retry delay to elapse...")
    
    time.sleep(delay + 2)  # Wait for delay + buffer
    
    print("   Retry worker should now pick up the execution...")
    print()
    
    # Check if retry worker processes it
    from execution_engine.executor.retry_service import RetryService
    
    retry_service = RetryService(execution_repository)
    
    # Find retryable
    retryable = retry_service.find_retryable_executions()
    
    print(f"📊 Retryable executions found: {len(retryable)}")
    
    if retryable:
        for exec in retryable:
            print(f"   - {exec.execution_id} (retry {exec.retry_count}/{exec.max_retries})")
    
    print()
    
    # Manually trigger retry
    if retryable:
        print("6️⃣  Manually triggering retry...")
        retry_service.process_retries()
        print()
        
        # Check new state
        retried_exec = execution_repository.get(execution.execution_id)
        
        print(f"📊 After retry:")
        print(f"   State: {retried_exec.state.value}")
        print(f"   Retry count: {retried_exec.retry_count}/{retried_exec.max_retries}")
        print(f"   Finished at: {retried_exec.finished_at}")
        print()
        
        if retried_exec.state == ExecutionState.CREATED:
            print("✅ Execution reset to CREATED - will be queued for retry")
        else:
            print(f"⚠️  Unexpected state: {retried_exec.state.value}")
    
    print()
    print("=" * 80)
    print("✅ RETRY LOGIC TEST COMPLETE")
    print("=" * 80)
    print()
    print("What to observe:")
    print("1. Executor fails with connection error (transient)")
    print("2. Retry worker detects after 10s delay")
    print("3. Execution reset to CREATED")
    print("4. Execution queued again (retry attempt 2)")
    print("5. Will fail again (same connection error)")
    print("6. After 30s delay, retry again (attempt 3)")
    print("7. After 90s delay, final retry (attempt 4)")
    print("8. Max retries reached - no more retries")
    print()


if __name__ == "__main__":
    main()