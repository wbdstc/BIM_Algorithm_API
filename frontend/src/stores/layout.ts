import { defineStore } from "pinia";

import type {
  BimDataStatusModel,
  ControlZoneModel,
  CraneModel,
  EnvelopeGuide,
  MaterialModel,
  ObstacleModel,
  OptimizationResult,
  PhaseModel,
  PlanVersionSummary,
  ProjectSnapshotModel,
  SceneGuides,
  SiteBoundary,
} from "../types/layout";

const colorPalette = ["#38BDF8", "#14B8A6", "#F59E0B", "#10B981", "#F97316", "#EF4444"];
const defaultProjectId = "demo-smart-site";
const defaultProjectName = "BIM Smart Site Demo";

const roadOffset = 15;
const roadThickness = 1.8;
const wallThickness = 1.4;

const building1Envelope: EnvelopeGuide = {
  min_x: 0.69275,
  max_x: 33.49305,
  min_y: -26.6726,
  max_y: 21.01,
  min_z: 0,
  max_z: 23.8,
  height: 23.8,
};

const building2Envelope: EnvelopeGuide = {
  min_x: 11.2,
  max_x: 24,
  min_y: -42.8,
  max_y: -26.8,
  min_z: 0,
  max_z: 15.2,
  height: 15.2,
};

const building3Envelope: EnvelopeGuide = {
  min_x: 45.3155,
  max_x: 56.2045,
  min_y: -10.78925,
  max_y: 22.46185,
  min_z: 0,
  max_z: 18,
  height: 18,
};

const buildingComponentIds = {
  building_1: [
    "5327272_5311496",
    "5327272_5311502",
    "5327272_5311484",
    "5327272_5311490",
  ],
  building_2: [
    "5327272_5311535",
    "5327272_5311529",
    "5327272_5311517",
    "5327272_5311523",
    "5327272_5311910",
  ],
  building_3: ["5327272_5314766", "5327272_5314769"],
} as const;

const wallEnvelope: EnvelopeGuide = {
  min_x: -18,
  max_x: 62,
  min_y: -46,
  max_y: 40,
};

const realSiteBoundary: SiteBoundary = {
  min_x: wallEnvelope.min_x,
  max_x: wallEnvelope.max_x,
  min_y: wallEnvelope.min_y,
  max_y: wallEnvelope.max_y,
};

const defaultSceneGuides: SceneGuides = {
  wall_envelope: wallEnvelope,
  wall_boundary_path: [
    { x: wallEnvelope.min_x, y: wallEnvelope.min_y + 12 },
    { x: wallEnvelope.min_x + 9, y: wallEnvelope.min_y },
    { x: wallEnvelope.max_x, y: wallEnvelope.min_y },
    { x: wallEnvelope.max_x, y: wallEnvelope.max_y },
    { x: wallEnvelope.min_x, y: wallEnvelope.max_y },
  ],
  building_envelopes: {
    building_1: building1Envelope,
    building_2: building2Envelope,
    building_3: building3Envelope,
  },
  recommended_road_offset: roadOffset,
};

const defaultPhases: PhaseModel[] = [
  {
    id: "phase-structure",
    name: "主体施工",
    sequence: 1,
    objective: "围绕主体结构吊装、钢筋和模板堆场进行场布。",
    start_day: 1,
    end_day: 28,
    status: "active",
  },
  {
    id: "phase-envelope",
    name: "外围封闭",
    sequence: 2,
    objective: "优先保证机电材料与外立面周转路径。",
    start_day: 29,
    end_day: 52,
    status: "planned",
  },
  {
    id: "phase-fitout",
    name: "机电穿插",
    sequence: 3,
    objective: "控制小批量、多频次物料的临时落位和清运节奏。",
    start_day: 53,
    end_day: 84,
    status: "planned",
  },
];

const defaultCranes: CraneModel[] = [
  {
    id: "crane-main",
    name: "QTZ60-1",
    x: 0,
    y: 0,
    max_radius: 75,
    capacity_tons: 6,
    priority_score: 1,
  },
  {
    id: "crane-secondary-2",
    name: "QTZ60-2",
    x: 21.683222,
    y: 5.603814,
    max_radius: 75,
    capacity_tons: 6,
    priority_score: 0.96,
  },
  {
    id: "crane-secondary-3",
    name: "QTZ60-3",
    x: 19.499692,
    y: -16.905839,
    max_radius: 75,
    capacity_tons: 6,
    priority_score: 0.94,
  },
];

