from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
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
    cranes: Mapped[list["Crane"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    obstacles: Mapped[list["Obstacle"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


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
