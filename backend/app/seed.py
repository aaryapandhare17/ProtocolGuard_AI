"""Explicit development-only account provisioning; passwords come from environment."""
import os
from sqlalchemy import select
from app.core.config import settings
from app.database.store import Base, configure
from app.models.entities import User, Admin
from app.security.credentials import hash_password


def seed(factory, user_password, admin_password):
    if min(len(user_password), len(admin_password)) < 12:
        raise ValueError("Use passwords of at least 12 characters")
    if user_password == admin_password:
        raise ValueError("Use different banking and administrator passwords")
    with factory.begin() as db:
        for i in range(1, 11):
            name = f"demo{i:02}"
            if not db.scalar(select(User).where(User.username == name)):
                db.add(User(username=name, password_hash=hash_password(user_password), balance_cents=125000+i*17500))
        if not db.scalar(select(Admin).where(Admin.username == "admin")):
            db.add(Admin(username="admin", password_hash=hash_password(admin_password)))


if __name__ == "__main__":
    if settings.protocolguard_env != "development":
        raise SystemExit("Demo provisioning is allowed only in development")
    engine, factory = configure(settings.database_url)
    Base.metadata.create_all(engine)
    seed(factory, os.environ["DEMO_USER_PASSWORD"], os.environ["DEMO_ADMIN_PASSWORD"])
    print("Provisioned demo01–demo10 and admin. Existing passwords were not changed.")
