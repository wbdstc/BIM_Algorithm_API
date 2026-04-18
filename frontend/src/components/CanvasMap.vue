<template>
  <section ref="shellRef" class="map-shell">
    <canvas ref="canvasRef" class="map-canvas" />

    <div class="map-status">
      <span>{{ statusLabel }}</span>
      <strong>{{ statusTitle }}</strong>
    </div>

    <div class="map-legend">
      <span><i class="legend-zone" /> 管控区</span>
      <span><i class="legend-road" /> 道路</span>
      <span><i class="legend-obstacle" /> 建筑障碍</span>
      <span><i class="legend-crane" /> 塔吊</span>
      <span><i class="legend-material" /> 物料落位</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import type { ControlZoneModel, EnvelopeGuide, ObstacleModel, SiteBoundary } from "../types/layout";
import { useLayoutStore } from "../stores/layout";
import { createCoordinateTransform } from "../utils/coordinateTransform";
import {
  envelopeFromPoints,
  expandEnvelope,
  getPrimaryBuildingEnvelope,
  getRoadPathGuide,
  getWallBoundaryPath,
  getWallEnvelope,
} from "../utils/siteVisuals";

const props = withDefaults(
  defineProps<{
    highlightMaterialId?: string | null;
  }>(),
  {
    highlightMaterialId: null,
  },
);

const layoutStore = useLayoutStore();
const {
  activeMaterials,
  activePhase,
  activePhaseId,
  loading,
  optimizationResult,
  phaseControlZones,
  sceneGuides,
  siteBoundary,
  obstacles,
  workingCranes,
} = storeToRefs(layoutStore);

const canvasRef = ref<HTMLCanvasElement | null>(null);
const shellRef = ref<HTMLDivElement | null>(null);

let animationFrameId = 0;
let resizeObserver: ResizeObserver | null = null;
let dashPhase = 0;
type LabelAlignment = "start" | "center";

const isSolidObstacle = (obstacle: ObstacleModel) =>
  obstacle.kind !== "wall" && obstacle.kind !== "crane";

const visiblePlacements = computed(() =>
  optimizationResult.value?.phase_id === activePhaseId.value
    ? optimizationResult.value.placements
    : [],
);

const focusedPlacement = computed(
  () =>
    visiblePlacements.value.find((placement) => placement.material_id === props.highlightMaterialId) ?? null,
);

const focusedZone = computed(() => {
  if (!focusedPlacement.value?.target_zone_id) {
    return null;
  }
  return phaseControlZones.value.find((zone) => zone.id === focusedPlacement.value?.target_zone_id) ?? null;
});

const visualBoundaryPath = computed(() =>
  getWallBoundaryPath(sceneGuides.value, siteBoundary.value, obstacles.value),
);

const visualBoundary = computed(() =>
  envelopeFromPoints(visualBoundaryPath.value)
  ?? getWallEnvelope(sceneGuides.value, siteBoundary.value, obstacles.value),
);

const viewportEnvelope = computed(() => {
  // Keep the viewport anchored to the wall boundary so the site fills the canvas.
  // Crane coverage outside the wall is clipped visually instead of shrinking the map.
  return expandEnvelope(visualBoundary.value, 2);
});

const primaryBuildingEnvelope = computed(() =>
  getPrimaryBuildingEnvelope(sceneGuides.value, obstacles.value),
);

const roadPathGuide = computed(() =>
  getRoadPathGuide(sceneGuides.value, siteBoundary.value, obstacles.value),
);

const hasExplicitRoadObstacles = computed(() =>
  obstacles.value.some((obstacle) => obstacle.kind === "road"),
);

const fallbackRoadEnvelope = computed(() => {
  if (!primaryBuildingEnvelope.value) {
    return null;
  }

  return expandEnvelope(
    primaryBuildingEnvelope.value,
    sceneGuides.value?.recommended_road_offset ?? 15,
  );
});

const statusLabel = computed(() => {
  if (focusedPlacement.value) {
    return "当前关注";
  }
  if (loading.value) {
    return "计算状态";
  }
  if (!visiblePlacements.value.length) {
    return "准备阶段";
  }
  return "阶段结果";
});

