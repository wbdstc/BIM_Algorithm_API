from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SiteBoundary(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class EnvelopeGuide(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float | None = None
    max_z: float | None = None
    height: float | None = None


class SceneGuides(BaseModel):
    wall_envelope: EnvelopeGuide | None = None
    building_envelopes: dict[str, EnvelopeGuide] = Field(default_factory=dict)
    recommended_road_offset: float | None = Field(default=None, ge=0)


class MaterialInput(BaseModel):
    id: str
    name: str
    category: str = "general"
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    weight_tons: float = Field(gt=0)
    handling_frequency: float = Field(default=1.0, gt=0)
    display_color: str | None = None


class CraneInput(BaseModel):
    id: str
    name: str
    x: float
    y: float
    max_radius: float = Field(gt=0)
    capacity_tons: float = Field(gt=0)
    priority_score: float = Field(default=1.0, gt=0)


class ObstacleInput(BaseModel):
    id: str
    name: str
    kind: str = "building"
    x: float
    y: float
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    min_z: float | None = None
    max_z: float | None = None
    height: float | None = Field(default=None, ge=0)
    group_key: str | None = None
    notes: str | None = None


class ProjectSnapshotRequest(BaseModel):
    name: str
    site_boundary: SiteBoundary
    working_cranes: list[CraneInput]
    obstacles: list[ObstacleInput] = Field(default_factory=list)
    materials: list[MaterialInput] = Field(default_factory=list)
    scene_guides: SceneGuides | None = None


class ProjectSnapshotResponse(ProjectSnapshotRequest):
    project_id: str
    latest_total_cost: float | None = None


class OptimizeProjectRequest(ProjectSnapshotRequest):
    population_size: int = Field(default=48, ge=12, le=512)
    generations: int = Field(default=80, ge=10, le=2000)
    mutation_rate: float = Field(default=0.18, ge=0.0, le=1.0)
    clearance: float = Field(default=0.8, ge=0.0)
    crane_path_penalty: float = Field(default=18.0, ge=0.0)
    random_seed: int | None = Field(default=42)


class PlacementResult(BaseModel):
    material_id: str
    material_name: str
    x: float
    y: float
    length: float
    width: float
    display_color: str | None = None
    assigned_crane_id: str | None = None
    assigned_crane_name: str | None = None
    distance: float | None = None
    transport_cost: float | None = None
    path_crosses_obstacle: bool = False
    status: str


class OptimizationMetrics(BaseModel):
    total_cost: float
    feasible_layout: bool
    placed_count: int
    unplaced_count: int
    generations: int
    best_fitness_history: list[float]
    warnings: list[str] = Field(default_factory=list)


class OptimizeProjectResponse(BaseModel):
    project_id: str
    project_name: str
    placements: list[PlacementResult]
    metrics: OptimizationMetrics


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
