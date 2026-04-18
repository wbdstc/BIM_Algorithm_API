from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

from .. import schemas


SnapshotModel = TypeVar("SnapshotModel", bound=BaseModel)

PLANIMETRIC_SCALE_TRIGGER = 500.0
PLANIMETRIC_SCALE_FACTOR = 0.01
HEIGHT_SCALE_TRIGGER = 60.0
MATERIAL_HEIGHT_SCALE_TRIGGER = 8.0
PRIMARY_BUILDING_GROUP_KEY = "building_1"
PRIMARY_BUILDING_HEIGHT_METERS = 23.8
QTZ60_MAX_RADIUS_METERS = 75.0
QTZ60_CLEARANCE_OVER_BUILDING_METERS = 6.0
RECOMMENDED_ROAD_OFFSET_METERS = 15.0
PLANIMETRIC_SCALE_OVERRIDE_ENV = "BIM_PLANIMETRIC_SCALE_OVERRIDE"
FORCE_CRANE_RADIUS_ENV = "BIM_FORCE_CRANE_RADIUS_METERS"


def _read_optional_positive_float(env_name: str) -> float | None:
    raw_value = os.getenv(env_name)
    if raw_value is None or raw_value == "":
        return None

    try:
        value = float(raw_value)
    except ValueError:
        return None

    if value <= 0:
        return None
    return value


def normalize_snapshot_payload(payload: SnapshotModel) -> SnapshotModel:
    data = payload.model_dump()
    planimetric_scale = _detect_planimetric_scale(data)
    if planimetric_scale != 1.0:
        _scale_planimetric_data(data, planimetric_scale)

    _normalize_vertical_data(data)
    _apply_project_calibration(data)
    return payload.__class__.model_validate(data)


def estimate_safe_transport_height(obstacles: list[schemas.ObstacleInput]) -> float:
    primary_tops: list[float] = []
    building_tops: list[float] = []

    for obstacle in obstacles:
        if obstacle.kind != "building":
            continue

        top = obstacle.max_z
        if top is None:
            top = (obstacle.min_z or 0.0) + (obstacle.height or 0.0)
        if top <= 0:
            continue

        building_tops.append(top)
        if obstacle.group_key == PRIMARY_BUILDING_GROUP_KEY or obstacle.id == PRIMARY_BUILDING_GROUP_KEY:
            primary_tops.append(top)

    reference_top = max(primary_tops or building_tops, default=0.0)
    if reference_top <= 0:
        return 0.0

    return reference_top + QTZ60_CLEARANCE_OVER_BUILDING_METERS


def _detect_planimetric_scale(data: dict) -> float:
    scale_override = _read_optional_positive_float(PLANIMETRIC_SCALE_OVERRIDE_ENV)
    if scale_override is not None:
        return scale_override

    values: list[float] = []

    boundary = data.get("site_boundary") or {}
    values.extend(
        [
            abs(boundary.get("min_x", 0.0)),
            abs(boundary.get("max_x", 0.0)),
            abs(boundary.get("min_y", 0.0)),
            abs(boundary.get("max_y", 0.0)),
            abs(boundary.get("max_x", 0.0) - boundary.get("min_x", 0.0)),
            abs(boundary.get("max_y", 0.0) - boundary.get("min_y", 0.0)),
        ]
    )

    for crane in data.get("working_cranes", []):
        values.extend(
            [
                abs(crane.get("x", 0.0)),
                abs(crane.get("y", 0.0)),
                abs(crane.get("max_radius", 0.0)),
            ]
        )

    for obstacle in data.get("obstacles", []):
        values.extend(
            [
                abs(obstacle.get("x", 0.0)),
                abs(obstacle.get("y", 0.0)),
                abs(obstacle.get("length", 0.0)),
                abs(obstacle.get("width", 0.0)),
            ]
        )

    for control_zone in data.get("control_zones", []):
        values.extend(
            [
                abs(control_zone.get("x", 0.0)),
                abs(control_zone.get("y", 0.0)),
                abs(control_zone.get("length", 0.0)),
                abs(control_zone.get("width", 0.0)),
            ]
        )

    for material in data.get("materials", []):
        values.extend([abs(material.get("length", 0.0)), abs(material.get("width", 0.0))])

    scene_guides = data.get("scene_guides") or {}
    values.append(abs(scene_guides.get("recommended_road_offset", 0.0) or 0.0))

    for point in scene_guides.get("wall_boundary_path", []):
        values.extend([abs(point.get("x", 0.0)), abs(point.get("y", 0.0))])

    for envelope in _iter_scene_envelopes(scene_guides):
        values.extend(
            [
                abs(envelope.get("min_x", 0.0)),
                abs(envelope.get("max_x", 0.0)),
                abs(envelope.get("min_y", 0.0)),
                abs(envelope.get("max_y", 0.0)),
            ]
        )

    max_value = max(values, default=0.0)
    return PLANIMETRIC_SCALE_FACTOR if max_value > PLANIMETRIC_SCALE_TRIGGER else 1.0


