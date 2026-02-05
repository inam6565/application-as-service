# Execution Engine Setup

## 1. Install Dependencies
```bash
pip install -r requirements.txt
```

## 2. Configure Environment

Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

## 3. Initialize Database
```bash
# Create database
createdb execution_engine

# Run migrations
alembic upgrade head
```

## 4. Verify Setup
```python
from execution_engine.infrastructure.postgres.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SELECT version()"))
    print(result.fetchone())
```

## 5. Run Tests
```bash
pytest tests/ -v --cov=execution_engine
```

## 6. Create New Migration
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```