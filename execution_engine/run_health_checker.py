# execution_engine/run_health_checker.py
"""Run health checker service (development)."""

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution_engine.health_checker.checker import HealthChecker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    logger.info("Starting Health Checker (Development Mode)")
    
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