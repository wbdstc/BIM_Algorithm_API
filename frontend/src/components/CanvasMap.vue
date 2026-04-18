<template>
  <section ref="shellRef" class="map-shell">
    <div ref="viewportRef" class="map-viewport" />

    <div class="map-status">
      <span>{{ statusLabel }}</span>
      <strong>{{ statusTitle }}</strong>
    </div>

    <div class="map-legend">
      <span><i class="legend-zone" /> 管控区</span>
      <span><i class="legend-road" /> 道路</span>
      <span><i class="legend-obstacle" /> 楼体/障碍</span>
      <span><i class="legend-crane" /> 塔吊半径</span>
      <span><i class="legend-material" /> 物料堆场</span>
      <span><i class="legend-warning" /> 重点告警</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import type {
  ControlZoneModel,
  EnvelopeGuide,
  ObstacleModel,
  PlacementResult,
} from "../types/layout";
import { useLayoutStore } from "../stores/layout";
import {
  envelopeFromPoints,
  expandEnvelope,
  getPrimaryBuildingEnvelope,
  getRoadPathGuide,
  getWallBoundaryPath,
  getWallEnvelope,
} from "../utils/siteVisuals";
import { resolveCraneName } from "../utils/craneLabels";

const props = withDefaults(
  defineProps<{
    highlightMaterialId?: string | null;
  }>(),
  {
    highlightMaterialId: null,
  },
);

type AnimatedTarget = {
  object: THREE.Object3D;
  baseScale: THREE.Vector3;
  speed: number;
  amplitude: number;
  opacityMaterial?: THREE.Material & { opacity: number };
  baseOpacity?: number;
};

type CraneVisual = {
  group: THREE.Group;
  mast: THREE.Mesh<THREE.CylinderGeometry, THREE.MeshStandardMaterial>;
  cabin: THREE.Mesh<THREE.SphereGeometry, THREE.MeshStandardMaterial>;
  mastMaterial: THREE.MeshStandardMaterial;
  cabinMaterial: THREE.MeshStandardMaterial;
  radiusRing: THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial>;
  radiusRingMaterial: THREE.MeshBasicMaterial;
  radiusOutline: THREE.LineLoop<THREE.BufferGeometry, THREE.LineBasicMaterial>;
  radiusOutlineMaterial: THREE.LineBasicMaterial;
};

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

const shellRef = ref<HTMLElement | null>(null);
const viewportRef = ref<HTMLDivElement | null>(null);

let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let controls: OrbitControls | null = null;
let worldGroup: THREE.Group | null = null;
let resizeObserver: ResizeObserver | null = null;
let animationFrameId = 0;

const animatedTargets: AnimatedTarget[] = [];
const craneTopMap = new Map<string, THREE.Vector3>();
const craneVisualMap = new Map<string, CraneVisual>();
const craneHitTargets: THREE.Object3D[] = [];
const hoveredCraneId = ref<string | null>(null);
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

const isSolidObstacle = (obstacle: ObstacleModel) =>
  obstacle.kind !== "wall" && obstacle.kind !== "crane";

const resolveHeight = (entity: { min_z?: number | null; max_z?: number | null; height?: number | null }) => {
  if (entity.height != null) {
    return Math.max(entity.height, 0);
  }
  if (entity.max_z != null || entity.min_z != null) {
    return Math.max((entity.max_z ?? 0) - (entity.min_z ?? 0), 0);
  }
  return 0;
};

const resolveBaseZ = (entity: { min_z?: number | null }) => entity.min_z ?? 0;

const formatHeightLabel = (value?: number | null) =>
  value != null ? `${value.toFixed(1)}m` : "--";

const displayCraneName = (craneId?: string | null, craneName?: string | null) =>
  resolveCraneName(craneId, craneName, workingCranes.value) ?? "未分配塔吊";

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

const viewportEnvelope = computed(() => expandEnvelope(visualBoundary.value, 4));

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

const sceneSpan = computed(() =>
  Math.max(
    viewportEnvelope.value.max_x - viewportEnvelope.value.min_x,
    viewportEnvelope.value.max_y - viewportEnvelope.value.min_y,
    40,
  ),
);

