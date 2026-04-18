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


class BoundaryPoint(BaseModel):
    x: float
    y: float


class SceneGuides(BaseModel):
    wall_envelope: EnvelopeGuide | None = None
    wall_boundary_path: list[BoundaryPoint] = Field(default_factory=list)
    building_envelopes: dict[str, EnvelopeGuide] = Field(default_factory=dict)
    recommended_road_offset: float | None = Field(default=None, ge=0)


class PhaseInput(BaseModel):
    id: str
    name: str
    sequence: int = Field(default=1, ge=1)
    objective: str | None = None
    start_day: int | None = None
    end_day: int | None = None
    status: str = "planned"


class ControlZoneInput(BaseModel):
    id: str
    name: str
    zone_type: str = "staging"
    x: float
    y: float
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    min_z: float | None = None
    max_z: float | None = None
    height: float | None = Field(default=None, ge=0)
    phase_id: str | None = None
    blocking: bool = False
    penalty_factor: float = Field(default=1.0, ge=0.0)
    notes: str | None = None


class MaterialInput(BaseModel):
    id: str
    name: str
    category: str = "general"
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    weight_tons: float = Field(gt=0)
    handling_frequency: float = Field(default=1.0, gt=0)
    phase_id: str | None = None
    batch_id: str | None = None
    priority_score: float = Field(default=1.0, gt=0)
    stay_days: float = Field(default=3.0, gt=0)
    target_zone_id: str | None = None
    notes: str | None = None
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
    phases: list[PhaseInput] = Field(default_factory=list)
    active_phase_id: str | None = None
    control_zones: list[ControlZoneInput] = Field(default_factory=list)
    obstacles: list[ObstacleInput] = Field(default_factory=list)
    materials: list[MaterialInput] = Field(default_factory=list)
    scene_guides: SceneGuides | None = None


class PlanVersionSummary(BaseModel):
    version_id: str
    version_label: str
    phase_id: str | None = None
    phase_name: str | None = None
    total_cost: float
    feasible_layout: bool
    placed_count: int
    unplaced_count: int
    created_at: str


class ProjectSnapshotResponse(ProjectSnapshotRequest):
    project_id: str
    latest_total_cost: float | None = None
    recent_plan_versions: list[PlanVersionSummary] = Field(default_factory=list)


class OptimizeProjectRequest(ProjectSnapshotRequest):
    population_size: int = Field(default=48, ge=12, le=512)
    generations: int = Field(default=80, ge=10, le=2000)
    mutation_rate: float = Field(default=0.18, ge=0.0, le=1.0)
    clearance: float = Field(default=0.8, ge=0.0)
    crane_path_penalty: float = Field(default=18.0, ge=0.0)
    zone_preference_penalty: float = Field(default=12.0, ge=0.0)
    random_seed: int | None = Field(default=42)


class CraneOption(BaseModel):
    crane_id: str
    crane_name: str
    reachable: bool
    reason: str
    distance: float | None = None
    estimated_cost: float | None = None
    path_crosses_obstacle: bool = False


class DecisionFactor(BaseModel):
    label: str
    value: str
    tone: str = "neutral"


class ActionItem(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    detail: str


class PlacementResult(BaseModel):
    material_id: str
    material_name: str
    x: float
    y: float
    z: float = 0.0
    length: float
    width: float
    height: float = Field(ge=0)
    display_color: str | None = None
    assigned_crane_id: str | None = None
    assigned_crane_name: str | None = None
    distance: float | None = None
    transport_cost: float | None = None
    phase_id: str | None = None
    batch_id: str | None = None
    priority_score: float = Field(default=1.0, gt=0)
    target_zone_id: str | None = None
    target_zone_name: str | None = None
    inside_target_zone: bool = False
    blocking_zone_hits: list[str] = Field(default_factory=list)
    decision_note: str = ""
    decision_factors: list[DecisionFactor] = Field(default_factory=list)
    crane_options: list[CraneOption] = Field(default_factory=list)
    path_crosses_obstacle: bool = False
    status: str


class OptimizationMetrics(BaseModel):
    phase_id: str | None = None
    phase_name: str | None = None
    total_cost: float
    transport_cost: float
    safety_penalty: float
    zone_penalty: float
    feasible_layout: bool
    placed_count: int
    unplaced_count: int
    in_target_zone_count: int
    generations: int
    best_fitness_history: list[float]
    warnings: list[str] = Field(default_factory=list)
    decision_summary: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


class OptimizeProjectResponse(BaseModel):
    project_id: str
    project_name: str
    phase_id: str | None = None
    phase_name: str | None = None
    placements: list[PlacementResult]
    metrics: OptimizationMetrics
    current_version: PlanVersionSummary


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
