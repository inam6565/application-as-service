# test_unhealthy_container.py
"""Test unhealthy container detection and restart."""

import time
import subprocess
from sqlalchemy import text

from execution_engine.infrastructure.postgres.database import engine


def main():
    print("=" * 80)
    print("🧪 UNHEALTHY CONTAINER TEST")
    print("=" * 80)
    print()
    
    # ============================================
    # Find Running Container
    # ============================================
    print("🔍 Finding deployed container...")
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT 
                    resource_id,
                    name,
                    external_id,
                    health_status
                FROM deployed_resources
                WHERE resource_type = 'CONTAINER'
                  AND status = 'running'
                ORDER BY created_at DESC
                LIMIT 1
            """)
        )
        
        row = result.fetchone()
    
    if not row:
        print("❌ No running containers found!")
        print("   Run test_health_checker.py first to deploy a container")
        return
    
    resource_id, name, container_id, health_status = row
    
    print(f"Found container: {name}")
    print(f"  Resource ID: {resource_id}")
    print(f"  Container ID: {container_id}")
    print(f"  Current health: {health_status}")
    print()
    
    # ============================================
    # Stop Container to Simulate Failure
    # ============================================
    print("🛑 Stopping container to simulate failure...")
    
    try:
        subprocess.run(
            ["docker", "stop", container_id],
            check=True,
            capture_output=True
        )
        print(f"✅ Container stopped: {container_id}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to stop container: {e}")
        return
    
    print()
    
    # ============================================
    # Monitor Health Checks
    # ============================================
    print("🏥 Monitoring health checks...")
    print("   Health checker runs every 10s")
    print("   Should mark UNHEALTHY after 3 failures (30s)")
    print("   Should restart after 60s delay")
    print()
    
    start_time = time.time()
    restart_detected = False
    
    for i in range(120):  # Monitor for 2 minutes
        elapsed = int(time.time() - start_time)
        
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT 
                        health_status,
                        consecutive_health_failures,
                        last_health_check_at,
                        status
                    FROM deployed_resources
                    WHERE resource_id = :resource_id
                """),
                {"resource_id": resource_id}
            )
            
            row = result.fetchone()
        
        if not row:
            print("❌ Resource disappeared!")
            break
        
        health, failures, last_check, status = row
        last_check_str = last_check.strftime("%H:%M:%S") if last_check else "Never"
        
        print(f"[{elapsed:3d}s] Health: {health:12} | Failures: {failures} | Status: {status:10} | Last: {last_check_str}")
        
        # Check if restarted
        if status == 'running' and failures == 0 and not restart_detected:
            print()
            print("🎉 Container restarted successfully!")
            restart_detected = True
            
            # Give it a few more seconds
            time.sleep(5)
            break
        
        time.sleep(1)
    
    print()
    
    # ============================================
    # Final Status
    # ============================================
    print("=" * 80)
    print("📊 FINAL STATUS")
    print("=" * 80)
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT 
                    health_status,
                    consecutive_health_failures,
                    status
                FROM deployed_resources
                WHERE resource_id = :resource_id
            """),
            {"resource_id": resource_id}
        )
        
        row = result.fetchone()
    
    if row:
        print(f"Health Status: {row[0]}")
        print(f"Consecutive Failures: {row[1]}")
        print(f"Container Status: {row[2]}")
        print()
        
        if row[0] == 'HEALTHY' or row[0] == 'STARTING':
            print("✅ TEST PASSED: Container auto-restarted successfully!")
        else:
            print("❌ TEST FAILED: Container still unhealthy")
    else:
        print("❌ Resource not found")


if __name__ == "__main__":
    main()