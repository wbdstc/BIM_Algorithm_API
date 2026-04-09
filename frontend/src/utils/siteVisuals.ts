import type { EnvelopeGuide, ObstacleModel, SceneGuides, SiteBoundary } from "../types/layout";

const toEnvelope = (boundary: SiteBoundary): EnvelopeGuide => ({
  min_x: boundary.min_x,
  max_x: boundary.max_x,
  min_y: boundary.min_y,
  max_y: boundary.max_y,
});

export const envelopeFromObstacles = (
  obstacles: ObstacleModel[],
  predicate: (obstacle: ObstacleModel) => boolean,
): EnvelopeGuide | null => {
  const matches = obstacles.filter(predicate);
  if (matches.length === 0) {
    return null;
  }

  return {
    min_x: Math.min(...matches.map((item) => item.x - item.length / 2)),
    max_x: Math.max(...matches.map((item) => item.x + item.length / 2)),
    min_y: Math.min(...matches.map((item) => item.y - item.width / 2)),
    max_y: Math.max(...matches.map((item) => item.y + item.width / 2)),
    min_z: matches.reduce<number | null>((value, item) => {
      if (item.min_z == null) {
        return value;
      }
      return value == null ? item.min_z : Math.min(value, item.min_z);
    }, null),
    max_z: matches.reduce<number | null>((value, item) => {
      if (item.max_z == null) {
        return value;
      }
      return value == null ? item.max_z : Math.max(value, item.max_z);
    }, null),
    height: matches.reduce<number | null>((value, item) => {
      if (item.height == null) {
        return value;
      }
      return value == null ? item.height : Math.max(value, item.height);
    }, null),
  };
};

export const getWallEnvelope = (
  sceneGuides: SceneGuides | null | undefined,
  boundary: SiteBoundary,
  obstacles: ObstacleModel[],
): EnvelopeGuide => {
  if (sceneGuides?.wall_envelope) {
    return sceneGuides.wall_envelope;
  }

  return envelopeFromObstacles(obstacles, (item) => item.kind === "wall") ?? toEnvelope(boundary);
};

export const getPrimaryBuildingEnvelope = (
  sceneGuides: SceneGuides | null | undefined,
  obstacles: ObstacleModel[],
): EnvelopeGuide | null => {
  const guideEnvelope = sceneGuides?.building_envelopes?.building_1;
  if (guideEnvelope) {
    return guideEnvelope;
  }

  const keyedEnvelope = envelopeFromObstacles(
    obstacles,
    (item) => item.kind === "building" && item.group_key === "building_1",
  );
  if (keyedEnvelope) {
    return keyedEnvelope;
  }

  return envelopeFromObstacles(obstacles, (item) => item.kind === "building");
};

export const expandEnvelope = (envelope: EnvelopeGuide, offset: number): EnvelopeGuide => ({
  min_x: envelope.min_x - offset,
  max_x: envelope.max_x + offset,
  min_y: envelope.min_y - offset,
  max_y: envelope.max_y + offset,
  min_z: envelope.min_z ?? null,
  max_z: envelope.max_z ?? null,
  height: envelope.height ?? null,
});

export const envelopeWidth = (envelope: EnvelopeGuide): number => envelope.max_x - envelope.min_x;

export const envelopeHeight = (envelope: EnvelopeGuide): number => envelope.max_y - envelope.min_y;
