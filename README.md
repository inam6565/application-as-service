# Application-as-Service Platform

## Overview

A Platform-as-a-Service (PaaS) system like Heroku/Render where users can deploy applications (WordPress, Nginx, custom apps) without managing infrastructure. The platform handles deployment, health monitoring, auto-restart, database provisioning, and scaling.

## Project Status

**Current Sprint:** Sprint 4, Day 8 (WordPress Deployment Stabilization)  
**Overall Progress:** 55% Complete  
**Production Ready:** No (MVP in development)

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│              Platform VM (192.168.1.100)         │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ API Server   │  │  Executor    │            │
│  │ (FastAPI)    │  │  Worker      │            │
│  │ Port 8000    │  │              │            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │Status Updater│  │Health Checker│            │
│  │   Service    │  │   Service    │            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
│  ┌──────────────┐                               │
│  │Retry Worker  │                               │
│  │   Service    │                               │
│  └──────────────┘                               │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │         PostgreSQL Database                │ │
│  │  (executions, deployments, applications)   │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│          Compute Node VM (192.168.1.101)         │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │     Runtime Agent (FastAPI)              │  │
│  │     Port 9000                            │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │     Docker Engine                        │  │
│  │     (runs user containers)               │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│            Database VM (optional)                │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │     MySQL (user app databases)           │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Technology Stack

- **Language:** Python 3.12
- **Web Framework:** FastAPI
- **ORM:** SQLAlchemy
- **Database:** PostgreSQL (platform), MySQL (user apps)
- **Migrations:** Alembic
- **Container Management:** Docker SDK
- **Process Management:** Systemd
- **Configuration:** python-dotenv

## Core Concepts

### 1. Execution Flow

```
User creates application from template
  ↓
Orchestrator creates deployment record
  ↓
Orchestrator creates execution(s) for each step
  ↓
Executor claims execution (30s lease)
  ↓
Executor calls Runtime Agent → deploys container/database
  ↓
Executor updates execution → COMPLETED
  ↓
Status Updater polls (5s) → deployment RUNNING
  ↓
Health Checker monitors (10s) → auto-restart if unhealthy
  ↓
Retry Worker retries failures (10s, 30s, 90s backoff)
```

### 2. Key Entities

- **ApplicationTemplate:** Pre-defined templates (Nginx, WordPress)
- **Application:** User's app instance
- **Deployment:** Specific deployment of an application
- **Execution:** Single task (container, database, volume)
- **DeployedResource:** Tracks containers/databases/volumes
- **InfrastructureNode:** Compute nodes available

### 3. Design Patterns

- **Async Architecture:** Non-blocking orchestrator, background workers
- **Lease-Based Execution:** 30s leases prevent duplicate work
- **Optimistic Locking:** Version field prevents race conditions
- **Crash-Only Design:** All state in DB, services can restart
- **Exponential Backoff:** 10s → 30s → 90s retry delays

## Project Structure

```
app-as-service/
├── execution_engine/       # Core platform services
│   ├── api/               # REST API endpoints
│   ├── core/              # Execution engine
│   ├── domain/            # Application domain models
│   ├── orchestrator/      # Deployment orchestration
│   ├── executor/          # Executor worker
│   ├── status_updater/    # Status monitoring
│   ├── health_checker/    # Container health monitoring
│   ├── node_manager/      # Infrastructure node management
│   └── infrastructure/    # Data layer (PostgreSQL)
│
├── runtime_agent/         # Runtime Agent (Compute Node)
├── alembic/              # Database migrations
├── tests/                # Test suite
└── *.py                  # Test scripts
```

## Services Overview

### Platform VM Services

1. **API Server** (`execution_engine/api/`)
   - FastAPI REST API
   - Application CRUD operations
   - Deployment triggers
   - Port: 8000

2. **Executor Worker** (`execution_engine/executor/`)
   - Claims and executes deployments
   - 2 concurrent slots
   - Calls Runtime Agent
   - Lease-based execution

3. **Status Updater** (`execution_engine/status_updater/`)
   - Polls deployments every 5s
   - Updates deployment/application status
   - Crash-safe (DB source of truth)

