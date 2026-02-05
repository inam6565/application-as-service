# execution_engine/run_executor.py

from execution_engine.infrastructure.postgres.repository import (
    PostgresExecutionRepository,
)
from execution_engine.infrastructure.postgres.config import POSTGRES_DSN

from execution_engine.core.service import ExecutionService
from execution_engine.core.events import MultiEventEmitter, PrintEventEmitter

from execution_engine.executor.executor import Executor
from execution_engine.container import service, repository
from execution_engine.executor.executor import Executor

# -------------------------
# Infrastructure
# -------------------------

repository = PostgresExecutionRepository(POSTGRES_DSN)

emitters = MultiEventEmitter([
    PrintEventEmitter()
])

service = ExecutionService(repository, emitters)

# -------------------------
# Executor
# -------------------------

executor = Executor(
    executor_id="worker-1",
    service=service,
    repository=repository,
    max_slots=2,
    lease_seconds=5,
    execution_runtime_seconds=3,
)

executor.start()

print("Executor running. Ctrl+C to stop.")

import time
while True:
    time.sleep(1)
