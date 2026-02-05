#execution_engine\domain\templates\wordpress.py

"""WordPress application template."""

from execution_engine.domain.models import (
    ApplicationTemplate, DeploymentStepDefinition, TemplateInputField,
    ResourceLimits, HealthCheckDefinition
)


WORDPRESS_TEMPLATE = ApplicationTemplate(
    template_id="wordpress",
    name="WordPress",
    description="The world's most popular CMS platform for blogs and websites",
    version="6.4",
    category="cms",
    icon_url="https://s.w.org/style/images/about/WordPress-logotype-wmark.png",
    
    database_required=True,
    database_type="mysql",
    
    deployment_steps=[
        DeploymentStepDefinition(
            step_id="create-volume",
            step_name="Create Persistent Volume",
            step_type="volume",
            order=1,
            depends_on=[],
            spec_template={
                "volume_name": "wp-data-{{application_id_short}}",
                "driver": "local",
                "labels": {
                    "application_id": "{{application_id}}",
                    "app": "wordpress"
                }
            },
            timeout_seconds=30,
        ),
        DeploymentStepDefinition(
            step_id="provision-database",
            step_name="Provision MySQL Database",
            step_type="database",
            order=2,
            depends_on=[],
            spec_template={
                "db_type": "mysql",
                "db_name": "wp_{{application_id_short}}",
                "db_user": "wp_user_{{application_id_short}}",
                "storage_size": "{{db_storage_size}}"
            },
            health_check=HealthCheckDefinition(
                type="tcp",
                port=3306,
                interval_seconds=5,
                timeout_seconds=3,
                retries=10,
                initial_delay_seconds=10,
            ),
            timeout_seconds=120,
        ),
        DeploymentStepDefinition(
            step_id="deploy-wordpress",
            step_name="Deploy WordPress Container",
            step_type="container",
            order=3,
            depends_on=["create-volume", "provision-database"],
            spec_template={
                "image": "wordpress:{{wordpress_version}}",
                "name": "wordpress-{{application_id_short}}",
                "ports": {"80/tcp": "{{exposed_port}}"},
                "env": {
                    "WORDPRESS_DB_HOST": "{{db_host}}:3306",
                    "WORDPRESS_DB_NAME": "wp_{{application_id_short}}",
                    "WORDPRESS_DB_USER": "wp_user_{{application_id_short}}",
                    "WORDPRESS_DB_PASSWORD": "{{db_password}}"
                },
                "volumes": ["wp-data-{{application_id_short}}:/var/www/html"],
                "resources": {
                    "cpu": "{{cpu_limit}}",
                    "memory": "{{memory_limit}}"
                },
                "restart_policy": "always"
            },
            health_check=HealthCheckDefinition(
                type="http",
                path="/wp-admin/install.php",
                port=80,
                interval_seconds=10,
                timeout_seconds=5,
                retries=10,
                initial_delay_seconds=30,
            ),
            timeout_seconds=300,
        ),
    ],
    
    required_inputs=[
        TemplateInputField(
            field_name="domain",
            field_type="domain",
            label="Your Domain",
            description="Domain name for your WordPress site (e.g., myblog.com)",
            required=True,
            validation_regex=r"^[a-z0-9\-\.]+\.[a-z]{2,}$",
            placeholder="myblog.com",
        ),
        TemplateInputField(
            field_name="db_host",
            field_type="string",
            label="Database Host",
            description="MySQL database host address",
            required=True,
            default_value="mysql-server.local",
            placeholder="mysql-server.local",
        ),
        TemplateInputField(
            field_name="db_password",
            field_type="password",
            label="Database Password",
            description="MySQL database password (auto-generated if not provided)",
            required=True,
        ),
        TemplateInputField(
            field_name="db_storage_size",
            field_type="select",
            label="Database Storage",
            description="Storage size for MySQL database",
            required=False,
            default_value="10",
            options=["5", "10", "20", "50"],
        ),
        TemplateInputField(
            field_name="wordpress_version",
            field_type="string",
            label="WordPress Version",
            description="Docker image tag",
            required=False,
            default_value="latest",
            placeholder="latest",
        ),
        TemplateInputField(
            field_name="cpu_limit",
            field_type="select",
            label="CPU Limit",
            description="Maximum CPU cores",
            required=False,
            default_value="1",
            options=["0.5", "1", "2", "4"],
        ),
        TemplateInputField(
            field_name="memory_limit",
            field_type="select",
            label="Memory Limit",
            description="Maximum RAM",
            required=False,
            default_value="1Gi",
            options=["512Mi", "1Gi", "2Gi", "4Gi"],
        ),
        TemplateInputField(
            field_name="exposed_port",
            field_type="integer",
            label="Exposed Port",
            description="Port to expose WordPress on",
            required=False,
            default_value="8080",
            min_value=1024,
            max_value=65535,
        ),
    ],
    
    default_resources=ResourceLimits(
        cpu="1",
        memory="1Gi",
        storage="10Gi",
    ),
)