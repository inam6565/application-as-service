#execution_engine\executor\slot_manager.py

class SlotManager:
    def __init__(self, max_slots: int):
        self._max_slots = max_slots
        self._active = 0

    def has_free_slot(self) -> bool:
        return self._active < self._max_slots

    def acquire(self) -> bool:
        if not self.has_free_slot():
            return False
        self._active += 1
        return True

    def release(self) -> None:
        if self._active > 0:
            self._active -= 1

    @property
    def active(self) -> int:
        return self._active

    @property
    def capacity(self) -> int:
        return self._max_slots
