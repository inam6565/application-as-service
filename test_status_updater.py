# test_status_updater.py
"""Test status updater functionality."""

from uuid import uuid4
import time

from execution_engine.container import (
    domain_service,
    node_manager_service,
    execution_service,        # ✅ ADD THIS
    execution_repository,     # ✅ ADD THIS
)
from execution_engine.orchestrator.deployment_orchestrator import DeploymentOrchestrator
from execution_engine.infrastructure.postgres.domain_repository import DeploymentRepository
from execution_engine.core.models import ExecutionState
from execution_engine.domain.models import DeploymentStatus, ApplicationStatus


def main():
    print("=" * 80)
    print("🧪 TESTING ASYNC STATUS UPDATER")
    print("=" * 80)
    print()
    
    # ============================================
    # Prerequisites Check
    # ============================================
    print("📋 Checking prerequisites...")
    
    # Check node registered
    nodes = node_manager_service.list_available_nodes()
    if not nodes:
        print("❌ No nodes available! Please register a node first.")
        return
    
    print(f"✅ Found {len(nodes)} node(s)")
    print()
    
    # ============================================
    # Create Application & Deployment
    # ============================================
    print("🎨 Creating application...")
    
    tenant_id = uuid4()
    user_inputs = {
        "nginx_version": "alpine",
        "exposed_port": 8080,
        "cpu_limit": "0.5",
        "memory_limit": "512Mi",
    }
    
    application = domain_service.create_application(
        tenant_id=tenant_id,
        template_id="nginx",
        name="Async Test Nginx",
        description="Testing async status updates",
        user_inputs=user_inputs,
    )
    
    print(f"✅ Created application: {application.application_id}")
    print(f"   Initial status: {application.status.value}")
    print()
    
    # ============================================
    # Start Deployment (Non-Blocking)
    # ============================================
    print("🚢 Starting deployment (async)...")
    
    deployment = domain_service.create_deployment(application.application_id)
    print(f"✅ Created deployment: {deployment.deployment_id}")
    print(f"   Initial status: {deployment.status.value}")
    print()
    
    deployment_repo = DeploymentRepository()
    orchestrator = DeploymentOrchestrator(
        domain_service=domain_service,
        execution_service=execution_service,
        node_manager_service=node_manager_service,
        deployment_repo=deployment_repo,
    )
    
    print("⚡ Starting orchestrator (returns immediately)...")
    start_time = time.time()
    
    try:
        orchestrator.start_deployment(deployment.deployment_id)
        orchestration_time = time.time() - start_time
        
        print(f"✅ Orchestrator returned in {orchestration_time:.2f}s")
        print()
    except Exception as e:
        print(f"❌ Orchestration failed: {e}")
        return
    
    # ============================================
    # Check Status Updates
    # ============================================
    print("🔍 Monitoring status updates...")
    print("   (Status updater should update these every 5s)")
    print()
    
    for i in range(30):  # Monitor for 30 seconds
        # Refresh from DB
        deployment = domain_service.get_deployment(deployment.deployment_id)
        application = domain_service.get_application(application.application_id)
        
        # Get execution state
        from execution_engine.container import execution_repository
        executions = []
        from execution_engine.infrastructure.postgres.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT execution_id FROM executions WHERE deployment_id = :dep_id"),
                {"dep_id": deployment.deployment_id}
            )
            for row in result:
                exec_obj = execution_repository.get(row[0])
                if exec_obj:
                    executions.append(exec_obj)
        
        # Print status
        exec_states = [e.state.value for e in executions]
        
        print(f"[{i:2d}s] Deployment: {deployment.status.value:12} | "
              f"Application: {application.status.value:12} | "
              f"Executions: {exec_states}")
        
        # Check if done
        if deployment.status == DeploymentStatus.RUNNING:
            print()
            print("🎉 SUCCESS! Deployment reached RUNNING state")
            print(f"   Total time: {i}s")
            break
        
        if deployment.status == DeploymentStatus.FAILED:
            print()
            print("❌ Deployment FAILED")
            print(f"   Error: {deployment.error_message}")
            break
        
        time.sleep(1)
    
    else:
        print()
        print("⏱️  Timeout waiting for deployment to complete")
    
    # ============================================
    # Final Status
    # ============================================
    print()
    print("=" * 80)
    print("📊 FINAL STATUS")
    print("=" * 80)
    
    deployment = domain_service.get_deployment(deployment.deployment_id)
    application = domain_service.get_application(application.application_id)
    
    print(f"Deployment: {deployment.status.value}")
    print(f"Application: {application.status.value}")
    
    if executions:
        print(f"Executions: {len(executions)}")
        for execution in executions:
            print(f"  - {execution.execution_id}: {execution.state.value}")
            if execution.error_message:
                print(f"    Error: {execution.error_message}")
    
    print()
    
    # Verify consistency
    if deployment.status == DeploymentStatus.RUNNING:
        if application.status == ApplicationStatus.RUNNING:
            print("✅ PASS: All statuses consistent!")
        else:
            print(f"❌ FAIL: Application status is {application.status.value}, expected RUNNING")
    elif deployment.status == DeploymentStatus.FAILED:
        if application.status == ApplicationStatus.FAILED:
            print("✅ PASS: Failure statuses consistent")
        else:
            print(f"❌ FAIL: Application status is {application.status.value}, expected FAILED")


if __name__ == "__main__":
    main()