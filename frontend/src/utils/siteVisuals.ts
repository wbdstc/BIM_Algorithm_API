import type {
  BoundaryPoint,
  EnvelopeGuide,
  ObstacleModel,
  SceneGuides,
  SiteBoundary,
} from "../types/layout";

export interface RoadPathGuide {
  path: BoundaryPoint[];
  width: number;
  closed: boolean;
}

const toEnvelope = (boundary: SiteBoundary): EnvelopeGuide => ({
  min_x: boundary.min_x,
  max_x: boundary.max_x,
  min_y: boundary.min_y,
  max_y: boundary.max_y,
});

const rectanglePathFromEnvelope = (envelope: EnvelopeGuide): BoundaryPoint[] => [
  { x: envelope.min_x, y: envelope.min_y },
  { x: envelope.max_x, y: envelope.min_y },
  { x: envelope.max_x, y: envelope.max_y },
  { x: envelope.min_x, y: envelope.max_y },
];

const obstacleCorners = (obstacle: ObstacleModel): BoundaryPoint[] => [
  { x: obstacle.x - obstacle.length / 2, y: obstacle.y - obstacle.width / 2 },
  { x: obstacle.x + obstacle.length / 2, y: obstacle.y - obstacle.width / 2 },
  { x: obstacle.x + obstacle.length / 2, y: obstacle.y + obstacle.width / 2 },
  { x: obstacle.x - obstacle.length / 2, y: obstacle.y + obstacle.width / 2 },
];

const cross = (origin: BoundaryPoint, left: BoundaryPoint, right: BoundaryPoint): number =>
  (left.x - origin.x) * (right.y - origin.y) - (left.y - origin.y) * (right.x - origin.x);

const pointDistance = (left: BoundaryPoint, right: BoundaryPoint): number =>
  Math.hypot(left.x - right.x, left.y - right.y);

const distancePointToSegment = (
  point: BoundaryPoint,
  start: BoundaryPoint,
  end: BoundaryPoint,
): number => {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) {
    return pointDistance(point, start);
  }

  const ratio = ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared;
  const clampedRatio = Math.max(0, Math.min(1, ratio));
  const projection = {
    x: start.x + dx * clampedRatio,
    y: start.y + dy * clampedRatio,
  };
  return pointDistance(point, projection);
};

const distancePointToPolyline = (point: BoundaryPoint, path: BoundaryPoint[]): number => {
  if (path.length <= 1) {
    return Number.POSITIVE_INFINITY;
  }

  let minimumDistance = Number.POSITIVE_INFINITY;
  path.forEach((start, index) => {
    const end = path[(index + 1) % path.length];
    minimumDistance = Math.min(minimumDistance, distancePointToSegment(point, start, end));
  });
  return minimumDistance;
};

interface RoadCenterlineSegment {
  id: string;
  span: number;
  thickness: number;
  start: BoundaryPoint;
  end: BoundaryPoint;
}

const toRoadCenterline = (obstacle: ObstacleModel): RoadCenterlineSegment => {
  if (obstacle.length >= obstacle.width) {
    return {
      id: obstacle.id,
      span: obstacle.length,
      thickness: obstacle.width,
      start: { x: obstacle.x - obstacle.length / 2, y: obstacle.y },
      end: { x: obstacle.x + obstacle.length / 2, y: obstacle.y },
    };
  }

  return {
    id: obstacle.id,
    span: obstacle.width,
    thickness: obstacle.length,
    start: { x: obstacle.x, y: obstacle.y - obstacle.width / 2 },
    end: { x: obstacle.x, y: obstacle.y + obstacle.width / 2 },
  };
};

const convexHull = (points: BoundaryPoint[]): BoundaryPoint[] => {
  const uniquePoints = Array.from(
    new Map(points.map((point) => [`${point.x.toFixed(6)}:${point.y.toFixed(6)}`, point])).values(),
  ).sort((left, right) => {
    if (left.x === right.x) {
      return left.y - right.y;
    }
    return left.x - right.x;
  });

  if (uniquePoints.length <= 1) {
    return uniquePoints;
  }

  const lower: BoundaryPoint[] = [];
  uniquePoints.forEach((point) => {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) {
      lower.pop();
    }
    lower.push(point);
  });

  const upper: BoundaryPoint[] = [];
  [...uniquePoints].reverse().forEach((point) => {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) {
      upper.pop();
    }
    upper.push(point);
  });

  return [...lower.slice(0, -1), ...upper.slice(0, -1)];
};

