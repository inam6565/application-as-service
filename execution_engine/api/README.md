# API Module

## Overview

FastAPI-based REST API server providing HTTP endpoints for application management, deployment control, and system monitoring.

## Purpose

The API module exposes the platform's functionality to users:
- Create and manage applications
- Trigger deployments
- Query execution status
- Register compute nodes
- Monitor system health

## Architecture

```
┌─────────────────────────────────────┐
│         API Server                   │
│         (FastAPI)                    │
│                                      │
│  ┌────────────────────────────────┐ │
│  │       Routes                   │ │
│  │  /applications                 │ │
│  │  /executions                   │ │
│  │  /nodes                        │ │
│  │  /ui/*                         │ │
│  │  /health                       │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │       Schemas                  │ │
│  │  (Pydantic models)             │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │       Container                │ │
│  │  (Dependency injection)        │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Components

### Routes (`routes/`)

#### applications.py
- `GET /templates` - List application templates
- `GET /templates/{template_id}` - Get template details
- `POST /applications` - Create application, optionally deploy immediately
- `GET /applications` - List tenant applications
- `GET /applications/{application_id}` - Get application
- `POST /applications/{application_id}/deploy` - Start a deployment
- `GET /applications/{application_id}/deployments` - List application deployments
- `GET /deployments/{deployment_id}` - Get deployment
- `GET /deployments/{deployment_id}/steps` - List deployment step progress
- `GET /deployments/{deployment_id}/executions` - List deployment executions
- `GET /deployments/{deployment_id}/resources` - List deployed resources
- `POST /deployments/{deployment_id}/cleanup` - Remove managed container resources for a deployment

#### executions.py
- `GET /api/executions` - List executions
- `GET /api/executions/{id}` - Get execution details
- `GET /api/executions/{id}/logs` - Get execution logs

#### nodes.py
- `POST /nodes/register` - Register node
- `GET /nodes` - List nodes
- `GET /nodes/{node_id}` - Get node details

#### ui.py
- `GET /ui/templates` - Template browser
- `GET /ui/templates/{template_id}/new` - Application create form
- `GET /ui/applications` - Application list
- `GET /ui/applications/{application_id}` - Application detail
- `GET /ui/deployments/{deployment_id}` - Deployment status page
- `GET /ui/nodes` - Node registration/list page

#### health
- `GET /health` - Health check endpoint

### Schemas (`schemas/`)

Pydantic models for request/response validation:

```python
class ApplicationCreateRequest(BaseModel):
    tenant_id: UUID
    template_id: str
    name: str
    description: Optional[str] = None
    user_inputs: Dict[str, Any] = {}
    deploy: bool = False

class ApplicationResponse(BaseModel):
    application_id: UUID
    tenant_id: UUID
    template_id: str
    template_version: str
    name: str
    status: str
    health_status: str
    current_deployment_id: Optional[UUID]
    public_url: Optional[str]

class DeploymentRequest(BaseModel):
    # POST /applications/{application_id}/deploy
    pass

class ExecutionResponse(BaseModel):
    execution_id: UUID
    state: str
    runtime_type: str
    created_at: datetime
    finished_at: Optional[datetime]
```

### Container (`container.py`)

Dependency injection container:
- Application service
- Execution service
- Node manager service
- Repositories

## WordPress Template Behavior

The WordPress template does not ask the user for database name, host, user, or password. The platform derives those values during deployment:

- `MYSQL_HOST` is used by the platform to provision the database.
- `MYSQL_APPLICATION_HOST` is injected into the WordPress container as `WORDPRESS_DB_HOST`.
- `WORDPRESS_DB_NAME`, `WORDPRESS_DB_USER`, and `WORDPRESS_DB_PASSWORD` are passed through Docker environment variables.

The UI form at `/ui/templates/wordpress/new` should only collect WordPress-facing settings such as domain, image tag, resources, and exposed port.

Deployment detail pages use `/deployments/{deployment_id}/steps` to show volume, database, and container progress. Runtime/container log endpoints are intentionally deferred until runtime-agent authentication is added, because logs may contain secrets.

## API Endpoints

### Application Management

#### Create Application
```http
POST /applications
Content-Type: application/json

{
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "template_id": "nginx",
  "name": "My Web Server",
  "user_inputs": {
    "nginx_version": "alpine",
    "exposed_port": 8080
  },
  "deploy": true
}

Response: 201 Created
{
  "application_id": "abc-123",
  "name": "My Web Server",
  "status": "CREATING",
  "template_id": "nginx"
}
```

#### Get Application
```http
GET /applications/{application_id}

Response: 200 OK
{
  "application_id": "abc-123",
  "application_name": "My Web Server",
  "status": "RUNNING",
  "template_id": "def-456",
  "configuration": {...},
  "created_at": "2026-03-03T10:00:00Z"
}
```

#### Deploy Application
```http
POST /applications/{application_id}/deploy