const createEnvelopeObstacle = (
  id: string,
  name: string,
  kind: string,
  envelope: EnvelopeGuide,
  groupKey?: string,
): ObstacleModel => ({
  id,
  name,
  kind,
  x: (envelope.min_x + envelope.max_x) / 2,
  y: (envelope.min_y + envelope.max_y) / 2,
  length: envelope.max_x - envelope.min_x,
  width: envelope.max_y - envelope.min_y,
  min_z: envelope.min_z ?? null,
  max_z: envelope.max_z ?? null,
  height: envelope.height ?? null,
  group_key: groupKey ?? null,
});

const createTiledEnvelopeObstacles = (
  ids: readonly string[],
  name: string,
  groupKey: string,
  envelope: EnvelopeGuide,
  columns: number,
  rows: number,
): ObstacleModel[] => {
  const tileLength = (envelope.max_x - envelope.min_x) / columns;
  const tileWidth = (envelope.max_y - envelope.min_y) / rows;

  return ids.map((id, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const min_x = envelope.min_x + (tileLength * column);
    const max_x = min_x + tileLength;
    const min_y = envelope.min_y + (tileWidth * row);
    const max_y = min_y + tileWidth;

    return createEnvelopeObstacle(
      id,
      `${name} Part ${index + 1}`,
      "building",
      {
        min_x,
        max_x,
        min_y,
        max_y,
        min_z: envelope.min_z ?? null,
        max_z: envelope.max_z ?? null,
        height: envelope.height ?? null,
      },
      groupKey,
    );
  });
};

const createRingRoadObstacles = (
  anchorEnvelope: EnvelopeGuide,
  offset: number,
  thickness: number,
): ObstacleModel[] => {
  const min_x = anchorEnvelope.min_x - offset;
  const max_x = anchorEnvelope.max_x + offset;
  const min_y = anchorEnvelope.min_y - offset;
  const max_y = anchorEnvelope.max_y + offset;
  const center_x = (min_x + max_x) / 2;
  const center_y = (min_y + max_y) / 2;

  return [
    createEnvelopeObstacle(
      "road-west",
      "West Ring Road",
      "road",
      {
        min_x,
        max_x: min_x + thickness,
        min_y,
        max_y,
      },
    ),
    createEnvelopeObstacle(
      "road-north",
      "North Ring Road",
      "road",
      {
        min_x,
        max_x,
        min_y: max_y - thickness,
        max_y,
      },
    ),
    createEnvelopeObstacle(
      "road-east",
      "East Ring Road",
      "road",
      {
        min_x: max_x - thickness,
        max_x,
        min_y,
        max_y,
      },
    ),
    createEnvelopeObstacle(
      "road-south",
      "South Ring Road",
      "road",
      {
        min_x,
        max_x,
        min_y,
        max_y: min_y + thickness,
      },
    ),
  ].map((item, index) => ({
    ...item,
    x: index % 2 === 0 ? item.x : center_x,
    y: index % 2 === 0 ? center_y : item.y,
  }));
};

const createWallObstacles = (envelope: EnvelopeGuide, thickness: number): ObstacleModel[] => [
  createEnvelopeObstacle(
    "wall-west",
    "West Wall",
    "wall",
    {
      min_x: envelope.min_x,
      max_x: envelope.min_x + thickness,
      min_y: envelope.min_y,
      max_y: envelope.max_y,
    },
  ),
  createEnvelopeObstacle(
    "wall-north",
    "North Wall",
    "wall",
    {
      min_x: envelope.min_x,
      max_x: envelope.max_x,
      min_y: envelope.max_y - thickness,
      max_y: envelope.max_y,
    },
  ),
  createEnvelopeObstacle(
    "wall-east",
    "East Wall",
    "wall",
    {
      min_x: envelope.max_x - thickness,
      max_x: envelope.max_x,
      min_y: envelope.min_y,
      max_y: envelope.max_y,
    },
  ),
  createEnvelopeObstacle(
    "wall-south",
    "South Wall",
    "wall",
    {
      min_x: envelope.min_x,
      max_x: envelope.max_x,
      min_y: envelope.min_y,
      max_y: envelope.min_y + thickness,
    },
  ),
];

