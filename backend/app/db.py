from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bim_smart_site.db")
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    connect_args=CONNECT_ARGS,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements: list[str] = []

    if "projects" in table_names:
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        if "scene_guides" not in project_columns:
            statements.append("ALTER TABLE projects ADD COLUMN scene_guides JSON")
        if "active_phase_id" not in project_columns:
            statements.append("ALTER TABLE projects ADD COLUMN active_phase_id VARCHAR(64)")

    if "materials" in table_names:
        material_columns = {column["name"] for column in inspector.get_columns("materials")}
        if "phase_id" not in material_columns:
            statements.append("ALTER TABLE materials ADD COLUMN phase_id VARCHAR(64)")
        if "batch_id" not in material_columns:
            statements.append("ALTER TABLE materials ADD COLUMN batch_id VARCHAR(64)")
        if "priority_score" not in material_columns:
            statements.append("ALTER TABLE materials ADD COLUMN priority_score FLOAT DEFAULT 1.0")
        if "stay_days" not in material_columns:
            statements.append("ALTER TABLE materials ADD COLUMN stay_days FLOAT DEFAULT 3.0")
        if "target_zone_id" not in material_columns:
            statements.append("ALTER TABLE materials ADD COLUMN target_zone_id VARCHAR(64)")
        if "notes" not in material_columns:
            statements.append("ALTER TABLE materials ADD COLUMN notes TEXT")

    if "obstacles" in table_names:
        obstacle_columns = {column["name"] for column in inspector.get_columns("obstacles")}
        if "min_z" not in obstacle_columns:
            statements.append("ALTER TABLE obstacles ADD COLUMN min_z FLOAT")
        if "max_z" not in obstacle_columns:
            statements.append("ALTER TABLE obstacles ADD COLUMN max_z FLOAT")
        if "height" not in obstacle_columns:
            statements.append("ALTER TABLE obstacles ADD COLUMN height FLOAT")
        if "group_key" not in obstacle_columns:
            statements.append("ALTER TABLE obstacles ADD COLUMN group_key VARCHAR(128)")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
