"""Small server-rendered UI for local application deployments."""

import os
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import DictLoader, Environment, select_autoescape

from execution_engine.container import (
    deployment_orchestrator,
    domain_service,
    execution_service,
    node_manager_service,
)
from execution_engine.node_manager.models import InfrastructureNode, NodeType
from execution_engine.domain.models import HealthStatus, ResourceType
from runtime_agent.client import RuntimeAgentClient
from uuid import uuid4

DEFAULT_TENANT_ID = UUID(os.getenv("DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001"))

router = APIRouter(include_in_schema=False)

BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} - App as Service</title>
  <style>
    :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }
    body { margin: 0; background: #f6f7f9; color: #17202a; }
    header { background: #111827; color: #fff; padding: 14px 24px; display: flex; align-items: center; gap: 22px; }
    header a { color: #d1d5db; text-decoration: none; font-size: 14px; }
    header a.brand { color: #fff; font-weight: 700; font-size: 16px; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    h1 { font-size: 24px; margin: 0 0 18px; }
    h2 { font-size: 18px; margin: 24px 0 12px; }
    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9dee7; }
    th, td { padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: 14px; vertical-align: top; }
    th { background: #f3f4f6; color: #374151; font-weight: 600; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
    .card { background: #fff; border: 1px solid #d9dee7; border-radius: 8px; padding: 16px; }
    .muted { color: #6b7280; font-size: 13px; }
    .status { display: inline-block; padding: 3px 8px; border-radius: 999px; background: #e5e7eb; font-size: 12px; font-weight: 600; }
    .RUNNING, .HEALTHY, .COMPLETED, .READY { background: #dcfce7; color: #166534; }
    .FAILED, .UNHEALTHY, .OFFLINE { background: #fee2e2; color: #991b1b; }
    .DEPLOYING, .CREATING, .STARTING, .QUEUED, .STARTED, .CLAIMED { background: #fef3c7; color: #92400e; }
    label { display: block; font-size: 13px; color: #374151; font-weight: 600; margin: 12px 0 5px; }
    input, select, textarea { width: 100%; box-sizing: border-box; padding: 9px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font: inherit; background: #fff; }
    textarea { min-height: 78px; }
    button, .button { display: inline-block; border: 0; background: #2563eb; color: #fff; padding: 9px 12px; border-radius: 6px; text-decoration: none; font-weight: 600; cursor: pointer; }
    button.secondary, .button.secondary { background: #374151; }
    form.inline { display: inline; }
    .actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
    .error { background: #fee2e2; border: 1px solid #fecaca; color: #991b1b; padding: 10px 12px; border-radius: 6px; margin-bottom: 14px; }
    code { background: #eef2f7; padding: 2px 4px; border-radius: 4px; }
  </style>
  {% if refresh %}<meta http-equiv="refresh" content="{{ refresh }}">{% endif %}
</head>
<body>
  <header>
    <a class="brand" href="/ui/applications">App as Service</a>
    <a href="/ui/templates">Templates</a>
    <a href="/ui/applications">Applications</a>
    <a href="/ui/nodes">Nodes</a>
  </header>
  <main>{% block content %}{% endblock %}</main>
</body>
</html>
"""

TEMPLATES = {
    "base.html": BASE_TEMPLATE,
    "templates.html": """{% extends "base.html" %}{% block content %}
<h1>Templates</h1>
<div class="grid">
{% for template in templates %}
  <section class="card">
    <h2>{{ template.name }}</h2>
    <p class="muted">{{ template.description }}</p>
    <p><span class="status">{{ template.category }}</span> Version {{ template.version }}</p>
    <p class="muted">{{ template.deployment_steps|length }} deployment step(s)</p>
    <div class="actions"><a class="button" href="/ui/templates/{{ template.template_id }}/new">Create App</a></div>
  </section>
{% endfor %}
</div>
{% endblock %}""",
    "new_application.html": """{% extends "base.html" %}{% block content %}
<h1>Create {{ template.name }} Application</h1>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<form method="post" action="/ui/applications" class="card">
  <input type="hidden" name="template_id" value="{{ template.template_id }}">
  <label>Application Name</label>
  <input name="name" required placeholder="my-{{ template.template_id }}">
  <label>Description</label>
  <textarea name="description"></textarea>
  {% for field in template.required_inputs %}
    <label>{{ field.label }}{% if field.required %} *{% endif %}</label>
    {% if field.field_type == "select" and field.options %}
      <select name="input__{{ field.field_name }}" {% if field.required %}required{% endif %}>
      {% for option in field.options %}
        <option value="{{ option }}" {% if option == field.default_value %}selected{% endif %}>{{ option }}</option>
      {% endfor %}
      </select>
    {% else %}
      <input name="input__{{ field.field_name }}" value="{{ field.default_value or '' }}" placeholder="{{ field.placeholder or '' }}" {% if field.required %}required{% endif %} {% if field.field_type == "password" %}type="password"{% else %}type="text"{% endif %}>
    {% endif %}
    <p class="muted">{{ field.description }}</p>
  {% endfor %}
  <div class="actions">
    <button type="submit" name="deploy" value="true">Create & Deploy</button>
    <button type="submit" name="deploy" value="false" class="secondary">Create Only</button>
  </div>
</form>
{% endblock %}""",
    "applications.html": """{% extends "base.html" %}{% block content %}
<h1>Applications</h1>
<div class="actions"><a class="button" href="/ui/templates">Create Application</a></div>
<table>
  <thead><tr><th>Name</th><th>Template</th><th>Status</th><th>Health</th><th>Current Deployment</th><th></th></tr></thead>
  <tbody>
  {% for app in applications %}
    <tr>
      <td>{{ app.name }}<div class="muted">{{ app.application_id }}</div></td>
      <td>{{ app.template_id }} {{ app.template_version }}</td>
      <td><span class="status {{ app.status.value }}">{{ app.status.value }}</span></td>
      <td><span class="status {{ app.health_status.value }}">{{ app.health_status.value }}</span></td>
      <td>{% if app.current_deployment_id %}<a href="/ui/deployments/{{ app.current_deployment_id }}">{{ app.current_deployment_id }}</a>{% else %}-{% endif %}</td>
      <td><a href="/ui/applications/{{ app.application_id }}">Open</a></td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}""",
    "application_detail.html": """{% extends "base.html" %}{% block content %}
<h1>{{ application.name }}</h1>
<p><span class="status {{ application.status.value }}">{{ application.status.value }}</span> <span class="status {{ application.health_status.value }}">{{ application.health_status.value }}</span></p>
<div class="actions">
  <form class="inline" method="post" action="/ui/applications/{{ application.application_id }}/deploy"><button type="submit">Deploy</button></form>
  <a class="button secondary" href="/ui/applications">Back</a>
</div>
<h2>Deployments</h2>
<table>
  <thead><tr><th>Deployment</th><th>Status</th><th>Steps</th><th>Error</th></tr></thead>
  <tbody>{% for deployment in deployments %}
    <tr>
      <td><a href="/ui/deployments/{{ deployment.deployment_id }}">{{ deployment.deployment_id }}</a></td>
      <td><span class="status {{ deployment.status.value }}">{{ deployment.status.value }}</span></td>
      <td>{{ deployment.current_step_index }}/{{ deployment.total_steps }}</td>
      <td>{{ deployment.error_message or "" }}</td>
    </tr>
  {% endfor %}</tbody>
</table>
{% endblock %}""",
    "deployment_detail.html": """{% extends "base.html" %}{% block content %}
<h1>Deployment {{ deployment.deployment_id }}</h1>
<p><span class="status {{ deployment.status.value }}">{{ deployment.status.value }}</span></p>
{% if deployment.error_message %}<div class="error">{{ deployment.error_message }}</div>{% endif %}
<div class="actions">
  <form class="inline" method="post" action="/ui/deployments/{{ deployment.deployment_id }}/cleanup"><button type="submit" class="secondary">Cleanup Resources</button></form>
</div>
<h2>Steps</h2>
<table>
  <thead><tr><th>Step</th><th>Status</th><th>Execution</th><th>Duration</th><th>Error</th></tr></thead>
  <tbody>{% for step in steps %}
    <tr>
      <td>{{ step.step_name }}<div class="muted">{{ step.step_id }}</div></td>
      <td><span class="status {{ step.status.value }}">{{ step.status.value }}</span></td>
      <td>{% if step.execution_id %}<code>{{ step.execution_id }}</code>{% else %}-{% endif %}</td>
      <td>{% if step.duration_seconds %}{{ "%.1f"|format(step.duration_seconds) }}s{% else %}-{% endif %}</td>
      <td>{{ step.error_message or "" }}</td>
    </tr>
  {% endfor %}</tbody>
</table>
<h2>Executions</h2>
<table>
  <thead><tr><th>Execution</th><th>State</th><th>Runtime</th><th>Error</th></tr></thead>
  <tbody>{% for execution in executions %}
    <tr><td>{{ execution.execution_id }}</td><td><span class="status {{ execution.state.value }}">{{ execution.state.value }}</span></td><td>{{ execution.runtime_type }}</td><td>{{ execution.error_message or "" }}</td></tr>
  {% endfor %}</tbody>
</table>
<h2>Resources</h2>
<table>
  <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Health</th><th>External ID</th></tr></thead>
  <tbody>{% for resource in resources %}
    <tr><td>{{ resource.name }}</td><td>{{ resource.resource_type.value }}</td><td>{{ resource.status }}</td><td><span class="status {{ resource.health_status.value }}">{{ resource.health_status.value }}</span></td><td><code>{{ resource.external_id }}</code></td></tr>
  {% endfor %}</tbody>
</table>
{% endblock %}""",
    "nodes.html": """{% extends "base.html" %}{% block content %}
<h1>Nodes</h1>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<section class="card">
  <h2>Register Node</h2>
  <form method="post" action="/ui/nodes/register">
    <label>Name</label><input name="node_name" required>
    <label>Runtime Agent URL</label><input name="runtime_agent_url" required placeholder="http://127.0.0.1:9000">
    <label>Internal IP</label><input name="internal_ip" required value="127.0.0.1">
    <label>Public IP</label><input name="public_ip">
    <label>Total CPU</label><input name="total_cpu" value="2">
    <label>Total Memory MB</label><input name="total_memory" value="2048">
    <label>Total Storage GB</label><input name="total_storage" value="20">
    <label>Max Containers</label><input name="max_containers" value="10">
    <div class="actions"><button type="submit">Register</button></div>
  </form>
</section>
<h2>Available Nodes</h2>
<table>
  <thead><tr><th>Name</th><th>Agent</th><th>Status</th><th>Health</th><th>Capacity</th></tr></thead>
  <tbody>{% for node in nodes %}
    <tr><td>{{ node.node_name }}<div class="muted">{{ node.node_id }}</div></td><td>{{ node.runtime_agent_url }}</td><td><span class="status {{ node.status.value }}">{{ node.status.value }}</span></td><td><span class="status {{ node.health_status.value }}">{{ node.health_status.value }}</span></td><td>{{ node.active_containers }}/{{ node.max_containers }} containers</td></tr>
  {% endfor %}</tbody>
</table>
{% endblock %}""",
}

env = Environment(
    loader=DictLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "xml"]),
)


def _ui_template_view(template):
    """Return a UI-safe template view with hidden platform-managed fields removed."""
    if not template or template.template_id != "wordpress":
        return template

    hidden_fields = {"db_host", "db_password", "db_storage_size", "db_user"}
    template.required_inputs = [
        field for field in template.required_inputs if field.field_name not in hidden_fields
    ]
    return template


def render(template_name: str, **context: Any) -> HTMLResponse:
    template = env.get_template(template_name)
    return HTMLResponse(template.render(**context))


@router.get("/", response_class=HTMLResponse)
def ui_root():
    return RedirectResponse("/ui/applications", status_code=303)


@router.get("/ui/templates", response_class=HTMLResponse)
def ui_templates():
    return render("templates.html", title="Templates", templates=domain_service.list_templates())


@router.get("/ui/templates/{template_id}/new", response_class=HTMLResponse)
def ui_new_application(template_id: str):
    template = domain_service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template = _ui_template_view(template)
    return render("new_application.html", title="Create Application", template=template, error=None)


@router.post("/ui/applications")
async def ui_create_application(request: Request):
    form = await request.form()
    template_id = str(form.get("template_id"))
    name = str(form.get("name") or "")
    description = str(form.get("description") or "")
    deploy = form.get("deploy") == "true"
    user_inputs: Dict[str, Any] = {
        key.removeprefix("input__"): value
        for key, value in form.items()
        if key.startswith("input__")
    }
    if template_id == "wordpress":
        user_inputs = {
            key: value
            for key, value in user_inputs.items()
            if key not in {"db_host", "db_password", "db_storage_size", "db_user"}
        }

    try:
        application = domain_service.create_application(
            tenant_id=DEFAULT_TENANT_ID,
            template_id=template_id,
            name=name,
            user_inputs=user_inputs,
            description=description,
        )
        if deploy:
            deployment = domain_service.create_deployment(application.application_id)
            deployment_orchestrator.start_deployment(deployment.deployment_id)
            return RedirectResponse(f"/ui/deployments/{deployment.deployment_id}", status_code=303)
        return RedirectResponse(f"/ui/applications/{application.application_id}", status_code=303)
    except Exception as exc:
        template = domain_service.get_template(template_id)
        template = _ui_template_view(template) if template else template
        return render("new_application.html", title="Create Application", template=template, error=str(exc))


@router.get("/ui/applications", response_class=HTMLResponse)
def ui_applications():
    applications = domain_service.list_applications(DEFAULT_TENANT_ID)
    return render("applications.html", title="Applications", applications=applications)


@router.get("/ui/applications/{application_id}", response_class=HTMLResponse)
def ui_application_detail(application_id: UUID):
    application = domain_service.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    deployments = domain_service.list_application_deployments(application_id)
    return render("application_detail.html", title=application.name, application=application, deployments=deployments)


@router.post("/ui/applications/{application_id}/deploy")
def ui_deploy_application(application_id: UUID):
    deployment = domain_service.create_deployment(application_id)
    deployment_orchestrator.start_deployment(deployment.deployment_id)
    return RedirectResponse(f"/ui/deployments/{deployment.deployment_id}", status_code=303)


@router.get("/ui/deployments/{deployment_id}", response_class=HTMLResponse)
def ui_deployment_detail(deployment_id: UUID):
    deployment = domain_service.get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    executions = execution_service.list_deployment_executions(deployment_id)
    resources = domain_service.list_deployment_resources(deployment_id)
    steps = domain_service.list_deployment_steps(deployment_id)
    return render("deployment_detail.html", title="Deployment", deployment=deployment, steps=steps, executions=executions, resources=resources, refresh=5)


@router.post("/ui/deployments/{deployment_id}/cleanup")
def ui_cleanup_deployment(deployment_id: UUID):
    resources = domain_service.list_deployment_resources(deployment_id)
    for resource in resources:
        if resource.resource_type != ResourceType.CONTAINER or resource.external_id == "pending":
            continue

        agent_url = resource.spec.get("deployment_result", {}).get("agent_url")
        if not agent_url:
            continue

        client = RuntimeAgentClient(agent_url)
        if client.remove_container(resource.external_id, force=True):
            resource.status = "removed"
            resource.health_status = HealthStatus.UNKNOWN
            domain_service.update_deployment_resource(resource)
    return RedirectResponse(f"/ui/deployments/{deployment_id}", status_code=303)


@router.get("/ui/nodes", response_class=HTMLResponse)
def ui_nodes(error: str | None = None):
    nodes = node_manager_service.list_available_nodes()
    return render("nodes.html", title="Nodes", nodes=nodes, error=error)


@router.post("/ui/nodes/register")
def ui_register_node(
    node_name: str = Form(...),
    runtime_agent_url: str = Form(...),
    internal_ip: str = Form(...),
    public_ip: str = Form(""),
    total_cpu: float = Form(2),
    total_memory: int = Form(2048),
    total_storage: int = Form(20),
    max_containers: int = Form(10),
):
    try:
        node = InfrastructureNode(
            node_id=uuid4(),
            node_name=node_name,
            node_type=NodeType.APP_NODE,
            internal_ip=internal_ip,
            public_ip=public_ip or None,
            runtime_agent_url=runtime_agent_url,
            supported_runtimes=["docker"],
            total_cpu=total_cpu,
            total_memory=total_memory,
            total_storage=total_storage,
            available_cpu=total_cpu,
            available_memory=total_memory,
            available_storage=total_storage,
            max_containers=max_containers,
            active_containers=0,
        )
        node_manager_service.register_node(node)
        return RedirectResponse("/ui/nodes", status_code=303)
    except Exception as exc:
        return ui_nodes(error=str(exc))
