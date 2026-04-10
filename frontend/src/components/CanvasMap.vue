<template>
  <section ref="shellRef" class="map-shell">
    <div class="map-shell__glow map-shell__glow--blue" />
    <div class="map-shell__glow map-shell__glow--violet" />
    <canvas ref="canvasRef" class="map-canvas" />

    <div class="map-overlay">
      <div class="overlay-chip">
        <span>场地边界</span>
        <strong>{{ boundaryLabel }}</strong>
      </div>
      <div class="overlay-chip">
        <span>塔吊 / 实体障碍</span>
        <strong>{{ workingCranes.length }} / {{ renderedObstacleCount }}</strong>
      </div>
      <div class="overlay-chip">
        <span>AI 结果</span>
        <strong>{{ optimizationResult?.placements.length ?? 0 }}</strong>
      </div>
    </div>

    <div class="legend">
      <div><i class="legend-boundary" /> 场地边界线</div>
      <div><i class="legend-road" /> 主路骨架</div>
      <div><i class="legend-obstacle" /> 实体障碍</div>
      <div><i class="legend-crane" /> 塔吊</div>
      <div><i class="legend-material" /> AI 寻优结果</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import type { BoundaryPoint, EnvelopeGuide, ObstacleModel, SiteBoundary } from "../types/layout";
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

const layoutStore = useLayoutStore();
const { obstacles, optimizationResult, sceneGuides, siteBoundary, workingCranes } =
  storeToRefs(layoutStore);

const canvasRef = ref<HTMLCanvasElement | null>(null);
const shellRef = ref<HTMLDivElement | null>(null);

let animationFrameId = 0;
let resizeObserver: ResizeObserver | null = null;
let dashPhase = 0;

const isSolidObstacle = (obstacle: ObstacleModel) =>
  obstacle.kind !== "road" && obstacle.kind !== "wall" && obstacle.kind !== "crane";

const visualBoundaryPath = computed(() =>
  getWallBoundaryPath(sceneGuides.value, siteBoundary.value, obstacles.value),
);

const visualBoundary = computed(() =>
  envelopeFromPoints(visualBoundaryPath.value)
  ?? getWallEnvelope(sceneGuides.value, siteBoundary.value, obstacles.value),
);

const primaryBuildingEnvelope = computed(() =>
  getPrimaryBuildingEnvelope(sceneGuides.value, obstacles.value),
);

const roadPathGuide = computed(() =>
  getRoadPathGuide(sceneGuides.value, siteBoundary.value, obstacles.value),
);

const fallbackRoadEnvelope = computed(() => {
  if (!primaryBuildingEnvelope.value) {
    return null;
  }

  return expandEnvelope(
    primaryBuildingEnvelope.value,
    sceneGuides.value?.recommended_road_offset ?? 1500,
  );
});

const renderedObstacleCount = computed(
  () => obstacles.value.filter((item) => isSolidObstacle(item)).length,
);