4. **Health Checker** (`execution_engine/health_checker/`)
   - Monitors containers every 10s
   - HTTP/TCP/Command health checks
   - Auto-restart after 3 failures

5. **Retry Worker** (`execution_engine/executor/retry_service.py`)
   - Retries failed executions
   - Exponential backoff
   - Max 3 retries

### Compute Node Services

6. **Runtime Agent** (`runtime_agent/`)
   - FastAPI server
   - Docker SDK integration
   - Container lifecycle management
   - Port: 9000

## Getting Started

### Prerequisites

```bash
# Python 3.12
python --version

# PostgreSQL
psql --version

# MySQL (for user applications)
mysql --version

# Docker (on Compute Node)
docker --version
```

### Installation

```bash
# Clone repository
git clone <repository-url>
cd app-as-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy .env template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### Configuration

Edit `.env` file:

```bash
# PostgreSQL (Platform Data)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=aas_platform
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# MySQL (User Application Databases)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_ROOT_USER=root
MYSQL_ROOT_PASSWORD=your_password
MYSQL_APPLICATION_HOST=host.docker.internal

# Local UI default tenant
DEFAULT_TENANT_ID=00000000-0000-0000-0000-000000000001
```

### Database Setup

```bash
# Create PostgreSQL database
createdb aas_platform

# Run migrations
alembic upgrade head

# Seed templates
python seed_templates.py
```

### Running Locally

The easiest local mode starts the API and platform workers from one runner:

```bash
python -m execution_engine.run_all
```

Open:

```text
http://localhost:8000/ui/applications
```

The unified runner starts:

- FastAPI API server on port `8000`
- Executor worker
- Status updater
- Health checker
- Retry worker

WordPress deployments automatically create a dedicated MySQL database on the configured MySQL host using the application and deployment IDs. You do not need to enter a DB name or password in the UI. `MYSQL_HOST` is used by the platform process for provisioning; `MYSQL_APPLICATION_HOST` is passed to WordPress containers. On Docker Desktop, use `host.docker.internal` when MySQL is running on the host.

The WordPress container receives database settings through Docker environment variables:

- `WORDPRESS_DB_HOST`
- `WORDPRESS_DB_NAME`
- `WORDPRESS_DB_USER`
- `WORDPRESS_DB_PASSWORD`

The official WordPress image keeps `wp-config.php` generic and reads these values at runtime via `getenv_docker(...)`.

Deployment detail pages show step-level progress for volume, database, and container steps. Container steps are linked to the async execution processed by the executor.

The runtime agent normally runs on a compute node. For a single-machine local setup, start it separately:

```bash
python -m runtime_agent.server
```

Or include it in the same local runner:

```bash
python -m execution_engine.run_all --runtime-agent
```

Register the local runtime agent from the UI at `/ui/nodes`, using:

```text
http://127.0.0.1:9000
```

Useful runner variants:

```bash
# API only
python -m execution_engine.run_all --no-workers

# Workers only
python -m execution_engine.run_all --no-api

# Custom ports
python -m execution_engine.run_all --api-port 8080 --runtime-agent-port 9001
```

### Running Services Separately

For production-like local debugging, services can still be run independently:

```bash
uvicorn execution_engine.api.main:app --host 0.0.0.0 --port 8000
python -m execution_engine.run_executor
python -m execution_engine.run_status_updater
python -m execution_engine.run_health_checker
python -m execution_engine.run_retry_worker
python -m runtime_agent.server
```

### Local UI Flow

1. Run PostgreSQL and apply migrations.
2. Start Docker.
3. Start MySQL and confirm the credentials in `.env`.
4. Start the runtime agent.
5. Start the unified runner.
6. Open `/ui/nodes` and register the runtime agent URL.
7. Open `/ui/templates`.
8. Create and deploy an Nginx or WordPress application.
9. Watch deployment status at `/ui/deployments/{deployment_id}`.

For WordPress, use a new deployment after changing template or MySQL settings. Old failed executions keep their original resolved deployment spec in PostgreSQL.

### Testing

```bash
# Test Nginx deployment
python test_nginx_deployment.py