const statusTitle = computed(() => {
  if (focusedPlacement.value) {
    return `${focusedPlacement.value.material_name} · ${focusedPlacement.value.assigned_crane_name || "未分配塔吊"}`;
  }
  if (loading.value) {
    return `正在生成 ${activePhase.value?.name || "当前阶段"} 场布方案`;
  }
  if (!visiblePlacements.value.length) {
    return `${activePhase.value?.name || "当前阶段"} 暂无计算结果，先调整物料和管控区。`;
  }
  return `${activePhase.value?.name || "当前阶段"} 已生成 ${visiblePlacements.value.length} 批物料落位。`;
});

const drawStar = (
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  outerRadius: number,
  innerRadius: number,
) => {
  ctx.beginPath();
  for (let index = 0; index < 10; index += 1) {
    const angle = Math.PI / 5 * index - Math.PI / 2;
    const radius = index % 2 === 0 ? outerRadius : innerRadius;
    const pointX = x + Math.cos(angle) * radius;
    const pointY = y + Math.sin(angle) * radius;
    if (index === 0) {
      ctx.moveTo(pointX, pointY);
    } else {
      ctx.lineTo(pointX, pointY);
    }
  }
  ctx.closePath();
};

const toBoundary = (envelope: EnvelopeGuide): SiteBoundary => ({
  min_x: envelope.min_x,
  max_x: envelope.max_x,
  min_y: envelope.min_y,
  max_y: envelope.max_y,
});

const controlZonePalette = (zone: ControlZoneModel) => {
  if (zone.blocking) {
    return {
      fill: "rgba(248, 113, 113, 0.12)",
      stroke: "rgba(252, 165, 165, 0.8)",
      label: "#fecaca",
      dash: [10, 6],
    };
  }
  return {
    fill: "rgba(34, 211, 238, 0.12)",
    stroke: "rgba(125, 211, 252, 0.78)",
    label: "#bae6fd",
    dash: [],
  };
};

const obstaclePalette = (obstacle: ObstacleModel) => {
  if (obstacle.kind === "road") {
    return {
      fill: "rgba(245, 158, 11, 0.14)",
      stroke: "rgba(251, 191, 36, 0.76)",
      label: "#fde68a",
    };
  }

  if (obstacle.group_key === "building_1") {
    return {
      fill: "rgba(59, 130, 246, 0.24)",
      stroke: "rgba(147, 197, 253, 0.82)",
      label: "rgba(248, 250, 252, 0.92)",
    };
  }

  return {
    fill: "rgba(45, 212, 191, 0.18)",
    stroke: "rgba(94, 234, 212, 0.68)",
    label: "rgba(248, 250, 252, 0.92)",
  };
};

const resolveObstacleLabel = (obstacle: ObstacleModel) => {
  if (obstacle.kind !== "road") {
    return obstacle.name;
  }

  const source = `${obstacle.id} ${obstacle.name}`.toLowerCase();
  if (source.includes("west")) {
    return "西侧道路";
  }
  if (source.includes("east")) {
    return "东侧道路";
  }
  if (source.includes("north")) {
    return "北侧道路";
  }
  if (source.includes("south")) {
    return "南侧道路";
  }

  if (obstacle.length >= obstacle.width) {
    return obstacle.y >= 0 ? "北侧道路" : "南侧道路";
  }
  return obstacle.x >= 0 ? "东侧道路" : "西侧道路";
};

const drawClampedLabel = (
  ctx: CanvasRenderingContext2D,
  text: string,
  anchorLeft: number,
  anchorTop: number,
  canvasWidth: number,
  canvasHeight: number,
  color: string,
  alignment: LabelAlignment = "start",
) => {
  ctx.save();
  ctx.font = "12px 'Microsoft YaHei UI', sans-serif";
  const metrics = ctx.measureText(text);
  const labelWidth = metrics.width;
  const x = Math.min(
    Math.max(alignment === "center" ? anchorLeft - labelWidth / 2 : anchorLeft, 10),
    canvasWidth - labelWidth - 10,
  );
  const y = Math.min(Math.max(anchorTop, 18), canvasHeight - 10);
  const pillLeft = x - 6;
  const pillTop = y - 13;
  const pillWidth = labelWidth + 12;
  const pillHeight = 18;
  ctx.fillStyle = "rgba(7, 17, 31, 0.82)";
  ctx.beginPath();
  ctx.roundRect(pillLeft, pillTop, pillWidth, pillHeight, 8);
  ctx.fill();
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
  ctx.restore();
};

