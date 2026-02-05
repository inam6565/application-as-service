# execution_engine/run_executor.py
"""Run executor worker to process queued executions."""

import logging
import time
import signal
import sys

from execution_engine.container import execution_service, execution_repository
from execution_engine.executor.executor import Executor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# -------------------------
# Executor
# -------------------------

executor = Executor(
    executor_id="worker-1",
    service=execution_service,
    repository=execution_repository,
    poll_interval=2.0,  # Poll every 2 seconds
    max_slots=2,        # Handle 2 concurrent executions
    lease_seconds=30,   # Lease duration
)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    logger.info("🛑 Shutting down executor...")
    executor.stop()
    sys.exit(0)


def main():
    """Main entry point."""
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 80)
    logger.info("🚀 EXECUTION ENGINE WORKER")
    logger.info("=" * 80)
    logger.info(f"Worker ID: {executor.executor_id}")
    logger.info(f"Max Slots: {executor.slots.total_slots()}")
    logger.info(f"Poll Interval: {executor.poll_interval}s")
    logger.info(f"Lease Duration: {executor.lease_seconds}s")
    logger.info("")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 80)
    logger.info("")
    
    # Start executor
    executor.start()
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down executor...")
        executor.stop()


if __name__ == "__main__":
    main()