const sceneCeiling = computed(() => {
  const obstacleTop = obstacles.value.reduce((highest, obstacle) => {
    const top = resolveBaseZ(obstacle) + resolveHeight(obstacle);
    return Math.max(highest, top);
  }, 0);

  const placementTop = visiblePlacements.value.reduce((highest, placement) => {
    const stackTop = placement.z + placement.height;
    const travelTop = placement.travel_height ?? 0;
    return Math.max(highest, stackTop, travelTop);
  }, 0);

  return Math.max(obstacleTop, placementTop, 22) + 8;
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
  return "三维复核";
});

const statusTitle = computed(() => {
  if (focusedPlacement.value) {
    return [
      focusedPlacement.value.material_name,
      displayCraneName(focusedPlacement.value.assigned_crane_id, focusedPlacement.value.assigned_crane_name),
      `堆高 ${formatHeightLabel(focusedPlacement.value.height)}`,
      focusedPlacement.value.travel_height != null
        ? `吊运净高 ${formatHeightLabel(focusedPlacement.value.travel_height)}`
        : null,
    ].filter(Boolean).join(" · ");
  }
  if (loading.value) {
    return `正在生成 ${activePhase.value?.name || "当前阶段"} 的三维复核场景`;
  }
  if (!visiblePlacements.value.length) {
    return `${activePhase.value?.name || "当前阶段"} 暂无计算结果，先执行一次场布计算。`;
  }
  return `${activePhase.value?.name || "当前阶段"} 已生成 ${visiblePlacements.value.length} 批物料的三维复核视图。`;
});

const placementHasAlert = (placement: PlacementResult, code: string) =>
  placement.review_alerts.some((alert) => alert.code === code);

const placementTone = (placement: PlacementResult) => {
  if (placementHasAlert(placement, "three_d_collision")) {
    return {
      color: "#fb7185",
      emissive: "#be123c",
      opacity: 0.94,
    };
  }
  if (placementHasAlert(placement, "over_crane_radius")) {
    return {
      color: "#facc15",
      emissive: "#ca8a04",
      opacity: 0.9,
    };
  }
  if (placementHasAlert(placement, "path_crosses_obstacle")) {
    return {
      color: "#fb923c",
      emissive: "#c2410c",
      opacity: 0.9,
    };
  }
  if (placement.material_id === props.highlightMaterialId) {
    return {
      color: "#7dd3fc",
      emissive: "#0ea5e9",
      opacity: 0.92,
    };
  }
  return {
    color: placement.display_color || "#14b8a6",
    emissive: placement.display_color || "#0f766e",
    opacity: 0.82,
  };
};

const siteToVector3 = (x: number, y: number, z = 0) =>
  new THREE.Vector3(x, z, -y);

const disposeMaterial = (material: THREE.Material | THREE.Material[]) => {
  const materials = Array.isArray(material) ? material : [material];
  materials.forEach((item) => {
    const candidate = item as THREE.Material & {
      map?: THREE.Texture | null;
      alphaMap?: THREE.Texture | null;
      emissiveMap?: THREE.Texture | null;
    };
    candidate.map?.dispose();
    candidate.alphaMap?.dispose();
    candidate.emissiveMap?.dispose();
    item.dispose();
  });
};

const disposeObject = (object: THREE.Object3D) => {
  object.traverse((child: THREE.Object3D) => {
    const mesh = child as THREE.Mesh;
    if (mesh.geometry) {
      mesh.geometry.dispose();
    }
    if (mesh.material) {
      disposeMaterial(mesh.material);
    }
  });
};

const clearWorld = () => {
  if (!worldGroup) {
    return;
  }

  animatedTargets.splice(0, animatedTargets.length);
  craneTopMap.clear();
  craneVisualMap.clear();
  craneHitTargets.splice(0, craneHitTargets.length);
  disposeObject(worldGroup);
  scene?.remove(worldGroup);
  worldGroup = null;
};

const makeLine = (points: THREE.Vector3[], color: string, dashed = false) => {
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = dashed
    ? new THREE.LineDashedMaterial({
        color,
        dashSize: 4,
        gapSize: 2,
        transparent: true,
        opacity: 0.95,
      })
    : new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: 0.96,
      });
  const line = new THREE.Line(geometry, material);
  if (dashed) {
    line.computeLineDistances();
  }
  return line;
};