const drawControlZone = (
  ctx: CanvasRenderingContext2D,
  zone: ControlZoneModel,
  transform: ReturnType<typeof createCoordinateTransform>,
  highlighted: boolean,
) => {
  const rect = transform.toScreenRect(zone.x, zone.y, zone.length, zone.width);
  const palette = controlZonePalette(zone);
  ctx.save();
  ctx.fillStyle = palette.fill;
  ctx.strokeStyle = highlighted ? "#f8fafc" : palette.stroke;
  ctx.lineWidth = highlighted ? 2.8 : 1.8;
  ctx.setLineDash(palette.dash);
  if (highlighted) {
    ctx.shadowColor = "rgba(248, 250, 252, 0.28)";
    ctx.shadowBlur = 18;
  }
  ctx.beginPath();
  ctx.rect(rect.left, rect.top, rect.width, rect.height);
  ctx.fill();
  ctx.stroke();
  ctx.restore();
};

const drawPhysicalObstacle = (
  ctx: CanvasRenderingContext2D,
  obstacle: ObstacleModel,
  transform: ReturnType<typeof createCoordinateTransform>,
) => {
  const rect = transform.toScreenRect(obstacle.x, obstacle.y, obstacle.length, obstacle.width);
  const palette = obstaclePalette(obstacle);

  ctx.fillStyle = palette.fill;
  ctx.strokeStyle = palette.stroke;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.rect(rect.left, rect.top, rect.width, rect.height);
  ctx.fill();
  ctx.stroke();
};

const drawBoundaryLoop = (
  ctx: CanvasRenderingContext2D,
  transform: ReturnType<typeof createCoordinateTransform>,
  boundaryPath: { x: number; y: number }[],
) => {
  if (boundaryPath.length < 3) {
    return;
  }

  const screenPoints = boundaryPath.map((point) => transform.toScreenPoint(point.x, point.y));

  ctx.beginPath();
  ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
  screenPoints.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.closePath();
  ctx.fillStyle = "rgba(255, 255, 255, 0.02)";
  ctx.fill();

  ctx.save();
  ctx.setLineDash([18, 10]);
  ctx.lineDashOffset = -dashPhase * 0.45;
  ctx.strokeStyle = "rgba(125, 211, 252, 0.86)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
  screenPoints.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
};

const applyBoundaryClip = (
  ctx: CanvasRenderingContext2D,
  transform: ReturnType<typeof createCoordinateTransform>,
  boundaryPath: { x: number; y: number }[],
) => {
  if (boundaryPath.length < 3) {
    return;
  }

  const screenPoints = boundaryPath.map((point) => transform.toScreenPoint(point.x, point.y));
  ctx.beginPath();
  ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
  screenPoints.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.closePath();
  ctx.clip();
};

const drawRoadLoop = (
  ctx: CanvasRenderingContext2D,
  transform: ReturnType<typeof createCoordinateTransform>,
  path: { x: number; y: number }[],
  roadWidthWorld: number,
  closed: boolean,
) => {
  if (path.length < 2) {
    return;
  }

  const screenPoints = path.map((point) => transform.toScreenPoint(point.x, point.y));
  const roadWidth = Math.max(10, Math.min(24, transform.scale * roadWidthWorld));

  const drawPath = () => {
    ctx.beginPath();
    ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
    screenPoints.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
    if (closed) {
      ctx.closePath();
    }
  };

  ctx.save();
  ctx.strokeStyle = "rgba(245, 158, 11, 0.22)";
  ctx.lineWidth = roadWidth + 10;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  drawPath();
  ctx.stroke();
  ctx.restore();

  ctx.save();
  ctx.setLineDash([22, 10]);
  ctx.lineDashOffset = -dashPhase;
  ctx.strokeStyle = "rgba(251, 191, 36, 0.88)";
  ctx.lineWidth = roadWidth;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  drawPath();
  ctx.stroke();
  ctx.restore();
};