export const envelopeFromPoints = (points: BoundaryPoint[]): EnvelopeGuide | null => {
  if (points.length === 0) {
    return null;
  }

  return {
    min_x: Math.min(...points.map((point) => point.x)),
    max_x: Math.max(...points.map((point) => point.x)),
    min_y: Math.min(...points.map((point) => point.y)),
    max_y: Math.max(...points.map((point) => point.y)),
  };
};

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
  const pathEnvelope = envelopeFromPoints(sceneGuides?.wall_boundary_path ?? []);
  if (pathEnvelope) {
    return pathEnvelope;
  }

  if (sceneGuides?.wall_envelope) {
    return sceneGuides.wall_envelope;
  }

  return envelopeFromObstacles(obstacles, (item) => item.kind === "wall") ?? toEnvelope(boundary);
};

export const getWallBoundaryPath = (
  sceneGuides: SceneGuides | null | undefined,
  boundary: SiteBoundary,
  obstacles: ObstacleModel[],
): BoundaryPoint[] => {
  if ((sceneGuides?.wall_boundary_path?.length ?? 0) >= 3) {
    return sceneGuides?.wall_boundary_path ?? [];
  }

  const wallHull = convexHull(
    obstacles
      .filter((item) => item.kind === "wall")
      .flatMap((obstacle) => obstacleCorners(obstacle)),
  );
  if (wallHull.length >= 3) {
    return wallHull;
  }

  return rectanglePathFromEnvelope(getWallEnvelope(sceneGuides, boundary, obstacles));
};

const longestPathFromGraph = (
  nodes: BoundaryPoint[],
  adjacency: Map<number, Array<{ next: number; weight: number }>>,
): { indices: number[]; length: number; closed: boolean } | null => {
  if (nodes.length === 0) {
    return null;
  }

  const degrees = nodes.map((_, index) => adjacency.get(index)?.length ?? 0);
  const leaves = degrees
    .map((degree, index) => ({ degree, index }))
    .filter((item) => item.degree <= 1)
    .map((item) => item.index);

  if (leaves.length === 0 && degrees.every((degree) => degree === 2)) {
    const orderedCycle = [0];
    let previous = -1;
    let current = 0;
    let totalLength = 0;

    while (true) {
      const neighbors = adjacency.get(current) ?? [];
      const nextEdge = neighbors.find((neighbor) => neighbor.next !== previous);
      if (!nextEdge) {
        break;
      }

      totalLength += nextEdge.weight;
      if (nextEdge.next === orderedCycle[0]) {
        return {
          indices: orderedCycle,
          length: totalLength,
          closed: true,
        };
      }

      orderedCycle.push(nextEdge.next);
      previous = current;
      current = nextEdge.next;

      if (orderedCycle.length > nodes.length + 1) {
        break;
      }
    }
  }

  let best: { indices: number[]; length: number; closed: boolean } | null = null;

  const dfs = (
    current: number,
    visitedEdges: Set<string>,
    path: number[],
    length: number,
  ) => {
    const neighbors = adjacency.get(current) ?? [];
    let advanced = false;

    neighbors.forEach((neighbor) => {
      const edgeKey = [current, neighbor.next].sort((left, right) => left - right).join(":");
      if (visitedEdges.has(edgeKey)) {
        return;
      }

      advanced = true;
      visitedEdges.add(edgeKey);
      path.push(neighbor.next);
      dfs(neighbor.next, visitedEdges, path, length + neighbor.weight);
      path.pop();
      visitedEdges.delete(edgeKey);
    });

    if (!advanced && (!best || length > best.length)) {
      best = { indices: [...path], length, closed: false };
    }
  };

  const starts = leaves.length > 0 ? leaves : nodes.map((_, index) => index);
  starts.forEach((start) => {
    dfs(start, new Set<string>(), [start], 0);
  });

  if (best) {
    return best;
  }

  return {
    indices: nodes.map((_, index) => index),
    length: 0,
    closed: true,
  };
};

