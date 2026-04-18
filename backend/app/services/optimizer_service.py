from __future__ import annotations

import math
import random
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .. import models, schemas
from .scene_calibration import estimate_safe_transport_height, normalize_snapshot_payload


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


class LayoutOptimizerService:
    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed

    def serialize_project(self, project: models.Project) -> schemas.ProjectSnapshotResponse:
        snapshot = schemas.ProjectSnapshotResponse(
            project_id=project.id,
            name=project.name,
            site_boundary=schemas.SiteBoundary(
                min_x=project.min_x,
                max_x=project.max_x,
                min_y=project.min_y,
                max_y=project.max_y,
            ),
            scene_guides=(
                schemas.SceneGuides.model_validate(project.scene_guides)
                if project.scene_guides
                else None
            ),
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
            obstacles=[
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
            ],
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
                    display_color=material.display_color,
                )
                for material in sorted(project.materials, key=lambda item: item.name)
            ],
            latest_total_cost=project.latest_total_cost,
        )
        return normalize_snapshot_payload(snapshot)

    def upsert_project_snapshot(
        self,
        db: Session,
        project_id: str,
        payload: schemas.ProjectSnapshotRequest,
    ) -> models.Project:
        payload = normalize_snapshot_payload(payload)
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
            )
        else:
            project.name = payload.name
            project.min_x = payload.site_boundary.min_x
            project.max_x = payload.site_boundary.max_x
            project.min_y = payload.site_boundary.min_y
            project.max_y = payload.site_boundary.max_y
            project.scene_guides = payload.scene_guides.model_dump() if payload.scene_guides else None

        db.add(project)
        db.flush()

        db.query(models.Material).filter(models.Material.project_id == project.id).delete()
        db.query(models.Crane).filter(models.Crane.project_id == project.id).delete()
        db.query(models.Obstacle).filter(models.Obstacle.project_id == project.id).delete()
        db.flush()

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
        rng = random.Random(payload.random_seed if payload.random_seed is not None else self.seed)
        site_polygon = (
            payload.scene_guides.wall_boundary_path
            if payload.scene_guides and len(payload.scene_guides.wall_boundary_path) >= 3
            else None
        )
        safe_transport_height = estimate_safe_transport_height(payload.obstacles)
        obstacle_boxes = [
            self._box_from_obstacle(obstacle, payload.clearance)
            for obstacle in payload.obstacles
        ]

        population = [
            self._build_candidate_solution(
                rng=rng,
                materials=payload.materials,
                boundary=payload.site_boundary,
                site_polygon=site_polygon,
                obstacle_boxes=obstacle_boxes,
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
                    materials=payload.materials,
                    cranes=payload.working_cranes,
                    boundary=payload.site_boundary,
                    site_polygon=site_polygon,
                    obstacle_boxes=obstacle_boxes,
                    clearance=payload.clearance,
                    crane_path_penalty=payload.crane_path_penalty,
                    safe_transport_height=safe_transport_height,
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
                    materials=payload.materials,
                    boundary=payload.site_boundary,
                    clearance=payload.clearance,
                )
                child = self._mutate(
                    rng=rng,
                    solution=child,
                    materials=payload.materials,
                    boundary=payload.site_boundary,
                    mutation_rate=payload.mutation_rate,
                    clearance=payload.clearance,
                )
                next_population.append(child)
            population = next_population

        if best_eval is None:
            best_eval = self._evaluate_solution(
                solution=best_solution,
                materials=payload.materials,
                cranes=payload.working_cranes,
                boundary=payload.site_boundary,
                site_polygon=site_polygon,
                obstacle_boxes=obstacle_boxes,
                clearance=payload.clearance,
                crane_path_penalty=payload.crane_path_penalty,
                safe_transport_height=safe_transport_height,
            )

        response = schemas.OptimizeProjectResponse(
            project_id=project.id,
            project_name=project.name,
            placements=[schemas.PlacementResult(**placement) for placement in best_eval["placements"]],
            metrics=schemas.OptimizationMetrics(
                total_cost=round(best_eval["total_cost"], 3),
                feasible_layout=best_eval["feasible_layout"],
                placed_count=best_eval["placed_count"],
                unplaced_count=best_eval["unplaced_count"],
                generations=payload.generations,
                best_fitness_history=best_history,
                warnings=best_eval["warnings"],
            ),
        )

        project.latest_total_cost = response.metrics.total_cost
        project.latest_plan = [item.model_dump() for item in response.placements]
        db.add(project)
        db.commit()
        db.refresh(project)
        return response

    def _build_candidate_solution(
        self,
        rng: random.Random,
        materials: list[schemas.MaterialInput],
        boundary: schemas.SiteBoundary,
        site_polygon: list[schemas.BoundaryPoint] | None,
        obstacle_boxes: list[Box3D],
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
                obstacle_boxes=obstacle_boxes,
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
        obstacle_boxes: list[Box3D],
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
                obstacle_boxes,
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
                    obstacle_boxes,
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
        obstacle_boxes: list[Box3D],
        occupied_boxes: list[Box3D],
        clearance: float,
    ) -> bool:
        box = self._material_box_from_center(candidate[0], candidate[1], material, clearance)
        if not self._box_inside_boundary(box, boundary, site_polygon):
            return False
        if any(self._boxes_overlap(box, obstacle) for obstacle in obstacle_boxes):
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
        clearance: float,
        crane_path_penalty: float,
        safe_transport_height: float,
    ) -> dict:
        placements: list[dict] = []
        warnings: list[str] = []
        occupied: list[Box3D] = []
        total_cost = 0.0
        penalty = 0.0
        placed_count = 0

        for position, material in zip(solution, materials):
            x, y = self._clamp_to_boundary(position, material, boundary, clearance)
            z = 0.0
            box = self._material_box_from_center(x, y, material, clearance)
            local_penalty = 0.0

            if not self._box_inside_boundary(box, boundary, site_polygon):
                local_penalty += 100000.0
                warnings.append(f"{material.name} exceeds site boundary.")
            if any(self._boxes_overlap(box, obstacle) for obstacle in obstacle_boxes):
                local_penalty += 120000.0
                warnings.append(f"{material.name} collides with an obstacle in 3D space.")
            if any(self._boxes_overlap(box, existing) for existing in occupied):
                local_penalty += 150000.0
                warnings.append(f"{material.name} overlaps another material stack in 3D space.")

            crane_choice = self._select_best_crane(
                material=material,
                x=x,
                y=y,
                z=z,
                cranes=cranes,
                obstacle_boxes=obstacle_boxes,
                crane_path_penalty=crane_path_penalty,
                clearance=clearance,
                safe_transport_height=safe_transport_height,
            )

            if crane_choice is None:
                local_penalty += 90000.0
                warnings.append(f"{material.name} is outside every crane radius or load limit.")
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
                    "assigned_crane_id": None,
                    "assigned_crane_name": None,
                    "distance": None,
                    "transport_cost": None,
                    "path_crosses_obstacle": False,
                    "status": "unreachable",
                }
            else:
                total_cost += crane_choice.cost
                placed_count += 1
                if crane_choice.path_crosses_obstacle:
                    warnings.append(f"{material.name} has a crane path crossing obstacle penalty.")
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
                    "assigned_crane_id": crane_choice.crane_id,
                    "assigned_crane_name": crane_choice.crane_name,
                    "distance": round(crane_choice.distance, 3),
                    "transport_cost": round(crane_choice.cost, 3),
                    "path_crosses_obstacle": crane_choice.path_crosses_obstacle,
                    "status": "placed" if local_penalty == 0 else "placed_with_penalty",
                }

            penalty += local_penalty
            occupied.append(box)
            placements.append(placement)

        return {
            "fitness": total_cost + penalty,
            "total_cost": total_cost,
            "feasible_layout": penalty == 0 and placed_count == len(materials),
            "placed_count": placed_count,
            "unplaced_count": len(materials) - placed_count,
            "warnings": sorted(set(warnings)),
            "placements": placements,
        }

    def _select_best_crane(
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
    ) -> CraneChoice | None:
        best_choice: CraneChoice | None = None

        for crane in cranes:
            if crane.capacity_tons < material.weight_tons:
                continue

            horizontal_distance = math.dist((crane.x, crane.y), (x, y))
            if horizontal_distance > crane.max_radius:
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
            )

            if best_choice is None or choice.cost < best_choice.cost:
                best_choice = choice

        return best_choice

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
    def _boxes_overlap(left: Box3D, right: Box3D) -> bool:
        return not (
            left.max_x <= right.min_x
            or left.min_x >= right.max_x
            or left.max_y <= right.min_y
            or left.min_y >= right.max_y
            or left.max_z <= right.min_z
            or left.min_z >= right.max_z
        )

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
