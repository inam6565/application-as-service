from fastapi import FastAPI
import logging

from execution_engine.api.routes.applications import router as applications_router
from execution_engine.api.routes.executions import router as executions_router
from execution_engine.api.routes.nodes import router as nodes_router
from execution_engine.api.routes.ui import router as ui_router
from execution_engine.container import domain_service
from execution_engine.domain.templates import NGINX_TEMPLATE, WORDPRESS_TEMPLATE

logger = logging.getLogger(__name__)

app = FastAPI(title="Execution Engine API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def seed_builtin_templates():
    """Ensure built-in templates exist for local UI/API usage."""
    for template in (NGINX_TEMPLATE, WORDPRESS_TEMPLATE):
        try:
            if not domain_service.get_template(template.template_id):
                domain_service.register_template(template)
        except Exception as exc:
            logger.warning("Could not seed template %s: %s", template.template_id, exc)

app.include_router(applications_router)
app.include_router(executions_router)
app.include_router(nodes_router)
app.include_router(ui_router)