Response: 202 Accepted
{
  "deployment_id": "ghi-789",
  "application_id": "abc-123",
  "status": "DEPLOYING",
  "total_steps": 2,
  "completed_steps": 0
}
```

### Execution Management

#### List Executions
```http
GET /api/executions?state=COMPLETED&limit=10

Response: 200 OK
{
  "executions": [
    {
      "execution_id": "xyz-001",
      "state": "COMPLETED",
      "runtime_type": "docker",
      "created_at": "2026-03-03T10:00:00Z",
      "finished_at": "2026-03-03T10:00:30Z"
    }
  ],
  "total": 1
}
```

#### Get Execution Details
```http
GET /api/executions/{execution_id}

Response: 200 OK
{
  "execution_id": "xyz-001",
  "state": "COMPLETED",
  "runtime_type": "docker",
  "spec": {...},
  "deployment_result": {...},
  "created_at": "2026-03-03T10:00:00Z",
  "started_at": "2026-03-03T10:00:05Z",
  "finished_at": "2026-03-03T10:00:30Z"
}
```

### Node Management

#### Register Node
```http
POST /api/nodes
Content-Type: application/json

{
  "node_name": "compute-node-01",
  "node_type": "APP_NODE",
  "internal_ip": "192.168.1.101",
  "runtime_agent_url": "http://192.168.1.101:9000",
  "total_cpu": 4.0,
  "total_memory": 8192,
  "total_storage": 100
}

Response: 201 Created
{
  "node_id": "node-abc",
  "node_name": "compute-node-01",
  "status": "ACTIVE"
}
```

### Health Checks

#### Health Check
```http
GET /health

Response: 200 OK
{
  "status": "healthy",
  "database": "connected",
  "services": {
    "executor": "running",
    "status_updater": "running"
  }
}
```

## Running the API

### Development Mode

```bash
python -m execution_engine.api.main
```

Server starts on http://0.0.0.0:8000

### Production Mode (Uvicorn)

```bash
uvicorn execution_engine.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4
```

### Production Mode (Gunicorn)

```bash
gunicorn execution_engine.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

## Configuration

### Environment Variables

```bash
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_LOG_LEVEL=info
```

### CORS Configuration

```python
# In main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Authentication (Future)

Currently no authentication. Planned:
- JWT token authentication
- API key authentication
- Role-based access control (RBAC)

## Rate Limiting (Future)

Planned:
- Per-IP rate limiting
- Per-user rate limiting
- Different limits for different endpoints

## Error Handling

### HTTP Status Codes

- `200 OK` - Successful request
- `201 Created` - Resource created
- `202 Accepted` - Request accepted (async)
- `400 Bad Request` - Invalid input
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict
- `500 Internal Server Error` - Server error

### Error Response Format

```json
{
  "error": {
    "code": "APPLICATION_NOT_FOUND",
    "message": "Application abc-123 not found",
    "details": {}
  }
}
```

## Testing

### Manual Testing (curl)

```bash
# Create application
curl -X POST http://localhost:8000/applications \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"00000000-0000-0000-0000-000000000001","template_id":"nginx","name":"Test","user_inputs":{"nginx_version":"alpine","exposed_port":8080},"deploy":true}'

# Get application
curl http://localhost:8000/applications/abc-123

# Deploy application
curl -X POST http://localhost:8000/applications/abc-123/deploy
```

### API Documentation

FastAPI auto-generates interactive API docs:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Monitoring

### Metrics (Future)

Planned Prometheus metrics:
- `api_requests_total` - Total requests
- `api_request_duration_seconds` - Request duration
- `api_errors_total` - Total errors

### Logging

```python
import logging

logger = logging.getLogger(__name__)

@app.get("/applications/{application_id}")
async def get_application(application_id: UUID):
    logger.info(f"Fetching application {application_id}")
    # ...
```

## Security Considerations

### Input Validation

- All inputs validated with Pydantic
- SQL injection prevented (SQLAlchemy)
- XSS prevented (JSON responses)

### Planned Security

- HTTPS/TLS
- Authentication
- Rate limiting
- Input sanitization
- CORS restrictions

## Performance

### Current Limits

- Max request size: 10MB
- Timeout: 30 seconds
- Connection pool: 20 connections

### Optimization Tips

- Use connection pooling
- Cache frequently accessed data
- Paginate large responses
- Use async/await properly

## Troubleshooting

### API Not Starting

**Check:**
1. Port 8000 available?
2. Database connection OK?
3. Dependencies installed?

**Solution:**
```bash
# Check port
netstat -tulpn | grep 8000

# Test database
python test_db_connection.py

# Reinstall dependencies
pip install -r requirements.txt
```

### Slow Responses

**Check:**
1. Database query performance
2. External service calls
3. Connection pool size

**Solution:**
```bash
# Enable query logging
export DB_ECHO=true

# Increase pool size
export DB_POOL_SIZE=50
```

## Future Enhancements

- GraphQL API
- WebSocket support (real-time updates)
- Batch operations
- Export/import functionality
- Audit logging

## Related Documentation

- `../core/README.md` - Execution core
- `../domain/README.md` - Domain models
- `../orchestrator/README.md` - Orchestration
