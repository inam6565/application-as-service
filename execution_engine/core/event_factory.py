#execution_engine\core\event_factory.py
from datetime import datetime, timezone
from execution_engine.core.events_model import ExecutionEvent, EventType

def build_event(
    *,
    execution_id: str,
    event_type: EventType,
    source: str,
    metadata: dict | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        event_id=ExecutionEvent.new_id(),
        execution_id=execution_id,
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc),
        source=source,
        metadata=metadata or {},
        version=1,
    )