const boundaryLabel = computed(() => {
  const boundary = visualBoundary.value;
  return `${boundary.min_x.toFixed(0)},${boundary.min_y.toFixed(0)} ~ ${boundary.max_x.toFixed(0)},${boundary.max_y.toFixed(0)}`;
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

const drawPhysicalObstacle = (
  ctx: CanvasRenderingContext2D,
  obstacle: ObstacleModel,
  transform: ReturnType<typeof createCoordinateTransform>,
) => {
  const rect = transform.toScreenRect(obstacle.x, obstacle.y, obstacle.length, obstacle.width);
  const isPrimary = obstacle.group_key === "building_1";
  const fillColor = isPrimary ? "rgba(59, 130, 246, 0.26)" : "rgba(45, 212, 191, 0.22)";
  const strokeColor = isPrimary ? "rgba(147, 197, 253, 0.86)" : "rgba(153, 246, 228, 0.82)";

  ctx.fillStyle = fillColor;
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  ctx.rect(rect.left, rect.top, rect.width, rect.height);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#f8fafc";
  ctx.font = "12px 'Microsoft YaHei UI', sans-serif";
  ctx.fillText(obstacle.name, rect.left + 8, rect.top + 18);

  if (obstacle.height != null) {
    ctx.fillStyle = "rgba(191, 219, 254, 0.88)";
    ctx.font = "11px 'Microsoft YaHei UI', sans-serif";
    ctx.fillText(`H ${obstacle.height.toFixed(1)}m`, rect.left + 8, rect.top + 34);
  }
};

const drawOriginAxes = (
  ctx: CanvasRenderingContext2D,
  transform: ReturnType<typeof createCoordinateTransform>,
) => {
  const boundary = visualBoundary.value;
  const hasXAxis = boundary.min_y <= 0 && boundary.max_y >= 0;
  const hasYAxis = boundary.min_x <= 0 && boundary.max_x >= 0;

  ctx.save();
  ctx.setLineDash([10, 10]);
  ctx.strokeStyle = "rgba(125, 211, 252, 0.18)";
  ctx.lineWidth = 1;

  if (hasXAxis) {
    const y = transform.toScreenY(0);
    ctx.beginPath();
    ctx.moveTo(transform.offsetX, y);
    ctx.lineTo(transform.canvasWidth - transform.offsetX, y);
    ctx.stroke();
  }

  if (hasYAxis) {
    const x = transform.toScreenX(0);
    ctx.beginPath();
    ctx.moveTo(x, transform.offsetY);
    ctx.lineTo(x, transform.canvasHeight - transform.offsetY);
    ctx.stroke();
  }

  if (hasXAxis && hasYAxis) {
    const origin = transform.toScreenPoint(0, 0);
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.fillStyle = "#f8fafc";
    ctx.arc(origin.x, origin.y, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.font = "600 12px 'Microsoft YaHei UI', sans-serif";
    ctx.fillText("(0, 0)", origin.x + 10, origin.y - 10);
  }

  ctx.restore();
};

const drawBoundaryLoop = (
  ctx: CanvasRenderingContext2D,
  transform: ReturnType<typeof createCoordinateTransform>,
  boundaryPath: BoundaryPoint[],
) => {
  if (boundaryPath.length < 3) {
    return;
  }

  const screenPoints = boundaryPath.map((point) => transform.toScreenPoint(point.x, point.y));

  ctx.beginPath();
  ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
  screenPoints.slice(1).forEach((point) => {
    ctx.lineTo(point.x, point.y);
  });
  ctx.closePath();
  ctx.fillStyle = "rgba(255, 255, 255, 0.025)";
  ctx.fill();

  ctx.save();
  ctx.setLineDash([18, 10]);
  ctx.lineDashOffset = -dashPhase * 0.45;
  ctx.strokeStyle = "rgba(125, 211, 252, 0.96)";
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
  screenPoints.slice(1).forEach((point) => {
    ctx.lineTo(point.x, point.y);
  });
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
};

const drawRoadLoop = (
  ctx: CanvasRenderingContext2D,
  transform: ReturnType<typeof createCoordinateTransform>,
  path: BoundaryPoint[],
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
    screenPoints.slice(1).forEach((point) => {
      ctx.lineTo(point.x, point.y);
    });
    if (closed) {
      ctx.closePath();
    }
  };

  ctx.save();
  ctx.shadowColor = "rgba(245, 158, 11, 0.34)";
  ctx.shadowBlur = 18;
  drawPath();
  ctx.strokeStyle = "rgba(245, 158, 11, 0.22)";
  ctx.lineWidth = roadWidth + 10;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.stroke();
  ctx.restore();

  ctx.save();
  ctx.setLineDash([22, 10]);
  ctx.lineDashOffset = -dashPhase;
  drawPath();
  ctx.strokeStyle = "rgba(251, 191, 36, 0.88)";
  ctx.lineWidth = roadWidth;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.stroke();
  ctx.restore();

  const labelPoint = screenPoints[Math.floor(screenPoints.length / 2)];
  ctx.fillStyle = "rgba(254, 240, 138, 0.88)";
  ctx.font = "600 12px 'Microsoft YaHei UI', sans-serif";
  ctx.fillText("Main road", labelPoint.x + 12, labelPoint.y - 10);
};

const render = () => {
  const shell = shellRef.value;
  const canvas = canvasRef.value;
  if (!shell || !canvas) {
    return;
  }

  const width = Math.max(shell.clientWidth, 320);
  const height = Math.max(shell.clientHeight, 480);
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

  const transform = createCoordinateTransform(toBoundary(visualBoundary.value), width, height);

  const backgroundGradient = ctx.createLinearGradient(0, 0, width, height);
  backgroundGradient.addColorStop(0, "#030917");
  backgroundGradient.addColorStop(0.55, "#08152b");
  backgroundGradient.addColorStop(1, "#0d1d36");
  ctx.fillStyle = backgroundGradient;
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(148, 163, 184, 0.06)";
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
  if (roadPathGuide.value) {
    drawRoadLoop(
      ctx,
      transform,
      roadPathGuide.value.path,
      roadPathGuide.value.width,
      roadPathGuide.value.closed,
    );
  } else if (fallbackRoadEnvelope.value) {
    drawRoadLoop(
      ctx,
      transform,
      [
        { x: fallbackRoadEnvelope.value.min_x, y: fallbackRoadEnvelope.value.min_y },
        { x: fallbackRoadEnvelope.value.max_x, y: fallbackRoadEnvelope.value.min_y },
        { x: fallbackRoadEnvelope.value.max_x, y: fallbackRoadEnvelope.value.max_y },
        { x: fallbackRoadEnvelope.value.min_x, y: fallbackRoadEnvelope.value.max_y },
      ],
      220,
      true,
    );
  }

  drawOriginAxes(ctx, transform);

  obstacles.value.filter(isSolidObstacle).forEach((obstacle) => {
    drawPhysicalObstacle(ctx, obstacle, transform);
  });

  workingCranes.value.forEach((crane) => {
    const center = transform.toScreenPoint(crane.x, crane.y);
    ctx.beginPath();
    ctx.setLineDash([8, 8]);
    ctx.lineDashOffset = 0;
    ctx.strokeStyle = "rgba(56, 189, 248, 0.26)";
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

    ctx.fillStyle = "#eff6ff";
    ctx.font = "12px 'Microsoft YaHei UI', sans-serif";
    ctx.fillText(crane.name, center.x + 14, center.y - 10);
  });

  const craneMap = new Map(workingCranes.value.map((item) => [item.id, item]));
  optimizationResult.value?.placements.forEach((placement) => {
    const center = transform.toScreenPoint(placement.x, placement.y);
    const rect = transform.toScreenRect(placement.x, placement.y, placement.length, placement.width);

    ctx.save();
    ctx.globalAlpha = 0.28;
    ctx.fillStyle = placement.display_color || "#8b5cf6";
    ctx.fillRect(rect.left, rect.top, rect.width, rect.height);
    ctx.restore();

    ctx.strokeStyle = placement.display_color || "#8b5cf6";
    ctx.lineWidth = 2;
    ctx.strokeRect(rect.left, rect.top, rect.width, rect.height);

    ctx.fillStyle = "#f8fafc";
    ctx.font = "13px 'Microsoft YaHei UI', sans-serif";
    ctx.fillText(placement.material_name, rect.left + 8, rect.top + 20);
    ctx.fillStyle = "rgba(191, 219, 254, 0.88)";
    ctx.font = "11px 'Microsoft YaHei UI', sans-serif";
    ctx.fillText(`Z ${placement.z.toFixed(1)}m / H ${placement.height.toFixed(1)}m`, rect.left + 8, rect.top + 36);

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
        : "rgba(56, 189, 248, 0.94)";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.beginPath();
      ctx.fillStyle = placement.display_color || "#8b5cf6";
      ctx.arc(center.x, center.y, 4.5, 0, Math.PI * 2);
      ctx.fill();
    }
  });

  if (!optimizationResult.value) {
    ctx.fillStyle = "rgba(236, 243, 249, 0.84)";
    ctx.font = "600 18px 'Microsoft YaHei UI', sans-serif";
    ctx.fillText("等待 AI 场布寻优结果", 56, height - 64);
  }
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

watch([sceneGuides, siteBoundary, workingCranes, obstacles, optimizationResult], () => render(), {
  deep: true,
});
</script>

<style scoped>
.map-shell {
  position: relative;
  min-height: calc(100vh - 40px);
  overflow: hidden;
  border-radius: 28px;
  background:
    linear-gradient(180deg, rgba(10, 18, 34, 0.8), rgba(5, 10, 20, 0.88)),
    rgba(15, 23, 42, 0.72);
  box-shadow:
    0 28px 64px rgba(2, 6, 23, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.map-shell::before {
  content: "";
  position: absolute;
  inset: 1px;
  border-radius: 27px;
  border: 1px solid rgba(148, 163, 184, 0.08);
  pointer-events: none;
  z-index: 3;
}

.map-shell__glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(76px);
  opacity: 0.24;
  pointer-events: none;
  z-index: 0;
}

.map-shell__glow--blue {
  top: -60px;
  right: -80px;
  width: 220px;
  height: 220px;
  background: rgba(56, 189, 248, 0.32);
}

.map-shell__glow--violet {
  bottom: -80px;
  left: -60px;
  width: 240px;
  height: 240px;
  background: rgba(124, 58, 237, 0.18);
}

.map-canvas {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  height: 100%;
}

.map-overlay,
.legend {
  position: absolute;
  z-index: 2;
}

.map-overlay {
  top: 18px;
  left: 18px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.overlay-chip,
.legend {
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.48);
  box-shadow:
    0 12px 28px rgba(2, 6, 23, 0.24),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.overlay-chip {
  min-width: 132px;
  padding: 10px 12px;
  color: #e2e8f0;
}

.overlay-chip span {
  display: block;
  margin-bottom: 4px;
  color: rgba(191, 219, 254, 0.74);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.overlay-chip strong {
  font-size: 13px;
  font-weight: 600;
}

.legend {
  right: 18px;
  bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  color: #e2e8f0;
}

.legend div {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.legend i {
  width: 12px;
  height: 12px;
  border-radius: 4px;
  display: inline-block;
  flex: 0 0 auto;
}

.legend-boundary {
  border: 2px solid #7dd3fc;
  background: transparent;
}

.legend-road {
  background: linear-gradient(135deg, #f59e0b, #facc15);
}

.legend-obstacle {
  background: linear-gradient(135deg, #38bdf8, #2dd4bf);
}

.legend-crane {
  background: #38bdf8;
  clip-path: polygon(50% 0%, 62% 35%, 100% 35%, 70% 57%, 82% 100%, 50% 74%, 18% 100%, 30% 57%, 0% 35%, 38% 35%);
}

.legend-material {
  background: linear-gradient(135deg, #38bdf8, #8b5cf6);
}

@media (max-width: 1260px) {
  .map-shell {
    min-height: 72vh;
  }
}

@media (max-width: 720px) {
  .map-overlay {
    right: 20px;
  }

  .legend {
    left: 20px;
    right: 20px;
    bottom: 20px;
  }
}
</style>