const addPulseTarget = (
  object: THREE.Object3D,
  speed: number,
  amplitude: number,
  opacityMaterial?: THREE.Material & { opacity: number },
) => {
  animatedTargets.push({
    object,
    baseScale: object.scale.clone(),
    speed,
    amplitude,
    opacityMaterial,
    baseOpacity: opacityMaterial?.opacity,
  });
};

const addGround = (group: THREE.Group) => {
  const envelope = viewportEnvelope.value;
  const width = envelope.max_x - envelope.min_x;
  const depth = envelope.max_y - envelope.min_y;
  const centerX = (envelope.min_x + envelope.max_x) / 2;
  const centerZ = -((envelope.min_y + envelope.max_y) / 2);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(width * 1.12, depth * 1.12),
    new THREE.MeshStandardMaterial({
      color: "#07111f",
      metalness: 0.05,
      roughness: 0.95,
    }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(centerX, 0, centerZ);
  group.add(ground);

  const grid = new THREE.GridHelper(sceneSpan.value * 1.08, Math.max(Math.round(sceneSpan.value / 4), 14));
  const gridMaterials = Array.isArray(grid.material) ? grid.material : [grid.material];
  gridMaterials.forEach((material: THREE.Material) => {
    const candidate = material as THREE.Material & { opacity: number };
    candidate.transparent = true;
    candidate.opacity = 0.14;
  });
  grid.position.set(centerX, 0.02, centerZ);
  group.add(grid);
};

const addBoundary = (group: THREE.Group) => {
  if (visualBoundaryPath.value.length < 3) {
    return;
  }

  const points = visualBoundaryPath.value
    .map((point) => siteToVector3(point.x, point.y, 0.06));
  points.push(points[0].clone());

  group.add(makeLine(points, "#7dd3fc"));
};

const addRoadRibbon = (
  group: THREE.Group,
  path: { x: number; y: number }[],
  width: number,
  closed: boolean,
) => {
  if (path.length < 2) {
    return;
  }

  const curve = new THREE.CatmullRomCurve3(
    path.map((point) => siteToVector3(point.x, point.y, 0.04)),
    closed,
  );
  const geometry = new THREE.TubeGeometry(curve, Math.max(path.length * 6, 32), width / 2, 12, closed);
  const material = new THREE.MeshStandardMaterial({
    color: "#f59e0b",
    transparent: true,
    opacity: 0.28,
    roughness: 0.82,
    metalness: 0.08,
  });
  group.add(new THREE.Mesh(geometry, material));
};

const addControlZones = (group: THREE.Group) => {
  phaseControlZones.value.forEach((zone) => {
    const isFocused = focusedZone.value?.id === zone.id;
    const height = zone.blocking ? 0.16 : 0.08;
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(zone.length, height, zone.width),
      new THREE.MeshStandardMaterial({
        color: zone.blocking ? "#f87171" : "#22d3ee",
        transparent: true,
        opacity: zone.blocking ? 0.2 : 0.12,
      }),
    );
    mesh.position.copy(siteToVector3(zone.x, zone.y, height / 2));
    group.add(mesh);

    const outline = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(zone.length, height, zone.width)),
      new THREE.LineBasicMaterial({
        color: isFocused ? "#f8fafc" : zone.blocking ? "#fda4af" : "#7dd3fc",
        transparent: true,
        opacity: 0.78,
      }),
    );
    outline.position.copy(mesh.position);
    group.add(outline);
  });
};

const addObstacles = (group: THREE.Group) => {
  obstacles.value.filter(isSolidObstacle).forEach((obstacle) => {
    if (obstacle.kind === "road") {
      const roadMesh = new THREE.Mesh(
        new THREE.BoxGeometry(obstacle.length, 0.12, obstacle.width),
        new THREE.MeshStandardMaterial({
          color: "#f59e0b",
          transparent: true,
          opacity: 0.24,
          roughness: 0.9,
          metalness: 0.02,
        }),
      );
      roadMesh.position.copy(siteToVector3(obstacle.x, obstacle.y, 0.06));
      group.add(roadMesh);
      return;
    }

    const height = Math.max(resolveHeight(obstacle), 0.6);
    const baseZ = resolveBaseZ(obstacle);
    const isPrimaryBuilding = obstacle.group_key === "building_1";

    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(obstacle.length, height, obstacle.width),
      new THREE.MeshStandardMaterial({
        color: isPrimaryBuilding ? "#60a5fa" : "#2dd4bf",
        transparent: true,
        opacity: isPrimaryBuilding ? 0.7 : 0.55,
        roughness: 0.45,
        metalness: 0.08,
      }),
    );
    mesh.position.copy(siteToVector3(obstacle.x, obstacle.y, baseZ + height / 2));
    group.add(mesh);

    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(obstacle.length, height, obstacle.width)),
      new THREE.LineBasicMaterial({
        color: isPrimaryBuilding ? "#bfdbfe" : "#99f6e4",
        transparent: true,
        opacity: 0.82,
      }),
    );
    edges.position.copy(mesh.position);
    group.add(edges);
  });
};

