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

const colorPalette = ["#38BDF8", "#14B8A6", "#F59E0B", "#10B981", "#F97316", "#EF4444"];

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

const defaultCranes: CraneModel[] = [
  {
    id: "crane-main",
    name: "QTZ60-1",
    x: 0,
    y: 0,
    max_radius: 50,
    capacity_tons: 6,
    priority_score: 1,
  },
  {
    id: "crane-secondary-2",
    name: "QTZ60-2",
    x: 21.683222,
    y: 5.603814,
    max_radius: 50,
    capacity_tons: 6,
    priority_score: 0.96,
  },
  {
    id: "crane-secondary-3",
    name: "QTZ60-3",
    x: 19.499692,
    y: -16.905839,
    max_radius: 50,
    capacity_tons: 6,
    priority_score: 0.94,
  },
];

const layoutSnapshot = [
  {
    material_name: "Rebar Yard",
    optimal_x: -3.2,
    optimal_y: 9.8,
    nearest_crane: "QTZ60-1",
    l: 2,
    w: 1,
  },
  {
    material_name: "Formwork Yard",
    optimal_x: -4.2,
    optimal_y: -8.2,
    nearest_crane: "QTZ60-1",
    l: 1.5,
    w: 1.5,
  },
] as const;

const isFormworkMaterial = (name: string) => name.toLowerCase().includes("formwork");

const createMaterialFromSnapshot = (
  item: (typeof layoutSnapshot)[number],
  index: number,
): MaterialModel => ({
  id: `material-${crypto.randomUUID()}`,
  name: item.material_name,
  category: isFormworkMaterial(item.material_name) ? "formwork" : "steel",
  length: item.l,
  width: item.w,
  height: isFormworkMaterial(item.material_name) ? 0.25 : 0.4,
  weight_tons: isFormworkMaterial(item.material_name) ? 1.5 : 3.5,
  handling_frequency: isFormworkMaterial(item.material_name) ? 0.8 : 1.2,
  display_color: colorPalette[index % colorPalette.length],
});

const createSnapshotOptimizationResult = (): OptimizationResult => {
  const craneByName = new Map(defaultCranes.map((crane) => [crane.name, crane]));

  return {
    project_id: "demo-smart-site",
    project_name: "BIM Smart Site Demo",
    placements: layoutSnapshot.map((item, index) => {
      const assignedCrane = craneByName.get(item.nearest_crane);
      const isFormwork = isFormworkMaterial(item.material_name);

      return {
        material_id: `snapshot-placement-${index + 1}`,
        material_name: item.material_name,
        x: item.optimal_x,
        y: item.optimal_y,
        z: 0,
        length: item.l,
        width: item.w,
        height: isFormwork ? 0.25 : 0.4,
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
  name: `Material ${index + 1}`,
  category: "steel",
  length: 1.2,
  width: 0.8,
  height: 0.3,
  weight_tons: 2,
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
      "Ring Road West",
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
      "Ring Road North",
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
      "Ring Road East",
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
      "Ring Road South",
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
  createEnvelopeObstacle("building-1", "Main Building 1", "building", building1Envelope, "building_1"),
  createEnvelopeObstacle("building-2", "Main Building 2", "building", building2Envelope, "building_2"),
  createEnvelopeObstacle("building-3", "Main Building 3", "building", building3Envelope, "building_3"),
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
    projectName: "BIM Smart Site Demo",
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
            clearance: 1.2,
            crane_path_penalty: 22,
          }),
        });

        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || "Layout optimization failed.");
        }

        this.optimizationResult = (await response.json()) as OptimizationResult;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Layout optimization failed.";
      } finally {
        this.loading = false;
      }
    },
  },
});
