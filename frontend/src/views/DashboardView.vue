<template>
  <div class="dashboard-shell">
    <header class="dashboard-toolbar">
      <div class="toolbar-copy">
        <p class="toolbar-kicker">PHASE PLANNING WORKSPACE</p>
        <h1>{{ projectName }}</h1>
        <p>{{ phaseSubtitle }}</p>
      </div>

      <div class="toolbar-stats">
        <article class="toolbar-stat">
          <span>当前阶段</span>
          <strong>{{ activePhase?.name ?? "未设置" }}</strong>
        </article>
        <article class="toolbar-stat">
          <span>本阶段物料</span>
          <strong>{{ activeMaterials.length }} 批</strong>
        </article>
        <article class="toolbar-stat">
          <span>管控区</span>
          <strong>{{ phaseControlZones.length }} 个</strong>
        </article>
        <article class="toolbar-stat">
          <span>版本</span>
          <strong>{{ phaseVersions.length }} 条</strong>
        </article>
      </div>

      <div class="toolbar-actions">
        <div class="panel-toggle-group">
          <button
            type="button"
            :class="['panel-toggle-chip', { 'panel-toggle-chip--active': leftPanelOpen }]"
            @click="leftPanelOpen = !leftPanelOpen"
          >
            {{ leftPanelOpen ? "收起左栏" : "展开左栏" }}
          </button>
          <button
            type="button"
            :class="['panel-toggle-chip', { 'panel-toggle-chip--active': rightPanelOpen }]"
            @click="rightPanelOpen = !rightPanelOpen"
          >
            {{ rightPanelOpen ? "收起右栏" : "展开右栏" }}
          </button>
        </div>
        <el-select
          :model-value="activePhaseId"
          placeholder="选择阶段"
          class="phase-select"
          @change="handlePhaseChange"
        >
          <el-option
            v-for="phase in phases"
            :key="phase.id"
            :label="phase.name"
            :value="phase.id"
          />
        </el-select>
        <span :class="['status-pill', reportToneClass]">{{ reportLabel }}</span>
        <el-button
          type="primary"
          size="large"
          class="cta-button"
          :loading="loading"
          @click="layoutStore.optimizeLayout"
        >
          生成本阶段场布
        </el-button>
      </div>
    </header>

    <div
      :class="[
        'workspace-grid',
        {
          'workspace-grid--left-collapsed': !leftPanelOpen,
          'workspace-grid--right-collapsed': !rightPanelOpen,
        },
      ]"
    >
      <aside :class="['panel panel--left', { 'panel--collapsed': !leftPanelOpen }]">
        <div v-if="!leftPanelOpen" class="collapsed-rail">
          <button type="button" class="rail-button rail-button--primary" @click="leftPanelOpen = true">
            左栏
          </button>
          <button type="button" class="rail-button" @click="leftPanelOpen = true; phaseExpanded = true">
            阶段
          </button>
          <button type="button" class="rail-button" @click="leftPanelOpen = true; materialsExpanded = true">
            物料
          </button>
        </div>

        <template v-else>
        <section class="panel-section">
          <div class="panel-head panel-head--button" @click="phaseExpanded = !phaseExpanded">
            <div>
              <p class="panel-kicker">Phase</p>
              <h2>阶段计划</h2>
            </div>
            <span class="section-toggle">{{ phaseExpanded ? "收起" : "展开" }}</span>
          </div>

          <div v-show="phaseExpanded" class="phase-list">
            <button
              v-for="phase in phases"
              :key="phase.id"
              type="button"
              :class="['phase-card', { 'phase-card--active': phase.id === activePhaseId }]"
              @click="layoutStore.setActivePhase(phase.id)"
            >
              <div class="phase-card__head">
                <strong>{{ phase.sequence }}. {{ phase.name }}</strong>
                <span class="phase-badge">{{ phase.status }}</span>
              </div>
              <p>{{ phase.objective || "暂无阶段目标" }}</p>
              <small v-if="phase.start_day && phase.end_day">第 {{ phase.start_day }} - {{ phase.end_day }} 天</small>
            </button>
          </div>
        </section>

        <section class="panel-section panel-section--fill">
          <div class="panel-head panel-head--button" @click="materialsExpanded = !materialsExpanded">
            <div>
              <p class="panel-kicker">Materials</p>
              <h2>本阶段物料</h2>
            </div>

            <el-button class="utility-button" @click.stop="layoutStore.addMaterial">
              新增物料
            </el-button>
            <span class="section-toggle">{{ materialsExpanded ? "收起" : "展开" }}</span>
          </div>

          <div v-show="materialsExpanded" class="material-list">
            <button
              v-for="material in activeMaterials"
              :key="material.id"
              type="button"
              :class="['material-card', { 'material-card--active': material.id === selectedMaterialId }]"
              @click="selectedMaterialId = material.id"
            >
              <div class="material-card__head">
                <div class="material-label">
                  <span class="material-dot" :style="{ background: material.display_color || '#38bdf8' }" />
                  <strong>{{ material.name }}</strong>
                </div>
                <span class="material-batch">{{ material.batch_id || "未分批" }}</span>
              </div>
              <p>{{ material.category }} · {{ formatMetric(material.weight_tons, 1) }} t · {{ formatMetric(material.stay_days, 0) }} 天</p>
              <small>{{ zoneName(material.target_zone_id) }}</small>
            </button>
          </div>

          <div v-if="materialsExpanded && selectedMaterial" class="editor-block">
            <div class="editor-head">
              <p class="panel-kicker">Editor</p>
              <h3>{{ selectedMaterial.name }}</h3>
            </div>

            <div class="field-grid">
              <label class="field-card field-card--full">
                <span>物料名称</span>
                <el-input v-model="selectedMaterial.name" class="ghost-input" />
              </label>
              <label class="field-card">
                <span>批次号</span>
                <el-input v-model="selectedMaterial.batch_id" class="ghost-input" />
              </label>
              <label class="field-card">
                <span>分类</span>
                <el-input v-model="selectedMaterial.category" class="ghost-input" />
              </label>
              <label class="field-card">
                <span>重量 (t)</span>
                <el-input-number
                  v-model="selectedMaterial.weight_tons"
                  :min="0.1"
                  :step="0.1"
                  :controls="false"
                  class="ghost-number"
                />
              </label>
              <label class="field-card">
                <span>停留天数</span>
                <el-input-number
                  v-model="selectedMaterial.stay_days"
                  :min="1"
                  :step="1"
                  :controls="false"
                  class="ghost-number"
                />
              </label>
              <label class="field-card">
                <span>优先级</span>
                <el-input-number
                  v-model="selectedMaterial.priority_score"
                  :min="0.2"
                  :step="0.1"
                  :controls="false"
                  class="ghost-number"
                />
              </label>
              <label class="field-card field-card--full">
                <span>目标管控区</span>
                <el-select v-model="selectedMaterial.target_zone_id" class="ghost-select">
                  <el-option
                    v-for="zone in assignableZones"
                    :key="zone.id"
                    :label="zone.name"
                    :value="zone.id"
                  />
                </el-select>
              </label>
            </div>

            <div class="editor-actions">
              <el-button text class="danger-button" @click="layoutStore.removeMaterial(selectedMaterial.id)">
                删除物料
              </el-button>
            </div>
          </div>
        </section>

        <p v-if="error" class="panel-error">{{ error }}</p>
        </template>
      </aside>

      <main class="panel panel--canvas">
        <CanvasMap :highlight-material-id="selectedMaterialId" />
      </main>

      <aside :class="['panel panel--right', { 'panel--collapsed': !rightPanelOpen }]">
        <div v-if="!rightPanelOpen" class="collapsed-rail">
          <button type="button" class="rail-button rail-button--primary" @click="rightPanelOpen = true">
            右栏
          </button>
          <button type="button" class="rail-button" @click="rightPanelOpen = true; decisionExpanded = true">
            解释
          </button>
          <button type="button" class="rail-button" @click="rightPanelOpen = true; actionsExpanded = true">
            动作
          </button>
        </div>

        <template v-else>
        <section class="panel-section">
          <div class="panel-head panel-head--button" @click="resultExpanded = !resultExpanded">
            <div>
              <p class="panel-kicker">Result</p>
              <h2>阶段结论</h2>
            </div>
            <span class="section-toggle">{{ resultExpanded ? "收起" : "展开" }}</span>
          </div>

          <div v-show="resultExpanded" class="summary-grid">
            <article class="summary-card summary-card--primary">
              <span>落位完成度</span>
              <strong>{{ currentResult ? `${placementRate}%` : "--" }}</strong>
              <p>{{ currentResult?.metrics.placed_count ?? 0 }} / {{ activeMaterials.length }} 批</p>
            </article>
            <article class="summary-card">
              <span>运输成本</span>
              <strong>{{ currentResult ? formatMetric(currentResult.metrics.transport_cost, 1) : "--" }}</strong>
            </article>
            <article class="summary-card">
              <span>安全罚分</span>
              <strong>{{ currentResult ? formatMetric(currentResult.metrics.safety_penalty, 1) : "--" }}</strong>
            </article>
            <article class="summary-card">
              <span>目标区命中</span>
              <strong>{{ currentResult ? `${currentResult.metrics.in_target_zone_count} 批` : "--" }}</strong>
            </article>
          </div>
        </section>

        <section class="panel-section panel-section--fill">
          <div class="panel-head panel-head--button" @click="decisionExpanded = !decisionExpanded">
            <div>
              <p class="panel-kicker">Decision</p>
              <h2>选中物料解释</h2>
            </div>
            <span class="section-toggle">{{ decisionExpanded ? "收起" : "展开" }}</span>
          </div>

          <template v-if="decisionExpanded && selectedPlacement">
            <div class="decision-card">
              <div class="decision-head">
                <div>
                  <strong>{{ selectedPlacement.material_name }}</strong>
                  <p>{{ selectedPlacement.batch_id || "未分批" }} · {{ selectedPlacement.assigned_crane_name || "未分配塔吊" }}</p>
                </div>
                <span :class="['status-pill', placementToneClass]">{{ placementLabel }}</span>
              </div>

              <p class="decision-note">{{ selectedPlacement.decision_note }}</p>

              <div class="tag-list">
                <span
                  v-for="factor in selectedPlacement.decision_factors"
                  :key="`${factor.label}-${factor.value}`"
                  :class="['decision-tag', `decision-tag--${factor.tone}`]"
                >
                  {{ factor.label }} · {{ factor.value }}
                </span>
              </div>

              <div class="subsection">
                <h3>塔吊方案</h3>
                <div class="option-list">
                  <article
                    v-for="option in selectedPlacement.crane_options"
                    :key="option.crane_id"
                    :class="['option-card', { 'option-card--muted': !option.reachable }]"
                  >
                    <div class="option-card__head">
                      <strong>{{ option.crane_name }}</strong>
                      <span>{{ option.reachable ? "可达" : "不可达" }}</span>
                    </div>
                    <p>{{ option.reason }}</p>
                    <small>
                      {{ option.distance != null ? `${formatMetric(option.distance, 1)} m` : "--" }}
                      ·
                      {{ option.estimated_cost != null ? formatMetric(option.estimated_cost, 1) : "--" }}
                    </small>
                  </article>
                </div>
              </div>
            </div>
          </template>

          <el-empty
            v-else-if="decisionExpanded"
            description="先选择一个本阶段物料，并执行一次场布计算。"
          />
        </section>

        <section class="panel-section">
          <div class="panel-head panel-head--button" @click="actionsExpanded = !actionsExpanded">
            <div>
              <p class="panel-kicker">Actions</p>
              <h2>待办动作</h2>
            </div>
            <span class="section-toggle">{{ actionsExpanded ? "收起" : "展开" }}</span>
          </div>

          <div v-if="actionsExpanded && currentResult?.metrics.action_items.length" class="action-list">
            <article
              v-for="item in currentResult.metrics.action_items"
              :key="item.id"
              :class="['action-card', `action-card--${item.severity}`]"
            >
              <strong>{{ item.title }}</strong>
              <p>{{ item.detail }}</p>
            </article>
          </div>
          <article v-else-if="actionsExpanded" class="empty-card">
            当前阶段暂无系统建议动作。
          </article>
        </section>

        <section class="panel-section">
          <div class="panel-head panel-head--button" @click="versionsExpanded = !versionsExpanded">
            <div>
              <p class="panel-kicker">Versions</p>
              <h2>方案留痕</h2>
            </div>
            <span class="section-toggle">{{ versionsExpanded ? "收起" : "展开" }}</span>
          </div>

          <div v-if="versionsExpanded && phaseVersions.length" class="version-list">
            <article v-for="version in phaseVersions" :key="version.version_id" class="version-card">
              <div class="version-card__head">
                <strong>{{ version.version_label }}</strong>
                <span>{{ version.phase_name || "全部阶段" }}</span>
              </div>
              <p>{{ formatTimestamp(version.created_at) }}</p>
              <small>
                成本 {{ formatMetric(version.total_cost, 1) }} ·
                {{ version.placed_count }}/{{ version.placed_count + version.unplaced_count }} 批
              </small>
            </article>
          </div>
          <article v-else-if="versionsExpanded" class="empty-card">
            还没有该阶段的计算版本。
          </article>
        </section>
        </template>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import CanvasMap from "../components/CanvasMap.vue";
