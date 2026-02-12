# execution_engine/executor/retry_service.py
"""Retry service for handling execution retries with exponential backoff."""

import time
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import List

from execution_engine.core.models import Execution, ExecutionState
from execution_engine.core.repository import ExecutionRepository

logger = logging.getLogger(__name__)


class RetryService:
    """
    Retry service for automatically retrying failed executions.
    
    Features:
    - Exponential backoff (10s, 30s, 90s)
    - Max 3 retries
    - Transient error detection
    - Scheduled retry execution
    """
    
    def __init__(self, repository: ExecutionRepository):
        self._repo = repository
    
    def find_retryable_executions(self, limit: int = 100) -> List[Execution]:
        """
        Find executions that can be retried.
        
        Criteria:
        - State = FAILED
        - retry_count < max_retries
        - Error is transient
        - Retry delay has elapsed
        
        Args:
            limit: Maximum number of executions to return
            
        Returns:
            List of retryable executions
        """
        # Get all failed executions
        failed = self._repo.list_by_state(
            state=ExecutionState.FAILED,
            limit=limit * 2,  # Get more to filter
        )
        
        retryable = []
        now = datetime.now(timezone.utc)
        
        for execution in failed:
            # Check if can retry
            if not execution.can_retry():
                continue
            
            # Check if error is transient
            if not execution.is_transient_error():
                logger.debug(
                    f"[retry] {execution.execution_id} - permanent error, won't retry"
                )
                continue
            
            # Check if retry delay has elapsed
            if execution.finished_at:
                delay = execution.calculate_retry_delay()
                retry_time = execution.finished_at + timedelta(seconds=delay)
                
                if now < retry_time:
                    remaining = (retry_time - now).total_seconds()
                    logger.debug(
                        f"[retry] {execution.execution_id} - retry in {int(remaining)}s"
                    )
                    continue
            
            retryable.append(execution)
            
            if len(retryable) >= limit:
                break
        
        return retryable
    
    def retry_execution(self, execution: Execution) -> None:
        """
        Retry a failed execution.
        
        Args:
            execution: Execution to retry
        """
        logger.info(
            f"[retry] Retrying execution {execution.execution_id} "
            f"(attempt {execution.retry_count + 1}/{execution.max_retries})"
        )
        
        # Increment retry count
        execution.retry_count += 1
        
        # Reset to CREATED state (will be queued next)
        execution.state = ExecutionState.CREATED
        execution.finished_at = None
        execution.error_message = None
        execution.lease_owner = None
        execution.lease_expires_at = None
        execution.version += 1
        
        # Update in repository
        self._repo.update(execution)
        
        logger.info(
            f"[retry] ✅ Execution {execution.execution_id} reset to CREATED "
            f"(retry {execution.retry_count}/{execution.max_retries})"
        )
    
    def process_retries(self) -> int:
        """
        Process all retryable executions.
        
        Returns:
            Number of executions retried
        """
        retryable = self.find_retryable_executions()
        
        if not retryable:
            return 0
        
        logger.info(f"[retry] Found {len(retryable)} executions to retry")
        
        retried = 0
        for execution in retryable:
            try:
                self.retry_execution(execution)
                retried += 1
            except Exception as e:
                logger.error(
                    f"[retry] Failed to retry {execution.execution_id}: {e}",
                    exc_info=True
                )
        
        logger.info(f"[retry] ✅ Retried {retried} execution(s)")
        
        return retried