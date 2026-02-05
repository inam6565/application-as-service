"""Clean up test data from database."""

from sqlalchemy import text
from execution_engine.infrastructure.postgres.database import engine


def main():
    print("🧹 Cleaning up test data...")
    print()
    
    with engine.connect() as conn:
        # Clean up in reverse order of foreign keys
        tables = [
            "deployment_step_executions",
            "deployed_resources",
            "deployments",
            "applications",
            "provisioned_databases",
            "domains",
            "executions",
            "infrastructure_nodes",
        ]
        
        for table in tables:
            result = conn.execute(text(f"DELETE FROM {table}"))
            conn.commit()
            print(f"   Cleaned {table}: {result.rowcount} rows deleted")
    
    print()
    print("✅ Cleanup complete!")


if __name__ == "__main__":
    main()