const defaultObstacles: ObstacleModel[] = [
  ...createTiledEnvelopeObstacles(
    buildingComponentIds.building_1,
    "Main Building 1",
    "building_1",
    building1Envelope,
    2,
    2,
  ),
  ...createTiledEnvelopeObstacles(
    buildingComponentIds.building_2,
    "Main Building 2",
    "building_2",
    building2Envelope,
    5,
    1,
  ),
  ...createTiledEnvelopeObstacles(
    buildingComponentIds.building_3,
    "Main Building 3",
    "building_3",
    building3Envelope,
    1,
    2,
  ),
  ...createRingRoadObstacles(building1Envelope, roadOffset, roadThickness),
  ...createWallObstacles(wallEnvelope, wallThickness),
];

const defaultControlZones: ControlZoneModel[] = [
  {
    id: "zone-north-staging",
    name: "北侧钢筋暂存区",
    zone_type: "staging",
    x: 17,
    y: 28.5,
    length: 18,
    width: 10,
    phase_id: "phase-structure",
    blocking: false,
    penalty_factor: 1,
    notes: "主体施工阶段优先存放钢筋与模板周转料。",
  },
  {
    id: "zone-west-buffer",
    name: "西侧模板缓冲区",
    zone_type: "staging",
    x: -5.5,
    y: -2,
    length: 12,
    width: 18,
    phase_id: "phase-structure",
    blocking: false,
    penalty_factor: 1.1,
    notes: "适合频繁周转的模板和支撑系统。",
  },
  {
    id: "zone-south-delivery",
    name: "南侧卸料通道",
    zone_type: "delivery_lane",
    x: -1,
    y: -38,
    length: 18,
    width: 6,
    phase_id: "phase-structure",
    blocking: true,
    penalty_factor: 1,
    notes: "保持混凝土车和运输车辆连续通行。",
  },
  {
    id: "zone-east-emergency",
    name: "东侧应急通廊",
    zone_type: "emergency_access",
    x: 54,
    y: -25,
    length: 8,
    width: 26,
    phase_id: null,
    blocking: true,
    penalty_factor: 1,
    notes: "各阶段必须保持净空。",
  },
  {
    id: "zone-mep-buffer",
    name: "机电成品缓冲区",
    zone_type: "staging",
    x: 38,
    y: 28,
    length: 16,
    width: 10,
    phase_id: "phase-envelope",
    blocking: false,
    penalty_factor: 1.1,
    notes: "外围封闭与机电穿插阶段共用。",
  },
];

const layoutSnapshot = [
  {
    material_name: "钢筋主堆场",
    phase_id: "phase-structure",
    batch_id: "S-01",
    optimal_x: -4,
    optimal_y: 25,
    l: 8,
    w: 4,
    height: 1.2,
    weight_tons: 5.5,
    handling_frequency: 1.4,
    priority_score: 1.2,
    stay_days: 5,
    target_zone_id: "zone-north-staging",
    category: "steel",
  },
  {
    material_name: "模板周转区",
    phase_id: "phase-structure",
    batch_id: "F-01",
    optimal_x: -7,
    optimal_y: -5,
    l: 6,
    w: 5,
    height: 1.1,
    weight_tons: 3.2,
    handling_frequency: 1.1,
    priority_score: 1,
    stay_days: 4,
    target_zone_id: "zone-west-buffer",
    category: "formwork",
  },
  {
    material_name: "幕墙龙骨包",
    phase_id: "phase-envelope",
    batch_id: "E-02",
    optimal_x: 39,
    optimal_y: 27,
    l: 5,
    w: 3,
    height: 1,
    weight_tons: 2.8,
    handling_frequency: 0.9,
    priority_score: 1,
    stay_days: 3,
    target_zone_id: "zone-mep-buffer",
    category: "facade",
  },
  {
    material_name: "桥架成品包",
    phase_id: "phase-fitout",
    batch_id: "M-03",
    optimal_x: 37,
    optimal_y: 27,
    l: 4.2,
    w: 2.2,
    height: 1,
    weight_tons: 1.8,
    handling_frequency: 1.5,
    priority_score: 1.3,
    stay_days: 2,
    target_zone_id: "zone-mep-buffer",
    category: "mep",
  },
] as const;

