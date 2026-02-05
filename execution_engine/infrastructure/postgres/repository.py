#execution_engine\infrastructure\postgres\repository.py

"""PostgreSQL repository implementation using SQLAlchemy."""

from datetime import datetime, timedelta
from typing import Iterable, Optional, Callable
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from execution_engine.core.repository import ExecutionRepository
from execution_engine.core.models import Execution, ExecutionState
from execution_engine.core.errors import (
    ExecutionConcurrencyError,
    ExecutionLeaseError,
    ExecutionNotFound,
    ExecutionAlreadyExists,
)
from execution_engine.infrastructure.postgres.database import SessionLocal
from execution_engine.infrastructure.postgres.models import ExecutionORM


# ============================================
# Mapping Functions
# ============================================

def orm_to_domain(orm: ExecutionORM) -> Execution:
    """Convert ORM model to domain model."""
    return Execution(
        execution_id=orm.execution_id,
        tenant_id=orm.tenant_id,
        application_id=orm.application_id,
        deployment_id=orm.deployment_id,
        step_execution_id=orm.step_execution_id,
        execution_type=orm.execution_type,
        target_resource_id=orm.target_resource_id,
        runtime_type=orm.runtime_type,
        spec=orm.spec,
        state=orm.state,
        created_at=orm.created_at,
        queued_at=orm.queued_at,
        claimed_at=orm.claimed_at,
        started_at=orm.started_at,
        finished_at=orm.finished_at,
        lease_owner=orm.lease_owner,
        lease_expires_at=orm.lease_expires_at,
        deployment_result=orm.deployment_result,
        error_message=orm.error_message,
        retry_count=orm.retry_count,
        max_retries=orm.max_retries,
        priority=orm.priority,
        version=orm.version,
    )


def domain_to_orm(execution: Execution) -> ExecutionORM:
    """Convert domain model to ORM model."""
    return ExecutionORM(
        execution_id=execution.execution_id,
        tenant_id=execution.tenant_id,
        application_id=execution.application_id,
        deployment_id=execution.deployment_id,
        step_execution_id=execution.step_execution_id,
        execution_type=execution.execution_type,
        target_resource_id=execution.target_resource_id,
        runtime_type=execution.runtime_type,
        spec=execution.spec,
        state=execution.state,
        created_at=execution.created_at,
        queued_at=execution.queued_at,
        claimed_at=execution.claimed_at,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        lease_owner=execution.lease_owner,
        lease_expires_at=execution.lease_expires_at,
        deployment_result=execution.deployment_result,
        error_message=execution.error_message,
        retry_count=execution.retry_count,
        max_retries=execution.max_retries,
        priority=execution.priority,
        version=execution.version,
    )


# ============================================
# Repository Implementation
# ============================================