export const getRoadPathGuide = (
  sceneGuides: SceneGuides | null | undefined,
  boundary: SiteBoundary,
  obstacles: ObstacleModel[],
): RoadPathGuide | null => {
  const roadSegments = obstacles.filter((item) => item.kind === "road").map(toRoadCenterline);
  if (roadSegments.length === 0) {
    return null;
  }

  if (roadSegments.length <= 4) {
    const averageThickness =
      roadSegments.reduce((total, segment) => total + segment.thickness, 0) / roadSegments.length;
    const joinThreshold = Math.max(averageThickness * 1.8, 2.6);
    const nodes: BoundaryPoint[] = [];
    const adjacency = new Map<number, Array<{ next: number; weight: number }>>();

    const getNodeIndex = (point: BoundaryPoint): number => {
      const existingIndex = nodes.findIndex((node) => pointDistance(node, point) <= joinThreshold);
      if (existingIndex >= 0) {
        return existingIndex;
      }
      nodes.push(point);
      return nodes.length - 1;
    };

    roadSegments.forEach((segment) => {
      const startIndex = getNodeIndex(segment.start);
      const endIndex = getNodeIndex(segment.end);

      adjacency.set(startIndex, [
        ...(adjacency.get(startIndex) ?? []),
        { next: endIndex, weight: segment.span },
      ]);
      adjacency.set(endIndex, [
        ...(adjacency.get(endIndex) ?? []),
        { next: startIndex, weight: segment.span },
      ]);
    });

    const pathResult = longestPathFromGraph(nodes, adjacency);
    if (!pathResult || pathResult.indices.length < 2) {
      return null;
    }

    return {
      path: pathResult.indices.map((index) => nodes[index]),
      width: Math.max(averageThickness, 1.2),
      closed: pathResult.closed,
    };
  }

  const wallPath = getWallBoundaryPath(sceneGuides, boundary, obstacles);
  const maxSpan = Math.max(...roadSegments.map((segment) => segment.span));
  const filteredSegments = roadSegments.filter((segment) => {
    const nearWall =
      distancePointToPolyline(segment.start, wallPath) <= Math.max(segment.thickness * 1.8, 2.5)
      || distancePointToPolyline(segment.end, wallPath) <= Math.max(segment.thickness * 1.8, 2.5);
    const isShortConnector = segment.span < maxSpan * 0.72;
    return !(nearWall && isShortConnector);
  });

  const sourceSegments = filteredSegments.length >= 2 ? filteredSegments : roadSegments;
  const averageThickness =
    sourceSegments.reduce((total, segment) => total + segment.thickness, 0) / sourceSegments.length;
  const joinThreshold = Math.max(averageThickness * 1.8, 2.6);

  const nodes: BoundaryPoint[] = [];
  const adjacency = new Map<number, Array<{ next: number; weight: number }>>();

  const getNodeIndex = (point: BoundaryPoint): number => {
    const existingIndex = nodes.findIndex((node) => pointDistance(node, point) <= joinThreshold);
    if (existingIndex >= 0) {
      return existingIndex;
    }
    nodes.push(point);
    return nodes.length - 1;
  };

  sourceSegments.forEach((segment) => {
    const startIndex = getNodeIndex(segment.start);
    const endIndex = getNodeIndex(segment.end);

    adjacency.set(startIndex, [
      ...(adjacency.get(startIndex) ?? []),
      { next: endIndex, weight: segment.span },
    ]);
    adjacency.set(endIndex, [
      ...(adjacency.get(endIndex) ?? []),
      { next: startIndex, weight: segment.span },
    ]);
  });

  const pathResult = longestPathFromGraph(nodes, adjacency);
  if (!pathResult || pathResult.indices.length < 2) {
    return null;
  }

  return {
    path: pathResult.indices.map((index) => nodes[index]),
    width: Math.max(averageThickness, 1.2),
    closed: pathResult.closed,
  };
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

export const getRoadEnvelope = (
  obstacles: ObstacleModel[],
): EnvelopeGuide | null =>
  envelopeFromObstacles(obstacles, (item) => item.kind === "road");

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
