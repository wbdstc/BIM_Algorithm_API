import { defineStore } from "pinia";

import type {
  CraneModel,
  EnvelopeGuide,
  MaterialModel,
  ObstacleModel,
  OptimizationResult,
  ProjectSnapshotModel,
  SceneGuides,
  SiteBoundary,
} from "../types/layout";

const colorPalette = ["#38BDF8", "#8B5CF6", "#F59E0B", "#10B981", "#F97316", "#EF4444"];

const roadOffset = 1500;
const roadThickness = 180;
const wallThickness = 140;

const building1Envelope: EnvelopeGuide = {
  min_x: 69.275,
  max_x: 3349.305,
  min_y: -2667.26,
  max_y: 2101.0,
  min_z: 0,
  max_z: 52,
  height: 52,
};

const building2Envelope: EnvelopeGuide = {
  min_x: 1120,
  max_x: 2400,
  min_y: -4280,
  max_y: -2680,
  min_z: 0,
  max_z: 34,
  height: 34,
};

const building3Envelope: EnvelopeGuide = {
  min_x: 4531.55,
  max_x: 5620.45,
  min_y: -1078.925,
  max_y: 2246.185,
  min_z: 0,
  max_z: 34,
  height: 34,
};

const wallEnvelope: EnvelopeGuide = {
  min_x: -1800,
  max_x: 6200,
  min_y: -4600,
  max_y: 4000,
};

const realSiteBoundary: SiteBoundary = {
  min_x: wallEnvelope.min_x,
  max_x: wallEnvelope.max_x,
  min_y: wallEnvelope.min_y,
  max_y: wallEnvelope.max_y,
};

const defaultSceneGuides: SceneGuides = {
  wall_envelope: wallEnvelope,
  building_envelopes: {
    building_1: building1Envelope,
    building_2: building2Envelope,
    building_3: building3Envelope,
  },
  recommended_road_offset: roadOffset,
};

const defaultCranes: CraneModel[] = [
  {
    id: "crane-main",
    name: "主塔吊_1",
    x: 0,
    y: 0,
    max_radius: 3200,
    capacity_tons: 18,
    priority_score: 1,
  },
  {
    id: "crane-secondary-2",
    name: "副塔吊_2",
    x: 2168.3222,
    y: 560.3814,
    max_radius: 2800,
    capacity_tons: 16,
    priority_score: 0.96,
  },
  {
    id: "crane-secondary-3",
    name: "副塔吊_3",
    x: 1949.9692,
    y: -1690.5839,
    max_radius: 2800,
    capacity_tons: 16,
    priority_score: 0.94,
  },
];

const layoutSnapshot = [
  {
    material_name: "重型钢筋加工区",
    optimal_x: -320,
    optimal_y: 980,
    nearest_crane: "主塔吊_1",
    l: 200,
    w: 100,
  },
  {
    material_name: "木模板堆场",
    optimal_x: -420,
    optimal_y: -820,
    nearest_crane: "主塔吊_1",
    l: 150,
    w: 150,
  },
] as const;

const createMaterialFromSnapshot = (
  item: (typeof layoutSnapshot)[number],
  index: number,
): MaterialModel => ({
  id: `material-${crypto.randomUUID()}`,
  name: item.material_name,
  category: item.material_name.includes("模板") ? "formwork" : "steel",
  length: item.l,
  width: item.w,
  height: item.material_name.includes("模板") ? 20 : 30,
  weight_tons: item.material_name.includes("模板") ? 4 : 12,
  handling_frequency: item.material_name.includes("模板") ? 0.8 : 1.2,
  display_color: colorPalette[index % colorPalette.length],
});

