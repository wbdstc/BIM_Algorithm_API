from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    min_x: Mapped[float] = mapped_column(Float, nullable=False)
    max_x: Mapped[float] = mapped_column(Float, nullable=False)
    min_y: Mapped[float] = mapped_column(Float, nullable=False)
    max_y: Mapped[float] = mapped_column(Float, nullable=False)
    latest_total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_plan: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    scene_guides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active_phase_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    materials: Mapped[list["Material"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    phases: Mapped[list["Phase"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    cranes: Mapped[list["Crane"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    control_zones: Mapped[list["ControlZone"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    obstacles: Mapped[list["Obstacle"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    plan_versions: Mapped[list["PlanVersion"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectRuntimeStatus(Base):
    __tablename__ = "project_runtime_status"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), default="demo", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="demo_data", nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Phase(Base):
    __tablename__ = "phases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planned", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="phases")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    length: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    weight_tons: Mapped[float] = mapped_column(Float, nullable=False)
    handling_frequency: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    phase_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    stay_days: Mapped[float] = mapped_column(Float, default=3.0, nullable=False)
    target_zone_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="materials")


class Crane(Base):
    __tablename__ = "cranes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    max_radius: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_tons: Mapped[float] = mapped_column(Float, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="cranes")


class ControlZone(Base):
    __tablename__ = "control_zones"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(64), default="staging", nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    length: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    min_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    phase_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    blocking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    penalty_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="control_zones")


class Obstacle(Base):
    __tablename__ = "obstacles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), default="building", nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    length: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    min_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    group_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="obstacles")


class PlanVersion(Base):
    __tablename__ = "plan_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version_label: Mapped[str] = mapped_column(String(128), nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False)
    feasible_layout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    placed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unplaced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="plan_versions")
