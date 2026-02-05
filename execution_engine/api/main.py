from fastapi import FastAPI
from execution_engine.api.routes.executions import router as executions_router

app = FastAPI(title="Execution Engine API")

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(executions_router)