class PostgresExecutionRepository(ExecutionRepository):
    """PostgreSQL implementation using SQLAlchemy with dependency injection."""
    
    def __init__(self, session_factory: Optional[sessionmaker] = None):
        """
        Initialize repository with optional session factory.
        
        Args:
            session_factory: SQLAlchemy session factory. If None, uses default production factory.
        """
        self._session_factory = session_factory or SessionLocal
    
    def _get_session(self) -> Session:
        """Get new session from the injected factory."""
        return self._session_factory()
    
    # -------------------------
    # CREATE
    # -------------------------
    
    def create(self, execution: Execution) -> None:
        """Create a new execution."""
        session = self._get_session()
        try:
            orm = domain_to_orm(execution)
            session.add(orm)
            session.commit()
            print(f"[postgres] create {execution.execution_id} -> done")
        except IntegrityError as e:
            session.rollback()
            raise ExecutionAlreadyExists(
                f"Execution {execution.execution_id} already exists"
            ) from e
        except SQLAlchemyError as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Failed to create execution: {e}") from e
        finally:
            session.close()
    
    # -------------------------
    # READ
    # -------------------------
    
    def get(self, execution_id: UUID) -> Optional[Execution]:
        """Get execution by ID."""
        session = self._get_session()
        try:
            orm = session.get(ExecutionORM, execution_id)
            
            if orm is None:
                print(f"[postgres] get {execution_id} -> not found")
                return None
            
            print(f"[postgres] get {execution_id} -> found")
            return orm_to_domain(orm)
        finally:
            session.close()
    
    # -------------------------
    # LIST BY STATE
    # -------------------------
    
    def list_by_state(
        self,
        state: ExecutionState,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> Iterable[Execution]:
        """List executions by state."""
        session = self._get_session()
        try:
            query = session.query(ExecutionORM).filter(
                ExecutionORM.state == state
            )
            
            if tenant_id:
                query = query.filter(ExecutionORM.tenant_id == tenant_id)
            
            query = query.order_by(
                ExecutionORM.priority.desc(),
                ExecutionORM.created_at.asc()
            ).limit(limit)
            
            results = query.all()
            print(f"[postgres] list_by_state state={state.value} -> {len(results)} rows")
            
            return [orm_to_domain(orm) for orm in results]
        finally:
            session.close()
    
    # -------------------------
    # CLAIM
    # -------------------------
    
    def try_claim(
        self,
        execution_id: UUID,
        worker_id: str,
        lease_seconds: int
    ) -> bool:
        """Atomically claim an execution."""
        session = self._get_session()
        try:
            now = datetime.utcnow()
            lease_expires_at = now + timedelta(seconds=lease_seconds)
            
            # Get execution with row lock
            execution_orm = session.query(ExecutionORM).filter(
                ExecutionORM.execution_id == execution_id
            ).with_for_update().first()
            
            if not execution_orm:
                return False
            
            # Check if claimable
            if execution_orm.state != ExecutionState.QUEUED:
                return False
            
            if execution_orm.lease_expires_at and execution_orm.lease_expires_at > now:
                return False
            
            # Claim it
            execution_orm.state = ExecutionState.CLAIMED
            execution_orm.lease_owner = worker_id
            execution_orm.lease_expires_at = lease_expires_at
            execution_orm.claimed_at = now
            execution_orm.version += 1
            
            session.commit()
            print(f"[postgres] try_claim {execution_id} by {worker_id} -> True")
            return True
            
        except Exception as e:
            session.rollback()
            print(f"[postgres] try_claim {execution_id} by {worker_id} -> False (error: {e})")
            return False
        finally:
            session.close()
    
    # -------------------------
    # START
    # -------------------------
    
    def start(self, execution_id: UUID, worker_id: str) -> None:
        """Start execution."""
        session = self._get_session()
        try:
            now = datetime.utcnow()
            
            # Get with lock
            execution_orm = session.query(ExecutionORM).filter(
                ExecutionORM.execution_id == execution_id
            ).with_for_update().first()
            
            if not execution_orm:
                raise ExecutionLeaseError(f"Execution {execution_id} not found")
            
            # Validate
            if execution_orm.state != ExecutionState.CLAIMED:
                raise ExecutionLeaseError(
                    f"Execution not in CLAIMED state (current: {execution_orm.state.value})"
                )
            
            if execution_orm.lease_owner != worker_id:
                raise ExecutionLeaseError(f"Execution owned by {execution_orm.lease_owner}")
            
            if not execution_orm.lease_expires_at or execution_orm.lease_expires_at <= now:
                raise ExecutionLeaseError("Lease expired")
            
            # Start it
            execution_orm.state = ExecutionState.STARTED
            execution_orm.started_at = now
            execution_orm.version += 1
            
            session.commit()
            print(f"[postgres] start succeeded for {execution_id}")
            
        except ExecutionLeaseError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise ExecutionLeaseError(f"Failed to start execution: {e}") from e
        finally:
            session.close()
    
    # -------------------------
    # UPDATE
    # -------------------------
    
    def update(self, execution: Execution) -> None:
        """Update execution with optimistic locking."""
        session = self._get_session()
        try:
            # Get current version
            current = session.query(ExecutionORM).filter(
                and_(
                    ExecutionORM.execution_id == execution.execution_id,
                    ExecutionORM.version == execution.version - 1
                )
            ).with_for_update().first()
            
            if not current:
                raise ExecutionConcurrencyError(
                    f"Update failed for {execution.execution_id} - concurrent modification"
                )
            
            # Update fields
            current.state = execution.state
            current.lease_owner = execution.lease_owner
            current.lease_expires_at = execution.lease_expires_at
            current.queued_at = execution.queued_at
            current.started_at = execution.started_at
            current.finished_at = execution.finished_at
            current.deployment_result = execution.deployment_result
            current.error_message = execution.error_message
            current.retry_count = execution.retry_count
            current.version = execution.version
            
            session.commit()
            print(f"[postgres] update {execution.execution_id} -> done")
            
        except ExecutionConcurrencyError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise ExecutionConcurrencyError(f"Update failed: {e}") from e
        finally:
            session.close()
    
    # -------------------------
    # RENEW LEASE
    # -------------------------
    
    def renew_lease(
        self,
        execution_id: UUID,
        worker_id: str,
        lease_seconds: int
    ) -> None:
        """Renew lease."""
        session = self._get_session()
        try:
            now = datetime.utcnow()
            new_expires_at = now + timedelta(seconds=lease_seconds)
            
            execution_orm = session.query(ExecutionORM).filter(
                ExecutionORM.execution_id == execution_id
            ).with_for_update().first()
            
            if not execution_orm:
                raise ExecutionLeaseError(f"Execution {execution_id} not found")
            
            if execution_orm.lease_owner != worker_id:
                raise ExecutionLeaseError(f"Execution owned by {execution_orm.lease_owner}")
            
            if not execution_orm.lease_expires_at or execution_orm.lease_expires_at <= now:
                raise ExecutionLeaseError("Lease already expired")
            
            execution_orm.lease_expires_at = new_expires_at
            execution_orm.version += 1
            
            session.commit()
            print(f"[postgres] renew_lease {execution_id} -> {new_expires_at}")
            
        except ExecutionLeaseError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise ExecutionLeaseError(f"Failed to renew lease: {e}") from e
        finally:
            session.close()
    
    # -------------------------
    # RECOVERABLE
    # -------------------------
    
    def list_recoverable(self, limit: int = 100) -> Iterable[Execution]:
        """List recoverable executions."""
        session = self._get_session()
        try:
            now = datetime.utcnow()
            
            results = session.query(ExecutionORM).filter(
                and_(
                    ExecutionORM.state == ExecutionState.STARTED,
                    ExecutionORM.lease_expires_at <= now
                )
            ).limit(limit).all()
            
            print(f"[postgres] list_recoverable -> {len(results)} rows")
            return [orm_to_domain(orm) for orm in results]
        finally:
            session.close()
    
    # -------------------------
    # FINALIZE
    # -------------------------
    
    def finalize(
        self,
        execution_id: UUID,
        worker_id: str,
        final_state: ExecutionState
    ) -> None:
        """Finalize execution."""
        if final_state not in (ExecutionState.COMPLETED, ExecutionState.FAILED):
            raise ValueError(f"Invalid final state: {final_state}")
        
        session = self._get_session()
        try:
            now = datetime.utcnow()
            
            execution_orm = session.query(ExecutionORM).filter(
                ExecutionORM.execution_id == execution_id
            ).with_for_update().first()
            
            if not execution_orm:
                raise ExecutionLeaseError(f"Execution {execution_id} not found")
            
            if execution_orm.lease_owner != worker_id:
                raise ExecutionLeaseError(f"Execution owned by {execution_orm.lease_owner}")
            
            if not execution_orm.lease_expires_at or execution_orm.lease_expires_at <= now:
                raise ExecutionLeaseError("Lease expired")
            
            execution_orm.state = final_state
            execution_orm.finished_at = now
            execution_orm.lease_owner = None
            execution_orm.lease_expires_at = None
            execution_orm.version += 1
            
            session.commit()
            print(f"[postgres] finalize {execution_id} -> {final_state.value}")
            
        except ExecutionLeaseError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise ExecutionLeaseError(f"Failed to finalize: {e}") from e
        finally:
            session.close()