import type { PlacementResult } from "../types/layout";
import { useLayoutStore } from "../stores/layout";

const layoutStore = useLayoutStore();
const {
  activeMaterials,
  activePhase,
  activePhaseId,
  controlZones,
  error,
  hasResult,
  loading,
  optimizationResult,
  phaseControlZones,
  phases,
  projectName,
  recentPlanVersions,
} = storeToRefs(layoutStore);

const selectedMaterialId = ref<string | null>(null);
const leftPanelOpen = ref(true);
const rightPanelOpen = ref(false);
const phaseExpanded = ref(true);
const materialsExpanded = ref(true);
const resultExpanded = ref(true);
const decisionExpanded = ref(true);
const actionsExpanded = ref(false);
const versionsExpanded = ref(false);

const formatMetric = (value: number, digits = 0) =>
  new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits > 0 ? Math.min(digits, 1) : 0,
  }).format(value);

const formatTimestamp = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));

const currentResult = computed(() =>
  hasResult.value ? optimizationResult.value : null,
);

const selectedMaterial = computed(
  () => activeMaterials.value.find((material) => material.id === selectedMaterialId.value) ?? null,
);

const selectedPlacement = computed<PlacementResult | null>(() => {
  if (!currentResult.value || !selectedMaterialId.value) {
    return null;
  }

  return currentResult.value.placements.find((placement) => placement.material_id === selectedMaterialId.value) ?? null;
});

