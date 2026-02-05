#execution_engine\executor\config.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutorConfig:
    worker_id: str

    poll_interval_seconds: float = 1.0
    claim_batch_size: int = 5
    max_slots: int = 2

    lease_seconds: int = 10