const render = () => {
  const shell = shellRef.value;
  const canvas = canvasRef.value;
  if (!shell || !canvas) {
    return;
  }

  const width = Math.max(shell.clientWidth, 320);
  const height = Math.max(shell.clientHeight, 320);
  const dpr = window.devicePixelRatio || 1;

  if (canvas.width !== Math.floor(width * dpr) || canvas.height !== Math.floor(height * dpr)) {
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const transform = createCoordinateTransform(toBoundary(viewportEnvelope.value), width, height);

  const backgroundGradient = ctx.createLinearGradient(0, 0, width, height);
  backgroundGradient.addColorStop(0, "#07111f");
  backgroundGradient.addColorStop(1, "#0c1b33");
  ctx.fillStyle = backgroundGradient;
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(148, 163, 184, 0.05)";
  ctx.lineWidth = 1;
  for (let x = 0; x < width; x += 36) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y < height; y += 36) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  drawBoundaryLoop(ctx, transform, visualBoundaryPath.value);
  ctx.save();
  applyBoundaryClip(ctx, transform, visualBoundaryPath.value);

  if (!hasExplicitRoadObstacles.value && roadPathGuide.value) {
    drawRoadLoop(
      ctx,
      transform,
      roadPathGuide.value.path,
      roadPathGuide.value.width,
      roadPathGuide.value.closed,
    );
  } else if (!hasExplicitRoadObstacles.value && fallbackRoadEnvelope.value) {
    drawRoadLoop(
      ctx,
      transform,
      [
        { x: fallbackRoadEnvelope.value.min_x, y: fallbackRoadEnvelope.value.min_y },
        { x: fallbackRoadEnvelope.value.max_x, y: fallbackRoadEnvelope.value.min_y },
        { x: fallbackRoadEnvelope.value.max_x, y: fallbackRoadEnvelope.value.max_y },
        { x: fallbackRoadEnvelope.value.min_x, y: fallbackRoadEnvelope.value.max_y },
      ],
      2.2,
      true,
    );
  }

  phaseControlZones.value.forEach((zone) => {
    drawControlZone(ctx, zone, transform, focusedZone.value?.id === zone.id);
  });

  obstacles.value.filter(isSolidObstacle).forEach((obstacle) => {
    drawPhysicalObstacle(ctx, obstacle, transform);
  });

  workingCranes.value.forEach((crane) => {
    const center = transform.toScreenPoint(crane.x, crane.y);

    ctx.beginPath();
    ctx.setLineDash([8, 8]);
    ctx.strokeStyle = "rgba(56, 189, 248, 0.22)";
    ctx.lineWidth = 1;
    ctx.arc(center.x, center.y, crane.max_radius * transform.scale, 0, Math.PI * 2);
    ctx.stroke();

    ctx.setLineDash([]);
    drawStar(ctx, center.x, center.y, 14, 7);
    ctx.fillStyle = "#38bdf8";
    ctx.fill();
    ctx.strokeStyle = "#dbeafe";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  });

  const craneMap = new Map(workingCranes.value.map((item) => [item.id, item]));

  visiblePlacements.value.forEach((placement) => {
    const center = transform.toScreenPoint(placement.x, placement.y);
    const rect = transform.toScreenRect(placement.x, placement.y, placement.length, placement.width);
    const isFocused = placement.material_id === props.highlightMaterialId;

    ctx.save();
    ctx.globalAlpha = isFocused ? 0.46 : 0.26;
    ctx.fillStyle = placement.display_color || "#14b8a6";
    if (isFocused) {
      ctx.shadowColor = "rgba(56, 189, 248, 0.36)";
      ctx.shadowBlur = 22;
    }
    ctx.fillRect(rect.left, rect.top, rect.width, rect.height);
    ctx.restore();

    ctx.strokeStyle = isFocused ? "#f8fafc" : placement.display_color || "#14b8a6";
    ctx.lineWidth = isFocused ? 3 : 2;
    ctx.strokeRect(rect.left, rect.top, rect.width, rect.height);

    const assignedCrane = placement.assigned_crane_id
      ? craneMap.get(placement.assigned_crane_id)
      : undefined;

    if (assignedCrane) {
      const craneCenter = transform.toScreenPoint(assignedCrane.x, assignedCrane.y);
      ctx.beginPath();
      ctx.setLineDash([14, 10]);
      ctx.lineDashOffset = -dashPhase;
      ctx.moveTo(craneCenter.x, craneCenter.y);
      ctx.lineTo(center.x, center.y);
      ctx.strokeStyle = placement.path_crosses_obstacle
        ? "rgba(251, 146, 60, 0.94)"
        : isFocused
          ? "rgba(248, 250, 252, 0.96)"
          : "rgba(56, 189, 248, 0.94)";
      ctx.lineWidth = isFocused ? 2.6 : 2;
      ctx.stroke();
      ctx.setLineDash([]);
    }
  });
  ctx.restore();

  phaseControlZones.value.forEach((zone) => {
    const rect = transform.toScreenRect(zone.x, zone.y, zone.length, zone.width);
    drawClampedLabel(
      ctx,
      zone.name,
      rect.left + 8,
      rect.top + 18,
      width,
      height,
      controlZonePalette(zone).label,
    );
  });

  obstacles.value.filter(isSolidObstacle).forEach((obstacle) => {
    const rect = transform.toScreenRect(obstacle.x, obstacle.y, obstacle.length, obstacle.width);
    const label = resolveObstacleLabel(obstacle);
    const isRoad = obstacle.kind === "road";
    drawClampedLabel(
      ctx,
      label,
      isRoad ? rect.left + rect.width / 2 : rect.left + 8,
      isRoad ? rect.top + rect.height / 2 + 4 : rect.top + 18,
      width,
      height,
      obstaclePalette(obstacle).label,
      isRoad ? "center" : "start",
    );
  });

  visiblePlacements.value.forEach((placement) => {
    const rect = transform.toScreenRect(placement.x, placement.y, placement.length, placement.width);
    drawClampedLabel(
      ctx,
      placement.material_name,
      rect.left + 8,
      rect.top + 20,
      width,
      height,
      "#f8fafc",
    );
  });
};

