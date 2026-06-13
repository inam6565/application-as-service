# Execution Engine

## Overview

The execution engine is the core platform service responsible for orchestrating application deployments, executing deployment tasks, monitoring health, and managing the lifecycle of deployed resources.

## Purpose

The execution engine transforms user deployment requests into concrete actions:
- Provisions databases
- Deploys containers
- Creates volumes
- Monitors health
- Handles failures
- Updates status

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Execution Engine                       │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │   API    │  │ Executor │  │  Status  │      │
│  │  Server  │  │  Worker  │  │ Updater  │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  ┌──────────┐  ┌──────────┐                     │
│  │  Health  │  │  Retry   │                     │
│  │ Checker  │  │  Worker  │                     │
│  └──────────┘  └──────────┘                     │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │         Orchestrator                       │ │
│  │  (coordinates multi-step deployments)     │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │         Domain Layer                       │ │
│  │  (applications, templates, deployments)   │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │         Infrastructure Layer               │ │
│  │  (PostgreSQL repositories)                │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Components

### 1. API (`api/`)
FastAPI REST API server for user interactions.
- Application CRUD
- Deployment triggers
- Execution queries
- Node management

### 2. Core (`core/`)
Execution state machine and core logic.
- Execution model and states
- Lease management
- Execution service
- Repository interface

### 3. Domain (`domain/`)
Application domain models and business logic.
- Application templates
- Deployment models
- Application service

### 4. Orchestrator (`orchestrator/`)
Multi-step deployment coordination.
- Template processing
- Step execution
- Dependency management
- Variable resolution

### 5. Executor (`executor/`)
Worker that claims and executes deployments.
- Slot-based concurrency
- Lease renewal
- Runtime Agent client
- Retry service

### 6. Status Updater (`status_updater/`)
Background service monitoring deployment status.
- Polls every 5 seconds
- Updates deployment status
- Updates application status
- Crash-safe

### 7. Health Checker (`health_checker/`)
Monitors container health and auto-restarts.
- HTTP/TCP/Command checks
- 10-second polling
- Auto-restart after 3 failures
- 60-second restart delay

### 8. Node Manager (`node_manager/`)
Manages compute nodes.
- Node registration
- Resource tracking
- Node selection

### 9. Infrastructure (`infrastructure/`)
Data persistence layer.
- PostgreSQL repositories
- SQLAlchemy models
- Database connection

## Execution Flow

### High-Level Flow

```
1. User creates application (via API)
   ↓
2. Orchestrator creates deployment
   ↓
3. Orchestrator creates execution(s) per step
   ↓
4. Executor claims execution (30s lease)
   ↓
5. Executor executes via Runtime Agent
   ↓
6. Executor updates execution → COMPLETED
   ↓
7. Status Updater polls → deployment RUNNING
   ↓
8. Health Checker monitors container
   ↓
9. Retry Worker handles failures
```

### Execution State Machine

```
CREATED → QUEUED → CLAIMED → STARTED → COMPLETED
                                    ↓
                                  FAILED
                                    ↓
                             (Retry if transient)
```

## Data Models

### Execution
```python
class Execution:
    execution_id: UUID
    state: ExecutionState
    runtime_type: str  # "docker", "database", "volume"
    spec: Dict[str, Any]
    deployment_result: Dict[str, Any]
    lease_owner: str
    lease_expires_at: datetime
    retry_count: int
    max_retries: int
    version: int  # Optimistic locking
```

### Deployment
```python
class Deployment:
    deployment_id: UUID
    application_id: UUID
    status: str  # "DEPLOYING", "RUNNING", "FAILED"
    total_steps: int
    completed_steps: int
    deployment_config: Dict[str, Any]
```

### Application
```python
class Application:
    application_id: UUID
    template_id: UUID
    application_name: str
    status: str  # "CREATING", "RUNNING", "FAILED", "STOPPED"
    configuration: Dict[str, Any]
```

### DeployedResource
```python
class DeployedResource:
    resource_id: UUID
    deployment_id: UUID
    resource_type: str  # "container", "database", "volume"
    external_id: str  # Container ID, DB name, volume name
    status: str
    health_status: str  # "UNKNOWN", "HEALTHY", "UNHEALTHY", "STARTING"
    consecutive_health_failures: int
```

## Configuration

### Environment Variables (.env)

```bash
# PostgreSQL platform database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=aas_platform
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# MySQL used by WordPress deployments
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_ROOT_USER=root
MYSQL_ROOT_PASSWORD=password
MYSQL_APPLICATION_HOST=host.docker.internal

# Executor
EXECUTOR_ID=executor-01
EXECUTOR_POLL_INTERVAL=2
EXECUTOR_MAX_SLOTS=2
EXECUTOR_LEASE_SECONDS=30

# Status Updater
STATUS_UPDATER_POLL_INTERVAL=5

# Health Checker
HEALTH_CHECKER_POLL_INTERVAL=10
HEALTH_CHECKER_FAILURE_THRESHOLD=3
HEALTH_CHECKER_RESTART_DELAY=60

# Retry Worker
RETRY_WORKER_POLL_INTERVAL=5
```

## Running Services