const phaseSubtitle = computed(() =>
  activePhase.value?.objective || "围绕阶段目标约束、道路净空和吊装效率生成可执行场布。",
);

const reportLabel = computed(() => {
  if (loading.value) {
    return "计算中";
  }
  if (!currentResult.value) {
    return "待计算";
  }
  if (!currentResult.value.metrics.feasible_layout) {
    return "需复核";
  }
  if (currentResult.value.metrics.action_items.length > 0) {
    return "有动作项";
  }
  return "可执行";
});

const reportToneClass = computed(() => {
  if (loading.value) {
    return "status-pill--running";
  }
  if (!currentResult.value) {
    return "status-pill--idle";
  }
  return currentResult.value.metrics.feasible_layout ? "status-pill--success" : "status-pill--warning";
});

const placementRate = computed(() => {
  if (!activeMaterials.value.length || !currentResult.value) {
    return 0;
  }
  return Math.round((currentResult.value.metrics.placed_count / activeMaterials.value.length) * 100);
});

const placementLabel = computed(() => {
  if (!selectedPlacement.value) {
    return "待分析";
  }
  if (selectedPlacement.value.status === "placed") {
    return "已落位";
  }
  if (selectedPlacement.value.status === "unreachable") {
    return "不可达";
  }
  if (selectedPlacement.value.status === "violated") {
    return "有冲突";
  }
  return "需关注";
});