const animate = () => {
  dashPhase = (dashPhase + 1.4) % 100;
  render();
  animationFrameId = window.requestAnimationFrame(animate);
};

onMounted(() => {
  render();
  animationFrameId = window.requestAnimationFrame(animate);

  if (shellRef.value) {
    resizeObserver = new ResizeObserver(() => render());
    resizeObserver.observe(shellRef.value);
  }
});

onBeforeUnmount(() => {
  window.cancelAnimationFrame(animationFrameId);
  resizeObserver?.disconnect();
});

watch(
  [sceneGuides, siteBoundary, workingCranes, obstacles, phaseControlZones, optimizationResult, activeMaterials, () => props.highlightMaterialId],
  () => render(),
  { deep: true },
);
</script>

<style scoped>
.map-shell {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(6, 17, 28, 0.96), rgba(9, 24, 37, 0.9));
}

.map-shell::before {
  content: "";
  position: absolute;
  inset: 1px;
  border-radius: 21px;
  border: 1px solid rgba(148, 163, 184, 0.08);
  pointer-events: none;
  z-index: 3;
}

.map-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.map-status,
.map-legend {
  position: absolute;
  z-index: 2;
  border-radius: 14px;
  background: rgba(8, 18, 28, 0.56);
  box-shadow:
    0 10px 20px rgba(2, 6, 23, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.map-status {
  top: 14px;
  left: 14px;
  max-width: 360px;
  padding: 10px 12px;
}

.map-status span {
  display: block;
  margin-bottom: 4px;
  color: rgba(191, 219, 254, 0.72);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.map-status strong {
  color: #f8fafc;
  font-size: 13px;
  line-height: 1.5;
}

.map-legend {
  right: 14px;
  bottom: 14px;
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  color: rgba(226, 232, 240, 0.8);
  font-size: 12px;
}

.map-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.map-legend i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.legend-zone {
  background: #7dd3fc;
}

.legend-road {
  background: #f59e0b;
}

.legend-obstacle {
  background: #22d3ee;
}

.legend-crane {
  background: #38bdf8;
}

.legend-material {
  background: #14b8a6;
}

@media (max-width: 720px) {
  .map-shell {
    min-height: 360px;
  }

  .map-legend {
    flex-wrap: wrap;
    left: 14px;
  }
}
</style>