def _scale_planimetric_data(data: dict, scale: float) -> None:
    boundary = data.get("site_boundary") or {}
    for key in ("min_x", "max_x", "min_y", "max_y"):
        if boundary.get(key) is not None:
            boundary[key] *= scale

    for crane in data.get("working_cranes", []):
        for key in ("x", "y", "max_radius"):
            if crane.get(key) is not None:
                crane[key] *= scale

    for obstacle in data.get("obstacles", []):
        for key in ("x", "y", "length", "width"):
            if obstacle.get(key) is not None:
                obstacle[key] *= scale

    for control_zone in data.get("control_zones", []):
        for key in ("x", "y", "length", "width"):
            if control_zone.get(key) is not None:
                control_zone[key] *= scale

    for material in data.get("materials", []):
        for key in ("length", "width"):
            if material.get(key) is not None:
                material[key] *= scale

    scene_guides = data.get("scene_guides") or {}
    recommended_road_offset = scene_guides.get("recommended_road_offset")
    if recommended_road_offset is not None:
        scene_guides["recommended_road_offset"] = recommended_road_offset * scale

    for point in scene_guides.get("wall_boundary_path", []):
        point["x"] *= scale
        point["y"] *= scale

    for envelope in _iter_scene_envelopes(scene_guides):
        for key in ("min_x", "max_x", "min_y", "max_y"):
            if envelope.get(key) is not None:
                envelope[key] *= scale


def _normalize_vertical_data(data: dict) -> None:
    for material in data.get("materials", []):
        material_height = material.get("height")
        if material_height is None:
            continue
        if material_height > MATERIAL_HEIGHT_SCALE_TRIGGER:
            material["height"] = material_height * PLANIMETRIC_SCALE_FACTOR

    for obstacle in data.get("obstacles", []):
        _normalize_vertical_block(obstacle)

    for control_zone in data.get("control_zones", []):
        _normalize_vertical_block(control_zone)

    scene_guides = data.get("scene_guides") or {}
    for envelope in _iter_scene_envelopes(scene_guides):
        _normalize_vertical_block(envelope)


def _apply_project_calibration(data: dict) -> None:
    forced_crane_radius = _read_optional_positive_float(FORCE_CRANE_RADIUS_ENV)
    for crane in data.get("working_cranes", []):
        max_radius = crane.get("max_radius")
        if forced_crane_radius is not None:
            crane["max_radius"] = forced_crane_radius
        elif max_radius is None or max_radius <= 0:
            crane["max_radius"] = QTZ60_MAX_RADIUS_METERS

    scene_guides = data.get("scene_guides") or {}
    road_offset = scene_guides.get("recommended_road_offset")
    if road_offset is None or road_offset <= 0 or road_offset > 60.0:
        scene_guides["recommended_road_offset"] = RECOMMENDED_ROAD_OFFSET_METERS

    building_envelopes = scene_guides.get("building_envelopes") or {}
    primary_envelope = building_envelopes.get(PRIMARY_BUILDING_GROUP_KEY)
    if primary_envelope:
        _apply_primary_building_height(primary_envelope)

    for obstacle in data.get("obstacles", []):
        if obstacle.get("kind") != "building":
            continue
        if obstacle.get("group_key") == PRIMARY_BUILDING_GROUP_KEY or obstacle.get("id") == PRIMARY_BUILDING_GROUP_KEY:
            _apply_primary_building_height(obstacle)


def _normalize_vertical_block(block: dict) -> None:
    min_z = _normalize_vertical_value(block.get("min_z"))
    max_z = _normalize_vertical_value(block.get("max_z"))
    height = _normalize_vertical_value(block.get("height"))

    if min_z is None:
        min_z = 0.0

    if max_z is None and height is not None:
        max_z = min_z + height
    elif max_z is not None:
        height = max(max_z - min_z, 0.0)

    block["min_z"] = min_z
    block["max_z"] = max_z
    block["height"] = height


def _normalize_vertical_value(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > HEIGHT_SCALE_TRIGGER:
        return value * PLANIMETRIC_SCALE_FACTOR
    return value


def _apply_primary_building_height(block: dict) -> None:
    min_z = block.get("min_z") or 0.0
    block["min_z"] = min_z
    block["height"] = PRIMARY_BUILDING_HEIGHT_METERS
    block["max_z"] = min_z + PRIMARY_BUILDING_HEIGHT_METERS


def _iter_scene_envelopes(scene_guides: dict) -> list[dict]:
    envelopes: list[dict] = []

    wall_envelope = scene_guides.get("wall_envelope")
    if wall_envelope:
        envelopes.append(wall_envelope)

    building_envelopes = scene_guides.get("building_envelopes") or {}
    envelopes.extend(building_envelopes.values())
    return envelopes
