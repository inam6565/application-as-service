#execution_engine\domain\models.py
"""Domain models for applications, templates, and deployments."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


# ============================================
# ENUMS
# ============================================

class ApplicationStatus(Enum):
    """Application lifecycle status."""
    CREATING = "CREATING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    DELETING = "DELETING"
    DELETED = "DELETED"


class DeploymentStatus(Enum):
    """Deployment status."""
    PENDING = "PENDING"
    DEPLOYING = "DEPLOYING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    DELETED = "DELETED"


class StepStatus(Enum):
    """Deployment step status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ResourceType(Enum):
    """Deployed resource type."""
    CONTAINER = "CONTAINER"
    DATABASE = "DATABASE"
    VOLUME = "VOLUME"
    NETWORK = "NETWORK"


class HealthStatus(Enum):
    """Health check status."""
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    STARTING = "STARTING"


# ============================================
# APPLICATION TEMPLATE
# ============================================

@dataclass
class HealthCheckDefinition:
    """Health check configuration."""
    type: str  # "http", "tcp", "command"
    path: Optional[str] = None
    port: Optional[int] = None
    command: Optional[str] = None
    interval_seconds: int = 10
    timeout_seconds: int = 5
    retries: int = 3
    initial_delay_seconds: int = 0


@dataclass
class DeploymentStepDefinition:
    """Step definition in application template."""
    step_id: str
    step_name: str
    step_type: str  # "container", "database", "volume", "network", "ssl"
    order: int
    depends_on: List[str] = field(default_factory=list)
    
    spec_template: Dict[str, Any] = field(default_factory=dict)
    health_check: Optional[HealthCheckDefinition] = None
    timeout_seconds: int = 300
    
    retry_on_failure: bool = True
    max_retries: int = 3
    cleanup_on_failure: bool = True


@dataclass
class TemplateInputField:
    """User input field definition."""
    field_name: str
    field_type: str  # "string", "password", "domain", "integer", "boolean", "select"
    label: str
    description: str
    required: bool
    default_value: Optional[Any] = None
    validation_regex: Optional[str] = None
    options: Optional[List[str]] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    placeholder: Optional[str] = None


@dataclass
class ResourceLimits:
    """Resource limits for containers."""
    cpu: str  # "0.5" (cores)
    memory: str  # "512Mi"
    storage: str  # "10Gi"


@dataclass
class ApplicationTemplate:
    """Application template (like Helm charts)."""
    template_id: str
    name: str
    description: str
    version: str
    category: str
    
    icon_url: Optional[str] = None
    
    deployment_steps: List[DeploymentStepDefinition] = field(default_factory=list)
    
    database_required: bool = False
    database_type: Optional[str] = None
    
    required_inputs: List[TemplateInputField] = field(default_factory=list)
    default_resources: Optional[ResourceLimits] = None
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


# ============================================
# APPLICATION
# ============================================

@dataclass
class Application:
    """User's application instance."""
    application_id: UUID
    tenant_id: UUID
    
    template_id: str
    template_version: str
    
    name: str
    description: Optional[str] = None
    user_inputs: Dict[str, Any] = field(default_factory=dict)
    
    current_deployment_id: Optional[UUID] = None
    
    status: ApplicationStatus = ApplicationStatus.CREATING
    health_status: HealthStatus = HealthStatus.UNKNOWN
    
    domain: Optional[str] = None
    public_url: Optional[str] = None
    ssl_enabled: bool = False
    
    resource_limits: Optional[ResourceLimits] = None
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = None


# ============================================
# DEPLOYMENT
# ============================================

@dataclass
class Deployment:
    """Deployment of an application."""
    deployment_id: UUID
    application_id: UUID
    tenant_id: UUID
    
    template_id: str
    template_version: str
    
    resolved_config: Dict[str, Any] = field(default_factory=dict)
    
    status: DeploymentStatus = DeploymentStatus.PENDING
    
    current_step_index: int = 0
    total_steps: int = 0
    
    public_url: Optional[str] = None
    internal_endpoints: Dict[str, str] = field(default_factory=dict)
    
    error_message: Optional[str] = None
    rollback_on_failure: bool = True
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentStepExecution:
    """Execution tracking for a deployment step."""
    step_execution_id: UUID
    deployment_id: UUID
    step_id: str
    step_name: str
    
    execution_id: Optional[UUID] = None
    
    status: StepStatus = StepStatus.PENDING
    
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


@dataclass
class DeployedResource:
    """A deployed resource (container, database, etc.)."""
    resource_id: UUID
    deployment_id: UUID
    resource_type: ResourceType
    
    external_id: str  # Docker container ID, DB name, etc.
    node_id: UUID
    
    name: str
    spec: Dict[str, Any] = field(default_factory=dict)
    
    status: str = "unknown"
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================
# DOMAIN
# ============================================

@dataclass
class DNSRecord:
    """DNS record configuration."""
    record_type: str  # "A", "CNAME", "TXT"
    name: str
    value: str
    ttl: int = 300


@dataclass
class Domain:
    """Domain configuration for an application."""
    domain_id: UUID
    application_id: UUID
    tenant_id: UUID
    
    domain_name: str
    is_subdomain: bool = False
    parent_domain: Optional[str] = None
    
    dns_verified: bool = False
    dns_verified_at: Optional[datetime] = None
    dns_records: List[DNSRecord] = field(default_factory=list)
    
    ssl_enabled: bool = False
    ssl_provider: str = "letsencrypt"
    ssl_status: str = "pending"
    ssl_cert_path: Optional[str] = None
    ssl_cert_expires_at: Optional[datetime] = None
    
    target_deployment_id: UUID = None
    target_port: int = 80
    
    status: str = "pending"
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================
# PROVISIONED DATABASE
# ============================================

@dataclass
class ProvisionedDatabase:
    """Platform-provisioned database."""
    database_id: UUID
    application_id: UUID
    tenant_id: UUID
    
    db_type: str  # "mysql", "postgresql"
    db_name: str
    db_user: str
    db_password_encrypted: bytes
    
    host: str
    port: int
    connection_string_encrypted: bytes
    
    storage_size_gb: int
    
    status: str = "provisioning"
    
    last_backup_at: Optional[datetime] = None
    backup_retention_days: int = 7
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = None