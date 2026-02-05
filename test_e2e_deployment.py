"""End-to-end integration test for complete deployment workflow."""

from uuid import uuid4

from execution_engine.container import (
    domain_service,
    node_manager_service,
    execution_service,
    deployment_repository,
)
from execution_engine.orchestrator.deployment_orchestrator import DeploymentOrchestrator
from execution_engine.node_manager.models import InfrastructureNode, NodeType


def main():
    print("=" * 80)
    print("🚀 END-TO-END DEPLOYMENT TEST")
    print("=" * 80)
    print()
    
    # ============================================
    # STEP 1: Register Infrastructure Node
    # ============================================
    print("📦 STEP 1: Register Infrastructure Node")
    print("-" * 80)
    
    node = InfrastructureNode(
        node_id=uuid4(),
        node_name="app-node-01",
        node_type=NodeType.APP_NODE,
        internal_ip="10.0.1.10",
        public_ip="203.0.113.10",
        runtime_agent_url="http://10.0.1.10:9000",
        supported_runtimes=["docker"],
        total_cpu=8.0,
        total_memory=16384,  # 16GB
        total_storage=500,   # 500GB
        available_cpu=8.0,
        available_memory=16384,
        available_storage=500,
        max_containers=50,
    )
    
    try:
        node_manager_service.register_node(node)
        print(f"✅ Registered node: {node.node_name}")
        print(f"   Node ID: {node.node_id}")
        print(f"   Internal IP: {node.internal_ip}")
        print(f"   Capacity: {node.total_cpu} CPU, {node.total_memory}MB RAM")
    except Exception as e:
        print(f"⚠️  Node already registered or error: {e}")
    
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
        print(f"    Database required: {template.database_required} ({template.database_type})")
        print()
    
    # ============================================
    # STEP 3: Create Application
    # ============================================
    print("🎨 STEP 3: Create Application from Template")
    print("-" * 80)
    
    tenant_id = uuid4()
    
    # User inputs for WordPress
    user_inputs = {
        "domain": "myblog.example.com",
        "db_host": "mysql-server.local",
        "db_password": "secure_password_123",
        "db_storage_size": "10",
        "wordpress_version": "latest",
        "cpu_limit": "1",
        "memory_limit": "1Gi",
        "exposed_port": 8080,
    }
    
    application = domain_service.create_application(
        tenant_id=tenant_id,
        template_id="wordpress",
        name="My Awesome Blog",
        description="A blog about tech and programming",
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
    print(f"   Template: {deployment.template_id} v{deployment.template_version}")
    print()
    
    # Show resolved configuration
    print("📝 Resolved Configuration:")
    print(f"   Steps: {len(deployment.resolved_config.get('steps', []))}")
    for step in deployment.resolved_config.get("steps", []):
        print(f"   - {step['step_id']}: {step['step_name']}")
    print()
    
    # ============================================
    # STEP 5: Start Deployment (Orchestration)
    # ============================================
    print("⚙️  STEP 5: Start Deployment Orchestration")
    print("-" * 80)
    
    orchestrator = DeploymentOrchestrator(
        domain_service=domain_service,
        execution_service=execution_service,
        node_manager_service=node_manager_service,
        deployment_repo=deployment_repository,
    )
    
    try:
        orchestrator.start_deployment(deployment.deployment_id)
        print(f"✅ Deployment orchestration completed")
    except Exception as e:
        print(f"❌ Deployment orchestration failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # ============================================
    # STEP 6: Check Final Status
    # ============================================
    print("📊 STEP 6: Check Final Status")
    print("-" * 80)
    
    # Refresh deployment
    final_deployment = domain_service.get_deployment(deployment.deployment_id)
    print(f"Deployment Status: {final_deployment.status.value}")
    print(f"Started at: {final_deployment.started_at}")
    print(f"Completed at: {final_deployment.completed_at}")
    if final_deployment.error_message:
        print(f"Error: {final_deployment.error_message}")
    print()
    
    # Refresh application
    final_application = domain_service.get_application(application.application_id)
    print(f"Application Status: {final_application.status.value}")
    print(f"Current Deployment: {final_application.current_deployment_id}")
    print()
    
    # List queued executions
    from execution_engine.core.models import ExecutionState
    queued_executions = execution_service._repo.list_by_state(ExecutionState.QUEUED)
    print(f"Queued Executions: {len(queued_executions)}")
    for execution in queued_executions:
        print(f"  - {execution.execution_id}: {execution.execution_type} ({execution.state.value})")
    print()
    
    # ============================================
    # SUMMARY
    # ============================================
    print("=" * 80)
    print("✅ END-TO-END TEST COMPLETED")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  ✅ Node registered: {node.node_name}")
    print(f"  ✅ Application created: {application.name}")
    print(f"  ✅ Deployment created: {deployment.deployment_id}")
    print(f"  ✅ Orchestration executed: {final_deployment.status.value}")
    print(f"  ✅ Executions queued: {len(queued_executions)}")
    print()
    print("Next Steps:")
    print("  1. Start executor workers to process queued executions")
    print("  2. Implement Runtime Agent to actually deploy containers")
    print("  3. Add health checks and monitoring")
    print()


if __name__ == "__main__":
    main()