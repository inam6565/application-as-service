#execution_engine\executor\slots.py

"""Slot manager for controlling executor concurrency."""

from typing import Optional
from uuid import UUID


class Slot:
    """Represents a single execution slot."""
    
    def __init__(self, slot_id: int):
        self.slot_id = slot_id
        self.execution_id: Optional[UUID] = None
    
    def is_free(self) -> bool:
        """Check if slot is available."""
        return self.execution_id is None
    
    def bind(self, execution_id: UUID) -> None:
        """Bind execution to this slot."""
        if not self.is_free():
            raise ValueError(f"Slot {self.slot_id} already occupied")
        self.execution_id = execution_id
    
    def release(self) -> None:
        """Release slot."""
        self.execution_id = None
    
    def __repr__(self) -> str:
        status = "free" if self.is_free() else f"occupied({self.execution_id})"
        return f"<Slot(id={self.slot_id}, {status})>"


class SlotManager:
    """Manages execution slots for an executor."""
    
    def __init__(self, max_slots: int):
        if max_slots < 1:
            raise ValueError("max_slots must be at least 1")
        
        self._slots = [Slot(i) for i in range(max_slots)]
    
    def acquire_free_slot(self) -> Optional[Slot]:
        """Get a free slot if available."""
        for slot in self._slots:
            if slot.is_free():
                return slot
        return None
    
    def active_slots(self) -> list[Slot]:
        """Get all occupied slots."""
        return [s for s in self._slots if not s.is_free()]
    
    def find_slot_by_execution(self, execution_id: UUID) -> Optional[Slot]:
        """Find slot containing given execution."""
        for slot in self._slots:
            if slot.execution_id == execution_id:
                return slot
        return None
    
    def total_slots(self) -> int:
        """Get total number of slots."""
        return len(self._slots)
    
    def free_slots(self) -> int:
        """Get number of free slots."""
        return sum(1 for s in self._slots if s.is_free())
    
    def __repr__(self) -> str:
        return (
            f"<SlotManager(total={self.total_slots()}, "
            f"free={self.free_slots()}, "
            f"active={len(self.active_slots())})>"
        )