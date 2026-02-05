#execution_engine\api\container.py
from execution_engine.infrastructure.postgres.repository import PostgresExecutionRepository
from execution_engine.infrastructure.postgres.config import POSTGRES_DSN
from execution_engine.core.service import ExecutionService
from execution_engine.core.events import MultiEventEmitter
from execution_engine.container import execution_service  


# Singletons
_repository = PostgresExecutionRepository(POSTGRES_DSN)
_emitters = MultiEventEmitter([])
_service = ExecutionService(_repository, _emitters)


def get_execution_service() -> ExecutionService:
    return _service
def get_execution_service():
    return execution_service