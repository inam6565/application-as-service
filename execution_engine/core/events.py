"""Event emitters for execution engine."""

from abc import ABC, abstractmethod
from typing import Iterable

from execution_engine.core.events_model import ExecutionEvent


ALLOWED_EVENTS = {
    "execution.registered",
    "execution.queued",
    "execution.claimed",  # NEW
    "execution.started",
    "execution.completed",
    "execution.failed",
    "execution.cancelled",
}


class EventEmitter(ABC):
    """Abstract event emitter."""
    
    @abstractmethod
    def emit(self, events: Iterable[ExecutionEvent]) -> None:
        """Emit one or more events."""
        pass


class PrintEventEmitter(EventEmitter):
    """Simple console event emitter for testing."""
    
    def __init__(self):
        self.events = []
    
    def emit(self, events: Iterable[ExecutionEvent]) -> None:
        """Print events to console."""
        for event in events:
            # Validation
            if event.event_type not in ALLOWED_EVENTS:
                raise ValueError(f"Invalid event type: {event.event_type}")
            if not event.execution_id:
                raise ValueError("Event must have execution_id")
            
            # Store in-memory
            self.events.append(event)
            
            # Print for manual verification
            print(f"[EVENT] {event.event_type} | execution={event.execution_id}")


class MultiEventEmitter:
    """Fan-out to multiple emitters."""
    
    def __init__(self, emitters: Iterable[EventEmitter]):
        self._emitters = list(emitters)
    
    def emit(self, events: Iterable[ExecutionEvent]):
        """Emit to all emitters."""
        for emitter in self._emitters:
            emitter.emit(events)


class NullEventEmitter(EventEmitter):
    """No-op emitter (used when events are not needed)."""
    
    def emit(self, events: Iterable[ExecutionEvent]) -> None:
        """Do nothing."""
        pass