const placementToneClass = computed(() => {
  if (!selectedPlacement.value) {
    return "status-pill--idle";
  }
  if (selectedPlacement.value.status === "placed") {
    return "status-pill--success";
  }
  if (selectedPlacement.value.status === "unreachable" || selectedPlacement.value.status === "violated") {
    return "status-pill--warning";
  }
  return "status-pill--idle";
});

const assignableZones = computed(() =>
  phaseControlZones.value.filter((zone) => !zone.blocking),
);

const phaseVersions = computed(() =>
  recentPlanVersions.value.filter((version) => version.phase_id === activePhaseId.value),
);

const zoneName = (zoneId?: string | null) =>
  controlZones.value.find((zone) => zone.id === zoneId)?.name ?? "未绑定目标区";

const handlePhaseChange = (phaseId: string) => {
  layoutStore.setActivePhase(phaseId);
};

watch(
  activeMaterials,
  (materials) => {
    if (!materials.length) {
      selectedMaterialId.value = null;
      return;
    }

    if (!selectedMaterialId.value || !materials.some((material) => material.id === selectedMaterialId.value)) {
      selectedMaterialId.value = materials[0].id;
    }
  },
  { immediate: true, deep: true },
);

onMounted(() => {
  void layoutStore.loadProjectSnapshot();
});
</script>