const addCranes = (group: THREE.Group) => {
  const mastHeight = Math.max(sceneCeiling.value * 0.82, 24);

  workingCranes.value.forEach((crane) => {
    const craneGroup = new THREE.Group();
    craneGroup.userData.craneId = crane.id;

    const mastMaterial = new THREE.MeshStandardMaterial({
      color: "#38bdf8",
      emissive: "#0284c7",
      emissiveIntensity: 0.28,
      roughness: 0.35,
      metalness: 0.22,
    });
    const mast = new THREE.Mesh(
      new THREE.CylinderGeometry(0.42, 0.55, mastHeight, 18),
      mastMaterial,
    );
    mast.userData.craneId = crane.id;
    mast.position.copy(siteToVector3(crane.x, crane.y, mastHeight / 2));
    craneGroup.add(mast);

    const cabinMaterial = new THREE.MeshStandardMaterial({
      color: "#dbeafe",
      emissive: "#38bdf8",
      emissiveIntensity: 0.3,
    });
    const cabin = new THREE.Mesh(
      new THREE.SphereGeometry(0.9, 18, 18),
      cabinMaterial,
    );
    cabin.userData.craneId = crane.id;
    cabin.position.copy(siteToVector3(crane.x, crane.y, mastHeight + 0.3));
    craneGroup.add(cabin);

    const hitArea = new THREE.Mesh(
      new THREE.CylinderGeometry(1.6, 1.6, mastHeight + 2.4, 14),
      new THREE.MeshBasicMaterial({
        transparent: true,
        opacity: 0,
        depthWrite: false,
      }),
    );
    hitArea.userData.craneId = crane.id;
    hitArea.position.copy(siteToVector3(crane.x, crane.y, mastHeight / 2));
    craneGroup.add(hitArea);
    craneHitTargets.push(hitArea);

    const radiusRingMaterial = new THREE.MeshBasicMaterial({
      color: "#38bdf8",
      transparent: true,
      opacity: 0.22,
      side: THREE.DoubleSide,
    });
    const radiusRing = new THREE.Mesh(
      new THREE.RingGeometry(Math.max(crane.max_radius - 0.35, 0.1), crane.max_radius, 96),
      radiusRingMaterial,
    );
    radiusRing.rotation.x = -Math.PI / 2;
    radiusRing.position.copy(siteToVector3(crane.x, crane.y, 0.06));
    radiusRing.visible = false;
    craneGroup.add(radiusRing);

    const radiusOutlineMaterial = new THREE.LineBasicMaterial({
      color: "#7dd3fc",
      transparent: true,
      opacity: 0.52,
    });
    const radiusOutline = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(
        Array.from({ length: 96 }, (_, index) => {
          const angle = index / 96 * Math.PI * 2;
          return siteToVector3(
            crane.x + Math.cos(angle) * crane.max_radius,
            crane.y + Math.sin(angle) * crane.max_radius,
            0.08,
          );
        }),
      ),
      radiusOutlineMaterial,
    );
    radiusOutline.visible = false;
    craneGroup.add(radiusOutline);

    group.add(craneGroup);
    craneVisualMap.set(crane.id, {
      group: craneGroup,
      mast,
      cabin,
      mastMaterial,
      cabinMaterial,
      radiusRing,
      radiusRingMaterial,
      radiusOutline,
      radiusOutlineMaterial,
    });
    craneTopMap.set(crane.id, siteToVector3(crane.x, crane.y, mastHeight));
  });
};

