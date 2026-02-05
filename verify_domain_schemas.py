"""Verify domain schema."""

from sqlalchemy import text
from execution_engine.infrastructure.postgres.database import engine


def main():
    print("🔍 Verifying Domain Schema...")
    print()
    
    with engine.connect() as conn:
        # Check tables
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        
        tables = [row[0] for row in result]
        
        print("✓ Tables created:")
        for table in tables:
            print(f"  - {table}")
        
        print()
        
        expected_tables = [
            'alembic_version',
            'application_templates',
            'applications',
            'deployment_step_executions',
            'deployments',
            'deployed_resources',
            'domains',
            'executions',
            'infrastructure_nodes',
            'provisioned_databases'
        ]
        
        missing = set(expected_tables) - set(tables)
        if missing:
            print(f"❌ Missing tables: {missing}")
        else:
            print("✅ All expected tables present!")
        
        print()
        
        # Check ENUMs
        result = conn.execute(text("""
            SELECT typname 
            FROM pg_type 
            WHERE typtype = 'e' 
            ORDER BY typname
        """))
        
        enums = [row[0] for row in result]
        
        print("✓ ENUM types created:")
        for enum in enums:
            print(f"  - {enum}")
        
        print()
        print("🎉 Domain schema verification complete!")


if __name__ == "__main__":
    main()