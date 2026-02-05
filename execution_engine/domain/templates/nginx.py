# execution_engine/domain/templates/nginx.py
"""Nginx application template - Simple static web server."""

from execution_engine.domain.models import (
    ApplicationTemplate, DeploymentStepDefinition, TemplateInputField,
    ResourceLimits, HealthCheckDefinition
)


NGINX_TEMPLATE = ApplicationTemplate(
    template_id="nginx",
    name="Nginx Web Server",
    description="Lightweight web server for serving static content",
    version="1.0",
    category="web",
    icon_url="https://nginx.org/nginx.png",
    
    database_required=False,
    database_type=None,
    
    deployment_steps=[
        DeploymentStepDefinition(
            step_id="deploy-nginx",
            step_name="Deploy Nginx Container",
            step_type="container",
            order=1,
            depends_on=[],
            spec_template={
                "image": "nginx:{{nginx_version}}",
                "name": "nginx-{{application_id_short}}",
                "ports": {"80/tcp": "{{exposed_port}}"},
                "env": {},
                "volumes": [],
                "resources": {
                    "cpu": "{{cpu_limit}}",
                    "memory": "{{memory_limit}}"
                },
                "restart_policy": "always",
                "labels": {
                    "app": "nginx",
                    "application_id": "{{application_id}}",
                }
            },
            health_check=HealthCheckDefinition(
                type="http",
                path="/",
                port=80,
                interval_seconds=10,
                timeout_seconds=5,
                retries=3,
                initial_delay_seconds=5,
            ),
            timeout_seconds=120,
            retry_on_failure=True,
            max_retries=3,
            cleanup_on_failure=True,
        ),
    ],
    
    required_inputs=[
        TemplateInputField(
            field_name="nginx_version",
            field_type="select",
            label="Nginx Version",
            description="Docker image tag",
            required=False,
            default_value="alpine",
            options=["alpine", "latest", "1.25", "1.24"],
        ),
        TemplateInputField(
            field_name="exposed_port",
            field_type="integer",
            label="Exposed Port",
            description="Port to expose Nginx on",
            required=False,
            default_value="8080",
            min_value=1024,
            max_value=65535,
        ),
        TemplateInputField(
            field_name="cpu_limit",
            field_type="select",
            label="CPU Limit",
            description="Maximum CPU cores",
            required=False,
            default_value="0.5",
            options=["0.25", "0.5", "1", "2"],
        ),
        TemplateInputField(
            field_name="memory_limit",
            field_type="select",
            label="Memory Limit",
            description="Maximum RAM",
            required=False,
            default_value="512Mi",
            options=["256Mi", "512Mi", "1Gi", "2Gi"],
        ),
    ],
    
    default_resources=ResourceLimits(
        cpu="0.5",
        memory="512Mi",
        storage="1Gi",
    ),
)