const updateCraneHoverVisuals = () => {
  craneVisualMap.forEach((visual, craneId) => {
    const isHovered = hoveredCraneId.value === craneId;

    visual.group.scale.setScalar(1);
    visual.mast.scale.setScalar(isHovered ? 1.08 : 1);
    visual.cabin.scale.setScalar(isHovered ? 1.15 : 1);
    visual.mastMaterial.color.set(isHovered ? "#e0f2fe" : "#38bdf8");
    visual.mastMaterial.emissive.set(isHovered ? "#38bdf8" : "#0284c7");
    visual.mastMaterial.emissiveIntensity = isHovered ? 0.68 : 0.28;

    visual.cabinMaterial.color.set(isHovered ? "#ffffff" : "#dbeafe");
    visual.cabinMaterial.emissive.set("#38bdf8");
    visual.cabinMaterial.emissiveIntensity = isHovered ? 0.72 : 0.3;

    visual.radiusRing.visible = isHovered;
    visual.radiusOutline.visible = isHovered;
    visual.radiusRingMaterial.opacity = isHovered ? 0.28 : 0.22;
    visual.radiusOutlineMaterial.opacity = isHovered ? 0.86 : 0.52;
  });
};

const setHoveredCrane = (craneId: string | null) => {
  if (hoveredCraneId.value === craneId) {
    return;
  }

  hoveredCraneId.value = craneId;
  updateCraneHoverVisuals();

  if (renderer?.domElement) {
    renderer.domElement.style.cursor = craneId ? "pointer" : "";
  }
};

const handlePointerMove = (event: PointerEvent) => {
  if (!renderer || !camera || craneHitTargets.length === 0) {
    return;
  }

  const bounds = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
  pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;

  raycaster.setFromCamera(pointer, camera);
  const [hit] = raycaster.intersectObjects(craneHitTargets, false);
  const craneId = typeof hit?.object.userData?.craneId === "string"
    ? hit.object.userData.craneId as string
    : null;

  setHoveredCrane(craneId);
};

const handlePointerLeave = () => {
  setHoveredCrane(null);
};

const addPlacementAlertBeacon = (group: THREE.Group, placement: PlacementResult, topY: number) => {
  if (placementHasAlert(placement, "three_d_collision")) {
    const beaconMaterial = new THREE.MeshBasicMaterial({
      color: "#fb7185",
      transparent: true,
      opacity: 0.3,
    });
    const beacon = new THREE.Mesh(
      new THREE.CylinderGeometry(0.45, 0.45, 6.5, 16),
      beaconMaterial,
    );
    beacon.position.copy(siteToVector3(placement.x, placement.y, topY + 3.4));
    group.add(beacon);
    addPulseTarget(beacon, 2.8, 0.1, beaconMaterial);
  }

  if (placementHasAlert(placement, "over_crane_radius")) {
    const warningRing = new THREE.Mesh(
      new THREE.TorusGeometry(Math.max(Math.max(placement.length, placement.width) * 0.45, 2.4), 0.14, 14, 48),
      new THREE.MeshBasicMaterial({
        color: "#facc15",
        transparent: true,
        opacity: 0.8,
      }),
    );
    warningRing.rotation.x = Math.PI / 2;
    warningRing.position.copy(siteToVector3(placement.x, placement.y, topY + 0.8));
    group.add(warningRing);
    addPulseTarget(warningRing, 2.4, 0.14);
  }
};

const addPlacements = (group: THREE.Group) => {
  visiblePlacements.value.forEach((placement) => {
    const tone = placementTone(placement);
    const height = Math.max(placement.height, 0.2);
    const baseZ = placement.z;
    const isFocused = placement.material_id === props.highlightMaterialId;

    const material = new THREE.MeshStandardMaterial({
      color: tone.color,
      transparent: true,
      opacity: tone.opacity,
      emissive: tone.emissive,
      emissiveIntensity: isFocused ? 0.58 : 0.32,
      roughness: 0.32,
      metalness: 0.08,
    });

    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(placement.length, height, placement.width),
      material,
    );
    mesh.position.copy(siteToVector3(placement.x, placement.y, baseZ + height / 2));
    mesh.scale.setScalar(isFocused ? 1.04 : 1);
    group.add(mesh);

    const edgeColor = placementHasAlert(placement, "three_d_collision")
      ? "#fecaca"
      : placementHasAlert(placement, "over_crane_radius")
        ? "#fde68a"
        : placementHasAlert(placement, "path_crosses_obstacle")
          ? "#fdba74"
          : isFocused
            ? "#f8fafc"
            : "#d1fae5";

    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(placement.length, height, placement.width)),
      new THREE.LineBasicMaterial({
        color: edgeColor,
        transparent: true,
        opacity: 0.95,
      }),
    );
    edges.position.copy(mesh.position);
    edges.scale.copy(mesh.scale);
    group.add(edges);

    const topY = baseZ + height;
    addPlacementAlertBeacon(group, placement, topY);
  });
};

