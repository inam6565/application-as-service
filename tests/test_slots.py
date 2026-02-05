#tests\test_slots.py

"""Test slot manager (Bug Fix #2 Verification)."""

import pytest
from uuid import uuid4

from execution_engine.executor.slots import Slot, SlotManager


class TestSlot:
    """Test individual slot."""
    
    def test_slot_initialization(self):
        """Test slot starts free."""
        slot = Slot(slot_id=0)
        assert slot.is_free()
        assert slot.execution_id is None
    
    def test_bind_execution(self):
        """Test binding execution to slot."""
        slot = Slot(slot_id=0)
        execution_id = uuid4()
        
        slot.bind(execution_id)
        
        assert not slot.is_free()
        assert slot.execution_id == execution_id
    
    def test_bind_occupied_slot_fails(self):
        """Test binding to occupied slot fails."""
        slot = Slot(slot_id=0)
        slot.bind(uuid4())
        
        with pytest.raises(ValueError):
            slot.bind(uuid4())
    
    def test_release_slot(self):
        """Test releasing slot."""
        slot = Slot(slot_id=0)
        slot.bind(uuid4())
        
        slot.release()
        
        assert slot.is_free()
        assert slot.execution_id is None


class TestSlotManager:
    """Test slot manager."""
    
    def test_initialization(self):
        """Test slot manager initialization."""
        manager = SlotManager(max_slots=5)
        
        assert manager.total_slots() == 5
        assert manager.free_slots() == 5
        assert len(manager.active_slots()) == 0
    
    def test_acquire_free_slot(self):
        """Test acquiring free slot."""
        manager = SlotManager(max_slots=3)
        
        slot = manager.acquire_free_slot()
        
        assert slot is not None
        assert slot.is_free()
    
    def test_acquire_when_all_occupied(self):
        """Test acquiring when all slots occupied."""
        manager = SlotManager(max_slots=2)
        
        # Occupy all slots
        slot1 = manager.acquire_free_slot()
        slot1.bind(uuid4())
        slot2 = manager.acquire_free_slot()
        slot2.bind(uuid4())
        
        # Try to acquire
        slot3 = manager.acquire_free_slot()
        assert slot3 is None
    
    def test_find_slot_by_execution(self):
        """Test finding slot by execution ID (Bug Fix #2)."""
        manager = SlotManager(max_slots=3)
        execution_id = uuid4()
        
        # Bind to a slot
        slot = manager.acquire_free_slot()
        slot.bind(execution_id)
        
        # Find it
        found_slot = manager.find_slot_by_execution(execution_id)
        
        assert found_slot is not None
        assert found_slot.execution_id == execution_id
    
    def test_find_nonexistent_execution(self):
        """Test finding execution that doesn't exist."""
        manager = SlotManager(max_slots=3)
        
        found_slot = manager.find_slot_by_execution(uuid4())
        assert found_slot is None
    
    def test_active_slots(self):
        """Test getting active slots."""
        manager = SlotManager(max_slots=5)
        
        # Bind 2 slots
        slot1 = manager.acquire_free_slot()
        slot1.bind(uuid4())
        slot2 = manager.acquire_free_slot()
        slot2.bind(uuid4())
        
        active = manager.active_slots()
        
        assert len(active) == 2
        assert manager.free_slots() == 3