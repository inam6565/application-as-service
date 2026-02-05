"""Verify integration between all services."""

from uuid import uuid4

from execution_engine.container import (
    domain_service,
    node_manager_service,
    execution_service,
)


def main():
    print("🔍 Verifying Service Integration...")
    print()
    
    # ============================================
    # Test 1: Domain Service
    # ============================================
    print("1️⃣  Testing Domain Service")
    
    templates = domain_service.list_templates()
    assert len(templates) > 0, "No templates found"
    print(f"   ✅ Found {len(templates)} templates")
    
    template = domain_service.get_template("wordpress")
    assert template is not None, "WordPress template not found"
    print(f"   ✅ Retrieved WordPress template")
    
    # ============================================
    # Test 2: Node Manager Service
    # ============================================
    print("2️⃣  Testing Node Manager Service")
    
    available_nodes = node_manager_service.list_available_nodes()
    print(f"   ✅ Found {len(available_nodes)} available nodes")
    
    if available_nodes:
        node = available_nodes[0]
        print(f"   ✅ Node: {node.node_name} ({node.internal_ip})")
        print(f"      Capacity: {node.available_cpu} CPU, {node.available_memory}MB RAM")
    
    # ============================================
    # Test 3: Execution Service
    # ============================================
    print("3️⃣  Testing Execution Service")
    
    from execution_engine.core.models import Execution, ExecutionState
    
    test_execution = Execution(
        execution_id=uuid4(),
        tenant_id=uuid4(),
        application_id=uuid4(),
        runtime_type="docker",
        spec={"test": "data"},
    )
    
    execution_service.register_execution(test_execution)
    print(f"   ✅ Created test execution: {test_execution.execution_id}")
    
    execution_service.queue_execution(test_execution.execution_id)
    print(f"   ✅ Queued test execution")
    
    retrieved = execution_service._repo.get(test_execution.execution_id)
    assert retrieved.state == ExecutionState.QUEUED
    print(f"   ✅ Verified execution state: {retrieved.state.value}")
    
    # ============================================
    # Test 4: Cross-Service Integration
    # ============================================
    print("4️⃣  Testing Cross-Service Integration")
    
    # Create application
    tenant_id = uuid4()
    app = domain_service.create_application(
        tenant_id=tenant_id,
        template_id="wordpress",
        name="Integration Test App",
        user_inputs={
            "domain": "test.example.com",
            "db_host": "localhost",
            "db_password": "test123",
            "exposed_port": 9000,
        }
    )
    print(f"   ✅ Created application: {app.application_id}")
    
    # Create deployment
    deployment = domain_service.create_deployment(app.application_id)
    print(f"   ✅ Created deployment: {deployment.deployment_id}")
    
    # Verify resolved config
    assert "steps" in deployment.resolved_config
    assert len(deployment.resolved_config["steps"]) > 0
    print(f"   ✅ Resolved config has {len(deployment.resolved_config['steps'])} steps")
    
    print()
    print("🎉 ALL INTEGRATION TESTS PASSED!")
    print()


if __name__ == "__main__":
    main()