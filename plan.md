# PaaS Roadmap Compared With Dokploy

Date: 2026-06-13

## Purpose

This plan compares the current Application-as-a-Service platform with Dokploy and defines the next engineering phases needed to move toward a Dokploy-like self-hosted PaaS.

References:

- Dokploy GitHub README: https://github.com/Dokploy/dokploy
- Dokploy Features: https://docs.dokploy.com/docs/core/features
- Dokploy Architecture: https://docs.dokploy.com/docs/core/architecture
- Dokploy Multi-Tenancy: https://docs.dokploy.com/docs/core/multi-tenancy
- Dokploy Applications: https://docs.dokploy.com/docs/core/applications
- Dokploy Databases: https://docs.dokploy.com/docs/core/databases
- Dokploy Docker Compose: https://docs.dokploy.com/docs/core/docker-compose
- Dokploy Domains: https://docs.dokploy.com/docs/core/domains
- Local source of truth: `features.md`

## Executive Summary

The current platform has built the core execution backbone:

- FastAPI API
- PostgreSQL persistence
- execution state machine
- lease-based executor
- retry worker
- runtime agent
- node registration
- health checker
- status updater
- simple local UI
- Nginx deployment
- WordPress deployment with automatic MySQL database provisioning
- unified local runner

Dokploy is a mature product-level PaaS. It includes applications, Docker Compose, multiple database services, backups, Traefik routing, domains, monitoring, logs, notifications, Git providers, remote servers, and a multi-level tenancy model.

The current platform is architecturally on a reasonable path, but it is still at the "runtime execution MVP" stage. The next correct step is not to add many templates. The next step is to build the missing platform control plane: deployment step tracking, lifecycle cleanup, logs, domains/reverse proxy, persistent volumes, and secrets.

## What Dokploy Provides

Based on Dokploy's public README and docs, Dokploy provides:

- Application deployments for many languages and runtimes.
- Multiple deployment sources: GitHub, Git, Docker, and webhooks.
- Build systems including Docker, Nixpacks, Heroku Buildpacks, and Paketo Buildpacks.
- Docker Compose and Docker Stack support.
- Databases: PostgreSQL, MySQL, MariaDB, MongoDB, Redis, and related management.
- Database backups and restore flows.
- Traefik integration for routing, load balancing, domains, and HTTPS.
- Environment variable management.
- Real-time logs.
- CPU, memory, disk, and network monitoring.
- Deployment history and queued deployment cancellation.
- Remote server support and cluster support.
- Notifications through services such as Slack, Discord, Telegram, and Email.
- Multi-tenancy hierarchy: Organization -> Project -> Environment -> Service.
- Users, roles, access control, and enterprise-grade audit features.

Dokploy architecture is centered around:

- Next.js application for UI/backend.
- PostgreSQL for configuration and operational data.
- Redis for deployment queues and scheduling.
- Traefik for reverse proxy, routing, and service discovery.
- Docker/Docker Swarm for runtime orchestration.

## What We Have Built

### Platform Foundation

Implemented:

- Python/FastAPI backend.
- PostgreSQL persistence with SQLAlchemy.
- Application templates.
- Application and deployment records.
- Execution state machine.
- Lease-based executor with slot control.
- Retry worker.
- Status updater.
- Health checker.
- Runtime agent that talks to Docker.
- Node manager and compute node registration.
- Unified local runner.
- Simple server-rendered UI.

This is a good foundation. It is closer to an execution engine/control plane than a simple Docker panel.

### Deployment Runtime

Implemented:

- Nginx template deployment.
- WordPress template deployment.
- MySQL database creation for WordPress.
- Docker environment injection for WordPress DB settings.
- Runtime-agent container deployment.
- Basic container health tracking.
- Runtime agent idempotency improvements for stale containers.

Still missing:

- Real volume creation through runtime agent.
- Real database resource records and cleanup.
- Per-deployment database users and least-privilege grants.
- Full step-level UI.
- Logs and terminal access.
- Proper rollback and cleanup.

### UI

Implemented:

- Template list.
- Application creation form.
- Applications list.
- Application detail.
- Deployment detail.
- Node registration/list page.

Missing compared with Dokploy:

- Deployment logs.
- Build/runtime logs.
- Step progress timeline.
- Terminal access.
- Environment variable management screens.
- Domain management screens.
- Database management screens.
- Resource metrics.
- Settings, users, teams, and roles.

### Multi-Tenancy

Implemented:

- `tenant_id` exists in core records.

Missing compared with Dokploy:

- Organization model.
- Project model.
- Environment model.
- Service model abstraction.
- User accounts.
- RBAC.
- Invitations.
- Audit logs.
- Tenant quotas.
- Tenant-level isolation.

## Key Architectural Comparison

### Where We Are Doing It Right

1. Execution lifecycle is explicit.

   Dokploy uses Redis queues for deployment coordination. Our platform uses a persisted execution state machine with leases. That is a strong backend foundation because crash recovery and ownership are first-class concepts.

