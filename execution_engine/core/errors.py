# execution_engine/core/errors.py

# -----------------------------
# Base Errors
# -----------------------------

class ExecutionError(Exception):
    """Base class for all execution engine errors."""
    pass


# -----------------------------
# Validation / Domain Errors
# -----------------------------

class ExecutionValidationError(ExecutionError):
    """Invalid input or malformed execution."""
    pass


class ExecutionInvalidStateError(ExecutionError):
    """Illegal state transition attempted."""
    pass


# -----------------------------
# Lease / Ownership Errors
# -----------------------------

class ExecutionLeaseError(ExecutionError):
    """Lease missing, expired, or owned by another worker."""
    pass


# -----------------------------
# Persistence Errors
# -----------------------------

class ExecutionPersistenceError(ExecutionError):
    pass


class ExecutionAlreadyExists(ExecutionPersistenceError):
    pass


class ExecutionNotFound(ExecutionPersistenceError):
    pass


class ExecutionConcurrencyError(ExecutionPersistenceError):
    pass
