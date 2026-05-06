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

export interface BoundaryPoint {
  x: number;
  y: number;
}

export interface SceneGuides {
  wall_envelope?: EnvelopeGuide | null;
  wall_boundary_path?: BoundaryPoint[];
  building_envelopes: Record<string, EnvelopeGuide>;
  recommended_road_offset?: number | null;
}

export interface PhaseModel {
  id: string;
  name: string;
  sequence: number;
  objective?: string | null;
  start_day?: number | null;
  end_day?: number | null;
  status: string;
}

export interface ControlZoneModel {
  id: string;
  name: string;
  zone_type: string;
  x: number;
  y: number;
  length: number;
  width: number;
  min_z?: number | null;
  max_z?: number | null;
  height?: number | null;
  phase_id?: string | null;
  blocking: boolean;
  penalty_factor: number;
  notes?: string | null;
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
  notes?: string | null;
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
  phase_id?: string | null;
  batch_id?: string | null;
  priority_score: number;
  stay_days: number;
  target_zone_id?: string | null;
  notes?: string | null;
  display_color?: string | null;
}

export interface CraneOption {
  crane_id: string;
  crane_name: string;
  reachable: boolean;
  reason: string;
  reason_code: string;
  distance?: number | null;
  estimated_cost?: number | null;
  path_crosses_obstacle: boolean;
  travel_height?: number | null;
}

export interface DecisionFactor {
  label: string;
  value: string;
  tone: string;
}

export interface PlacementAlert {
  code: string;
  level: string;
  title: string;
  detail: string;
}

export interface ActionItem {
  id: string;
  category: string;
  severity: string;
  title: string;
  detail: string;
}

export interface PlacementResult {
  material_id: string;
  material_name: string;
  x: number;
  y: number;
  z: number;
  length: number;
  width: number;
  height: number;
  display_color?: string | null;
  assigned_crane_id?: string | null;
  assigned_crane_name?: string | null;
  distance?: number | null;
  transport_cost?: number | null;
  phase_id?: string | null;
  batch_id?: string | null;
  priority_score: number;
  target_zone_id?: string | null;
  target_zone_name?: string | null;
  inside_target_zone: boolean;
  blocking_zone_hits: string[];
  decision_note: string;
  decision_factors: DecisionFactor[];
  crane_options: CraneOption[];
  path_crosses_obstacle: boolean;
  travel_height?: number | null;
  review_alerts: PlacementAlert[];
  status: string;
}

export interface PlanVersionSummary {
  version_id: string;
  version_label: string;
  phase_id?: string | null;
  phase_name?: string | null;
  total_cost: number;
  feasible_layout: boolean;
  placed_count: number;
  unplaced_count: number;
  created_at: string;
}

export type BimDataStatusState = "syncing" | "live" | "demo" | "offline";

export interface BimDataStatusModel {
  state: BimDataStatusState;
  source: "realtime_snapshot" | "demo_data" | "unknown";
  message: string;
  detail?: string | null;
  last_sync_error?: string | null;
  last_sync_attempt_at?: string | null;
  last_sync_success_at?: string | null;
  snapshot_updated_at?: string | null;
}

export interface OptimizationMetrics {
  phase_id?: string | null;
  phase_name?: string | null;
  total_cost: number;
  transport_cost: number;
  safety_penalty: number;
  zone_penalty: number;
  feasible_layout: boolean;
  placed_count: number;
  unplaced_count: number;
  in_target_zone_count: number;
  generations: number;
  best_fitness_history: number[];
  warnings: string[];
  decision_summary: string[];
  action_items: ActionItem[];
}

export interface OptimizationResult {
  project_id: string;
  project_name: string;
  phase_id?: string | null;
  phase_name?: string | null;
  placements: PlacementResult[];
  metrics: OptimizationMetrics;
  current_version: PlanVersionSummary;
}

export interface ProjectSnapshotModel {
  project_id: string;
  name: string;
  site_boundary: SiteBoundary;
  phases: PhaseModel[];
  active_phase_id?: string | null;
  control_zones: ControlZoneModel[];
  working_cranes: CraneModel[];
  obstacles: ObstacleModel[];
  materials: MaterialModel[];
  scene_guides?: SceneGuides | null;
  latest_total_cost?: number | null;
  recent_plan_versions: PlanVersionSummary[];
  latest_optimization_result?: OptimizationResult | null;
  bim_data_status: BimDataStatusModel;
}
