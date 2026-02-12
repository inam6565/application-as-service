# Sprint 4, Day 5: Retry Logic - Implementation Guide

## Overview

Implemented exponential backoff retry logic for handling transient failures in execution engine.

## Files Created/Modified

### New Files
1. `execution_engine/executor/retry_service.py` - Core retry logic
2. `execution_engine/run_retry_worker.py` - Retry worker service
3. `test_retry_logic.py` - Test script

### Modified Files (Manual Steps Required)
1. `execution_engine/core/models.py` - Add methods to Execution class
2. `execution_engine/executor/__init__.py` - Export RetryService

## Implementation Steps

### Step 1: Update Execution Model

**File:** `execution_engine/core/models.py`

**Location:** In the `Execution` class, after the existing `can_retry()` method

**Add these two methods:**

```python
def is_transient_error(self) -> bool:
    """
    Determine if error is transient (retryable).
    
    Transient errors:
    - Network errors (connection, timeout)
    - Node unavailable
    - Resource temporarily unavailable
    
    Permanent errors:
    - Validation errors
    - Business logic errors
    - Invalid configuration
    """
    if not self.error_message:
        return False
    
    error_lower = self.error_message.lower()
    
    # Transient error patterns
    transient_patterns = [
        'connection',
        'timeout',
        'unavailable',
        'temporary',
        'network',
        'refused',
        'unreachable',
        'no route',
        'connection reset',
        'broken pipe',
        'node not found',
        'node offline',
    ]
    
    # Permanent error patterns
    permanent_patterns = [
        'validation',
        'invalid',
        'not found',  # Resource not found (not node)
        'unauthorized',
        'forbidden',
        'bad request',
        'malformed',
        'missing required',
    ]
    
    # Check permanent first (takes precedence)
    for pattern in permanent_patterns:
        if pattern in error_lower:
            return False
    
    # Check transient
    for pattern in transient_patterns:
        if pattern in error_lower:
            return True
    
    # Default: don't retry unknown errors
    return False

def calculate_retry_delay(self) -> int:
    """
    Calculate retry delay in seconds using exponential backoff.
    
    Returns:
        Delay in seconds: 10s, 30s, 90s
    """
    delays = [10, 30, 90]
    
    if self.retry_count >= len(delays):
        return delays[-1]
    
    return delays[self.retry_count]
```

### Step 2: Copy Files to Project

```bash
# From /home/claude directory
cp retry_service.py execution_engine/executor/retry_service.py
cp run_retry_worker.py execution_engine/run_retry_worker.py
cp test_retry_logic.py test_retry_logic.py
```

### Step 3: Update __init__.py

**File:** `execution_engine/executor/__init__.py`

**Add:**
```python
from .retry_service import RetryService

__all__ = ["RetryService"]
```

## How It Works

### Architecture

```
Failed Execution
      ↓
Retry Worker polls every 5s
      ↓
Check: can_retry() and is_transient_error()
      ↓
Wait for exponential backoff delay
      ↓
Reset execution to CREATED state
      ↓
Queue execution (retry attempt N)
      ↓
Executor picks up and tries again
```

### Retry Delays

| Attempt | Delay  | Total Time |
|---------|--------|------------|
| 1       | 0s     | 0s         |
| 2       | 10s    | 10s        |
| 3       | 30s    | 40s        |
| 4       | 90s    | 130s       |
| Stop    | -      | -          |

### Error Classification

**Transient (Retry):**
- Connection refused
- Timeout
- Network unreachable
- Node offline
- Temporary unavailable

