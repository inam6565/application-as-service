#execution_engine\infrastructure\postgres\models.py
"""SQLAlchemy ORM models for database tables."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, DateTime, JSON, Enum as SQLEnum, Index, Text, Boolean, Float, ForeignKey, LargeBinary
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from execution_engine.core.models import ExecutionState
from execution_engine.infrastructure.postgres.database import Base
from execution_engine.domain.models import (
    ApplicationStatus, DeploymentStatus, StepStatus, ResourceType, HealthStatus
)
from execution_engine.node_manager.models import NodeType, NodeStatus, NodeHealthStatus


class ExecutionORM(Base):
    """
    Execution table - stores execution state.
    
    Indexes:
    - Primary key on execution_id
    - Composite index on (state, lease_expires_at) for querying available work
    - Index on tenant_id for tenant isolation
    - Index on application_id for application queries
    """
    
    __tablename__ = "executions"
    
    # Primary key
    execution_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    
    # Identity
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    deployment_id = Column(UUID(as_uuid=True), nullable=True)
    step_execution_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Execution type
    execution_type = Column(String(50), nullable=False, default="deploy")
    target_resource_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Runtime
    runtime_type = Column(String(50), nullable=False)
    spec = Column(JSON, nullable=False)
    
    # State
    state = Column(
        SQLEnum(ExecutionState, name="execution_state"),
        nullable=False,
        default=ExecutionState.CREATED,
        index=True
    )
    
    # Lifecycle timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    queued_at = Column(DateTime, nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True, index=True)
    finished_at = Column(DateTime, nullable=True)
    
    # Lease management
    lease_owner = Column(String(255), nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    
    # Results
    deployment_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Retry
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # Priority
    priority = Column(Integer, nullable=False, default=0, index=True)
    
    # Optimistic concurrency
    version = Column(Integer, nullable=False, default=0)
    
    # Composite indexes for common queries
    __table_args__ = (
        # Index for finding queued executions
        Index(
            'ix_executions_queued_lookup',
            'state',
            'priority',
            'created_at',
            postgresql_where=(state == ExecutionState.QUEUED.value)
        ),
        # Index for finding recoverable executions
        Index(
            'ix_executions_recoverable_lookup',
            'state',
            'lease_expires_at',
            postgresql_where=(state == ExecutionState.STARTED.value)
        ),
        # Index for tenant-scoped queries
        Index('ix_executions_tenant_state', 'tenant_id', 'state'),
        # Index for application-scoped queries
        Index('ix_executions_app_state', 'application_id', 'state'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ExecutionORM(execution_id={self.execution_id}, "
            f"state={self.state.value}, "
            f"lease_owner={self.lease_owner})>"
        )
    
# ============================================
# APPLICATION TEMPLATES
# ============================================

class ApplicationTemplateORM(Base):
    """Application template table."""
    
    __tablename__ = "application_templates"
    
    template_id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    version = Column(String(50), nullable=False)
    category = Column(String(100), nullable=False)
    
    icon_url = Column(String(500), nullable=True)
    
    deployment_steps = Column(JSON, nullable=False)  # List of step definitions
    
    database_required = Column(Boolean, nullable=False, default=False)
    database_type = Column(String(50), nullable=True)
    
    required_inputs = Column(JSON, nullable=False)  # List of input field definitions
    default_resources = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)
    
    __table_args__ = (
        Index('ix_templates_category', 'category'),
        Index('ix_templates_active', 'is_active'),
    )


# ============================================
# APPLICATIONS
# ============================================

class ApplicationORM(Base):
    """Application table."""
    
    __tablename__ = "applications"
    
    application_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    template_id = Column(String(100), ForeignKey('application_templates.template_id'), nullable=False)
    template_version = Column(String(50), nullable=False)
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    user_inputs = Column(JSON, nullable=False)
    
    current_deployment_id = Column(UUID(as_uuid=True), nullable=True)
    
    status = Column(SQLEnum(ApplicationStatus), nullable=False, default=ApplicationStatus.CREATING, index=True)
    health_status = Column(SQLEnum(HealthStatus), nullable=False, default=HealthStatus.UNKNOWN)
    
    domain = Column(String(255), nullable=True)
    public_url = Column(String(500), nullable=True)
    ssl_enabled = Column(Boolean, nullable=False, default=False)
    
    resource_limits = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    template = relationship("ApplicationTemplateORM", backref="applications")
    
    __table_args__ = (
        Index('ix_applications_tenant_status', 'tenant_id', 'status'),
        Index('ix_applications_tenant_created', 'tenant_id', 'created_at'),
    )


# ============================================
# DEPLOYMENTS
# ============================================

class DeploymentORM(Base):
    """Deployment table."""
    
    __tablename__ = "deployments"
    
    deployment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.application_id'), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    template_id = Column(String(100), nullable=False)
    template_version = Column(String(50), nullable=False)
    
    resolved_config = Column(JSON, nullable=False)
    
    status = Column(SQLEnum(DeploymentStatus), nullable=False, default=DeploymentStatus.PENDING, index=True)
    
    current_step_index = Column(Integer, nullable=False, default=0)
    total_steps = Column(Integer, nullable=False, default=0)
    
    public_url = Column(String(500), nullable=True)
    internal_endpoints = Column(JSON, nullable=False, default={})
    
    error_message = Column(Text, nullable=True)
    rollback_on_failure = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    deployment_metadata = Column(JSON, nullable=False, default={})
    
    # Relationships
    application = relationship("ApplicationORM", backref="deployments")
    
    __table_args__ = (
        Index('ix_deployments_app_created', 'application_id', 'created_at'),
        Index('ix_deployments_status', 'status'),
    )


# ============================================
# DEPLOYMENT STEPS
# ============================================

class DeploymentStepExecutionORM(Base):
    """Deployment step execution table."""
    
    __tablename__ = "deployment_step_executions"
    
    step_execution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey('deployments.deployment_id'), nullable=False, index=True)
    step_id = Column(String(100), nullable=False)
    step_name = Column(String(255), nullable=False)
    
    execution_id = Column(UUID(as_uuid=True), ForeignKey('executions.execution_id'), nullable=True)
    
    status = Column(SQLEnum(StepStatus), nullable=False, default=StepStatus.PENDING, index=True)
    
    result = Column(JSON, nullable=False, default={})
    error_message = Column(Text, nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Relationships
    deployment = relationship("DeploymentORM", backref="steps")
    execution = relationship("ExecutionORM", backref="step_executions")
    
    __table_args__ = (
        Index('ix_step_executions_deployment', 'deployment_id'),
        Index('ix_step_executions_status', 'status'),
    )


# ============================================
# DEPLOYED RESOURCES
# ============================================

class DeployedResourceORM(Base):
    """Deployed resource table."""
    
    __tablename__ = "deployed_resources"
    
    resource_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey('deployments.deployment_id'), nullable=False, index=True)
    resource_type = Column(SQLEnum(ResourceType), nullable=False)
    
    external_id = Column(String(255), nullable=False)  # Docker container ID, etc.
    node_id = Column(UUID(as_uuid=True), ForeignKey('infrastructure_nodes.node_id'), nullable=False)
    
    name = Column(String(255), nullable=False)
    spec = Column(JSON, nullable=False)
    
    status = Column(String(50), nullable=False, default="unknown")
    
    # ✅ ADD health tracking
    health_status = Column(SQLEnum(HealthStatus), nullable=False, default=HealthStatus.UNKNOWN)
    consecutive_health_failures = Column(Integer, nullable=False, default=0)
    last_health_check_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    deployment = relationship("DeploymentORM", backref="resources")
    
    __table_args__ = (
        Index('ix_resources_deployment', 'deployment_id'),
        Index('ix_resources_type', 'resource_type'),
        Index('ix_resources_health', 'health_status'),  # ✅ ADD index
    )


# ============================================
# DOMAINS
# ============================================

class DomainORM(Base):
    """Domain table."""
    
    __tablename__ = "domains"
    
    domain_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.application_id'), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    domain_name = Column(String(255), nullable=False, unique=True, index=True)
    is_subdomain = Column(Boolean, nullable=False, default=False)
    parent_domain = Column(String(255), nullable=True)
    
    dns_verified = Column(Boolean, nullable=False, default=False)
    dns_verified_at = Column(DateTime, nullable=True)
    dns_records = Column(JSON, nullable=False, default=[])
    
    ssl_enabled = Column(Boolean, nullable=False, default=False)
    ssl_provider = Column(String(50), nullable=False, default="letsencrypt")
    ssl_status = Column(String(50), nullable=False, default="pending")
    ssl_cert_path = Column(String(500), nullable=True)
    ssl_cert_expires_at = Column(DateTime, nullable=True)
    
    target_deployment_id = Column(UUID(as_uuid=True), nullable=True)
    target_port = Column(Integer, nullable=False, default=80)
    
    status = Column(String(50), nullable=False, default="pending")
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    application = relationship("ApplicationORM", backref="domains")
    
    __table_args__ = (
        Index('ix_domains_app', 'application_id'),
        Index('ix_domains_tenant', 'tenant_id'),
    )


# ============================================
# PROVISIONED DATABASES
# ============================================

class ProvisionedDatabaseORM(Base):
    """Provisioned database table."""
    
    __tablename__ = "provisioned_databases"
    
    database_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.application_id'), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    db_type = Column(String(50), nullable=False)
    db_name = Column(String(255), nullable=False, unique=True)
    db_user = Column(String(255), nullable=False)
    db_password_encrypted = Column(LargeBinary, nullable=False)
    
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    connection_string_encrypted = Column(LargeBinary, nullable=False)
    
    storage_size_gb = Column(Integer, nullable=False)
    
    status = Column(String(50), nullable=False, default="provisioning")
    
    last_backup_at = Column(DateTime, nullable=True)
    backup_retention_days = Column(Integer, nullable=False, default=7)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    application = relationship("ApplicationORM", backref="databases")
    
    __table_args__ = (
        Index('ix_provisioned_dbs_app', 'application_id'),
        Index('ix_provisioned_dbs_tenant', 'tenant_id'),
        Index('ix_provisioned_dbs_type', 'db_type'),
    )


# ============================================
# INFRASTRUCTURE NODES
# ============================================

class InfrastructureNodeORM(Base):
    """Infrastructure node table."""
    
    __tablename__ = "infrastructure_nodes"
    
    node_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    node_name = Column(String(255), nullable=False, unique=True)
    node_type = Column(SQLEnum(NodeType), nullable=False, index=True)
    
    internal_ip = Column(String(50), nullable=False)
    public_ip = Column(String(50), nullable=True)
    
    runtime_agent_url = Column(String(500), nullable=False)
    supported_runtimes = Column(JSON, nullable=False, default=["docker"])
    
    total_cpu = Column(Float, nullable=False, default=0.0)
    total_memory = Column(Integer, nullable=False, default=0)
    total_storage = Column(Integer, nullable=False, default=0)
    
    available_cpu = Column(Float, nullable=False, default=0.0)
    available_memory = Column(Integer, nullable=False, default=0)
    available_storage = Column(Integer, nullable=False, default=0)
    
    max_containers = Column(Integer, nullable=False, default=50)
    active_containers = Column(Integer, nullable=False, default=0)
    
    status = Column(SQLEnum(NodeStatus), nullable=False, default=NodeStatus.READY, index=True)
    health_status = Column(SQLEnum(NodeHealthStatus), nullable=False, default=NodeHealthStatus.UNKNOWN)
    
    last_heartbeat_at = Column(DateTime, nullable=True)
    
    labels = Column(JSON, nullable=False, default={})
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    registered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_nodes_type_status', 'node_type', 'status'),
        Index('ix_nodes_status', 'status'),
        Index('ix_nodes_heartbeat', 'last_heartbeat_at'),
    )

