# test_health_checker.py
"""Test health checker functionality."""

from uuid import uuid4
import time
import requests

from execution_engine.container import (
    domain_service,
    node_manager_service,
)
from execution_engine.orchestrator.deployment_orchestrator import DeploymentOrchestrator
from execution_engine.infrastructure.postgres.domain_repository import DeploymentRepository
from execution_engine.domain.models import DeploymentStatus
from execution_engine.infrastructure.postgres.database import engine
from sqlalchemy import text


def main():
    print("=" * 80)
    print("🧪 TESTING HEALTH CHECKER")
    print("=" * 80)
    print()
    
    # ============================================
    # Prerequisites Check
    # ============================================
    print("📋 Checking prerequisites...")
    
    nodes = node_manager_service.list_available_nodes()
    if not nodes:
        print("❌ No nodes available!")
        return
    
    print(f"✅ Found {len(nodes)} node(s)")
    print()
    
    # ============================================
    # Deploy Nginx (Has HTTP Health Check)
    # ============================================
    print("🚀 Deploying Nginx with health check...")
    
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
        name="Health Check Test Nginx",
        description="Testing health checker",
        user_inputs=user_inputs,
    )
    
    print(f"✅ Created application: {application.application_id}")
    
    deployment = domain_service.create_deployment(application.application_id)
    print(f"✅ Created deployment: {deployment.deployment_id}")
    
    # Start deployment
    from execution_engine.container import execution_service
    
    deployment_repo = DeploymentRepository()
    orchestrator = DeploymentOrchestrator(
        domain_service=domain_service,
        execution_service=execution_service,
        node_manager_service=node_manager_service,
        deployment_repo=deployment_repo,
    )
    
    orchestrator.start_deployment(deployment.deployment_id)
    print(f"✅ Deployment started")
    print()
    
    # ============================================
    # Wait for Deployment to Complete
    # ============================================
    print("⏳ Waiting for deployment to complete...")
    
    for i in range(60):
        deployment = domain_service.get_deployment(deployment.deployment_id)
        
        print(f"[{i:2d}s] Deployment: {deployment.status.value}")
        
        if deployment.status == DeploymentStatus.RUNNING:
            print()
            print("✅ Deployment completed!")
            break
        
        if deployment.status == DeploymentStatus.FAILED:
            print()
            print(f"❌ Deployment failed: {deployment.error_message}")
            return
        
        time.sleep(1)
    else:
        print("⏱️  Timeout waiting for deployment")
        return
    
    print()
    
    # ============================================
    # Check Deployed Resources
    # ============================================
    print("📦 Checking deployed resources...")
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT 
                    resource_id,
                    name,
                    external_id,
                    status,
                    health_status,
                    consecutive_health_failures
                FROM deployed_resources
                WHERE deployment_id = :deployment_id
            """),
            {"deployment_id": deployment.deployment_id}
        )
        
        resources = result.fetchall()
    
    if not resources:
        print("❌ No deployed resources found!")
        return
    
    for row in resources:
        print(f"Resource: {row[1]}")
        print(f"  ID: {row[0]}")
        print(f"  Container ID: {row[2]}")
        print(f"  Status: {row[3]}")
        print(f"  Health: {row[4]}")
        print(f"  Failures: {row[5]}")
    
    print()
    
    # ============================================
    # Monitor Health Checks
    # ============================================
    print("🏥 Monitoring health checks (30 seconds)...")
    print("   Health checker should check every 10s")
    print()
    
    for i in range(30):
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT 
                        name,
                        health_status,
                        consecutive_health_failures,
                        last_health_check_at
                    FROM deployed_resources
                    WHERE deployment_id = :deployment_id
                """),
                {"deployment_id": deployment.deployment_id}
            )
            
            row = result.fetchone()
            if row:
                last_check = row[3].strftime("%H:%M:%S") if row[3] else "Never"
                print(f"[{i:2d}s] Health: {row[1]:12} | Failures: {row[2]} | Last check: {last_check}")
        
        time.sleep(1)
    
    print()
    
    # ============================================
    # Test HTTP Health Check Manually
    # ============================================
    print("🔍 Testing HTTP health check manually...")
    
    try:
        response = requests.get("http://localhost:8080/", timeout=5)
        if response.status_code == 200:
            print("✅ HTTP health check: PASS (200 OK)")
        else:
            print(f"⚠️  HTTP health check: Status {response.status_code}")
    except Exception as e:
        print(f"❌ HTTP health check: FAIL ({e})")
    
    print()
    
    # ============================================
    # Simulate Unhealthy Container
    # ============================================
    print("=" * 80)
    print("🔧 SIMULATING UNHEALTHY CONTAINER")
    print("=" * 80)
    print()
    print("To test auto-restart:")
    print("1. Stop the nginx container manually:")
    print(f"   docker stop <container_id>")
    print()
    print("2. Watch health checker logs - it should:")
    print("   - Detect 3 consecutive failures")
    print("   - Mark container UNHEALTHY")
    print("   - Wait 60 seconds")
    print("   - Restart the container")
    print()
    
    # Get container ID
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT external_id
                FROM deployed_resources
                WHERE deployment_id = :deployment_id
                  AND resource_type = 'CONTAINER'
            """),
            {"deployment_id": deployment.deployment_id}
        )
        
        row = result.fetchone()
        if row:
            container_id = row[0]
            print(f"Container ID: {container_id}")
            print(f"Stop command: docker stop {container_id}")
            print()


if __name__ == "__main__":
    main()