**Permanent (Don't Retry):**
- Validation error
- Invalid configuration
- Not found (resource)
- Unauthorized
- Forbidden

## Testing

### Terminal Setup

**Terminal 1: Executor**
```bash
python -m execution_engine.run_executor
```

**Terminal 2: Status Updater**
```bash
python -m execution_engine.run_status_updater
```

**Terminal 3: Health Checker**
```bash
python -m execution_engine.run_health_checker
```

**Terminal 4: Retry Worker**
```bash
python -m execution_engine.run_retry_worker
```

**Terminal 5: Test**
```bash
python test_retry_logic.py
```

### Expected Test Flow

1. **t=0s:** Execution created with unreachable node
2. **t=2s:** Executor picks up, tries to deploy, fails with "Connection refused"
3. **t=10s:** Retry worker detects (after 10s delay)
4. **t=10s:** Execution reset to CREATED, retry_count=1
5. **t=12s:** Executor picks up retry attempt 2, fails again
6. **t=42s:** Retry worker detects (after 30s delay)
7. **t=42s:** Execution reset, retry_count=2
8. **t=44s:** Executor tries attempt 3, fails
9. **t=134s:** Retry worker detects (after 90s delay)
10. **t=134s:** Execution reset, retry_count=3
11. **t=136s:** Executor tries final attempt 4, fails
12. **t=136s:** Max retries reached, no more retries

### Verification Queries

```sql
-- Check execution retry status
SELECT 
    execution_id,
    state,
    retry_count,
    max_retries,
    error_message,
    finished_at
FROM executions
WHERE retry_count > 0
ORDER BY created_at DESC;

-- Check retry timeline
SELECT 
    execution_id,
    state,
    retry_count,
    finished_at,
    EXTRACT(EPOCH FROM (NOW() - finished_at)) AS seconds_since_failure
FROM executions
WHERE state = 'FAILED'
AND retry_count < max_retries
ORDER BY finished_at DESC;
```

## Configuration

**Retry Worker:**
- Poll interval: 5 seconds
- Max retries: 3 (per execution)
- Backoff delays: [10s, 30s, 90s]

**To Change:**
Edit `execution_engine/run_retry_worker.py`:
```python
worker = RetryWorker(poll_interval=5)  # Change interval here
```

Edit `execution_engine/core/models.py`:
```python
# In Execution class
max_retries: int = 3  # Change default here

# In calculate_retry_delay()
delays = [10, 30, 90]  # Change backoff schedule here
```

## Monitoring

**Logs to Watch:**
- `[retry] Found N executions to retry` - Retry worker found work
- `[retry] Retrying execution ... (attempt N/3)` - Starting retry
- `[retry] ✅ Execution ... reset to CREATED` - Retry queued
- `[executor] Found queued execution` - Executor picking up retry
- `[executor] ❌ Failed: ...` - Retry attempt failed

**Success Indicators:**
- retry_count increments after each failure
- Delays between retries match exponential backoff
- Final attempt stops at max_retries

**Failure Indicators:**
- retry_count not incrementing (retry worker not running)
- Immediate retries (delay not working)
- Permanent errors being retried (error classification wrong)

## Production Considerations

### Monitoring
Add metrics:
- Total retries per hour
- Success rate by retry attempt
- Average time to success
- Executions exhausting retries

### Tuning
Consider:
- Increase max_retries for critical deployments
- Shorter delays for urgent retries
- Circuit breaker if node permanently offline
- Exponential backoff with jitter (avoid thundering herd)

### Alerts
Set up alerts for:
- High retry rate (may indicate systemic issue)
- Executions exhausting retries
- Long retry delays (>5 minutes)

## Troubleshooting

### Retries Not Happening
**Check:**
1. Is retry worker running? (`ps aux | grep retry_worker`)
2. Are errors transient? (check `is_transient_error()` output)
3. Has delay elapsed? (check `finished_at` timestamp)
4. Is retry_count < max_retries?

### Too Many Retries
**Check:**
1. Are permanent errors being classified as transient?
2. Update `permanent_patterns` in `is_transient_error()`

### Wrong Delay
**Check:**
1. Verify `calculate_retry_delay()` logic
2. Check `finished_at` timestamp is set correctly

## Next Steps (Sprint 4, Day 6-7)

After retry logic is working:
1. ✅ Retry logic complete
2. ⏳ Set up Database VM
3. ⏳ Implement Database Manager service
4. ⏳ Add database provisioning step type
5. ⏳ Test MySQL database creation

---

**Status:** Implementation complete, ready for testing
**Dependencies:** Requires all 4 services running (executor, status updater, health checker, retry worker)