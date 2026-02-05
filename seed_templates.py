"""Seed database with application templates."""

from execution_engine.domain.templates import WORDPRESS_TEMPLATE
from execution_engine.infrastructure.postgres.domain_repository import ApplicationTemplateRepository


def main():
    print("🌱 Seeding application templates...")
    print()
    
    repo = ApplicationTemplateRepository()
    
    # WordPress
    try:
        repo.create(WORDPRESS_TEMPLATE)
        print(f"✅ Created WordPress template")
    except Exception as e:
        print(f"⚠️  WordPress template already exists or error: {e}")
    
    print()
    print("🎉 Template seeding complete!")
    
    # List templates
    templates = repo.list_active()
    print()
    print(f"📋 Available templates: {len(templates)}")
    for template in templates:
        print(f"  - {template.template_id}: {template.name} v{template.version}")


if __name__ == "__main__":
    main()