const createMaterialFromSnapshot = (
  item: (typeof layoutSnapshot)[number],
  index: number,
): MaterialModel => ({
  id: `material-${crypto.randomUUID()}`,
  name: item.material_name,
  category: item.category,
  length: item.l,
  width: item.w,
  height: item.height,
  weight_tons: item.weight_tons,
  handling_frequency: item.handling_frequency,
  phase_id: item.phase_id,
  batch_id: item.batch_id,
  priority_score: item.priority_score,
  stay_days: item.stay_days,
  target_zone_id: item.target_zone_id,
  notes: null,
  display_color: colorPalette[index % colorPalette.length],
});

const cloneSiteBoundary = (boundary: SiteBoundary): SiteBoundary => ({ ...boundary });

const cloneSceneGuides = (sceneGuides: SceneGuides | null): SceneGuides | null =>
  sceneGuides ? structuredClone(sceneGuides) : null;

const createDemoMaterials = () =>
  layoutSnapshot.map((item, index) => createMaterialFromSnapshot(item, index));

const normalizeMaterials = (materials: MaterialModel[]): MaterialModel[] =>
  materials.map((material, index) => ({
    ...material,
    phase_id: material.phase_id ?? defaultPhases[0].id,
    priority_score: material.priority_score || 1,
    stay_days: material.stay_days || 3,
    display_color: material.display_color || colorPalette[index % colorPalette.length],
  }));

const clonePhases = (phases: PhaseModel[]): PhaseModel[] =>
  phases.map((phase) => ({ ...phase }));

const cloneZones = (zones: ControlZoneModel[]): ControlZoneModel[] =>
  zones.map((zone) => ({ ...zone }));

const cloneObstacles = (obstacles: ObstacleModel[]): ObstacleModel[] =>
  obstacles.map((obstacle) => ({ ...obstacle }));

const cloneCranes = (cranes: CraneModel[]): CraneModel[] =>
  cranes.map((crane) => ({ ...crane }));

const createDefaultMaterial = (
  index: number,
  phaseId: string | null,
  targetZoneId: string | null,
): MaterialModel => ({
  id: `material-${crypto.randomUUID()}`,
  name: `新物料 ${index + 1}`,
  category: "general",
  length: 4.5,
  width: 2.5,
  height: 1,
  weight_tons: 2.5,
  handling_frequency: 1,
  phase_id: phaseId,
  batch_id: `B-${index + 1}`,
  priority_score: 1,
  stay_days: 3,
  target_zone_id: targetZoneId,
  notes: null,
  display_color: colorPalette[index % colorPalette.length],
});

const mergeRecentVersions = (
  existing: PlanVersionSummary[],
  incoming: PlanVersionSummary,
): PlanVersionSummary[] => {
  const deduped = [incoming, ...existing.filter((item) => item.version_id !== incoming.version_id)];
  return deduped.slice(0, 6);
};

const createDemoSceneState = () => ({
  currentProjectId: defaultProjectId,
  projectName: defaultProjectName,
  siteBoundary: cloneSiteBoundary(realSiteBoundary),
  sceneGuides: cloneSceneGuides(defaultSceneGuides),
  phases: clonePhases(defaultPhases),
  activePhaseId: defaultPhases[0].id,
  controlZones: cloneZones(defaultControlZones),
  workingCranes: cloneCranes(defaultCranes),
  obstacles: cloneObstacles(defaultObstacles),
  materials: createDemoMaterials(),
  recentPlanVersions: [] as PlanVersionSummary[],
});

const createDemoBimDataStatus = (detail?: string | null): BimDataStatusModel => ({
  state: "demo",
  source: "demo_data",
  message: "未加载实时 BIM 快照，当前使用 demo 数据",
  detail: detail ?? "前端已回退到本地 demo 场景。",
  last_sync_error: null,
  last_sync_attempt_at: null,
  last_sync_success_at: null,
  snapshot_updated_at: null,
});

