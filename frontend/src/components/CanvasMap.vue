<template>
  <section ref="shellRef" class="map-shell">
    <canvas ref="canvasRef" class="map-canvas" />

    <div v-if="statusTitle" class="map-status">
      <span>{{ statusLabel }}</span>
      <strong>{{ statusTitle }}</strong>
    </div>

    <div class="map-legend">
      <span><i class="legend-road" /> 道路</span>
      <span><i class="legend-obstacle" /> 障碍</span>
      <span><i class="legend-crane" /> 塔吊</span>
      <span><i class="legend-material" /> 落位</span>
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

const props = withDefaults(
  defineProps<{
    highlightPlacementName?: string | null;
  }>(),
  {
    highlightPlacementName: null,
  },
);

const layoutStore = useLayoutStore();
const { loading, obstacles, optimizationResult, sceneGuides, siteBoundary, workingCranes } =
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
    sceneGuides.value?.recommended_road_offset ?? 15,
  );
});

const focusedPlacement = computed(
  () =>
    optimizationResult.value?.placements.find(
      (placement) => placement.material_name === props.highlightPlacementName,
    ) ?? null,
);

const statusLabel = computed(() => {
  if (focusedPlacement.value) {
    return "当前聚焦";
  }

  if (loading.value) {
    return "计算状态";
  }

  if (!optimizationResult.value) {
    return "等待结果";
  }

  return "结果状态";
});

const statusTitle = computed(() => {
  if (focusedPlacement.value) {
    return `${focusedPlacement.value.material_name} · ${focusedPlacement.value.assigned_crane_name || "未分配塔吊"}`;
  }

  if (loading.value) {
    return "正在生成场布方案";
  }

  if (!optimizationResult.value) {
    return "执行寻优后显示落位结果";
  }

  return "点击右侧落位项可高亮地图";
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

  ctx.fillStyle = isPrimary ? "rgba(59, 130, 246, 0.24)" : "rgba(45, 212, 191, 0.18)";
  ctx.strokeStyle = isPrimary ? "rgba(147, 197, 253, 0.82)" : "rgba(94, 234, 212, 0.68)";
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.rect(rect.left, rect.top, rect.width, rect.height);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "rgba(248, 250, 252, 0.92)";
  ctx.font = "12px 'Microsoft YaHei UI', sans-serif";
  ctx.fillText(obstacle.name, rect.left + 8, rect.top + 18);
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

  const transform = createCoordinateTransform(toBoundary(visualBoundary.value), width, height);

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
      2.2,
      true,
    );
  }

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

  optimizationResult.value?.placements.forEach((placement) => {
    const center = transform.toScreenPoint(placement.x, placement.y);
    const rect = transform.toScreenRect(placement.x, placement.y, placement.length, placement.width);
    const isFocused = placement.material_name === props.highlightPlacementName;

    ctx.save();
    ctx.globalAlpha = isFocused ? 0.42 : 0.26;
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

    ctx.fillStyle = "#f8fafc";
    ctx.font = "13px 'Microsoft YaHei UI', sans-serif";
    ctx.fillText(placement.material_name, rect.left + 8, rect.top + 20);

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

watch([sceneGuides, siteBoundary, workingCranes, obstacles, optimizationResult, () => props.highlightPlacementName], () => render(), {
  deep: true,
});
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
  max-width: 320px;
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
