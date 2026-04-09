export interface SiteBoundary {
  min_x: number;
  max_x: number;
  min_y: number;
  max_y: number;
}

export interface EnvelopeGuide {
  min_x: number;
  max_x: number;
  min_y: number;
  max_y: number;
  min_z?: number | null;
  max_z?: number | null;
  height?: number | null;
}

export interface SceneGuides {
  wall_envelope?: EnvelopeGuide | null;
  building_envelopes: Record<string, EnvelopeGuide>;
  recommended_road_offset?: number | null;
}

export interface CraneModel {
  id: string;
  name: string;
  x: number;
  y: number;
  max_radius: number;
  capacity_tons: number;
  priority_score: number;
}

export interface ObstacleModel {
  id: string;
  name: string;
  kind: string;
  x: number;
  y: number;
  length: number;
  width: number;
  min_z?: number | null;
  max_z?: number | null;
  height?: number | null;
  group_key?: string | null;
  notes?: string;
}

export interface MaterialModel {
  id: string;
  name: string;
  category: string;
  length: number;
  width: number;
  height: number;
  weight_tons: number;
  handling_frequency: number;
  display_color?: string;
}

export interface PlacementResult {
  material_id: string;
  material_name: string;
  x: number;
  y: number;
  length: number;
  width: number;
  display_color?: string | null;
  assigned_crane_id?: string | null;
  assigned_crane_name?: string | null;
  distance?: number | null;
  transport_cost?: number | null;
  path_crosses_obstacle: boolean;
  status: string;
}

export interface OptimizationMetrics {
  total_cost: number;
  feasible_layout: boolean;
  placed_count: number;
  unplaced_count: number;
  generations: number;
  best_fitness_history: number[];
  warnings: string[];
}

export interface OptimizationResult {
  project_id: string;
  project_name: string;
  placements: PlacementResult[];
  metrics: OptimizationMetrics;
}

export interface ProjectSnapshotModel {
  project_id: string;
  name: string;
  site_boundary: SiteBoundary;
  working_cranes: CraneModel[];
  obstacles: ObstacleModel[];
  materials: MaterialModel[];
  scene_guides?: SceneGuides | null;
  latest_total_cost?: number | null;
}