2. Runtime agent boundary is useful.

   Separating platform API/workers from compute-node Docker access is the correct direction for multi-node deployments.

3. Domain/service/repository layers are good.

   The current codebase is not just route handlers calling Docker. It has a domain layer and repository layer, which will help as the platform grows.

4. Templates are a good starting point.

   Nginx and WordPress are enough to validate the architecture before supporting arbitrary Git and Compose apps.

5. Unified local runner is useful but not a production coupling.

   Keeping workers separate internally while providing one local runner mirrors the right dev/prod split.

### Where Dokploy Is Ahead

1. Routing and domains.

   Dokploy's Traefik integration is a major product feature. It lets users attach domains and HTTPS without manual port mapping. Our platform currently relies on exposed host ports.

2. Product data model.

   Dokploy organizes resources as Organization -> Project -> Environment -> Service. Our platform has tenant/application/deployment, which is not enough for team/product workflows.

3. Git and build pipeline.

   Dokploy supports Git sources and several build types. Our platform currently deploys predefined Docker image templates.

4. Docker Compose.

   Dokploy supports Docker Compose and Docker Stack. Our multi-step templates are useful, but not equivalent to arbitrary Compose stacks.

5. Observability.

   Dokploy exposes logs and resource graphs. Our platform has health checks and logs in the process output, but not user-facing observability.

6. Managed databases.

   Dokploy supports multiple databases, backups, logs, terminal access, and resource controls. Our current database support is WordPress-specific MySQL schema provisioning.

7. Security and access control.

   Dokploy has a multi-tenant hierarchy and role model. Our platform has only `tenant_id` fields.

## Critical Gaps To Close

### P0: Make Current MVP Robust

These are required before expanding features:

- Step-level deployment records.
- Step status UI.
- Runtime logs and deployment logs.
- Failed deployment cleanup.
- Idempotent resource creation.
- Database resource tracking.
- Volume creation and cleanup.
- Secrets handling for DB passwords.
- Better runtime-agent error reporting.
- E2E tests for Nginx and WordPress.

### P1: Become A Usable Self-Hosted PaaS

These make the platform feel like Dokploy/Coolify/Render:

- Reverse proxy integration.
- Domain management.
- Automatic HTTPS.
- Generated local/free domains for development.
- Environment variable management.
- Service logs.
- Container terminal access.
- Stop/restart/delete actions.
- Deployment history and redeploy.

### P2: Become A Multi-Service Platform

These move beyond templates:

- Managed database services: PostgreSQL, MySQL/MariaDB, Redis.
- Docker Compose support.
- Git repository source support.
- Build pipeline with Dockerfile first.
- Later: Nixpacks/Buildpacks.
- Deployment queue cancellation.
- Notifications.

### P3: Become Multi-Tenant And Production-Grade

These are needed for real teams:

- Organization, Project, Environment, Service hierarchy.
- Users and authentication.
- RBAC.
- Audit logs.
- Tenant quotas.
- Remote server onboarding.
- Metrics and dashboards.
- Backup/restore.

## Recommended Next Phase

The next phase should be:

## Phase 5: Deployment Control Plane

Goal:

Turn the current working deployments into reliable, inspectable, recoverable deployment workflows.

This phase should not focus on adding many new app templates. It should make Nginx and WordPress production-shaped.

### Step 1: Deployment Step Records

Build real persistence for each deployment step:

- volume step
- database step
- container step

Use existing `deployment_step_executions` table or refine it if needed.

Each step should track:

- step id
- step name
- step type
- status: pending/running/completed/failed/skipped
- started_at
- completed_at
- result
- error_message
- linked execution_id when the step is async

Why:

Dokploy shows deployment progress and logs. Our current deployment only has execution-level visibility, and database/volume steps are mostly invisible.

### Step 2: Deployment Detail UI Upgrade

Add a proper deployment detail page:

- timeline of steps
- status per step
- error message per step
- created resource list
- Docker container name/id
- host port/public URL
- database name
- deployment logs section

Why:

This is the first user-facing control plane improvement. Without this, debugging deployments stays log-file driven.

### Step 3: Resource Lifecycle And Cleanup

Every created resource should be tracked and cleanup-capable:

- containers
- volumes
- databases
- domains later

Add cleanup behavior:

- failed deployment cleanup
- manual delete application
- manual delete deployment resources
- idempotent cleanup

Why:

Dokploy supports stop/delete actions. A PaaS must not leak containers, databases, ports, or volumes after failed deployments.

### Step 4: Runtime Agent Lifecycle API

Expand runtime agent from "deploy container" to lifecycle management:

- create/start container
- stop container
- restart container
- delete container
- inspect container
- stream/fetch logs
- create/delete volume
- list resources managed by platform

Keep sensitive env values redacted in all API responses.

Why:

This prepares for UI actions and removes direct manual Docker debugging.

### Step 5: Logs

Add logs to the deployment UI:

- execution logs from platform workers
- runtime-agent deployment result logs
- container logs from Docker

Minimum version:

- `GET /deployments/{deployment_id}/logs`
- `GET /resources/{resource_id}/logs`
- UI log panel with refresh

Why:

Dokploy's user experience depends heavily on logs. Logs are also required before Git/build deployments.

### Step 6: WordPress Hardening

Make WordPress a reference-quality template:

- real volume creation
- stable persistent volume
- MySQL connectivity validation before container step
- database resource record
- optional cleanup on failed deployment
- expose correct URL/port in UI

Open decision:

Per-deployment MySQL users require MySQL DDL (`CREATE USER`, `GRANT`). This conflicts with the previous "no raw SQL" rule unless explicitly approved for database administration. If approved, isolate it in a MySQL admin provisioner and do not spread SQL strings through the codebase.

### Step 7: E2E Tests

Add targeted tests:

- Nginx deploy success
- WordPress deploy success
- WordPress failed DB connectivity
- stale container recreate behavior
- retry worker naive/aware datetime behavior
- deployment step status transitions

## Next Phase Acceptance Criteria

Phase 5 is complete when:

- A user can deploy Nginx and see every step in the UI.
- A user can deploy WordPress and see volume/database/container steps.
- A failed deployment shows the failed step and error.
- A failed deployment can be cleaned up.
- Runtime agent can stop/restart/delete managed containers.
- WordPress deployment does not require manual Docker inspection.
- Deployment resources are not leaked after failure.
- Basic deployment logs are visible in the UI.

## What Not To Build Yet

Do not build these before Phase 5 is done:

- GitHub/Git deployment.
- Nixpacks/Buildpacks.
- Docker Compose.
- Full RBAC.
- Billing.
- Kubernetes.
- Fancy dashboard metrics.

Reason:

Those features depend on the same lifecycle primitives: step tracking, logs, cleanup, secrets, domains, and resource management. Building them now would multiply bugs.

## Phase 6: Domains And Reverse Proxy

After Phase 5, build the Dokploy-like routing layer:

- Traefik or Caddy integration.
- Domain model and UI.
- Generated local domains.
- Automatic HTTPS.
- Route to container internal port instead of exposing random host ports.
- Hot reload routing config.

This is the biggest product leap after reliable deployments.

## Phase 7: Managed Services

Add first-class services:

- MySQL service
- PostgreSQL service
- Redis service

Each should support:

- create
- stop/start/restart
- logs
- resource limits
- persistent volume
- backup placeholder
- connection info

This moves the platform closer to Dokploy's database feature set.

## Phase 8: Git And Build Deployments

Add:

- Git repository connection
- Dockerfile build
- image tagging
- deployment logs
- redeploy
- webhook trigger

Only after logs and cleanup are solid.

## Phase 9: Multi-Tenancy Product Model

Refactor from only `tenant_id` to:

- Organization
- Project
- Environment
- Service

Map existing concepts:

- Tenant -> Organization
- Application -> Service
- Deployment -> Deployment
- Template -> Service source/template

This aligns with Dokploy's model and gives a clean path to users/RBAC later.

## Architecture Direction

The current architecture should not be thrown away.

Keep:

- execution state machine
- lease-based worker model
- runtime agent boundary
- repository/service layering
- domain model approach

Improve:

- step tracking
- event logging
- runtime resource abstraction
- resource cleanup
- secrets
- UI control plane

Potential future adjustment:

Dokploy uses Redis for queues. Our PostgreSQL lease queue is acceptable for MVP and small installations. Introduce Redis/NATS only when queue throughput, delayed jobs, or event fan-out becomes a real bottleneck.

## Immediate Next Implementation Checklist

1. Add or complete `DeploymentStepExecutionRepository`. Done.
2. Create step records during orchestration before each step starts. Done.
3. Update step status for synchronous steps directly. Done.
4. Link container step to `execution_id`. Done.
5. Update status updater to reflect step/execution states. Done.
6. Add deployment steps table to UI. Done.
7. Add runtime-agent logs endpoint with safe bounds. Deferred until runtime-agent authentication exists.
8. Add container stop/restart/delete API and UI actions. Partially done: cleanup uses existing runtime-agent delete path.
9. Track volume/database resources. Pending.
10. Add cleanup path for failed deployments. Partially done: managed containers can be cleaned up.

This should be the next coding phase.

## Phase 5 Progress Update

Implemented in the first Phase 5 pass:

- Deployment step repository.
- Step records for volume/database/container orchestration.
- Synchronous step completion.
- Async container step linkage to execution records.
- Status updater reconciliation from execution state to step state.
- `/deployments/{deployment_id}/steps` API.
- Deployment UI step table.
- Basic cleanup API/UI path for managed containers.
- Documentation updates.

Deferred:

- Runtime/container logs. This needs runtime-agent authentication first because container logs can contain secrets.
- Per-deployment MySQL users. This needs explicit approval for MySQL account host scope, for example whether generated users should be created as `'user'@'%'`, `'user'@'host.docker.internal'`, or a restricted Docker network CIDR.
- Database and volume resource tracking.
- Full rollback for DB/volume/container resources.