const createOfflineBimDataStatus = (detail: string): BimDataStatusModel => ({
  state: "offline",
  source: "unknown",
  message: "后端未连接",
  detail,
  last_sync_error: detail,
  last_sync_attempt_at: null,
  last_sync_success_at: null,
  snapshot_updated_at: null,
});

export const useLayoutStore = defineStore("layout", {
  state: () => ({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1",
    ...createDemoSceneState(),
    optimizationResult: null as OptimizationResult | null,
    bimDataStatus: createDemoBimDataStatus(),
    snapshotLoading: false,
    hasLoadedRealtimeSnapshot: false,
    loading: false,
    error: "",
  }),
  getters: {
    activePhase: (state) =>
      state.phases.find((phase) => phase.id === state.activePhaseId) ?? state.phases[0] ?? null,
    activeMaterials: (state) => {
      if (!state.phases.length || !state.activePhaseId) {
        return state.materials;
      }
      return state.materials.filter((material) => material.phase_id === state.activePhaseId);
    },
    phaseControlZones: (state) =>
      state.controlZones.filter((zone) => !zone.phase_id || zone.phase_id === state.activePhaseId),
    hasResult: (state) =>
      state.optimizationResult !== null && state.optimizationResult.phase_id === state.activePhaseId,
  },
  actions: {
    applyProjectSnapshot(snapshot: ProjectSnapshotModel) {
      this.currentProjectId = snapshot.project_id;
      this.projectName = snapshot.name;
      this.siteBoundary = cloneSiteBoundary(snapshot.site_boundary);
      this.sceneGuides = cloneSceneGuides(snapshot.scene_guides ?? defaultSceneGuides);
      this.phases = snapshot.phases.length ? clonePhases(snapshot.phases) : clonePhases(defaultPhases);
      this.activePhaseId = snapshot.active_phase_id ?? this.phases[0]?.id ?? null;
      this.controlZones = snapshot.control_zones.length
        ? cloneZones(snapshot.control_zones)
        : cloneZones(defaultControlZones);
      this.workingCranes = snapshot.working_cranes.length
        ? cloneCranes(snapshot.working_cranes)
        : cloneCranes(defaultCranes);
      this.obstacles = snapshot.obstacles.length
        ? cloneObstacles(snapshot.obstacles)
        : cloneObstacles(defaultObstacles);
      if (snapshot.materials.length > 0) {
        this.materials = normalizeMaterials(snapshot.materials);
      }
      this.recentPlanVersions = [...snapshot.recent_plan_versions];
      this.optimizationResult = snapshot.latest_optimization_result ?? null;
      this.bimDataStatus = { ...snapshot.bim_data_status };
      this.hasLoadedRealtimeSnapshot = snapshot.bim_data_status.state === "live"
        || snapshot.bim_data_status.state === "syncing";
      if (this.optimizationResult && this.optimizationResult.phase_id !== this.activePhaseId) {
        this.optimizationResult = null;
      }
    },
    resetToDemoScene() {
      const demoScene = createDemoSceneState();
      this.currentProjectId = demoScene.currentProjectId;
      this.projectName = demoScene.projectName;
      this.siteBoundary = demoScene.siteBoundary;
      this.sceneGuides = demoScene.sceneGuides;
      this.phases = demoScene.phases;
      this.activePhaseId = demoScene.activePhaseId;
      this.controlZones = demoScene.controlZones;
      this.workingCranes = demoScene.workingCranes;
      this.obstacles = demoScene.obstacles;
      this.materials = demoScene.materials;
      this.recentPlanVersions = demoScene.recentPlanVersions;
      this.optimizationResult = null;
      this.hasLoadedRealtimeSnapshot = false;
      this.error = "";
    },
    setBimDataStatus(status: BimDataStatusModel) {
      this.bimDataStatus = { ...status };
    },
    setActivePhase(phaseId: string) {
      this.activePhaseId = phaseId;
      if (this.optimizationResult && this.optimizationResult.phase_id !== phaseId) {
        this.optimizationResult = null;
      }
    },
    async loadProjectSnapshot() {
      const hadRealtimeSnapshot = this.hasLoadedRealtimeSnapshot;
      const projectId = this.currentProjectId || defaultProjectId;
      const statusUrl = `${this.apiBaseUrl}/projects/${projectId}/bim-data-status`;
      const projectUrl = `${this.apiBaseUrl}/projects/${projectId}`;

      this.snapshotLoading = true;
      try {
        const statusResponse = await fetch(statusUrl);
        if (!statusResponse.ok) {
          const message = await statusResponse.text();
          throw new Error(message || "Failed to load BIM snapshot status.");
        }

        const status = (await statusResponse.json()) as BimDataStatusModel;
        this.setBimDataStatus(status);

        const canUseRealtimeSnapshot = status.state === "live"
          || (status.state === "syncing" && Boolean(status.snapshot_updated_at || status.last_sync_success_at));

        if (!canUseRealtimeSnapshot) {
          this.resetToDemoScene();
          this.setBimDataStatus(status);
          return status.state;
        }

        const response = await fetch(projectUrl);
        if (response.status === 404) {
          this.resetToDemoScene();
          this.setBimDataStatus(
            createDemoBimDataStatus("后端状态显示实时快照可用，但项目快照不存在，已回退到 demo 场景。"),
          );
          return "demo";
        }
        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || "Failed to load BIM project snapshot.");
        }

        this.applyProjectSnapshot((await response.json()) as ProjectSnapshotModel);
        return this.bimDataStatus.state;
      } catch (error) {
        const detail = error instanceof Error ? error.message : "无法连接 FastAPI 后端。";
        const previousStatus = { ...this.bimDataStatus };
        if (!hadRealtimeSnapshot) {
          this.resetToDemoScene();
        }
        const offlineStatus = createOfflineBimDataStatus(
          hadRealtimeSnapshot
            ? `无法连接 FastAPI 后端，当前保留最近一次已加载的快照。${detail ? ` ${detail}` : ""}`
            : `无法连接 FastAPI 后端，当前继续使用 demo 数据。${detail ? ` ${detail}` : ""}`,
        );
        offlineStatus.last_sync_success_at = previousStatus.last_sync_success_at ?? null;
        offlineStatus.snapshot_updated_at = previousStatus.snapshot_updated_at ?? null;
        this.setBimDataStatus(offlineStatus);
        return "offline";
      } finally {
        this.snapshotLoading = false;
      }
    },
    addMaterial() {
      const targetZoneId =
        this.phaseControlZones.find((zone) => !zone.blocking && zone.zone_type === "staging")?.id ?? null;
      this.materials.push(createDefaultMaterial(this.materials.length, this.activePhaseId, targetZoneId));
    },
    appendImportedMaterials(materials: MaterialModel[]) {
      if (!materials.length) {
        return;
      }

      this.materials = normalizeMaterials([...this.materials, ...materials]);
    },
    removeMaterial(id: string) {
      if (this.materials.length === 1) {
        return;
      }

      this.materials = this.materials.filter((item) => item.id !== id);
    },
    async optimizeLayout() {
      this.loading = true;
      this.error = "";

      try {
        const response = await fetch(`${this.apiBaseUrl}/projects/${this.currentProjectId}/optimize`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: this.projectName,
            site_boundary: this.siteBoundary,
            phases: this.phases,
            active_phase_id: this.activePhaseId,
            control_zones: this.controlZones,
            scene_guides: this.sceneGuides,
            working_cranes: this.workingCranes,
            obstacles: this.obstacles,
            materials: this.materials,
            population_size: 56,
            generations: 90,
            mutation_rate: 0.22,
            clearance: 1.2,
            crane_path_penalty: 22,
            zone_preference_penalty: 14,
          }),
        });

        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || "Layout optimization failed.");
        }

        this.optimizationResult = (await response.json()) as OptimizationResult;
        this.recentPlanVersions = mergeRecentVersions(
          this.recentPlanVersions,
          this.optimizationResult.current_version,
        );
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Layout optimization failed.";
      } finally {
        this.loading = false;
      }
    },
  },
});
