from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from .. import models, schemas
from .scene_calibration import estimate_safe_transport_height, normalize_snapshot_payload


BLOCKING_ZONE_TYPES = {"keep_clear", "emergency_access", "delivery_lane", "no_stack"}
CONTROL_ZONE_OBSTACLE_CLEARANCE = 0.2
CONTROL_ZONE_MIN_LENGTH = 6.0
CONTROL_ZONE_MIN_WIDTH = 3.0
CONTROL_ZONE_PRIORITY = {
    "zone-north-staging": 0,
    "zone-west-buffer": 1,
    "zone-south-delivery": 2,
    "zone-east-emergency": 3,
    "zone-mep-buffer": 4,
}


@dataclass(frozen=True)
class Box3D:
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float


@dataclass(frozen=True)
class CraneChoice:
    crane_id: str
    crane_name: str
    distance: float
    cost: float
    path_crosses_obstacle: bool
    travel_height: float


class LayoutOptimizerService:
    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed

    def serialize_project(self, db: Session, project: models.Project) -> schemas.ProjectSnapshotResponse:
        phases = sorted(project.phases, key=lambda item: (item.sequence, item.name))
        phase_name_map = {phase.id: phase.name for phase in phases}
        scene_guides = (
            schemas.SceneGuides.model_validate(project.scene_guides)
            if project.scene_guides
            else None
        )
        site_boundary = schemas.SiteBoundary(
            min_x=project.min_x,
            max_x=project.max_x,
            min_y=project.min_y,
            max_y=project.max_y,
        )
        obstacle_inputs = [
            schemas.ObstacleInput(
                id=obstacle.id,
                name=obstacle.name,
                kind=obstacle.kind,
                x=obstacle.x,
                y=obstacle.y,
                length=obstacle.length,
                width=obstacle.width,
                min_z=obstacle.min_z,
                max_z=obstacle.max_z,
                height=obstacle.height,
                group_key=obstacle.group_key,
                notes=obstacle.notes,
            )
            for obstacle in sorted(project.obstacles, key=lambda item: item.name)
        ]
        site_polygon = (
            scene_guides.wall_boundary_path
            if scene_guides and len(scene_guides.wall_boundary_path) >= 3
            else None
        )
        control_zone_inputs = self._sanitize_control_zones(
            [
                schemas.ControlZoneInput(
                    id=zone.id,
                    name=zone.name,
                    zone_type=zone.zone_type,
                    x=zone.x,
                    y=zone.y,
                    length=zone.length,
                    width=zone.width,
                    min_z=zone.min_z,
                    max_z=zone.max_z,
                    height=zone.height,
                    phase_id=zone.phase_id,
                    blocking=zone.blocking,
                    penalty_factor=zone.penalty_factor,
                    notes=zone.notes,
                )
                for zone in sorted(project.control_zones, key=lambda item: (item.phase_id or "", item.name))
            ],
            site_boundary,
            site_polygon,
            obstacle_inputs,
        )
        active_phase_id = self._resolve_active_phase_id(
            [
                schemas.PhaseInput(
                    id=phase.id,
                    name=phase.name,
                    sequence=phase.sequence,
                    objective=phase.objective,
                    start_day=phase.start_day,
                    end_day=phase.end_day,
                    status=phase.status,
                )
                for phase in phases
            ],
            project.active_phase_id,
        )
        recent_plan_versions = (
            db.query(models.PlanVersion)
            .filter(models.PlanVersion.project_id == project.id)
            .order_by(models.PlanVersion.created_at.desc())
            .limit(6)
            .all()
        )

        snapshot = schemas.ProjectSnapshotResponse(
            project_id=project.id,
            name=project.name,
            site_boundary=site_boundary,
            phases=[
                schemas.PhaseInput(
                    id=phase.id,
                    name=phase.name,
                    sequence=phase.sequence,
                    objective=phase.objective,
                    start_day=phase.start_day,
                    end_day=phase.end_day,
                    status=phase.status,
                )
                for phase in phases
            ],
            active_phase_id=active_phase_id,
            control_zones=control_zone_inputs,
            scene_guides=scene_guides,
            working_cranes=[
                schemas.CraneInput(
                    id=crane.id,
                    name=crane.name,
                    x=crane.x,
                    y=crane.y,
                    max_radius=crane.max_radius,
                    capacity_tons=crane.capacity_tons,
                    priority_score=crane.priority_score,
                )
                for crane in sorted(project.cranes, key=lambda item: item.name)
            ],
            obstacles=obstacle_inputs,
            materials=[
                schemas.MaterialInput(
                    id=material.id,
                    name=material.name,
                    category=material.category,
                    length=material.length,
                    width=material.width,
                    height=material.height,
                    weight_tons=material.weight_tons,
                    handling_frequency=material.handling_frequency,
                    phase_id=material.phase_id,
                    batch_id=material.batch_id,
                    priority_score=material.priority_score,
                    stay_days=material.stay_days,
                    target_zone_id=material.target_zone_id,
                    notes=material.notes,
                    display_color=material.display_color,
                )
                for material in sorted(project.materials, key=lambda item: item.name)
            ],
            latest_total_cost=project.latest_total_cost,
            recent_plan_versions=[
                self._serialize_plan_version_summary(version, phase_name_map)
                for version in recent_plan_versions
            ],
            latest_optimization_result=(
                recent_plan_versions[0].response_payload
                if recent_plan_versions
                else None
            ),
            bim_data_status=self.serialize_bim_data_status(db, project.id, project=project),
        )
        return normalize_snapshot_payload(snapshot)

    def serialize_bim_data_status(
        self,
        db: Session,
        project_id: str,
        *,
        project: models.Project | None = None,
    ) -> schemas.BimDataStatus:
        runtime_status = db.get(models.ProjectRuntimeStatus, project_id)
        if runtime_status is not None:
            return self._serialize_bim_data_status_record(runtime_status)

        inferred_project = project or db.get(models.Project, project_id)
        if inferred_project is not None and (inferred_project.obstacles or inferred_project.cranes):
            inferred_updated_at = self._isoformat(inferred_project.updated_at)
            return schemas.BimDataStatus(
                state="live",
                source="realtime_snapshot",
                message="实时快照已加载",
                detail="未发现单独的启动状态记录，已根据后端现有项目快照推断为实时数据。",
                last_sync_success_at=inferred_updated_at,
                snapshot_updated_at=inferred_updated_at,
            )

        return schemas.BimDataStatus(
            state="demo",
            source="demo_data",
            message="未加载实时 BIM 快照，当前使用 demo 数据",
            detail="后端尚未收到启动同步结果，前端会继续使用本地 demo 场景。",
        )

    def upsert_bim_data_status(
        self,
        db: Session,
        project_id: str,
        payload: schemas.BimDataStatusUpdateRequest,
    ) -> schemas.BimDataStatus:
        runtime_status = db.get(models.ProjectRuntimeStatus, project_id)
        if runtime_status is None:
            runtime_status = models.ProjectRuntimeStatus(
                project_id=project_id,
                state="demo",
                source="demo_data",
                message="未加载实时 BIM 快照，当前使用 demo 数据",
            )

        now = datetime.now(UTC)
        runtime_status.state = payload.state
        runtime_status.source = payload.source
        runtime_status.message = payload.message
        runtime_status.detail = payload.detail
        runtime_status.last_sync_attempt_at = now

        if payload.state == "live":
            runtime_status.snapshot_updated_at = now
            runtime_status.last_sync_success_at = now
            runtime_status.last_sync_error = None
        elif payload.state == "syncing":
            runtime_status.last_sync_error = None
        else:
            runtime_status.last_sync_error = payload.last_sync_error

        db.add(runtime_status)
        db.commit()
        db.refresh(runtime_status)
        return self._serialize_bim_data_status_record(runtime_status)

    def upsert_project_snapshot(
        self,
        db: Session,
        project_id: str,
        payload: schemas.ProjectSnapshotRequest,
    ) -> models.Project:
        payload = normalize_snapshot_payload(payload)
        site_polygon = (
            payload.scene_guides.wall_boundary_path
            if payload.scene_guides and len(payload.scene_guides.wall_boundary_path) >= 3
            else None
        )
        payload = payload.model_copy(
            update={
                "control_zones": self._sanitize_control_zones(
                    payload.control_zones,
                    payload.site_boundary,
                    site_polygon,
                    payload.obstacles,
                )
            }
        )
        active_phase_id = self._resolve_active_phase_id(payload.phases, payload.active_phase_id)

        project = db.get(models.Project, project_id)
        if project is None:
            project = models.Project(
                id=project_id,
                name=payload.name,
                min_x=payload.site_boundary.min_x,
                max_x=payload.site_boundary.max_x,
                min_y=payload.site_boundary.min_y,
                max_y=payload.site_boundary.max_y,
                scene_guides=payload.scene_guides.model_dump() if payload.scene_guides else None,
                active_phase_id=active_phase_id,
            )
        else:
            project.name = payload.name
            project.min_x = payload.site_boundary.min_x
            project.max_x = payload.site_boundary.max_x
            project.min_y = payload.site_boundary.min_y
            project.max_y = payload.site_boundary.max_y
            project.scene_guides = payload.scene_guides.model_dump() if payload.scene_guides else None
            project.active_phase_id = active_phase_id

        db.add(project)
        db.flush()

        db.query(models.Material).filter(models.Material.project_id == project.id).delete()
        db.query(models.Phase).filter(models.Phase.project_id == project.id).delete()
        db.query(models.Crane).filter(models.Crane.project_id == project.id).delete()
        db.query(models.ControlZone).filter(models.ControlZone.project_id == project.id).delete()
        db.query(models.Obstacle).filter(models.Obstacle.project_id == project.id).delete()
        db.flush()

        project.phases = [
            models.Phase(
                id=item.id,
                name=item.name,
                sequence=item.sequence,
                objective=item.objective,
                start_day=item.start_day,
                end_day=item.end_day,
                status=item.status,
            )
            for item in payload.phases
        ]
        project.materials = [
            models.Material(
                id=item.id,
                name=item.name,
                category=item.category,
                length=item.length,
                width=item.width,
                height=item.height,
                weight_tons=item.weight_tons,
                handling_frequency=item.handling_frequency,
                phase_id=item.phase_id,
                batch_id=item.batch_id,
                priority_score=item.priority_score,
                stay_days=item.stay_days,
                target_zone_id=item.target_zone_id,
                notes=item.notes,
                display_color=item.display_color,
            )
            for item in payload.materials
        ]
        project.cranes = [
            models.Crane(
                id=item.id,
                name=item.name,
                x=item.x,
                y=item.y,
                max_radius=item.max_radius,
                capacity_tons=item.capacity_tons,
                priority_score=item.priority_score,
            )
            for item in payload.working_cranes
        ]
        project.control_zones = [
            models.ControlZone(
                id=item.id,
                name=item.name,
                zone_type=item.zone_type,
                x=item.x,
                y=item.y,
                length=item.length,
                width=item.width,
                min_z=item.min_z,
                max_z=item.max_z,
                height=item.height,
                phase_id=item.phase_id,
                blocking=item.blocking,
                penalty_factor=item.penalty_factor,
                notes=item.notes,
            )
            for item in payload.control_zones
        ]
        project.obstacles = [
            models.Obstacle(
                id=item.id,
                name=item.name,
                kind=item.kind,
                x=item.x,
                y=item.y,
                length=item.length,
                width=item.width,
                min_z=item.min_z,
                max_z=item.max_z,
                height=item.height,
                group_key=item.group_key,
                notes=item.notes,
            )
            for item in payload.obstacles
        ]

        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def optimize_project(
        self,
        db: Session,
        project: models.Project,
        payload: schemas.OptimizeProjectRequest,
    ) -> schemas.OptimizeProjectResponse:
        payload = normalize_snapshot_payload(payload)
        site_polygon = (
            payload.scene_guides.wall_boundary_path
            if payload.scene_guides and len(payload.scene_guides.wall_boundary_path) >= 3
            else None
        )
        payload = payload.model_copy(
            update={
                "control_zones": self._sanitize_control_zones(
                    payload.control_zones,
                    payload.site_boundary,
                    site_polygon,
                    payload.obstacles,
                )
            }
        )
        active_phase_id = self._resolve_active_phase_id(payload.phases, payload.active_phase_id)
        active_phase = next((phase for phase in payload.phases if phase.id == active_phase_id), None)
        phase_name = active_phase.name if active_phase else None
        phase_materials = self._select_phase_materials(payload.materials, payload.phases, active_phase_id)
        active_control_zones = [
            zone for zone in payload.control_zones if self._zone_applies(zone, active_phase_id)
        ]
        phase_name_map = {phase.id: phase.name for phase in payload.phases}

        if not phase_materials:
            return self._build_empty_phase_response(
                db=db,
                project=project,
                phase_id=active_phase_id,
                phase_name=phase_name,
                phase_name_map=phase_name_map,
            )

        rng = random.Random(payload.random_seed if payload.random_seed is not None else self.seed)
        safe_transport_height = estimate_safe_transport_height(payload.obstacles)
        obstacle_boxes = [
            self._box_from_obstacle(obstacle, payload.clearance)
            for obstacle in payload.obstacles
        ]
        blocking_zone_pairs = [
            (zone, self._box_from_control_zone(zone, payload.clearance))
            for zone in active_control_zones
            if zone.blocking or zone.zone_type in BLOCKING_ZONE_TYPES
        ]
        reserved_boxes = obstacle_boxes + [box for _, box in blocking_zone_pairs]
        target_zone_map = {zone.id: zone for zone in active_control_zones}

        population = [
            self._build_candidate_solution(
                rng=rng,
                materials=phase_materials,
                boundary=payload.site_boundary,
                site_polygon=site_polygon,
                reserved_boxes=reserved_boxes,
                clearance=payload.clearance,
            )
            for _ in range(payload.population_size)
        ]

        elite_count = max(2, int(payload.population_size * 0.2))
        best_solution = population[0]
        best_eval: dict | None = None
        best_history: list[float] = []

        for _ in range(payload.generations):
            scored_population: list[tuple[float, list[tuple[float, float]], dict]] = []
            for solution in population:
                evaluation = self._evaluate_solution(
                    solution=solution,
                    materials=phase_materials,
                    cranes=payload.working_cranes,
                    boundary=payload.site_boundary,
                    site_polygon=site_polygon,
                    obstacle_boxes=obstacle_boxes,
                    control_zones=active_control_zones,
                    blocking_zone_pairs=blocking_zone_pairs,
                    target_zone_map=target_zone_map,
                    clearance=payload.clearance,
                    crane_path_penalty=payload.crane_path_penalty,
                    zone_preference_penalty=payload.zone_preference_penalty,
                    safe_transport_height=safe_transport_height,
                    phase_id=active_phase_id,
                    phase_name=phase_name,
                )
                scored_population.append((evaluation["fitness"], solution, evaluation))

            scored_population.sort(key=lambda item: item[0])
            best_history.append(round(scored_population[0][0], 3))

            if best_eval is None or scored_population[0][0] < best_eval["fitness"]:
                best_solution = list(scored_population[0][1])
                best_eval = scored_population[0][2]

            next_population = [list(solution) for _, solution, _ in scored_population[:elite_count]]
            while len(next_population) < payload.population_size:
                parent_a = self._tournament_select(rng, scored_population)
                parent_b = self._tournament_select(rng, scored_population)
                child = self._crossover(
                    rng=rng,
                    parent_a=parent_a,
                    parent_b=parent_b,
                    materials=phase_materials,
                    boundary=payload.site_boundary,
                    clearance=payload.clearance,
                )
                child = self._mutate(
                    rng=rng,
                    solution=child,
                    materials=phase_materials,
                    boundary=payload.site_boundary,
                    mutation_rate=payload.mutation_rate,
                    clearance=payload.clearance,
                )
                next_population.append(child)
            population = next_population

        if best_eval is None:
            best_eval = self._evaluate_solution(
                solution=best_solution,
                materials=phase_materials,
                cranes=payload.working_cranes,
                boundary=payload.site_boundary,
                site_polygon=site_polygon,
                obstacle_boxes=obstacle_boxes,
                control_zones=active_control_zones,
                blocking_zone_pairs=blocking_zone_pairs,
                target_zone_map=target_zone_map,
                clearance=payload.clearance,
                crane_path_penalty=payload.crane_path_penalty,
                zone_preference_penalty=payload.zone_preference_penalty,
                safe_transport_height=safe_transport_height,
                phase_id=active_phase_id,
                phase_name=phase_name,
            )

        response = schemas.OptimizeProjectResponse(
            project_id=project.id,
            project_name=project.name,
            phase_id=active_phase_id,
            phase_name=phase_name,
            placements=[schemas.PlacementResult(**placement) for placement in best_eval["placements"]],
            metrics=schemas.OptimizationMetrics(
                phase_id=active_phase_id,
                phase_name=phase_name,
                total_cost=round(best_eval["total_cost"], 3),
                transport_cost=round(best_eval["transport_cost"], 3),
                safety_penalty=round(best_eval["safety_penalty"], 3),
                zone_penalty=round(best_eval["zone_penalty"], 3),
                feasible_layout=best_eval["feasible_layout"],
                placed_count=best_eval["placed_count"],
                unplaced_count=best_eval["unplaced_count"],
                in_target_zone_count=best_eval["in_target_zone_count"],
                generations=payload.generations,
                best_fitness_history=best_history,
                warnings=best_eval["warnings"],
                decision_summary=best_eval["decision_summary"],
                action_items=[schemas.ActionItem(**item) for item in best_eval["action_items"]],
            ),
            current_version=schemas.PlanVersionSummary(
                version_id="pending",
                version_label="pending",
                phase_id=active_phase_id,
                phase_name=phase_name,
                total_cost=round(best_eval["total_cost"], 3),
                feasible_layout=best_eval["feasible_layout"],
                placed_count=best_eval["placed_count"],
                unplaced_count=best_eval["unplaced_count"],
                created_at=datetime.now(UTC).isoformat(),
            ),
        )

        current_version = self._persist_plan_version(
            db=db,
            project=project,
            response=response,
            phase_id=active_phase_id,
            phase_name_map=phase_name_map,
        )
        response.current_version = current_version
        return response

    def _build_empty_phase_response(
        self,
        db: Session,
        project: models.Project,
        phase_id: str | None,
        phase_name: str | None,
        phase_name_map: dict[str, str],
    ) -> schemas.OptimizeProjectResponse:
        response = schemas.OptimizeProjectResponse(
            project_id=project.id,
            project_name=project.name,
            phase_id=phase_id,
            phase_name=phase_name,
            placements=[],
            metrics=schemas.OptimizationMetrics(
                phase_id=phase_id,
                phase_name=phase_name,
                total_cost=0.0,
                transport_cost=0.0,
                safety_penalty=0.0,
                zone_penalty=0.0,
                feasible_layout=False,
                placed_count=0,
                unplaced_count=0,
                in_target_zone_count=0,
                generations=0,
                best_fitness_history=[],
                warnings=["当前阶段还没有分配待复核物料，暂未生成场布方案。"],
                decision_summary=[
                    f"当前复核范围：{phase_name or '当前阶段'}。",
                    "未执行场布计算，因为当前阶段没有可参与复核的物料批次。",
                ],
                action_items=[
                    schemas.ActionItem(
                        id=f"phase-empty-{phase_id or 'all'}",
                        category="phase",
                        severity="medium",
                        title="先给当前阶段分配物料批次",
                        detail="至少补充一批当前阶段物料后，再生成场布和吊运复核结果。",
                    )
                ],
            ),
            current_version=schemas.PlanVersionSummary(
                version_id="pending",
                version_label="pending",
                phase_id=phase_id,
                phase_name=phase_name,
                total_cost=0.0,
                feasible_layout=False,
                placed_count=0,
                unplaced_count=0,
                created_at=datetime.now(UTC).isoformat(),
            ),
        )
        current_version = self._persist_plan_version(
            db=db,
            project=project,
            response=response,
            phase_id=phase_id,
            phase_name_map=phase_name_map,
        )
        response.current_version = current_version
        return response

    def _persist_plan_version(
        self,
        db: Session,
        project: models.Project,
        response: schemas.OptimizeProjectResponse,
        phase_id: str | None,
        phase_name_map: dict[str, str],
    ) -> schemas.PlanVersionSummary:
        version_id = f"plan-{uuid.uuid4().hex[:12]}"
        existing_count = (
            db.query(models.PlanVersion)
            .filter(
                models.PlanVersion.project_id == project.id,
                models.PlanVersion.phase_id == phase_id,
            )
            .count()
        )
        phase_sequence = next(
            (phase.sequence for phase in project.phases if phase.id == phase_id),
            0,
        )
        version_label = f"P{phase_sequence or 0:02d}-V{existing_count + 1:02d}"
        plan_version = models.PlanVersion(
            id=version_id,
            project_id=project.id,
            phase_id=phase_id,
            version_label=version_label,
            total_cost=response.metrics.total_cost,
            feasible_layout=response.metrics.feasible_layout,
            placed_count=response.metrics.placed_count,
            unplaced_count=response.metrics.unplaced_count,
            response_payload=response.model_dump(mode="json"),
        )

        project.latest_total_cost = response.metrics.total_cost
        project.latest_plan = [item.model_dump(mode="json") for item in response.placements]
        project.active_phase_id = phase_id

        db.add(plan_version)
        db.add(project)
        db.commit()
        db.refresh(plan_version)
        db.refresh(project)

        return self._serialize_plan_version_summary(plan_version, phase_name_map)

    def _serialize_plan_version_summary(
        self,
        version: models.PlanVersion,
        phase_name_map: dict[str, str],
    ) -> schemas.PlanVersionSummary:
        created_at = version.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return schemas.PlanVersionSummary(
            version_id=version.id,
            version_label=version.version_label,
            phase_id=version.phase_id,
            phase_name=phase_name_map.get(version.phase_id),
            total_cost=version.total_cost,
            feasible_layout=version.feasible_layout,
            placed_count=version.placed_count,
            unplaced_count=version.unplaced_count,
            created_at=created_at.isoformat(),
        )

    def _serialize_bim_data_status_record(
        self,
        runtime_status: models.ProjectRuntimeStatus,
    ) -> schemas.BimDataStatus:
        return schemas.BimDataStatus(
            state=runtime_status.state,
            source=runtime_status.source,
            message=runtime_status.message,
            detail=runtime_status.detail,
            last_sync_error=runtime_status.last_sync_error,
            last_sync_attempt_at=self._isoformat(runtime_status.last_sync_attempt_at),
            last_sync_success_at=self._isoformat(runtime_status.last_sync_success_at),
            snapshot_updated_at=self._isoformat(runtime_status.snapshot_updated_at),
        )

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()

    @staticmethod
    def _resolve_active_phase_id(
        phases: list[schemas.PhaseInput],
        active_phase_id: str | None,
    ) -> str | None:
        if not phases:
            return None
        if active_phase_id and any(phase.id == active_phase_id for phase in phases):
            return active_phase_id
        return sorted(phases, key=lambda item: (item.sequence, item.name))[0].id

    @staticmethod
    def _select_phase_materials(
        materials: list[schemas.MaterialInput],
        phases: list[schemas.PhaseInput],
        active_phase_id: str | None,
    ) -> list[schemas.MaterialInput]:
        if not phases or active_phase_id is None:
            return materials
        return [material for material in materials if material.phase_id == active_phase_id]

    @staticmethod
    def _zone_applies(zone: schemas.ControlZoneInput, active_phase_id: str | None) -> bool:
        return zone.phase_id is None or zone.phase_id == active_phase_id

    def _sanitize_control_zones(
        self,
        control_zones: list[schemas.ControlZoneInput],
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        obstacles: list[schemas.ObstacleInput],
    ) -> list[schemas.ControlZoneInput]:
        blocked_boxes = [
            self._box_from_obstacle(obstacle, CONTROL_ZONE_OBSTACLE_CLEARANCE)
            for obstacle in obstacles
            if obstacle.kind != "crane"
        ]
        occupied_zone_boxes: list[Box3D] = []
        sanitized_by_id: dict[str, schemas.ControlZoneInput] = {}

        for zone in sorted(
            control_zones,
            key=lambda item: (CONTROL_ZONE_PRIORITY.get(item.id, 999), item.phase_id or "", item.id),
        ):
            adjusted = self._find_feasible_control_zone(
                zone=zone,
                boundary=boundary,
                site_polygon=site_polygon,
                obstacles=obstacles,
                blocked_boxes=blocked_boxes,
                occupied_zone_boxes=occupied_zone_boxes,
            )
            sanitized_by_id[zone.id] = adjusted
            occupied_zone_boxes.append(self._box_from_control_zone(adjusted))

        return [sanitized_by_id[zone.id] for zone in control_zones if zone.id in sanitized_by_id]

    def _find_feasible_control_zone(
        self,
        zone: schemas.ControlZoneInput,
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        obstacles: list[schemas.ObstacleInput],
        blocked_boxes: list[Box3D],
        occupied_zone_boxes: list[Box3D],
    ) -> schemas.ControlZoneInput:
        dimension_profiles = self._control_zone_dimension_profiles(zone)

        for length, width in dimension_profiles:
            candidate = zone.model_copy(update={"length": length, "width": width})
            positioned = self._position_control_zone(
                candidate,
                boundary,
                site_polygon,
                obstacles,
                blocked_boxes,
                occupied_zone_boxes,
            )
            if positioned is not None:
                return positioned

        fallback_length, fallback_width = dimension_profiles[-1]
        fallback_zone = zone.model_copy(update={"length": fallback_length, "width": fallback_width})
        return self._clamp_control_zone_center(fallback_zone, boundary)

    def _control_zone_dimension_profiles(
        self,
        zone: schemas.ControlZoneInput,
    ) -> list[tuple[float, float]]:
        min_length = min(zone.length, CONTROL_ZONE_MIN_LENGTH)
        min_width = min(zone.width, CONTROL_ZONE_MIN_WIDTH)
        profiles: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()

        def add_profile(length: float, width: float) -> None:
            profile = (round(length, 3), round(width, 3))
            if profile in seen:
                return
            seen.add(profile)
            profiles.append(profile)

        add_profile(zone.length, zone.width)
        for factor in (0.92, 0.84, 0.76, 0.68, 0.6):
            add_profile(max(zone.length * factor, min_length), zone.width)
            add_profile(zone.length, max(zone.width * factor, min_width))
            add_profile(
                max(zone.length * factor, min_length),
                max(zone.width * factor, min_width),
            )
        for factor in (0.52, 0.44):
            add_profile(max(zone.length * factor, min_length), max(zone.width * factor, min_width))

        return profiles

    def _position_control_zone(
        self,
        zone: schemas.ControlZoneInput,
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        obstacles: list[schemas.ObstacleInput],
        blocked_boxes: list[Box3D],
        occupied_zone_boxes: list[Box3D],
    ) -> schemas.ControlZoneInput | None:
        preferred_centers = self._preferred_control_zone_centers(zone, boundary, obstacles)
        preferred_centers.append((zone.x, zone.y))

        for center_x, center_y in preferred_centers:
            candidate = self._clamp_control_zone_center(
                zone.model_copy(update={"x": center_x, "y": center_y}),
                boundary,
            )
            if self._is_control_zone_feasible(
                candidate,
                boundary,
                site_polygon,
                blocked_boxes,
                occupied_zone_boxes,
            ):
                return candidate

        half_length = zone.length / 2
        half_width = zone.width / 2
        min_x = boundary.min_x + half_length
        max_x = boundary.max_x - half_length
        min_y = boundary.min_y + half_width
        max_y = boundary.max_y - half_width

        if min_x > max_x or min_y > max_y:
            return None

        span_x = max_x - min_x
        span_y = max_y - min_y
        step_x = max(1.0, min(zone.length / 2, span_x if span_x > 0 else zone.length))
        step_y = max(1.0, min(zone.width / 2, span_y if span_y > 0 else zone.width))
        cols = max(int(math.ceil(span_x / step_x)), 1)
        rows = max(int(math.ceil(span_y / step_y)), 1)
        x_values = [
            min_x + ((span_x * index) / cols if cols > 0 else 0.0)
            for index in range(cols + 1)
        ]
        y_values = [
            min_y + ((span_y * index) / rows if rows > 0 else 0.0)
            for index in range(rows + 1)
        ]
        candidates = [
            (x, y)
            for x in x_values
            for y in y_values
        ]
        candidates.sort(key=lambda item: math.dist((item[0], item[1]), (zone.x, zone.y)))

        for x, y in candidates:
            candidate = zone.model_copy(update={"x": x, "y": y})
            if self._is_control_zone_feasible(
                candidate,
                boundary,
                site_polygon,
                blocked_boxes,
                occupied_zone_boxes,
            ):
                return candidate

        return None

    def _preferred_control_zone_centers(
        self,
        zone: schemas.ControlZoneInput,
        boundary: schemas.SiteBoundary,
        obstacles: list[schemas.ObstacleInput],
    ) -> list[tuple[float, float]]:
        building_map = self._group_building_references(obstacles)
        building_1 = building_map.get("building_1")
        building_2 = building_map.get("building_2")
        building_3 = building_map.get("building_3")
        margin = 0.8
        centers: list[tuple[float, float]] = []

        if zone.id == "zone-north-staging" and building_1:
            centers.extend(
                [
                    (building_1.x, building_1.y + (building_1.width + zone.width) / 2 + margin),
                    (building_1.x - 6.0, building_1.y + (building_1.width + zone.width) / 2 + margin),
                    (building_1.x + 6.0, building_1.y + (building_1.width + zone.width) / 2 + margin),
                ]
            )
        elif zone.id == "zone-west-buffer" and building_1:
            centers.extend(
                [
                    (building_1.x - (building_1.length + zone.length) / 2 - margin, building_1.y),
                    (building_1.x - (building_1.length + zone.length) / 2 - margin, building_1.y - 6.0),
                    (building_1.x - (building_1.length + zone.length) / 2 - margin, building_1.y + 6.0),
                ]
            )
        elif zone.id == "zone-south-delivery":
            anchor_x = (
                (building_2.x - (building_2.length + zone.length) / 2 - margin)
                if building_2
                else (boundary.min_x + zone.length / 2 + margin)
            )
            centers.extend(
                [
                    (anchor_x, boundary.min_y + zone.width / 2 + margin),
                    (anchor_x + 6.0, boundary.min_y + zone.width / 2 + margin),
                    (anchor_x - 6.0, boundary.min_y + zone.width / 2 + margin),
                ]
            )
        elif zone.id == "zone-east-emergency" and building_3:
            centers.extend(
                [
                    (building_3.x, building_3.y - (building_3.width + zone.width) / 2 - margin),
                    (building_3.x + 4.0, building_3.y - (building_3.width + zone.width) / 2 - margin),
                    (building_3.x - 4.0, building_3.y - (building_3.width + zone.width) / 2 - margin),
                ]
            )
        elif zone.id == "zone-mep-buffer":
            if building_3:
                centers.extend(
                    [
                        (building_3.x - (building_3.length + zone.length) / 2 - margin, building_3.y - 6.0),
                        (building_3.x - (building_3.length + zone.length) / 2 - margin, building_3.y + 8.0),
                    ]
                )
            elif building_1:
                centers.append((building_1.x + 6.0, building_1.y - (building_1.width + zone.width) / 2 - margin))

        centers.append(((boundary.min_x + boundary.max_x) / 2, (boundary.min_y + boundary.max_y) / 2))
        unique_centers: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for center_x, center_y in centers:
            marker = (round(center_x, 3), round(center_y, 3))
            if marker in seen:
                continue
            seen.add(marker)
            unique_centers.append((center_x, center_y))
        return unique_centers

    @staticmethod
    def _group_building_references(
        obstacles: list[schemas.ObstacleInput],
    ) -> dict[str, schemas.ObstacleInput]:
        grouped: dict[str, list[schemas.ObstacleInput]] = {}
        for obstacle in obstacles:
            if obstacle.kind != "building":
                continue
            grouped.setdefault(obstacle.group_key or obstacle.id, []).append(obstacle)

        building_map: dict[str, schemas.ObstacleInput] = {}
        for key, members in grouped.items():
            min_x = min(item.x - item.length / 2 for item in members)
            max_x = max(item.x + item.length / 2 for item in members)
            min_y = min(item.y - item.width / 2 for item in members)
            max_y = max(item.y + item.width / 2 for item in members)
            min_z = min((item.min_z if item.min_z is not None else 0.0) for item in members)
            max_z = max(
                (
                    item.max_z
                    if item.max_z is not None
                    else (item.min_z or 0.0) + (item.height or 0.0)
                )
                for item in members
            )
            group_key = next((item.group_key for item in members if item.group_key), None)

            building_map[key] = schemas.ObstacleInput(
                id=key,
                name=members[0].name,
                kind="building",
                x=(min_x + max_x) / 2,
                y=(min_y + max_y) / 2,
                length=max_x - min_x,
                width=max_y - min_y,
                min_z=min_z,
                max_z=max_z,
                height=max(max_z - min_z, 0.0),
                group_key=group_key,
                notes=None,
            )
        return building_map

    def _clamp_control_zone_center(
        self,
        zone: schemas.ControlZoneInput,
        boundary: schemas.SiteBoundary,
    ) -> schemas.ControlZoneInput:
        half_length = zone.length / 2
        half_width = zone.width / 2
        min_x = boundary.min_x + half_length
        max_x = boundary.max_x - half_length
        min_y = boundary.min_y + half_width
        max_y = boundary.max_y - half_width

        clamped_x = (
            min(max(zone.x, min_x), max_x)
            if min_x <= max_x
            else (boundary.min_x + boundary.max_x) / 2
        )
        clamped_y = (
            min(max(zone.y, min_y), max_y)
            if min_y <= max_y
            else (boundary.min_y + boundary.max_y) / 2
        )
        return zone.model_copy(update={"x": clamped_x, "y": clamped_y})

    def _is_control_zone_feasible(
        self,
        zone: schemas.ControlZoneInput,
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        blocked_boxes: list[Box3D],
        occupied_zone_boxes: list[Box3D],
    ) -> bool:
        box = self._box_from_control_zone(zone)
        if not self._box_inside_boundary(box, boundary, site_polygon):
            return False
        if any(self._footprints_overlap(box, blocked_box) for blocked_box in blocked_boxes):
            return False
        if any(self._footprints_overlap(box, occupied_box) for occupied_box in occupied_zone_boxes):
            return False
        return True

    def _build_candidate_solution(
        self,
        rng: random.Random,
        materials: list[schemas.MaterialInput],
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        reserved_boxes: list[Box3D],
        clearance: float,
    ) -> list[tuple[float, float]]:
        solution: list[tuple[float, float]] = []
        occupied: list[Box3D] = []
        for material in materials:
            position = self._find_feasible_position(
                rng=rng,
                material=material,
                boundary=boundary,
                site_polygon=site_polygon,
                reserved_boxes=reserved_boxes,
                occupied_boxes=occupied,
                clearance=clearance,
            )
            solution.append(position)
            occupied.append(self._material_box_from_center(position[0], position[1], material, clearance))
        return solution

    def _find_feasible_position(
        self,
        rng: random.Random,
        material: schemas.MaterialInput,
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        reserved_boxes: list[Box3D],
        occupied_boxes: list[Box3D],
        clearance: float,
    ) -> tuple[float, float]:
        for _ in range(90):
            candidate = self._random_position(rng, material, boundary, clearance)
            if self._is_slot_feasible(
                candidate,
                material,
                boundary,
                site_polygon,
                reserved_boxes,
                occupied_boxes,
                clearance,
            ):
                return candidate

        scan_steps = 10
        step_x = (boundary.max_x - boundary.min_x) / max(scan_steps, 1)
        step_y = (boundary.max_y - boundary.min_y) / max(scan_steps, 1)

        for col in range(scan_steps + 1):
            for row in range(scan_steps + 1):
                candidate = (
                    boundary.min_x + (col * step_x),
                    boundary.min_y + (row * step_y),
                )
                candidate = self._clamp_to_boundary(candidate, material, boundary, clearance)
                if self._is_slot_feasible(
                    candidate,
                    material,
                    boundary,
                    site_polygon,
                    reserved_boxes,
                    occupied_boxes,
                    clearance,
                ):
                    return candidate

        center = ((boundary.min_x + boundary.max_x) / 2, (boundary.min_y + boundary.max_y) / 2)
        return self._clamp_to_boundary(center, material, boundary, clearance)

    def _is_slot_feasible(
        self,
        candidate: tuple[float, float],
        material: schemas.MaterialInput,
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        reserved_boxes: list[Box3D],
        occupied_boxes: list[Box3D],
        clearance: float,
    ) -> bool:
        box = self._material_box_from_center(candidate[0], candidate[1], material, clearance)
        if not self._box_inside_boundary(box, boundary, site_polygon):
            return False
        if any(self._boxes_overlap(box, obstacle) for obstacle in reserved_boxes):
            return False
        if any(self._boxes_overlap(box, item) for item in occupied_boxes):
            return False
        return True

    def _evaluate_solution(
        self,
        solution: list[tuple[float, float]],
        materials: list[schemas.MaterialInput],
        cranes: list[schemas.CraneInput],
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        obstacle_boxes: list[Box3D],
        control_zones: list[schemas.ControlZoneInput],
        blocking_zone_pairs: list[tuple[schemas.ControlZoneInput, Box3D]],
        target_zone_map: dict[str, schemas.ControlZoneInput],
        clearance: float,
        crane_path_penalty: float,
        zone_preference_penalty: float,
        safe_transport_height: float,
        phase_id: str | None,
        phase_name: str | None,
    ) -> dict:
        placements: list[dict] = []
        warnings: list[str] = []
        occupied: list[Box3D] = []
        action_item_map: dict[str, dict] = {}
        transport_cost = 0.0
        safety_penalty = 0.0
        zone_penalty = 0.0
        placed_count = 0
        in_target_zone_count = 0

        for position, material in zip(solution, materials):
            x, y = self._clamp_to_boundary(position, material, boundary, clearance)
            z = 0.0
            box = self._material_box_from_center(x, y, material, clearance)
            local_safety_penalty = 0.0
            local_zone_penalty = 0.0
            blocking_zone_hits: list[str] = []
            decision_factors: list[dict] = []
            review_alerts: list[dict] = []

            boundary_violation = not self._box_inside_boundary(box, boundary, site_polygon)
            obstacle_collision = any(self._boxes_overlap(box, obstacle) for obstacle in obstacle_boxes)
            stack_collision = any(self._boxes_overlap(box, existing) for existing in occupied)
            has_3d_collision = obstacle_collision or stack_collision

            if boundary_violation:
                local_safety_penalty += 100000.0
                warnings.append(f"{material.name} 超出场地边界，请把堆位收回审批红线内。")
                self._append_review_alert(
                    review_alerts,
                    code="boundary",
                    level="warning",
                    title="超出场地边界",
                    detail="当前堆位压线或出界，需现场收回到围挡范围内。",
                )
                self._register_action_item(
                    action_item_map,
                    item_id=f"boundary-{material.id}",
                    category="layout",
                    severity="high",
                    title=f"调整 {material.name} 堆位至场地边界内",
                    detail="当前堆位已超出审批范围，需先回收边界后再复核吊运。",
                )

            if obstacle_collision:
                local_safety_penalty += 120000.0
                warnings.append(f"{material.name} 与楼体或永久障碍发生 3D 碰撞，不能直接落位。")
                self._append_review_alert(
                    review_alerts,
                    code="three_d_collision",
                    level="danger",
                    title="3D 碰撞",
                    detail="当前堆位与楼体或固定障碍在三维范围内重叠，需立即调整。",
                )
                self._register_action_item(
                    action_item_map,
                    item_id=f"obstacle-{material.id}",
                    category="safety",
                    severity="high",
                    title=f"清除 {material.name} 周边 3D 碰撞",
                    detail="当前堆位与楼体或固定障碍重叠，需重新选点后再组织吊装。",
                )

            if stack_collision:
                local_safety_penalty += 150000.0
                warnings.append(f"{material.name} 与其他物料堆场发生 3D 碰撞，请分区或错峰摆放。")
                self._append_review_alert(
                    review_alerts,
                    code="three_d_collision",
                    level="danger",
                    title="3D 碰撞",
                    detail="当前堆位与已布置物料重叠，需拆分堆位或调整顺序。",
                )
                self._register_action_item(
                    action_item_map,
                    item_id=f"stack-{material.id}",
                    category="layout",
                    severity="high",
                    title=f"拆分 {material.name} 与相邻堆场",
                    detail="两个计划堆位重叠，需重新分区或调整进场先后。",
                )

            for zone, zone_box in blocking_zone_pairs:
                if self._boxes_overlap(box, zone_box):
                    blocking_zone_hits.append(zone.name)

            if blocking_zone_hits:
                local_safety_penalty += 160000.0 * len(blocking_zone_hits)
                warnings.append(
                    f"{material.name} 占用了 {', '.join(sorted(blocking_zone_hits))}，需恢复通道净空。"
                )
                self._append_review_alert(
                    review_alerts,
                    code="blocking_zone",
                    level="danger",
                    title="占用受限通道",
                    detail=f"当前堆位压占 {', '.join(sorted(blocking_zone_hits))}，现场需先腾空后再执行。",
                )
                self._register_action_item(
                    action_item_map,
                    item_id=f"zone-block-{material.id}",
                    category="access",
                    severity="high",
                    title=f"释放 {material.name} 周边受限通道",
                    detail=f"将该堆位移出 {', '.join(sorted(blocking_zone_hits))}，恢复车辆和消防净空。",
                )

            target_zone = target_zone_map.get(material.target_zone_id) if material.target_zone_id else None
            target_zone_name = target_zone.name if target_zone else None
            inside_target_zone = False
            if target_zone:
                target_box = self._box_from_control_zone(target_zone)
                inside_target_zone = self._box_inside_zone_footprint(box, target_box)
                if inside_target_zone:
                    in_target_zone_count += 1
                else:
                    zone_distance = self._distance_between_box_centers(box, target_box)
                    local_zone_penalty += (
                        zone_distance
                        * zone_preference_penalty
                        * material.priority_score
                        * max(target_zone.penalty_factor, 1.0)
                    )
                    warnings.append(
                        f"{material.name} 偏离目标区 {target_zone.name} 约 {zone_distance:.1f}m，请结合周转路线复核。"
                    )
                    self._append_review_alert(
                        review_alerts,
                        code="outside_target_zone",
                        level="warning",
                        title="未命中目标区",
                        detail=f"当前堆位距离目标区 {target_zone.name} 约 {zone_distance:.1f}m，可能拉长二次转运路线。",
                    )
                    self._register_action_item(
                        action_item_map,
                        item_id=f"zone-target-{material.id}",
                        category="logistics",
                        severity="medium",
                        title=f"把 {material.name} 收回到 {target_zone.name}",
                        detail="当前堆位偏离目标区，建议优先压缩周转距离后再定点。",
                    )

            crane_options, crane_choice = self._rank_crane_options(
                material=material,
                x=x,
                y=y,
                z=z,
                cranes=cranes,
                obstacle_boxes=obstacle_boxes + [zone_box for _, zone_box in blocking_zone_pairs],
                crane_path_penalty=crane_path_penalty,
                clearance=clearance,
                safe_transport_height=safe_transport_height,
            )

            if crane_choice is None:
                has_radius_limit = any(item["reason_code"] == "over_radius" for item in crane_options)
                has_capacity_limit = any(item["reason_code"] == "over_capacity" for item in crane_options)
                local_safety_penalty += 90000.0
                if has_radius_limit and has_capacity_limit:
                    warnings.append(f"{material.name} 当前无可用塔吊：既超出作业半径，也存在起重量不足。")
                elif has_radius_limit:
                    warnings.append(f"{material.name} 超出塔吊覆盖半径，当前没有可用吊点。")
                    self._append_review_alert(
                        review_alerts,
                        code="over_crane_radius",
                        level="danger",
                        title="超塔吊半径",
                        detail="当前堆位到塔吊的平面距离超出作业半径，需换位或调整吊装资源。",
                    )
                else:
                    warnings.append(f"{material.name} 当前没有满足起重量的塔吊，暂不能吊运。")
                    self._append_review_alert(
                        review_alerts,
                        code="no_crane_capacity",
                        level="warning",
                        title="塔吊能力不足",
                        detail="现有塔吊起重量不满足该批物料，需调整设备或拆分吊次。",
                    )
                self._register_action_item(
                    action_item_map,
                    item_id=f"crane-{material.id}",
                    category="equipment",
                    severity="high",
                    title=f"恢复 {material.name} 的塔吊覆盖",
                    detail="需调整堆位或补充吊装资源，确保至少一台塔吊满足半径和起重量条件。",
                )
                status = "unreachable"
            else:
                transport_cost += crane_choice.cost
                placed_count += 1
                if crane_choice.path_crosses_obstacle:
                    warnings.append(
                        f"{material.name} 吊运净高约 {crane_choice.travel_height:.1f}m，空中运输线穿越障碍。"
                    )
                    self._append_review_alert(
                        review_alerts,
                        code="path_crosses_obstacle",
                        level="warning",
                        title="吊运路径穿越障碍",
                        detail=f"按约 {crane_choice.travel_height:.1f}m 的吊运净高复核，空中通道仍穿越楼体或受限区。",
                    )
                    self._register_action_item(
                        action_item_map,
                        item_id=f"path-{material.id}",
                        category="safety",
                        severity="medium",
                        title=f"清理 {material.name} 的吊运通道",
                        detail="最优塔吊路径仍穿越楼体或受限区，需调整堆位或吊装路线。",
                    )
                if local_safety_penalty > 0:
                    status = "violated"
                elif not inside_target_zone and target_zone_name:
                    status = "at_risk"
                elif crane_choice.path_crosses_obstacle:
                    status = "at_risk"
                else:
                    status = "placed"

            decision_factors.extend(
                self._build_decision_factors(
                    material=material,
                    phase_name=phase_name,
                    target_zone_name=target_zone_name,
                    inside_target_zone=inside_target_zone,
                    blocking_zone_hits=blocking_zone_hits,
                    crane_choice=crane_choice,
                )
            )
            decision_note = self._build_decision_note(
                material=material,
                target_zone_name=target_zone_name,
                inside_target_zone=inside_target_zone,
                blocking_zone_hits=blocking_zone_hits,
                crane_choice=crane_choice,
                boundary_violation=boundary_violation,
                has_3d_collision=has_3d_collision,
                is_beyond_crane_radius=any(item["code"] == "over_crane_radius" for item in review_alerts),
            )

            placement = {
                "material_id": material.id,
                "material_name": material.name,
                "x": round(x, 3),
                "y": round(y, 3),
                "z": round(z, 3),
                "length": material.length,
                "width": material.width,
                "height": material.height,
                "display_color": material.display_color,
                "assigned_crane_id": crane_choice.crane_id if crane_choice else None,
                "assigned_crane_name": crane_choice.crane_name if crane_choice else None,
                "distance": round(crane_choice.distance, 3) if crane_choice else None,
                "transport_cost": round(crane_choice.cost, 3) if crane_choice else None,
                "phase_id": phase_id or material.phase_id,
                "batch_id": material.batch_id,
                "priority_score": material.priority_score,
                "target_zone_id": material.target_zone_id,
                "target_zone_name": target_zone_name,
                "inside_target_zone": inside_target_zone,
                "blocking_zone_hits": sorted(blocking_zone_hits),
                "decision_note": decision_note,
                "decision_factors": decision_factors,
                "crane_options": crane_options,
                "path_crosses_obstacle": crane_choice.path_crosses_obstacle if crane_choice else False,
                "travel_height": round(crane_choice.travel_height, 3) if crane_choice else None,
                "review_alerts": review_alerts,
                "status": status,
            }

            safety_penalty += local_safety_penalty
            zone_penalty += local_zone_penalty
            occupied.append(box)
            placements.append(placement)

        total_cost = transport_cost + safety_penalty + zone_penalty
        decision_summary = self._build_decision_summary(
            phase_name=phase_name,
            materials=materials,
            placed_count=placed_count,
            in_target_zone_count=in_target_zone_count,
            warnings=warnings,
        )

        return {
            "fitness": total_cost,
            "total_cost": total_cost,
            "transport_cost": transport_cost,
            "safety_penalty": safety_penalty,
            "zone_penalty": zone_penalty,
            "feasible_layout": safety_penalty == 0 and placed_count == len(materials),
            "placed_count": placed_count,
            "unplaced_count": len(materials) - placed_count,
            "in_target_zone_count": in_target_zone_count,
            "warnings": sorted(set(warnings)),
            "placements": placements,
            "action_items": list(action_item_map.values()),
            "decision_summary": decision_summary,
        }

    def _rank_crane_options(
        self,
        material: schemas.MaterialInput,
        x: float,
        y: float,
        z: float,
        cranes: list[schemas.CraneInput],
        obstacle_boxes: list[Box3D],
        crane_path_penalty: float,
        clearance: float,
        safe_transport_height: float,
    ) -> tuple[list[dict], CraneChoice | None]:
        reachable_choices: list[CraneChoice] = []
        crane_options: list[dict] = []

        for crane in cranes:
            if crane.capacity_tons < material.weight_tons:
                crane_options.append(
                    schemas.CraneOption(
                        crane_id=crane.id,
                        crane_name=crane.name,
                        reachable=False,
                        reason=f"起重量不足：需 {material.weight_tons:.1f}t，塔吊上限 {crane.capacity_tons:.1f}t。",
                        reason_code="over_capacity",
                    ).model_dump()
                )
                continue

            horizontal_distance = math.dist((crane.x, crane.y), (x, y))
            if horizontal_distance > crane.max_radius:
                over_radius = horizontal_distance - crane.max_radius
                crane_options.append(
                    schemas.CraneOption(
                        crane_id=crane.id,
                        crane_name=crane.name,
                        reachable=False,
                        reason=(
                            f"超出作业半径 {over_radius:.1f}m"
                            f"（当前 {horizontal_distance:.1f}m / 半径 {crane.max_radius:.1f}m）。"
                        ),
                        reason_code="over_radius",
                        distance=round(horizontal_distance, 3),
                    ).model_dump()
                )
                continue

            travel_z = max(
                z + material.height + max(clearance, 0.1),
                safe_transport_height,
            )
            path_crosses_obstacle = any(
                self._segment_intersects_box_at_height(crane.x, crane.y, x, y, travel_z, obstacle)
                for obstacle in obstacle_boxes
            )

            distance = math.dist((crane.x, crane.y, 0.0), (x, y, z + material.height / 2))
            cost = distance * material.weight_tons * material.handling_frequency
            if path_crosses_obstacle:
                cost += crane_path_penalty * material.weight_tons
            cost *= crane.priority_score

            choice = CraneChoice(
                crane_id=crane.id,
                crane_name=crane.name,
                distance=distance,
                cost=cost,
                path_crosses_obstacle=path_crosses_obstacle,
                travel_height=travel_z,
            )
            reachable_choices.append(choice)
            crane_options.append(
                schemas.CraneOption(
                    crane_id=crane.id,
                    crane_name=crane.name,
                    reachable=True,
                    reason=(
                        f"可吊运，但按 {travel_z:.1f}m 净高复核仍存在空中穿越。"
                        if path_crosses_obstacle
                        else "覆盖范围和起重量满足要求，可直接吊运。"
                    ),
                    reason_code="path_crosses_obstacle" if path_crosses_obstacle else "reachable",
                    distance=round(distance, 3),
                    estimated_cost=round(cost, 3),
                    path_crosses_obstacle=path_crosses_obstacle,
                    travel_height=round(travel_z, 3),
                ).model_dump()
            )

        reachable_choices.sort(key=lambda item: item.cost)
        crane_options.sort(
            key=lambda item: (
                0 if item["reachable"] else 1,
                item["estimated_cost"] if item["estimated_cost"] is not None else float("inf"),
                item["crane_name"],
            )
        )
        return crane_options, reachable_choices[0] if reachable_choices else None

    @staticmethod
    def _build_decision_factors(
        material: schemas.MaterialInput,
        phase_name: str | None,
        target_zone_name: str | None,
        inside_target_zone: bool,
        blocking_zone_hits: list[str],
        crane_choice: CraneChoice | None,
    ) -> list[dict]:
        factors: list[dict] = []
        if phase_name:
            factors.append(
                schemas.DecisionFactor(
                    label="阶段",
                    value=phase_name,
                    tone="neutral",
                ).model_dump()
            )
        if material.batch_id:
            factors.append(
                schemas.DecisionFactor(
                    label="批次",
                    value=material.batch_id,
                    tone="neutral",
                ).model_dump()
            )
        if target_zone_name:
            factors.append(
                schemas.DecisionFactor(
                    label="目标区",
                    value=target_zone_name if inside_target_zone else f"偏离 {target_zone_name}",
                    tone="success" if inside_target_zone else "warning",
                ).model_dump()
            )
        if blocking_zone_hits:
            factors.append(
                schemas.DecisionFactor(
                    label="受限区",
                    value=", ".join(blocking_zone_hits),
                    tone="danger",
                ).model_dump()
            )
        if crane_choice:
            factors.append(
                schemas.DecisionFactor(
                    label="塔吊",
                    value=crane_choice.crane_name,
                    tone="warning" if crane_choice.path_crosses_obstacle else "success",
                ).model_dump()
            )
            factors.append(
                schemas.DecisionFactor(
                    label="吊运净高",
                    value=f"{crane_choice.travel_height:.1f}m",
                    tone="warning" if crane_choice.path_crosses_obstacle else "neutral",
                ).model_dump()
            )
        return factors

    @staticmethod
    def _build_decision_note(
        material: schemas.MaterialInput,
        target_zone_name: str | None,
        inside_target_zone: bool,
        blocking_zone_hits: list[str],
        crane_choice: CraneChoice | None,
        boundary_violation: bool,
        has_3d_collision: bool,
        is_beyond_crane_radius: bool,
    ) -> str:
        if boundary_violation:
            return f"{material.name} 当前堆位已经超出场地边界，需先回收红线内再做吊装复核。"
        if crane_choice is None:
            if is_beyond_crane_radius:
                return f"{material.name} 当前堆位超出塔吊覆盖半径，现场需换位或补充吊装资源。"
            return f"{material.name} 当前没有满足起重量或覆盖条件的塔吊，暂不具备吊运条件。"
        if has_3d_collision:
            return f"{material.name} 当前堆位与楼体或其他堆场发生 3D 碰撞，不能直接执行。"
        if blocking_zone_hits:
            return f"{material.name} 占用了 {', '.join(sorted(blocking_zone_hits))}，需先恢复通道净空。"
        if target_zone_name and not inside_target_zone:
            return f"{material.name} 虽可吊运，但偏离目标区 {target_zone_name}，需现场确认二次转运路线。"
        if crane_choice.path_crosses_obstacle:
            return (
                f"{material.name} 吊运净高约 {crane_choice.travel_height:.1f}m，"
                "空中运输线仍穿越楼体或受限区，需重点复核。"
            )
        return f"{material.name} 已生成可执行堆位，堆高 {material.height:.1f}m，塔吊覆盖满足要求。"

    @staticmethod
    def _build_decision_summary(
        phase_name: str | None,
        materials: list[schemas.MaterialInput],
        placed_count: int,
        in_target_zone_count: int,
        warnings: list[str],
    ) -> list[str]:
        summary = [
            f"当前复核范围：{phase_name or '全部物料'}。",
            f"本轮已完成 {placed_count} / {len(materials)} 批物料落位。",
            f"其中 {in_target_zone_count} 批命中预设目标区。",
        ]
        if warnings:
            summary.append(f"共识别 {len(set(warnings))} 项需现场复核的风险。")
        return summary

    @staticmethod
    def _append_review_alert(
        alerts: list[dict],
        *,
        code: str,
        level: str,
        title: str,
        detail: str,
    ) -> None:
        if any(alert["code"] == code for alert in alerts):
            return
        alerts.append(
            schemas.PlacementAlert(
                code=code,
                level=level,
                title=title,
                detail=detail,
            ).model_dump()
        )

    @staticmethod
    def _register_action_item(
        action_item_map: dict[str, dict],
        *,
        item_id: str,
        category: str,
        severity: str,
        title: str,
        detail: str,
    ) -> None:
        action_item_map[item_id] = schemas.ActionItem(
            id=item_id,
            category=category,
            severity=severity,
            title=title,
            detail=detail,
        ).model_dump()

    def _tournament_select(
        self,
        rng: random.Random,
        scored_population: list[tuple[float, list[tuple[float, float]], dict]],
    ) -> list[tuple[float, float]]:
        bracket = rng.sample(scored_population, k=min(4, len(scored_population)))
        bracket.sort(key=lambda item: item[0])
        return list(bracket[0][1])

    def _crossover(
        self,
        rng: random.Random,
        parent_a: list[tuple[float, float]],
        parent_b: list[tuple[float, float]],
        materials: list[schemas.MaterialInput],
        boundary: schemas.SiteBoundary,
        clearance: float,
    ) -> list[tuple[float, float]]:
        child: list[tuple[float, float]] = []

        for index, (gene_a, gene_b) in enumerate(zip(parent_a, parent_b)):
            roll = rng.random()
            if roll < 0.4:
                gene = gene_a
            elif roll < 0.8:
                gene = gene_b
            else:
                gene = ((gene_a[0] + gene_b[0]) / 2, (gene_a[1] + gene_b[1]) / 2)

            child.append(self._clamp_to_boundary(gene, materials[index], boundary, clearance))
        return child

    def _mutate(
        self,
        rng: random.Random,
        solution: list[tuple[float, float]],
        materials: list[schemas.MaterialInput],
        boundary: schemas.SiteBoundary,
        mutation_rate: float,
        clearance: float,
    ) -> list[tuple[float, float]]:
        mutated: list[tuple[float, float]] = []

        for index, gene in enumerate(solution):
            material = materials[index]
            if rng.random() <= mutation_rate:
                step_x = max(material.length * 0.8, 1.0)
                step_y = max(material.width * 0.8, 1.0)
                jittered = (
                    gene[0] + rng.uniform(-step_x, step_x),
                    gene[1] + rng.uniform(-step_y, step_y),
                )
                mutated.append(self._clamp_to_boundary(jittered, material, boundary, clearance))
            else:
                mutated.append(gene)

        return mutated

    def _random_position(
        self,
        rng: random.Random,
        material: schemas.MaterialInput,
        boundary: schemas.SiteBoundary,
        clearance: float,
    ) -> tuple[float, float]:
        half_length = (material.length / 2) + clearance
        half_width = (material.width / 2) + clearance

        if boundary.min_x + half_length >= boundary.max_x - half_length:
            x = (boundary.min_x + boundary.max_x) / 2
        else:
            x = rng.uniform(boundary.min_x + half_length, boundary.max_x - half_length)

        if boundary.min_y + half_width >= boundary.max_y - half_width:
            y = (boundary.min_y + boundary.max_y) / 2
        else:
            y = rng.uniform(boundary.min_y + half_width, boundary.max_y - half_width)

        return x, y

    def _clamp_to_boundary(
        self,
        position: tuple[float, float],
        material: schemas.MaterialInput,
        boundary: schemas.SiteBoundary,
        clearance: float,
    ) -> tuple[float, float]:
        half_length = (material.length / 2) + clearance
        half_width = (material.width / 2) + clearance

        min_x = boundary.min_x + half_length
        max_x = boundary.max_x - half_length
        min_y = boundary.min_y + half_width
        max_y = boundary.max_y - half_width

        if min_x > max_x:
            x = (boundary.min_x + boundary.max_x) / 2
        else:
            x = min(max(position[0], min_x), max_x)

        if min_y > max_y:
            y = (boundary.min_y + boundary.max_y) / 2
        else:
            y = min(max(position[1], min_y), max_y)

        return x, y

    @staticmethod
    def _material_box_from_center(
        x: float,
        y: float,
        material: schemas.MaterialInput,
        clearance: float = 0.0,
    ) -> Box3D:
        half_length = (material.length / 2) + clearance
        half_width = (material.width / 2) + clearance
        return Box3D(
            min_x=x - half_length,
            max_x=x + half_length,
            min_y=y - half_width,
            max_y=y + half_width,
            min_z=0.0,
            max_z=material.height,
        )

    @staticmethod
    def _box_from_obstacle(obstacle: schemas.ObstacleInput, clearance: float = 0.0) -> Box3D:
        half_length = (obstacle.length / 2) + clearance
        half_width = (obstacle.width / 2) + clearance
        min_z = obstacle.min_z if obstacle.min_z is not None else 0.0
        if obstacle.max_z is not None:
            max_z = obstacle.max_z
        else:
            max_z = min_z + (obstacle.height or 0.0)
        return Box3D(
            min_x=obstacle.x - half_length,
            max_x=obstacle.x + half_length,
            min_y=obstacle.y - half_width,
            max_y=obstacle.y + half_width,
            min_z=min_z,
            max_z=max_z,
        )

    @staticmethod
    def _box_from_control_zone(zone: schemas.ControlZoneInput, clearance: float = 0.0) -> Box3D:
        half_length = (zone.length / 2) + clearance
        half_width = (zone.width / 2) + clearance
        min_z = zone.min_z if zone.min_z is not None else 0.0
        if zone.max_z is not None:
            max_z = zone.max_z
        else:
            max_z = min_z + (zone.height or 0.0)
        return Box3D(
            min_x=zone.x - half_length,
            max_x=zone.x + half_length,
            min_y=zone.y - half_width,
            max_y=zone.y + half_width,
            min_z=min_z,
            max_z=max_z,
        )

    @staticmethod
    def _boxes_overlap(left: Box3D, right: Box3D) -> bool:
        return not (
            left.max_x <= right.min_x
            or left.min_x >= right.max_x
            or left.max_y <= right.min_y
            or left.min_y >= right.max_y
            or left.max_z <= right.min_z
            or left.min_z >= right.max_z
        )

    @staticmethod
    def _footprints_overlap(left: Box3D, right: Box3D) -> bool:
        return not (
            left.max_x <= right.min_x
            or left.min_x >= right.max_x
            or left.max_y <= right.min_y
            or left.min_y >= right.max_y
        )

    @staticmethod
    def _box_inside_zone_footprint(box: Box3D, zone_box: Box3D) -> bool:
        return (
            box.min_x >= zone_box.min_x
            and box.max_x <= zone_box.max_x
            and box.min_y >= zone_box.min_y
            and box.max_y <= zone_box.max_y
        )

    @staticmethod
    def _distance_between_box_centers(left: Box3D, right: Box3D) -> float:
        left_center = ((left.min_x + left.max_x) / 2, (left.min_y + left.max_y) / 2)
        right_center = ((right.min_x + right.max_x) / 2, (right.min_y + right.max_y) / 2)
        return math.dist(left_center, right_center)

    def _box_inside_boundary(
        self,
        box: Box3D,
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
    ) -> bool:
        inside_envelope = (
            box.min_x >= boundary.min_x
            and box.max_x <= boundary.max_x
            and box.min_y >= boundary.min_y
            and box.max_y <= boundary.max_y
        )
        if not inside_envelope:
            return False
        if not site_polygon:
            return True

        corners = [
            (box.min_x, box.min_y),
            (box.max_x, box.min_y),
            (box.max_x, box.max_y),
            (box.min_x, box.max_y),
        ]
        return all(self._point_in_polygon(x, y, site_polygon) for x, y in corners)

    def _segment_intersects_box_at_height(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        z: float,
        box: Box3D,
    ) -> bool:
        if z <= box.min_z or z >= box.max_z:
            return False
        if self._point_in_box_footprint(x1, y1, box) or self._point_in_box_footprint(x2, y2, box):
            return True

        corners = [
            (box.min_x, box.min_y),
            (box.max_x, box.min_y),
            (box.max_x, box.max_y),
            (box.min_x, box.max_y),
        ]
        edges = [
            (corners[0], corners[1]),
            (corners[1], corners[2]),
            (corners[2], corners[3]),
            (corners[3], corners[0]),
        ]

        for start, end in edges:
            if self._segments_intersect((x1, y1), (x2, y2), start, end):
                return True
        return False

    @staticmethod
    def _point_in_box_footprint(x: float, y: float, box: Box3D) -> bool:
        return box.min_x <= x <= box.max_x and box.min_y <= y <= box.max_y

    @staticmethod
    def _point_in_polygon(
        x: float,
        y: float,
        polygon: list[schemas.BoundaryPoint],
    ) -> bool:
        inside = False
        for index, point in enumerate(polygon):
            next_point = polygon[(index + 1) % len(polygon)]
            if LayoutOptimizerService._point_on_segment(x, y, point, next_point):
                return True
            intersects = ((point.y > y) != (next_point.y > y)) and (
                x < (next_point.x - point.x) * (y - point.y) / ((next_point.y - point.y) or 1e-9) + point.x
            )
            if intersects:
                inside = not inside
        return inside

    @staticmethod
    def _point_on_segment(
        x: float,
        y: float,
        start: schemas.BoundaryPoint,
        end: schemas.BoundaryPoint,
    ) -> bool:
        cross = (x - start.x) * (end.y - start.y) - (y - start.y) * (end.x - start.x)
        if abs(cross) > 1e-6:
            return False

        return (
            min(start.x, end.x) - 1e-6 <= x <= max(start.x, end.x) + 1e-6
            and min(start.y, end.y) - 1e-6 <= y <= max(start.y, end.y) + 1e-6
        )

    @staticmethod
    def _segments_intersect(
        a1: tuple[float, float],
        a2: tuple[float, float],
        b1: tuple[float, float],
        b2: tuple[float, float],
    ) -> bool:
        def orientation(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
            return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

        def on_segment(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> bool:
            return (
                min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
                and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
            )

        o1 = orientation(a1, a2, b1)
        o2 = orientation(a1, a2, b2)
        o3 = orientation(b1, b2, a1)
        o4 = orientation(b1, b2, a2)

        if o1 == 0 and on_segment(a1, b1, a2):
            return True
        if o2 == 0 and on_segment(a1, b2, a2):
            return True
        if o3 == 0 and on_segment(b1, a1, b2):
            return True
        if o4 == 0 and on_segment(b1, a2, b2):
            return True

        return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)
