# execution_engine/health_checker/checker.py
"""
Health Checker Service - Monitors container health and restarts unhealthy ones.

Runs as a separate process and checks health every 10 seconds.
"""

import time
import logging
import signal
import sys
import requests
import socket
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from execution_engine.domain.models import HealthStatus, ResourceType
from execution_engine.infrastructure.postgres.database import engine
from sqlalchemy import text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Background service that monitors container health.
    
    Architecture:
    - Runs as separate process (not thread)
    - Checks every 10 seconds
    - Marks UNHEALTHY after 3 consecutive failures
    - Auto-restarts after 60 second delay
    """
    
    def __init__(
        self,
        check_interval: int = 10,
        failure_threshold: int = 3,
        restart_delay: int = 60
    ):
        """
        Initialize health checker.
        
        Args:
            check_interval: How often to check health (seconds)
            failure_threshold: Consecutive failures before UNHEALTHY
            restart_delay: Delay before restarting unhealthy container (seconds)
        """
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        self.restart_delay = restart_delay
        self._stop_requested = False
        
        logger.info("Health Checker initialized")
        logger.info(f"Check interval: {check_interval}s")
        logger.info(f"Failure threshold: {failure_threshold}")
        logger.info(f"Restart delay: {restart_delay}s")
    
    def start(self):
        """Start the health checker loop."""
        logger.info("=" * 80)
        logger.info("🏥 HEALTH CHECKER STARTED")
        logger.info("=" * 80)
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Failure threshold: {self.failure_threshold}")
        logger.info(f"Restart delay: {self.restart_delay}s")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 80)
        logger.info("")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Main loop
        while not self._stop_requested:
            try:
                self._check_cycle()
            except Exception as e:
                logger.error(f"Error in check cycle: {e}", exc_info=True)
            
            # Wait before next cycle
            if not self._stop_requested:
                time.sleep(self.check_interval)
        
        logger.info("Health Checker stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, stopping...")
        self._stop_requested = True
    
    def _check_cycle(self):
        """
        Single health check cycle.
        
        1. Find all deployed containers
        2. For each container, perform health check
        3. Update health status
        4. Restart if unhealthy
        """
        # Find containers to check
        containers = self._find_containers_to_check()
        
        if not containers:
            logger.debug("No containers to check")
            return
        
        logger.info(f"Checking health of {len(containers)} container(s)")
        
        for container in containers:
            try:
                self._check_container_health(container)
            except Exception as e:
                logger.error(
                    f"Error checking container {container['resource_id']}: {e}"
                )
    
    def _find_containers_to_check(self) -> List[Dict[str, Any]]:
        """
        Find deployed containers that need health checking.
        
        Returns:
            List of container records
        """
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    dr.resource_id,
                    dr.deployment_id,
                    dr.external_id,
                    dr.name,
                    dr.spec,
                    dr.node_id,
                    dr.health_status,
                    dr.consecutive_health_failures,
                    dr.last_health_check_at,
                    n.runtime_agent_url
                FROM deployed_resources dr
                JOIN infrastructure_nodes n ON dr.node_id = n.node_id
                WHERE dr.resource_type = 'CONTAINER'
                AND dr.status = 'running'
                AND dr.external_id != 'pending'  -- ✅ ADD: Exclude pending
                ORDER BY dr.last_health_check_at ASC NULLS FIRST
            """))
            
            containers = []
            for row in result:
                # ✅ FIX: Parse spec if it's a string
                spec = row[4]
                if isinstance(spec, str):
                    import json
                    spec = json.loads(spec)
                
                containers.append({
                    'resource_id': row[0],
                    'deployment_id': row[1],
                    'external_id': row[2],
                    'name': row[3],
                    'spec': spec,
                    'node_id': row[5],
                    'health_status': row[6],
                    'consecutive_failures': row[7],
                    'last_check_at': row[8],
                    'runtime_agent_url': row[9],
                })
            
            return containers
    
    def _check_container_health(self, container: Dict[str, Any]):
        """
        Check health of a single container.
        
        Args:
            container: Container record
        """
        resource_id = container['resource_id']
        container_id = container['external_id']
        spec = container['spec']
        
        logger.debug(f"[{resource_id}] Checking health: {container['name']}")
        
        # Get health check configuration from spec
        health_check = spec.get('health_check')
        
        if not health_check:
            # No health check configured, assume healthy
            self._update_health_status(
                resource_id=resource_id,
                is_healthy=True,
                current_failures=container['consecutive_failures']
            )
            return
        
        # Perform health check based on type
        check_type = health_check.get('type', 'http')
        
        try:
            if check_type == 'http':
                is_healthy = self._check_http_health(container, health_check)
            elif check_type == 'tcp':
                is_healthy = self._check_tcp_health(container, health_check)
            elif check_type == 'command':
                is_healthy = self._check_command_health(container, health_check)
            else:
                logger.warning(f"Unknown health check type: {check_type}")
                is_healthy = True  # Default to healthy
            
            # Update status
            self._update_health_status(
                resource_id=resource_id,
                is_healthy=is_healthy,
                current_failures=container['consecutive_failures']
            )
            
            # Check if we need to restart
            if not is_healthy:
                self._handle_unhealthy_container(container)
            
        except Exception as e:
            logger.error(f"[{resource_id}] Health check failed: {e}")
            # Treat exceptions as failures
            self._update_health_status(
                resource_id=resource_id,
                is_healthy=False,
                current_failures=container['consecutive_failures']
            )
    