# Test health checker
python test_health_checker.py

# Test retry logic
python test_retry_logic.py

# Test status updater
python test_status_updater.py

# Clean test data
python cleanup_test_data.py
```

## Development Workflow

### Making Changes

1. Update code
2. Restart affected service (Ctrl+C, re-run)
3. Clean test data: `python cleanup_test_data.py`
4. Run test script
5. Check logs for errors
6. Verify database state

### Adding Features

1. Update domain models (if needed)
2. Create Alembic migration (if schema change)
3. Implement service logic
4. Update orchestrator/executor (if needed)
5. Create test script
6. Document in README

### Creating Migrations

```bash
# Auto-generate migration
alembic revision --autogenerate -m "description"

# Review migration file
# Edit if needed

# Apply migration
alembic upgrade head
```

## Database Schema

### Key Tables

- **executions:** Execution state machine
- **deployments:** Multi-step deployment tracking
- **applications:** User applications
- **application_templates:** Nginx, WordPress templates
- **deployed_resources:** Containers, databases, volumes
- **infrastructure_nodes:** Compute nodes

See individual module READMEs for detailed schemas.

## API Endpoints

### Template Management
- `GET /templates` - List available templates
- `GET /templates/{template_id}` - Get template details

### Application Management
- `POST /applications` - Create application, optionally deploy immediately
- `GET /applications?tenant_id={tenant_id}` - List tenant applications
- `GET /applications/{application_id}` - Get application
- `POST /applications/{application_id}/deploy` - Deploy application
- `GET /applications/{application_id}/deployments` - List deployments

### Execution Management
- `POST /executions` - Create low-level execution
- `POST /executions/{execution_id}/queue` - Queue low-level execution
- `GET /executions/{execution_id}` - Get execution details
- `GET /deployments/{deployment_id}/executions` - List deployment executions

### Deployment Resources
- `GET /deployments/{deployment_id}` - Get deployment
- `GET /deployments/{deployment_id}/steps` - List step-level deployment progress
- `GET /deployments/{deployment_id}/resources` - List deployed resources
- `POST /deployments/{deployment_id}/cleanup` - Remove managed container resources for a deployment

### Node Management
- `POST /nodes/register` - Register node
- `GET /nodes` - List nodes
- `GET /nodes/{node_id}` - Get node

### UI
- `GET /ui/templates`
- `GET /ui/applications`
- `GET /ui/nodes`
- `GET /ui/deployments/{deployment_id}`

See `execution_engine/api/README.md` for details.

## Production Deployment Notes

The unified runner is intended for local development and demos. In production, run each service as a separate process managed by systemd, Docker Compose, or Kubernetes:

- API server: externally reachable, horizontally scalable.
- Executor workers: scale independently based on queued execution volume.
- Status updater: one or a small controlled number of instances.
- Health checker: one per platform shard or node group.
- Retry worker: one controlled instance unless retry claiming is made fully distributed.
- Runtime agent: runs on compute nodes with Docker access.

Recommended production practices:

- Use a reverse proxy or ingress in front of the API.
- Terminate TLS at the edge.
- Keep runtime agents on private network addresses.
- Store database and runtime credentials in a secret manager.
- Keep the MySQL admin credentials available only to the platform service that provisions WordPress databases.
- Run Alembic migrations before starting new application versions.
- Use structured logs and metrics for API, executor, health checker, and runtime agent.
- Keep the runtime agent separate from the platform API unless running a single-node development environment.

## Troubleshooting

### Services Not Starting

**Check:**
1. Is .env configured correctly?
2. Is PostgreSQL running?
3. Are migrations applied?
4. Are ports available?

**Solution:**
```bash
# Check PostgreSQL
systemctl status postgresql

# Check ports
netstat -tulpn | grep 8000