<style scoped>
.dashboard-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100svh;
  overflow: hidden;
  padding: 14px;
}

.dashboard-toolbar,
.panel,
.phase-card,
.material-card,
.summary-card,
.decision-card,
.action-card,
.version-card,
.option-card,
.empty-card {
  border: 1px solid rgba(146, 181, 205, 0.12);
  border-radius: 24px;
  background: rgba(8, 18, 28, 0.82);
  box-shadow: var(--panel-shadow);
  backdrop-filter: blur(var(--panel-blur));
  -webkit-backdrop-filter: blur(var(--panel-blur));
}

.dashboard-toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) auto 260px;
  gap: 16px;
  align-items: center;
  min-height: 136px;
  padding: 18px;
}

.toolbar-kicker,
.panel-kicker {
  margin: 0 0 6px;
  color: #7dd3fc;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.toolbar-copy h1,
.panel-head h2,
.editor-head h3 {
  margin: 0;
  color: var(--app-text-primary);
  letter-spacing: -0.03em;
}

.toolbar-copy p,
.phase-card p,
.material-card p,
.summary-card p,
.decision-note,
.action-card p,
.version-card p,
.option-card p,
.empty-card,
.phase-card small,
.material-card small,
.version-card small {
  margin: 0;
  color: var(--app-text-secondary);
  line-height: 1.5;
}

.toolbar-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.toolbar-stat {
  min-width: 100px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.045);
}

.toolbar-stat span,
.summary-card span,
.field-card span {
  display: block;
  margin-bottom: 6px;
  color: var(--app-text-tertiary);
  font-size: 12px;
}

.toolbar-stat strong,
.summary-card strong {
  color: var(--app-text-primary);
}

.toolbar-actions {
  display: grid;
  grid-template-rows: repeat(4, minmax(0, auto));
  gap: 10px;
  width: 260px;
  min-width: 260px;
}

.panel-toggle-group {
  display: flex;
  gap: 8px;
}

.panel-toggle-chip {
  min-height: 32px;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--app-text-secondary);
  cursor: pointer;
}

.panel-toggle-chip--active {
  background: rgba(56, 189, 248, 0.14);
  color: #e0f2fe;
}

.phase-select {
  width: 100%;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.status-pill--idle {
  background: rgba(56, 189, 248, 0.12);
  color: #bae6fd;
}

.status-pill--running {
  background: rgba(14, 165, 233, 0.14);
  color: #e0f2fe;
}

.status-pill--success {
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

.status-pill--warning {
  background: rgba(245, 158, 11, 0.14);
  color: #fde68a;
}

.workspace-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr) 360px;
  gap: 14px;
}

.workspace-grid--left-collapsed {
  grid-template-columns: 72px minmax(0, 1fr) 360px;
}

.workspace-grid--right-collapsed {
  grid-template-columns: 340px minmax(0, 1fr) 72px;
}

.workspace-grid--left-collapsed.workspace-grid--right-collapsed {
  grid-template-columns: 72px minmax(0, 1fr) 72px;
}

.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.panel--left,
.panel--right {
  gap: 12px;
  padding: 12px;
  overflow: auto;
}

.panel--canvas {
  padding: 8px;
}

.panel--canvas :deep(.map-shell) {
  flex: 1;
  min-height: 0;
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.panel-section--fill {
  flex: 1;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.panel-head--button {
  width: 100%;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.section-toggle {
  color: var(--app-text-secondary);
  font-size: 12px;
}

.collapsed-rail {
  display: grid;
  align-content: start;
  gap: 10px;
  min-height: 100%;
}

.rail-button {
  width: 100%;
  min-height: 42px;
  border: 0;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--app-text-secondary);
  cursor: pointer;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  letter-spacing: 0.08em;
  padding: 10px 0;
}

.rail-button--primary {
  background: rgba(56, 189, 248, 0.14);
  color: #e0f2fe;
}

.phase-list,
.material-list,
.action-list,
.version-list,
.option-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.material-list,
.version-list,
.action-list {
  max-height: 220px;
  overflow: auto;
  padding-right: 4px;
}

.phase-card,
.material-card {
  width: 100%;
  display: grid;
  gap: 8px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
}

.phase-card--active,
.material-card--active {
  border-color: rgba(56, 189, 248, 0.28);
  background: rgba(56, 189, 248, 0.08);
}

.phase-card__head,
.material-card__head,
.version-card__head,
.decision-head,
.option-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.phase-badge,
.material-batch {
  border-radius: 999px;
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--app-text-secondary);
  font-size: 12px;
}

.material-label {
  display: flex;
  align-items: center;
  gap: 10px;
}

.material-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.04);
}