# execution_engine/health_checker/checker.py

    def _check_http_health(
        self,
        container: Dict[str, Any],
        health_check: Dict[str, Any]
    ) -> bool:
        """
        Perform HTTP health check.
        
        Args:
            container: Container record
            health_check: Health check configuration
            
        Returns:
            True if healthy, False otherwise
        """
        # ✅ FIX: Get deployment result correctly
        spec = container['spec']
        deployment_result = spec.get('deployment_result', {})
        
        # ✅ FIX: Port mapping structure is different
        # deployment_result has: {"ports": {"80/tcp": 8080}}
        ports = deployment_result.get('ports', {})
        
        # Get the port from health check config
        internal_port = health_check.get('port', 80)
        
        # ✅ FIX: Try different port key formats
        port_key = f"{internal_port}/tcp"
        
        if port_key in ports:
            host_port = ports[port_key]
        else:
            # Try as integer key
            if internal_port in ports:
                host_port = ports[internal_port]
            else:
                logger.warning(
                    f"[{container['resource_id']}] Port {internal_port} not found in mappings: {ports}"
                )
                return False
        
        path = health_check.get('path', '/')
        
        # Construct URL
        url = f"http://localhost:{host_port}{path}"
        
        timeout = health_check.get('timeout_seconds', 5)
        
        try:
            response = requests.get(url, timeout=timeout)
            is_healthy = 200 <= response.status_code < 400
            
            if is_healthy:
                logger.info(f"[{container['resource_id']}] ✅ HTTP check OK: {url} ({response.status_code})")
            else:
                logger.warning(
                    f"[{container['resource_id']}] ❌ HTTP check FAIL: "
                    f"{url} returned {response.status_code}"
                )
            
            return is_healthy
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"[{container['resource_id']}] ❌ HTTP check error: {e}")
            return False
                
    def _check_tcp_health(
        self,
        container: Dict[str, Any],
        health_check: Dict[str, Any]
    ) -> bool:
        """
        Perform TCP health check.
        
        Args:
            container: Container record
            health_check: Health check configuration
            
        Returns:
            True if healthy, False otherwise
        """
        # Get port mapping
        deployment_result = container['spec'].get('deployment_result', {})
        ports = deployment_result.get('ports', {})
        
        internal_port = health_check.get('port', 80)
        port_key = f"{internal_port}/tcp"
        
        if port_key not in ports:
            logger.warning(f"Port {internal_port} not found in port mappings")
            return False
        
        host_port = ports[port_key]
        timeout = health_check.get('timeout_seconds', 5)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(('localhost', host_port))
            sock.close()
            
            is_healthy = result == 0
            
            if is_healthy:
                logger.debug(
                    f"[{container['resource_id']}] TCP check OK: "
                    f"localhost:{host_port}"
                )
            else:
                logger.warning(
                    f"[{container['resource_id']}] TCP check FAIL: "
                    f"localhost:{host_port}"
                )
            
            return is_healthy
            
        except Exception as e:
            logger.warning(f"[{container['resource_id']}] TCP check error: {e}")
            return False
    
    def _check_command_health(
        self,
        container: Dict[str, Any],
        health_check: Dict[str, Any]
    ) -> bool:
        """
        Perform command-based health check (exec in container).
        
        Args:
            container: Container record
            health_check: Health check configuration
            
        Returns:
            True if healthy, False otherwise
        """
        # This requires calling Runtime Agent to exec command
        runtime_agent_url = container['runtime_agent_url']
        container_id = container['external_id']
        command = health_check.get('command')
        
        if not command:
            logger.warning("No command specified for command health check")
            return False
        
        try:
            # Call Runtime Agent to exec command
            response = requests.post(
                f"{runtime_agent_url}/containers/{container_id}/exec",
                json={"command": command},
                timeout=health_check.get('timeout_seconds', 5)
            )
            
            if response.status_code == 200:
                result = response.json()
                exit_code = result.get('exit_code', 1)
                
                is_healthy = exit_code == 0
                
                if is_healthy:
                    logger.debug(
                        f"[{container['resource_id']}] Command check OK"
                    )
                else:
                    logger.warning(
                        f"[{container['resource_id']}] Command check FAIL: "
                        f"exit code {exit_code}"
                    )
                
                return is_healthy
            else:
                logger.warning(
                    f"[{container['resource_id']}] Command check error: "
                    f"HTTP {response.status_code}"
                )
                return False
                
        except Exception as e:
            logger.warning(f"[{container['resource_id']}] Command check error: {e}")
            return False
    
    def _update_health_status(
        self,
        resource_id: UUID,
        is_healthy: bool,
        current_failures: int
    ):
        """
        Update container health status in database.
        
        Args:
            resource_id: Resource ID
            is_healthy: Whether check passed
            current_failures: Current consecutive failure count
        """
        now = datetime.now(timezone.utc)
        
        if is_healthy:
            # Reset failure count
            new_failures = 0
            new_status = HealthStatus.HEALTHY
        else:
            # Increment failure count
            new_failures = current_failures + 1
            
            if new_failures >= self.failure_threshold:
                new_status = HealthStatus.UNHEALTHY
                logger.warning(
                    f"[{resource_id}] Marked UNHEALTHY after "
                    f"{new_failures} consecutive failures"
                )
            else:
                new_status = HealthStatus.HEALTHY  # Still healthy, but tracking failures
        
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE deployed_resources
                    SET health_status = :status,
                        consecutive_health_failures = :failures,
                        last_health_check_at = :checked_at
                    WHERE resource_id = :resource_id
                """),
                {
                    'status': new_status.value,
                    'failures': new_failures,
                    'checked_at': now,
                    'resource_id': resource_id
                }
            )
            conn.commit()
    
    def _handle_unhealthy_container(self, container: Dict[str, Any]):
        """
        Handle an unhealthy container.
        
        Args:
            container: Container record
        """
        resource_id = container['resource_id']
        failures = container['consecutive_failures']
        
        # Only restart if we just crossed threshold
        if failures + 1 == self.failure_threshold:
            logger.warning(
                f"[{resource_id}] Container unhealthy, scheduling restart "
                f"in {self.restart_delay}s"
            )
            
            # Wait before restarting (avoid restart loops)
            time.sleep(self.restart_delay)
            
            # Restart container via Runtime Agent
            self._restart_container(container)
    
    def _restart_container(self, container: Dict[str, Any]):
        """
        Restart a container via Runtime Agent.
        
        Args:
            container: Container record
        """
        resource_id = container['resource_id']
        container_id = container['external_id']
        runtime_agent_url = container['runtime_agent_url']
        
        logger.info(f"[{resource_id}] Restarting container {container_id}")
        
        try:
            # Call Runtime Agent to restart
            response = requests.post(
                f"{runtime_agent_url}/containers/{container_id}/restart",
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"[{resource_id}] ✅ Container restarted successfully")
                
                # Reset health status to STARTING
                with engine.connect() as conn:
                    conn.execute(
                        text("""
                            UPDATE deployed_resources
                            SET health_status = :status,
                                consecutive_health_failures = 0
                            WHERE resource_id = :resource_id
                        """),
                        {
                            'status': HealthStatus.STARTING.value,
                            'resource_id': resource_id
                        }
                    )
                    conn.commit()
            else:
                logger.error(
                    f"[{resource_id}] Failed to restart container: "
                    f"HTTP {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"[{resource_id}] Error restarting container: {e}")


def main():
    """Main entry point."""
    checker = HealthChecker(
        check_interval=10,
        failure_threshold=3,
        restart_delay=60
    )
    
    try:
        checker.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()