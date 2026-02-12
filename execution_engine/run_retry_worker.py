# execution_engine/run_retry_worker.py
"""Retry worker - automatically retries failed executions."""

import logging
import time
import signal
import sys

from execution_engine.container import execution_repository, execution_service
from execution_engine.executor.retry_service import RetryService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class RetryWorker:
    """
    Retry worker - polls for failed executions and retries them.
    
    Separate process that:
    - Checks every 5 seconds for failed executions
    - Retries transient failures with exponential backoff
    - Respects max retry limits
    """
    
    def __init__(self, poll_interval: int = 5):
        """
        Initialize retry worker.
        
        Args:
            poll_interval: How often to check for retries (seconds)
        """
        self.poll_interval = poll_interval
        self._stop_requested = False
        
        self.retry_service = RetryService(repository=execution_repository)
        
        logger.info("Retry Worker initialized")
        logger.info(f"Poll interval: {poll_interval}s")
    
    def start(self):
        """Start the retry worker loop."""
        logger.info("=" * 80)
        logger.info("🔄 RETRY WORKER STARTED")
        logger.info("=" * 80)
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info("Max retries: 3")
        logger.info("Backoff delays: 10s, 30s, 90s")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 80)
        logger.info("")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Main loop
        while not self._stop_requested:
            try:
                self._retry_cycle()
            except Exception as e:
                logger.error(f"Error in retry cycle: {e}", exc_info=True)
            
            # Wait before next cycle
            if not self._stop_requested:
                time.sleep(self.poll_interval)
        
        logger.info("Retry Worker stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, stopping...")
        self._stop_requested = True
    
    def _retry_cycle(self):
        """Single retry processing cycle."""
        retried = self.retry_service.process_retries()
        
        if retried > 0:
            logger.info(f"[retry] Processed {retried} retry/retries")
            
            # Queue retried executions
            from execution_engine.core.models import ExecutionState
            
            created = execution_repository.list_by_state(
                state=ExecutionState.CREATED,
                limit=100
            )
            
            for execution in created:
                if execution.retry_count > 0:  # Only queue retries
                    try:
                        execution_service.queue_execution(execution.execution_id)
                        logger.info(
                            f"[retry] ✅ Queued retry {execution.execution_id} "
                            f"(attempt {execution.retry_count + 1})"
                        )
                    except Exception as e:
                        logger.error(
                            f"[retry] Failed to queue {execution.execution_id}: {e}"
                        )


def main():
    """Main entry point."""
    logger.info("Starting Retry Worker (Development Mode)")
    
    worker = RetryWorker(poll_interval=5)
    
    try:
        worker.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()