.editor-block,
.decision-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  overflow: auto;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.field-card {
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.045);
}

.field-card--full {
  grid-column: 1 / -1;
}

.editor-actions {
  display: flex;
  justify-content: flex-end;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.summary-card {
  padding: 14px;
}

.summary-card--primary {
  grid-column: 1 / -1;
}

.summary-card--primary strong {
  font-size: 1.8rem;
}

.decision-head {
  align-items: flex-start;
}

.decision-head p {
  margin-top: 4px;
}

.decision-note {
  color: var(--app-text-primary);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.decision-tag {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.decision-tag--success {
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

.decision-tag--warning {
  background: rgba(245, 158, 11, 0.14);
  color: #fde68a;
}

.decision-tag--danger {
  background: rgba(239, 68, 68, 0.14);
  color: #fecaca;
}

.decision-tag--neutral {
  background: rgba(255, 255, 255, 0.06);
  color: var(--app-text-secondary);
}

.subsection {
  display: grid;
  gap: 10px;
}

.subsection h3 {
  margin: 0;
  color: var(--app-text-primary);
  font-size: 0.95rem;
}

.option-card,
.action-card,
.version-card,
.empty-card {
  padding: 14px;
}

.option-card--muted {
  opacity: 0.7;
}

.action-card--high {
  border-color: rgba(239, 68, 68, 0.22);
}

.action-card--medium {
  border-color: rgba(245, 158, 11, 0.2);
}

.panel-error {
  margin: 0;
  color: #fda4af;
}

:deep(.ghost-input .el-input__wrapper),
:deep(.ghost-number.el-input-number),
:deep(.ghost-number .el-input__wrapper),
:deep(.ghost-select .el-select__wrapper),
:deep(.phase-select .el-select__wrapper) {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  box-shadow: none;
}

:deep(.ghost-number.el-input-number) {
  width: 100%;
}

:deep(.ghost-input .el-input__wrapper.is-focus),
:deep(.ghost-number .el-input__wrapper.is-focus),
:deep(.ghost-number.el-input-number:focus-within),
:deep(.ghost-select .el-select__wrapper.is-focused),
:deep(.phase-select .el-select__wrapper.is-focused) {
  background: rgba(8, 18, 28, 0.98);
  box-shadow:
    0 0 0 1px rgba(56, 189, 248, 0.6),
    0 0 0 5px rgba(56, 189, 248, 0.08);
}

:deep(.ghost-input .el-input__inner),
:deep(.ghost-number .el-input__inner) {
  color: var(--app-text-primary);
}

:deep(.utility-button.el-button),
:deep(.danger-button.el-button) {
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--app-text-primary);
  box-shadow: none;
}

:deep(.danger-button.el-button) {
  color: #fda4af;
}

:deep(.cta-button.el-button) {
  width: 100%;
  min-height: 40px;
  border: 0;
  border-radius: 16px;
  background: linear-gradient(135deg, #38bdf8 0%, #0ea5e9 60%, #0284c7 100%);
  box-shadow:
    0 16px 32px rgba(14, 165, 233, 0.24),
    0 0 24px rgba(56, 189, 248, 0.12);
}

:deep(.el-empty) {
  padding-block: 36px 10px;
}

@media (max-width: 1460px) {
  .dashboard-toolbar {
    grid-template-columns: 1fr;
  }

  .workspace-grid {
    grid-template-columns: 320px minmax(0, 1fr);
  }

  .panel--right {
    display: none;
  }
}

@media (max-width: 980px) {
  .dashboard-shell {
    height: auto;
    min-height: 100svh;
    overflow: visible;
  }

  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .panel--left,
  .panel--right {
    max-height: none;
  }

  .material-list,
  .version-list,
  .action-list {
    max-height: none;
  }
}

@media (max-width: 720px) {
  .dashboard-shell {
    padding: 12px;
  }

  .summary-grid,
  .field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