### Start Local Runner

```bash
python -m execution_engine.run_all
```

The local runner starts the API, executor, status updater, health checker, and retry worker for development.

Start the runtime agent separately on the compute node, or include it in local single-machine mode:

```bash
python -m runtime_agent.server
python -m execution_engine.run_all --runtime-agent
```

### Run Services Separately

```bash
uvicorn execution_engine.api.main:app --host 0.0.0.0 --port 8000
python -m execution_engine.run_executor
python -m execution_engine.run_status_updater
python -m execution_engine.run_health_checker
python -m execution_engine.run_retry_worker
python -m runtime_agent.server
```

### Systemd Services

```bash
# Create systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start services
sudo systemctl start aas-executor
sudo systemctl start aas-status-updater
sudo systemctl start aas-health-checker
sudo systemctl start aas-retry-worker
sudo systemctl start aas-api

# Enable on boot
sudo systemctl enable aas-*
```

## Testing

```bash
# Unit tests
pytest tests/

# Integration tests
python test_e2e_deployment.py

# Component tests
python test_executor.py
python test_status_updater.py
python test_health_checker.py
python test_retry_logic.py
```

## WordPress Deployment

WordPress is deployed through the multi-step template flow:

1. Create/reuse the WordPress data volume.
2. Provision a dedicated MySQL database named from the application and deployment IDs.
3. Inject database settings into the WordPress container environment.
4. Queue the Docker container deployment through the runtime agent.
5. Let the status updater mark the deployment running after the container execution completes.

The official WordPress image keeps `wp-config.php` generic. It reads these values from Docker environment variables:

- `WORDPRESS_DB_HOST`
- `WORDPRESS_DB_NAME`
- `WORDPRESS_DB_USER`
- `WORDPRESS_DB_PASSWORD`

`MYSQL_HOST` is used by the platform process for database provisioning. `MYSQL_APPLICATION_HOST` is passed to WordPress containers. On Docker Desktop, use `host.docker.internal` when MySQL runs on the host.

Deployment steps are persisted in `deployment_step_executions` and shown in the deployment UI. Synchronous steps such as volume/database provisioning complete during orchestration. Container steps are linked to execution records and completed by the status updater when the executor finishes.

## Database Schema

### Tables

- **executions:** Execution records
- **deployments:** Deployment tracking
- **applications:** User applications
- **application_templates:** Nginx, WordPress templates
- **deployed_resources:** Containers, databases, volumes
- **infrastructure_nodes:** Compute nodes
- **deployment_step_executions:** Step tracking

### Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Troubleshooting

### Executor Not Picking Up Executions

**Check:**
1. Is executor running?
2. Are executions in QUEUED state?
3. Are slots full?
4. Check logs

**Solution:**
```bash
# Check status
ps aux | grep run_executor

# Check queued work through application logs or API
python -m execution_engine.run_executor

# Restart executor
python -m execution_engine.run_executor
```

### Status Not Updating

**Check:**
1. Is status updater running?
2. Are executions completed?
3. Check logs

**Solution:**
```bash
# Restart status updater
python -m execution_engine.run_status_updater
```

### Health Checks Failing

**Check:**
1. Is health checker running?
2. Is container actually healthy?
3. Check health check configuration

**Solution:**
```bash
# Test manually
curl http://localhost:PORT/health

# Check container
docker ps

# Restart health checker
python -m execution_engine.run_health_checker
```

## Design Patterns

### Lease-Based Execution

Executors claim executions with 30-second leases:
- Prevents duplicate work
- Enables executor scaling
- Automatic recovery on crash

### Optimistic Locking

Version field prevents concurrent updates:
- No database locks needed
- Scales well
- Simple retry logic

### Crash-Only Design

All state in database:
- Services can crash safely
- No in-memory state
- Easy to restart

### Separation of Concerns

Each service has one responsibility:
- API: User interface
- Executor: Execute deployments
- Status Updater: Monitor status
- Health Checker: Monitor health
- Retry Worker: Handle failures

## Performance

### Current Metrics

- Executor throughput: ~30 deployments/hour per instance
- Status updater latency: 5 seconds
- Health check latency: 10 seconds
- Retry delay: 10s, 30s, 90s

### Scaling

- Run multiple executors
- Increase executor slots
- Optimize database queries
- Add connection pooling

## Future Enhancements

### Short Term
- Runtime-agent authentication before exposing logs or inspect endpoints
- Full cleanup/rollback for failed container and database deployments
- Per-deployment MySQL users and grants after approving MySQL account host scope
- Volume management

### Medium Term
- Secrets encryption
- Network isolation
- SSL/TLS support
- Observability and metrics

### Long Term
- Kubernetes deployment
- Auto-scaling
- Multi-region support

## Module Documentation

For detailed documentation of each module:
- `api/README.md` - API server
- `core/README.md` - Execution engine core
- `domain/README.md` - Domain models
- `orchestrator/README.md` - Orchestration
- `executor/README.md` - Executor worker
- `status_updater/README.md` - Status monitoring
- `health_checker/README.md` - Health monitoring
- `infrastructure/README.md` - Data layer

## Contributing

See main project README for contribution guidelines.
