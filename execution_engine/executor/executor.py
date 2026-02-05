# execution_engine/executor/executor.py

import threading
import time
from datetime import datetime

from execution_engine.executor.slots import SlotManager
from execution_engine.core.models import ExecutionState
from execution_engine.core.errors import ExecutionLeaseError


class Executor:
    def __init__(
        self,
        *,
        executor_id: str,
        service,
        repository,
        poll_interval: float = 1.0,
        max_slots: int = 1,
        lease_seconds: int = 5,
        execution_runtime_seconds: int = 2,
    ):
        self.executor_id = executor_id
        self.service = service
        self.repo = repository
        self.poll_interval = poll_interval
        self.lease_seconds = lease_seconds
        self.execution_runtime_seconds = execution_runtime_seconds

        self.slots = SlotManager(max_slots)
        self._stop_event = threading.Event()
        self._thread = None

        self._running = {}

    # -------------------------

    def start(self):
        print(f"[executor {self.executor_id}] starting")
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    # -------------------------

    def _run_loop(self):
        while not self._stop_event.is_set():
            self._renew_running_leases()
            self._advance_running_executions()
            self._claim_and_start()
            time.sleep(self.poll_interval)

    # -------------------------
    # Lease heartbeat
    # -------------------------

    def _renew_running_leases(self):
        for execution_id in list(self._running.keys()):
            try:
                self.service.renew_execution_lease(
                    execution_id=execution_id,
                    worker_id=self.executor_id,
                    lease_seconds=self.lease_seconds,
                )
            except ExecutionLeaseError:
                self._handle_lost_execution(execution_id)

    def _handle_lost_execution(self, execution_id):
        slot = self.slots.find_slot_by_execution(execution_id)
        if slot:
            slot.release()
        self._running.pop(execution_id, None)
        print(f"[executor] lost lease {execution_id}")

    # -------------------------
    # Claim + start
    # -------------------------

    def _claim_and_start(self):
        print("[executor] polling...")

        slot = self.slots.acquire_free_slot()
        if not slot:
            print("[executor] no free slots")
            return

        # -------- FIRST: normal queued --------
        queued = self.repo.list_by_state(
            state=ExecutionState.QUEUED,
            limit=1,
        )

        print(f"[executor] queued found: {len(queued)}")

        for execution in queued:
            print(f"[executor] trying claim QUEUED {execution.execution_id}")

            claimed = self.service.claim_execution(
                execution_id=execution.execution_id,
                worker_id=self.executor_id,
                lease_seconds=self.lease_seconds,
            )

            if not claimed:
                print("[executor] claim failed")
                continue

            try:
                self.service.start_execution(
                    execution.execution_id,
                    worker_id=self.executor_id,
                )
            except ExecutionLeaseError:
                print("[executor] start failed")
                slot.release()
                return

            slot.bind(execution.execution_id)
            self._running[execution.execution_id] = datetime.utcnow()

            print(
                f"[executor] STARTED {execution.execution_id} "
                f"in slot {slot.slot_id}"
            )
            return

        # -------- SECOND: recovery --------
        recoverable = self.repo.list_recoverable(limit=1)

        print(f"[executor] recoverable found: {len(recoverable)}")

        for execution in recoverable:
            print(f"[executor] trying recover {execution.execution_id}")

            claimed = self.service.claim_execution(
                execution_id=execution.execution_id,
                worker_id=self.executor_id,
                lease_seconds=self.lease_seconds,
            )

            if not claimed:
                continue

            slot.bind(execution.execution_id)
            self._running[execution.execution_id] = datetime.utcnow()

            print(
                f"[executor] RECOVERED {execution.execution_id} "
                f"in slot {slot.slot_id}"
            )
            return

    # -------------------------
    # Complete executions
    # -------------------------

    def _advance_running_executions(self):
        now = datetime.utcnow()

        for slot in self.slots.active_slots():
            execution_id = slot.execution_id
            started_at = self._running.get(execution_id)

            if not started_at:
                continue

            elapsed = (now - started_at).total_seconds()
            if elapsed < self.execution_runtime_seconds:
                continue

            self.service.complete_execution(
                execution_id=execution_id,
                worker_id=self.executor_id,
            )

            slot.release()
            self._running.pop(execution_id, None)

            print(f"[executor] COMPLETED {execution_id}")
