# FEATURES.md

# Application-as-a-Service Platform

## Project Goal

Provide a multi-tenant platform capable of executing application deployments through a controlled execution engine.

The system is designed to support future deployment runtimes such as:

* Docker
* Kubernetes
* Virtual Machines
* Bare Metal
* Custom Runtime Providers

while maintaining a consistent execution lifecycle.

---

# Current Development Status

Current phase:

✅ Core Execution Engine

✅ API Layer

✅ PostgreSQL Persistence

✅ Leasing & Concurrency Controls

✅ Executor Framework

🚧 Runtime Integration

🚧 Status Updater

🚧 Health Monitoring

🚧 Multi-Step Deployments

🚧 Event Bus Integration

---

# Architecture Principles

The architecture is intentionally designed around:

* Clean Architecture
* Domain Driven Design (lightweight)
* Repository Pattern
* Service Layer Pattern
* Dependency Injection
* Event Driven Design (future)
* Optimistic Concurrency
* Lease Based Ownership



---

# Core Domain

Primary domain object:

Execution

Represents a deployment or runtime operation.

Execution lifecycle:

CREATED
↓
QUEUED
↓
STARTED
↓
COMPLETED

Possible terminal states:

* COMPLETED
* FAILED
* CANCELLED

---

# Execution Engine

Location:

execution_engine/

Responsibilities:

* Store executions
* Queue executions
* Claim executions
* Start executions
* Complete executions
* Handle execution ownership
* Support crash recovery

The execution engine is runtime agnostic.

It does not know whether the execution deploys:

* Docker
* Kubernetes
* VM
* Future Runtime

It only manages lifecycle.

---

# API

Current Endpoints

## Create Execution

POST /executions

Creates a new execution.

Initial state:

CREATED

---

## Queue Execution

POST /executions/{execution_id}/queue

Transitions:

CREATED → QUEUED

---

## Health

GET /health

Basic service health endpoint.

---

# Repository Layer

Contract:

ExecutionRepository

Responsibilities:

* Create execution
* Get execution
* Update execution
* List by state
* Claim execution
* Lease renewal
* Finalization
* Recovery

Current implementation:

PostgresExecutionRepository

Future implementations:

* Redis Repository
* Event Store Repository
* DynamoDB Repository

Possible without modifying domain layer.

---

# Service Layer

ExecutionService

Responsibilities:

* Business rules
* State validation
* Lease validation
* Event generation
* Transition enforcement

The service layer is the only place allowed to enforce domain rules.

Repositories must remain persistence-only.

---

# State Machine

Execution state transitions are controlled.

Allowed:

CREATED → QUEUED

QUEUED → STARTED

STARTED → COMPLETED

STARTED → FAILED

STARTED → CANCELLED

Forbidden transitions raise domain errors.

---

# Leasing System

Purpose:

Prevent multiple executors from processing the same execution.

Mechanism:

lease_owner
lease_expires_at

Example:

worker-1 claims execution

lease_owner = worker-1

lease_expires_at = NOW()+5s

Only owner may:

* start execution
* renew lease
* complete execution

---

# Executor

Current implementation:

Executor

Responsibilities:

* Poll queued executions
* Claim execution
* Start execution
* Renew lease
* Complete execution

Executor runs independently from API.

Example:

python -m execution_engine.run_executor

---

# Slot Manager

Purpose:

Limit concurrency.

Example:

max_slots = 2

Only 2 executions may run simultaneously.

Additional queued executions wait.

---

# Crash Recovery

Current Design

Executor periodically checks:

STARTED executions

where:

lease_expires_at < NOW()

Such executions become recoverable.

Future executor may reclaim them.

Purpose:

Recover from worker crashes.

---

# Event System

Current Status

Implemented:

* Event models
* Event emitters
* Multi emitter
* Print emitter

Current usage:

Debugging and local visibility

Example events:

execution.registered

execution.queued

execution.claimed

execution.started

execution.completed

execution.failed

execution.cancelled

---

# Runtime Abstraction

Design exists.

Implementation pending.

Future contract:

RuntimeClient

Responsibilities:

deploy()

destroy()

status()

logs()

health()

Current target:

Docker Runtime

Future:

Kubernetes Runtime

---

# PostgreSQL Persistence

Current Table

executions

Columns:

execution_id

tenant_id

application_id

runtime_type

spec

state

lease_owner

lease_expires_at

started_at

finished_at

version

---

# Concurrency Control

Current strategy:

Lease-based ownership

Plus:

Optimistic versioning

Column:

version

Purpose:

Prevent lost updates.

---

# Multi-Tenancy

Current support:

tenant_id

All executions belong to a tenant.

Future:

Tenant isolation

Tenant quotas

Tenant limits

RBAC

---

# Deployment Runtime (Planned)

Docker Runtime

Will support:

* Image pull
* Container creation
* Port mapping
* Environment variables
* Resource limits

Execution example:

{
"image": "nginx:alpine",
"ports": {
"80/tcp": 8085
}
}

---

# Status Updater (Planned)

Separate process.

Responsibilities:

* Poll runtime state
* Update deployment status
* Detect failures
* Detect unhealthy containers

Recommended interval:

10 seconds

---

# Health Monitoring (Planned)

Checks:

Container Running

Container Health

Container Exit Code

Failure threshold:

3 consecutive failures

Actions:

Mark unhealthy

Auto restart (configurable)

Emit events

---

# Retry Logic (Planned)

Retries:

5

Backoff:

Exponential

10s

20s

40s

80s

160s

Retry only transient failures.

Examples:

Network errors

Registry unavailable

Docker daemon unavailable

Do not retry:

Invalid image

Invalid configuration

Permission errors

---

# Database Strategy

Current:

PostgreSQL

Planned:

Connection pooling

Read replicas

Automated backups

Point-in-time recovery

---

# Multi-Step Deployments (Planned)

Examples:

Step 1:
Create Database

Step 2:
Create Network

Step 3:
Deploy Backend

Step 4:
Deploy Frontend

Features:

Dependency graph

Rollback support

Execution tracking

Step status visibility

---

# Future Event Driven Architecture

Current system:

Database driven orchestration

Future:

Hybrid EDA

Examples:

execution.queued

execution.started

deployment.created

deployment.failed

container.unhealthy

Events may be published to:

RabbitMQ

Kafka

NATS

Consumers:

* Status updater
* Notification service
* Audit service
* Metrics service

Execution engine remains source of truth.

---

# Observability (Planned)

Metrics:

Execution count

Success rate

Failure rate

Average runtime

Lease failures

Executor utilization

Tools:

Prometheus

Grafana

OpenTelemetry

---

# Security (Planned)

RBAC

Tenant isolation

Audit logging

Secrets management

Runtime credential separation

API authentication

---

# Current Known Issue

Executor successfully:

* Detects queued executions
* Claims executions

But execution start path is failing.

Current debugging focus:

claim_execution() succeeds

start_execution() fails

Need end-to-end tracing through:

Executor
→ Service
→ Repository
→ Database

to identify exact failure point.