const createSnapshotOptimizationResult = (): OptimizationResult => {
  const craneByName = new Map(defaultCranes.map((crane) => [crane.name, crane]));

  return {
    project_id: "demo-smart-site",
    project_name: "BIM 智慧工地 AI 场布示范项目",
    placements: layoutSnapshot.map((item, index) => {
      const assignedCrane = craneByName.get(item.nearest_crane);

      return {
        material_id: `snapshot-placement-${index + 1}`,
        material_name: item.material_name,
        x: item.optimal_x,
        y: item.optimal_y,
        length: item.l,
        width: item.w,
        display_color: colorPalette[index % colorPalette.length],
        assigned_crane_id: assignedCrane?.id ?? null,
        assigned_crane_name: assignedCrane?.name ?? item.nearest_crane,
        distance: null,
        transport_cost: null,
        path_crosses_obstacle: false,
        status: "placed",
      };
    }),
    metrics: {
      total_cost: 0,
      feasible_layout: true,
      placed_count: layoutSnapshot.length,
      unplaced_count: 0,
      generations: 0,
      best_fitness_history: [],
      warnings: [],
    },
  };
};

const createDefaultMaterial = (index: number): MaterialModel => ({
  id: `material-${crypto.randomUUID()}`,
  name: `新增物料 ${index + 1}`,
  category: "steel",
  length: 120,
  width: 80,
  height: 20,
  weight_tons: 6,
  handling_frequency: 1,
  display_color: colorPalette[index % colorPalette.length],
});

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
      "环路西段",
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
      "环路北段",
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
      "环路东段",
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
      "环路南段",
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
    "西侧围墙",
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
    "北侧围墙",
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
    "东侧围墙",
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
    "南侧围墙",
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
  createEnvelopeObstacle("building-1", "主体建筑1", "building", building1Envelope, "building_1"),
  createEnvelopeObstacle("building-2", "主体建筑2", "building", building2Envelope, "building_2"),
  createEnvelopeObstacle("building-3", "主体建筑3", "building", building3Envelope, "building_3"),
  ...createRingRoadObstacles(building1Envelope, roadOffset, roadThickness),
  ...createWallObstacles(wallEnvelope, wallThickness),
];

const normalizeMaterials = (materials: MaterialModel[]): MaterialModel[] =>
  materials.map((material, index) => ({
    ...material,
    display_color: material.display_color || colorPalette[index % colorPalette.length],
  }));

export const useLayoutStore = defineStore("layout", {
  state: () => ({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1",
    currentProjectId: "demo-smart-site",
    projectName: "BIM 智慧工地 AI 场布示范项目",
    siteBoundary: realSiteBoundary,
    sceneGuides: defaultSceneGuides as SceneGuides | null,
    workingCranes: defaultCranes,
    obstacles: defaultObstacles,
    materials: layoutSnapshot.map((item, index) => createMaterialFromSnapshot(item, index)),
    optimizationResult: createSnapshotOptimizationResult() as OptimizationResult | null,
    loading: false,
    error: "",
  }),
  getters: {
    totalMaterials: (state) => state.materials.length,
    hasResult: (state) => state.optimizationResult !== null,
  },
  actions: {
    applyProjectSnapshot(snapshot: ProjectSnapshotModel) {
      this.currentProjectId = snapshot.project_id;
      this.projectName = snapshot.name;
      this.siteBoundary = { ...snapshot.site_boundary };
      this.sceneGuides = snapshot.scene_guides ?? null;
      this.workingCranes = [...snapshot.working_cranes];
      this.obstacles = [...snapshot.obstacles];
      if (snapshot.materials.length > 0) {
        this.materials = normalizeMaterials(snapshot.materials);
      }
      this.optimizationResult = null;
    },
    async loadProjectSnapshot() {
      try {
        const response = await fetch(`${this.apiBaseUrl}/projects/${this.currentProjectId}`);
        if (response.status === 404 || !response.ok) {
          return;
        }

        this.applyProjectSnapshot((await response.json()) as ProjectSnapshotModel);
      } catch {
        // Keep the local demo scene when the backend snapshot is unavailable.
      }
    },
    addMaterial() {
      this.materials.push(createDefaultMaterial(this.materials.length));
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
            scene_guides: this.sceneGuides,
            working_cranes: this.workingCranes,
            obstacles: this.obstacles,
            materials: this.materials,
            population_size: 56,
            generations: 90,
            mutation_rate: 0.22,
            clearance: 1,
            crane_path_penalty: 22,
          }),
        });

        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || "优化接口请求失败");
        }

        this.optimizationResult = (await response.json()) as OptimizationResult;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "优化请求异常";
      } finally {
        this.loading = false;
      }
    },
  },
});
