# test_nginx_deployment.py
"""End-to-end test for Nginx deployment."""

from uuid import uuid4
import time
import requests

from execution_engine.container import (
    domain_service,
    node_manager_service,
    execution_service,
)
from execution_engine.orchestrator.deployment_orchestrator import DeploymentOrchestrator
from execution_engine.infrastructure.postgres.domain_repository import DeploymentRepository


def main():
    print("=" * 80)
    print("🚀 NGINX DEPLOYMENT END-TO-END TEST")
    print("=" * 80)
    print()
    
    # ============================================
    # STEP 1: Verify Node is Registered
    # ============================================
    print("📦 STEP 1: Check Infrastructure Nodes")
    print("-" * 80)
    
    available_nodes = node_manager_service.list_available_nodes()
    
    if not available_nodes:
        print("❌ No nodes available!")
        print("Please register a node first:")
        print("  POST http://localhost:8000/nodes/register")
        print("  {")
        print('    "node_name": "compute-node-01",')
        print('    "node_type": "APP_NODE",')
        print('    "internal_ip": "10.0.1.10",')
        print('    "runtime_agent_url": "http://localhost:9000",')
        print('    "total_cpu": 4.0,')
        print('    "total_memory": 8192,')
        print('    "total_storage": 100')
        print("  }")
        return
    
    node = available_nodes[0]
    print(f"✅ Found node: {node.node_name}")
    print(f"   Node ID: {node.node_id}")
    print(f"   Agent URL: {node.runtime_agent_url}")
    print(f"   Capacity: {node.available_cpu} CPU, {node.available_memory}MB RAM")
    print()
    
    # Test agent health
    try:
        response = requests.get(f"{node.runtime_agent_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Runtime agent is healthy")
        else:
            print(f"⚠️  Runtime agent returned: {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot connect to runtime agent: {e}")
        return
    
    print()
    
    # ============================================
    # STEP 2: List Available Templates
    # ============================================
    print("📋 STEP 2: List Available Templates")
    print("-" * 80)
    
    templates = domain_service.list_templates()
    print(f"Found {len(templates)} templates:")
    for template in templates:
        print(f"  - {template.template_id}: {template.name} v{template.version}")
        print(f"    Category: {template.category}")
        print(f"    Steps: {len(template.deployment_steps)}")
        print()
    
    # Check for nginx template
    nginx_template = domain_service.get_template("nginx")
    if not nginx_template:
        print("❌ Nginx template not found!")
        print("Run: python seed_templates.py")
        return
    
    print("✅ Nginx template found")
    print()
    
    # ============================================
    # STEP 3: Create Application
    # ============================================
    print("🎨 STEP 3: Create Nginx Application")
    print("-" * 80)
    
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
        name="My Nginx Server",
        description="Simple static web server",
        user_inputs=user_inputs,
    )
    
    print(f"✅ Created application: {application.name}")
    print(f"   Application ID: {application.application_id}")
    print(f"   Template: {application.template_id} v{application.template_version}")
    print(f"   Status: {application.status.value}")
    print()
    
    # ============================================
    # STEP 4: Create Deployment
    # ============================================
    print("🚢 STEP 4: Create Deployment")
    print("-" * 80)
    
    deployment = domain_service.create_deployment(application.application_id)
    
    print(f"✅ Created deployment: {deployment.deployment_id}")
    print(f"   Status: {deployment.status.value}")
    print(f"   Total steps: {deployment.total_steps}")
    print()
    
    # ============================================
    # STEP 5: Start Deployment
    # ============================================
    print("⚙️  STEP 5: Start Deployment Orchestration")
    print("-" * 80)
    
    deployment_repo = DeploymentRepository()
    
    orchestrator = DeploymentOrchestrator(
        domain_service=domain_service,
        execution_service=execution_service,
        node_manager_service=node_manager_service,
        deployment_repo=deployment_repo,
    )
    
    try:
        orchestrator.start_deployment(deployment.deployment_id)
        print(f"✅ Deployment orchestration completed")
    except Exception as e:
        print(f"❌ Deployment orchestration failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # ============================================
    # STEP 6: Wait for Executor to Process
    # ============================================
    print("⏳ STEP 6: Waiting for Executor to Process...")
    print("-" * 80)
    print("NOTE: Make sure executor is running!")
    print("Run: python -m execution_engine.run_executor")
    print()
    
    # Wait a bit for executor to pick up
    print("Waiting 10 seconds for execution to complete...")
    time.sleep(10)
    
    # ============================================
    # STEP 7: Check Final Status
    # ============================================
    print("📊 STEP 7: Check Final Status")
    print("-" * 80)
    
    # Check deployment status
    final_deployment = domain_service.get_deployment(deployment.deployment_id)
    print(f"Deployment Status: {final_deployment.status.value}")
    
    # List queued/completed executions
    from execution_engine.core.models import ExecutionState
    
    queued = execution_service._repo.list_by_state(ExecutionState.QUEUED)
    started = execution_service._repo.list_by_state(ExecutionState.STARTED)
    completed = execution_service._repo.list_by_state(ExecutionState.COMPLETED)
    failed = execution_service._repo.list_by_state(ExecutionState.FAILED)
    
    print(f"Queued Executions: {len(queued)}")
    print(f"Started Executions: {len(started)}")
    print(f"Completed Executions: {len(completed)}")
    print(f"Failed Executions: {len(failed)}")
    print()
    
    if completed:
        print("✅ Execution completed!")
        execution = completed[0]
        print(f"   Execution ID: {execution.execution_id}")
        if execution.deployment_result:
            print(f"   Container ID: {execution.deployment_result.get('container_id', 'N/A')[:12]}")
            print(f"   Container Name: {execution.deployment_result.get('container_name', 'N/A')}")
            print(f"   Status: {execution.deployment_result.get('status', 'N/A')}")
            print(f"   Ports: {execution.deployment_result.get('ports', {})}")
        print()
        print("🎉 SUCCESS! Try accessing:")
        print("   http://localhost:8080")
    
    elif failed:
        print("❌ Execution failed!")
        execution = failed[0]
        print(f"   Error: {execution.error_message}")
    
    elif queued or started:
        print("⏳ Execution still in progress...")
        print("   Wait a bit longer and check again")
    
    print()
    print("=" * 80)
    print("✅ END-TO-END TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()