const addTransportPaths = (group: THREE.Group) => {
  visiblePlacements.value.forEach((placement) => {
    if (!placement.assigned_crane_id) {
      return;
    }

    const craneTop = craneTopMap.get(placement.assigned_crane_id);
    if (!craneTop) {
      return;
    }

    const travelHeight = placement.travel_height ?? Math.max(sceneCeiling.value * 0.55, placement.height + 5);
    const placementTop = siteToVector3(placement.x, placement.y, placement.z + placement.height);
    const craneSiteY = -craneTop.z;
    const liftStart = siteToVector3(craneTop.x, craneSiteY, travelHeight);
    const travelEnd = siteToVector3(placement.x, placement.y, travelHeight);

    const pathColor = placement.path_crosses_obstacle
      ? "#fb923c"
      : placement.material_id === props.highlightMaterialId
        ? "#f8fafc"
        : "#38bdf8";

    const path = makeLine(
      [
        craneTop.clone(),
        liftStart,
        travelEnd,
        placementTop,
      ],
      pathColor,
      placement.path_crosses_obstacle,
    );
    group.add(path);

    if (placement.path_crosses_obstacle) {
      const warningNodeMaterial = new THREE.MeshBasicMaterial({
        color: "#fb923c",
        transparent: true,
        opacity: 0.9,
      });
      const warningNode = new THREE.Mesh(
        new THREE.SphereGeometry(0.45, 16, 16),
        warningNodeMaterial,
      );
      warningNode.position.copy(
        siteToVector3(
          (craneTop.x + placement.x) / 2,
          (craneSiteY + placement.y) / 2,
          travelHeight,
        ),
      );
      group.add(warningNode);
      addPulseTarget(warningNode, 3.2, 0.18, warningNodeMaterial);
    }
  });
};

const configureCamera = () => {
  if (!camera || !controls) {
    return;
  }

  const envelope = viewportEnvelope.value;
  const centerX = (envelope.min_x + envelope.max_x) / 2;
  const centerZ = -((envelope.min_y + envelope.max_y) / 2);
  const span = sceneSpan.value;
  const ceiling = sceneCeiling.value;

  camera.near = 0.1;
  camera.far = span * 30;
  camera.position.set(centerX + span * 0.82, ceiling + span * 0.68, centerZ + span * 0.88);
  camera.lookAt(centerX, ceiling * 0.18, centerZ);
  camera.updateProjectionMatrix();

  controls.target.set(centerX, Math.min(ceiling * 0.18, 12), centerZ);
  controls.minDistance = span * 0.28;
  controls.maxDistance = span * 4.5;
  controls.minPolarAngle = Math.PI / 5;
  controls.maxPolarAngle = Math.PI / 2.04;
  controls.maxAzimuthAngle = Math.PI / 2.2;
  controls.minAzimuthAngle = -Math.PI / 1.2;
  controls.enablePan = true;
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.update();

  if (scene) {
    scene.fog = new THREE.Fog("#07111f", span * 1.4, span * 5.2);
  }
};