# Apply migrations
alembic upgrade head
```

### Deployments Stuck

**Check:**
1. Is executor running?
2. Is status updater running?
3. Are there errors in logs?
4. Check database for state

**Solution:**
```bash
# Restart services
Ctrl+C in each terminal
Re-run service commands
```

### Database Connection Failed

**Check:**
1. Credentials in .env correct?
2. PostgreSQL/MySQL running?
3. Databases exist?
4. For WordPress in Docker Desktop, is `MYSQL_APPLICATION_HOST=host.docker.internal`?
5. Does the MySQL user allow remote/container connections?

**Solution:**
```bash
# Test PostgreSQL
psql -U postgres -d aas_platform

# Test MySQL
mysql -u root -p
```

### WordPress Shows Database Connection Error

**Check:**
1. The runtime agent and unified runner were restarted after code/config changes.
2. The WordPress deployment was newly created after the restart.
3. `MYSQL_HOST` is reachable from the platform process.
4. `MYSQL_APPLICATION_HOST` is reachable from inside the WordPress container.
5. The container was recreated after stale failed attempts.

**Useful commands:**
```bash
docker ps -a
docker inspect <wordpress_container_name>
docker logs <wordpress_container_name>
```

In `docker inspect`, check `Config.Env` for `WORDPRESS_DB_HOST`, `WORDPRESS_DB_NAME`, `WORDPRESS_DB_USER`, and `WORDPRESS_DB_PASSWORD`.

## Contributing

### Code Style

- Follow PEP 8
- Type hints for all functions
- Docstrings for classes and methods
- Descriptive variable names

### Commit Messages

```
feat: Add database provisioning
fix: Fix executor resource update
docs: Update API documentation
test: Add health checker tests
```

### Pull Request Process

1. Create feature branch
2. Make changes
3. Add tests
4. Update documentation
5. Submit PR

## Roadmap

### Sprint 4 (Current)
- [x] Status Updater Service
- [x] Health Checker Service
- [x] Retry Logic
- [x] Database Provisioning
- [x] Full WordPress Deployment
- [x] Deployment step records
- [x] Basic failed deployment cleanup for managed containers
- [ ] Volume Management
- [ ] Rollback Support

### Sprint 5 (Planned)
- [ ] Runtime-agent authentication before exposing logs or inspect endpoints
- [ ] Per-deployment MySQL users and password grants after approving MySQL account host scope
- [ ] Deployment logs and container logs in UI
- [ ] Full cleanup/rollback for failed deployments
- [ ] Secrets Encryption
- [ ] Network Isolation
- [ ] SSL/TLS Support
- [ ] Prometheus Metrics
- [ ] Grafana Dashboards

### Sprint 6 (Planned)
- [ ] Load Testing
- [ ] Admin UI
- [ ] Production Deployment
- [ ] Documentation

## Architecture Decisions

### Why Separate Services?

- **Isolation:** Each service can crash independently
- **Scalability:** Can run multiple executors
- **Clarity:** Clear separation of concerns
- **Resilience:** Crash-safe design

### Why Shared Database?

- **Simplicity:** Single source of truth
- **Consistency:** No eventual consistency issues
- **MVP Speed:** Faster development

### Why Polling vs Events?

- **Simplicity:** No message queue needed
- **Crash-Safe:** Services restart cleanly
- **Good Enough:** 5-10s latency acceptable

## Performance

### Current Metrics

- Deployment time: 10-30 seconds
- Concurrent deployments: 2 per executor
- Health check latency: 10 seconds
- Retry delay: 10s, 30s, 90s

### Scaling Limits

- Single executor: ~100 deployments/hour
- Single database: ~1000 applications
- Need Kubernetes beyond 1000 users

## Security

### Current Security

- PostgreSQL password authentication
- MySQL password authentication
- No encryption at rest (yet)
- No network isolation (yet)

### Planned Security

- HashiCorp Vault for secrets
- Docker network isolation
- TLS for all connections
- Rate limiting

## License

[Your License Here]

## Contact

[Your Contact Info]

---

**For detailed documentation of each module, see:**
- `execution_engine/README.md` - Core platform
- `execution_engine/api/README.md` - API server
- `execution_engine/executor/README.md` - Executor worker
- `runtime_agent/README.md` - Runtime agent
- And more in each subdirectory