const buildWorld = () => {
  if (!scene) {
    return;
  }

  clearWorld();

  const group = new THREE.Group();
  worldGroup = group;

  addGround(group);
  addBoundary(group);
  addControlZones(group);
  addObstacles(group);
  addCranes(group);

  if (!hasExplicitRoadObstacles.value && roadPathGuide.value) {
    addRoadRibbon(group, roadPathGuide.value.path, Math.max(roadPathGuide.value.width, 1.8), roadPathGuide.value.closed);
  } else if (!hasExplicitRoadObstacles.value && fallbackRoadEnvelope.value) {
    addRoadRibbon(
      group,
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

  addPlacements(group);
  addTransportPaths(group);
  scene.add(group);
  if (hoveredCraneId.value && !craneVisualMap.has(hoveredCraneId.value)) {
    hoveredCraneId.value = null;
  }
  updateCraneHoverVisuals();
  configureCamera();
};

const resizeRenderer = () => {
  if (!renderer || !camera || !shellRef.value) {
    return;
  }

  const width = Math.max(shellRef.value.clientWidth, 320);
  const height = Math.max(shellRef.value.clientHeight, 320);

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
};

const ensureScene = () => {
  if (!viewportRef.value || renderer) {
    return;
  }

  renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = false;
  viewportRef.value.appendChild(renderer.domElement);
  renderer.domElement.addEventListener("pointermove", handlePointerMove);
  renderer.domElement.addEventListener("pointerleave", handlePointerLeave);

  scene = new THREE.Scene();

  camera = new THREE.PerspectiveCamera(42, 1, 0.1, 2000);
  controls = new OrbitControls(camera, renderer.domElement);

  const ambientLight = new THREE.HemisphereLight("#dbeafe", "#020617", 1.35);
  scene.add(ambientLight);

  const keyLight = new THREE.DirectionalLight("#f8fafc", 1.05);
  keyLight.position.set(28, sceneCeiling.value + 20, 18);
  scene.add(keyLight);

  const rimLight = new THREE.DirectionalLight("#38bdf8", 0.56);
  rimLight.position.set(-24, sceneCeiling.value * 0.72, -30);
  scene.add(rimLight);

  resizeRenderer();
  buildWorld();
};

const animate = (timestamp: number) => {
  animationFrameId = window.requestAnimationFrame(animate);

  const time = timestamp * 0.001;
  animatedTargets.forEach((target) => {
    const pulse = 1 + Math.sin(time * target.speed) * target.amplitude;
    target.object.scale.set(
      target.baseScale.x * pulse,
      target.baseScale.y * pulse,
      target.baseScale.z * pulse,
    );

    if (target.opacityMaterial && target.baseOpacity != null) {
      target.opacityMaterial.opacity = Math.max(
        Math.min(target.baseOpacity + Math.sin(time * target.speed) * 0.14, 0.95),
        0.12,
      );
    }
  });

  controls?.update();
  if (renderer && scene && camera) {
    renderer.render(scene, camera);
  }
};

onMounted(() => {
  ensureScene();
  animationFrameId = window.requestAnimationFrame(animate);

  if (shellRef.value) {
    resizeObserver = new ResizeObserver(() => {
      resizeRenderer();
      configureCamera();
    });
    resizeObserver.observe(shellRef.value);
  }
});

onBeforeUnmount(() => {
  window.cancelAnimationFrame(animationFrameId);
  resizeObserver?.disconnect();
  controls?.dispose();
  clearWorld();
  renderer?.domElement.removeEventListener("pointermove", handlePointerMove);
  renderer?.domElement.removeEventListener("pointerleave", handlePointerLeave);
  renderer?.dispose();
  renderer?.domElement.remove();
  renderer = null;
  scene = null;
  camera = null;
  controls = null;
});

watch(
  [sceneGuides, siteBoundary, workingCranes, obstacles, phaseControlZones, optimizationResult, activeMaterials, () => props.highlightMaterialId],
  () => {
    ensureScene();
    buildWorld();
  },
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
  background:
    radial-gradient(circle at 18% 18%, rgba(56, 189, 248, 0.12), transparent 32%),
    radial-gradient(circle at 84% 24%, rgba(245, 158, 11, 0.08), transparent 26%),
    linear-gradient(180deg, rgba(6, 17, 28, 0.98), rgba(9, 24, 37, 0.94));
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

.map-viewport {
  width: 100%;
  height: 100%;
}

.map-viewport :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}

.map-status,
.map-legend {
  position: absolute;
  z-index: 2;
  border-radius: 14px;
  background: rgba(8, 18, 28, 0.62);
  box-shadow:
    0 12px 24px rgba(2, 6, 23, 0.24),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.map-status {
  top: 14px;
  left: 14px;
  max-width: 420px;
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
  left: 14px;
  bottom: 14px;
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  color: rgba(226, 232, 240, 0.84);
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
  background: #60a5fa;
}

.legend-crane {
  background: #38bdf8;
}

.legend-material {
  background: #14b8a6;
}

.legend-warning {
  background: #fb7185;
}

@media (max-width: 720px) {
  .map-shell {
    min-height: 420px;
  }

  .map-legend {
    right: 14px;
    flex-wrap: wrap;
  }
}
</style>
