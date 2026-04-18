<template>
  <div class="dashboard-shell">
    <header class="dashboard-toolbar">
      <div class="toolbar-brand">
        <p class="toolbar-kicker">BIM SMART SITE</p>
        <h1>{{ projectName }}</h1>
        <p class="toolbar-copy">{{ toolbarCopy }}</p>
      </div>

      <div class="toolbar-stats">
        <article
          v-for="metric in toolbarStats"
          :key="metric.label"
          class="toolbar-stat"
        >
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </article>
      </div>

      <div class="toolbar-actions">
        <span :class="['status-pill', reportToneClass]">{{ reportTitle }}</span>
        <el-button
          type="primary"
          size="large"
          class="cta-button"
          :loading="loading"
          @click="layoutStore.optimizeLayout"
        >
          {{ optimizationResult ? "重新计算方案" : "开始计算方案" }}
        </el-button>
      </div>
    </header>

    <div class="workspace-grid">
      <aside class="panel panel--materials">
        <div class="panel-head">
          <div>
            <p class="panel-kicker">Materials</p>
            <h2>物料清单</h2>
          </div>

          <el-button class="utility-button" @click="layoutStore.addMaterial">
            新增物料
          </el-button>
        </div>

        <div class="panel-summary">
          <article class="summary-pill">
            <span>物料</span>
            <strong>{{ materials.length }} 项</strong>
          </article>
          <article class="summary-pill">
            <span>总重量</span>
            <strong>{{ formatMetric(totalWeight, 1) }} t</strong>
          </article>
          <article class="summary-pill">
            <span>高频搬运</span>
            <strong>{{ highFrequencyCount }} 项</strong>
          </article>
        </div>

        <div class="panel-body">
          <div class="material-list">
            <article
              v-for="material in materials"
              :key="material.id"
              :class="[
                'material-item',
                { 'material-item--active': expandedMaterialId === material.id },
              ]"
            >
              <button
                type="button"
                class="material-row"
                @click="toggleMaterial(material.id, material.name)"
              >
                <div class="material-main">
                  <span
                    class="material-dot"
                    :style="{ background: material.display_color || '#38bdf8' }"
                  />
                  <div class="material-copy">
                    <strong>{{ material.name }}</strong>
                    <p>{{ material.category || "未分类" }}</p>
                  </div>
                </div>

                <div class="material-meta">
                  <span>{{ formatMetric(material.weight_tons, 1) }} t</span>
                  <span>{{ formatMetric(material.handling_frequency, 1) }} 次</span>
                </div>
              </button>

              <Transition name="expand">
                <div
                  v-if="expandedMaterialId === material.id"
                  class="material-editor"
                >
                  <div class="material-editor__actions">
                    <el-button
                      v-if="hasPlacement(material.name)"
                      text
                      class="utility-button utility-button--inline"
                      @click.stop="focusPlacement(material.name)"
                    >
                      定位结果
                    </el-button>
                    <el-button
                      text
                      class="danger-button"
                      @click.stop="layoutStore.removeMaterial(material.id)"
                    >
                      删除
                    </el-button>
                  </div>

                  <div class="field-grid">
                    <label class="field-card">
                      <span>物料名称</span>
                      <el-input
                        v-model="material.name"
                        placeholder="输入物料名称"
                        class="ghost-input"
                      />
                    </label>
                    <label class="field-card">
                      <span>物料类别</span>
                      <el-input
                        v-model="material.category"
                        placeholder="steel / formwork / prefab"
                        class="ghost-input"
                      />
                    </label>
                    <label class="field-card">
                      <span>长度</span>
                      <el-input-number
                        v-model="material.length"
                        :min="0.1"
                        :step="0.1"
                        :controls="false"
                        class="ghost-number"
                      />
                    </label>
                    <label class="field-card">
                      <span>宽度</span>
                      <el-input-number
                        v-model="material.width"
                        :min="0.1"
                        :step="0.1"
                        :controls="false"
                        class="ghost-number"
                      />
                    </label>
                    <label class="field-card">
                      <span>高度</span>
                      <el-input-number
                        v-model="material.height"
                        :min="0.05"
                        :step="0.05"
                        :controls="false"
                        class="ghost-number"
                      />
                    </label>
                    <label class="field-card">
                      <span>重量</span>
                      <el-input-number
                        v-model="material.weight_tons"
                        :min="0.1"
                        :step="0.1"
                        :controls="false"
                        class="ghost-number"
                      />
                    </label>
                    <label class="field-card field-card--full">
                      <span>搬运频次</span>
                      <el-input-number
                        v-model="material.handling_frequency"
                        :min="0.2"
                        :step="0.1"
                        :controls="false"
                        class="ghost-number"
                      />
                    </label>
                  </div>
                </div>
              </Transition>
            </article>
          </div>
        </div>

        <p v-if="error" class="panel-error">{{ error }}</p>
      </aside>

      <main class="panel panel--canvas">
        <CanvasMap :highlight-placement-name="activePlacementName" />
      </main>

      <aside class="panel panel--review">
        <div class="panel-head">
          <div>
            <p class="panel-kicker">Review</p>
            <h2>落位结果</h2>
          </div>

          <div class="review-tabs">
            <button
              type="button"
              :class="['tab-button', { 'tab-button--active': reviewTab === 'placements' }]"
              @click="reviewTab = 'placements'"
            >
              落位
            </button>
            <button
              type="button"
              :class="['tab-button', { 'tab-button--active': reviewTab === 'warnings' }]"
              @click="reviewTab = 'warnings'"
            >
              告警
            </button>
          </div>
        </div>

        <div class="review-summary">
          <article class="summary-card summary-card--primary">
            <span>落位率</span>
            <strong>{{ optimizationResult ? `${placementRate}%` : "--" }}</strong>
            <p>{{ placedCount }} / {{ materials.length }} 已落位</p>
          </article>
          <article class="summary-card">
            <span>总成本</span>
            <strong>{{ optimizationResult ? formatMetric(optimizationResult.metrics.total_cost, 2) : "--" }}</strong>
          </article>
          <article class="summary-card">
            <span>告警</span>
            <strong>{{ warningCount }} 条</strong>
          </article>
        </div>

        <div class="panel-body">
          <template v-if="optimizationResult">
            <div v-if="reviewTab === 'placements'" class="placement-list">
              <button
                v-for="placement in sortedPlacements"
                :key="placement.material_id"
                type="button"
                :class="[
                  'placement-item',
                  { 'placement-item--active': activePlacementName === placement.material_name },
                ]"
                @click="selectPlacement(placement.material_name)"
              >
                <div class="placement-item__head">
                  <div class="placement-name">
                    <span
                      class="material-dot"
                      :style="{ background: placement.display_color || '#38bdf8' }"
                    />
                    <strong>{{ placement.material_name }}</strong>
                  </div>
                  <span :class="['item-state', placementTone(placement)]">
                    {{ placementStatusLabel(placement) }}
                  </span>
                </div>
                <p>{{ coordinateLabel(placement) }}</p>
                <p>{{ placement.assigned_crane_name || "未分配塔吊" }}</p>
              </button>
            </div>

            <div v-else class="warning-list">
              <article
                v-if="optimizationResult.metrics.warnings.length === 0"
                class="warning-item warning-item--empty"
              >
                当前没有系统告警，可重点检查坐标和塔吊覆盖是否符合现场习惯。
              </article>
              <article
                v-for="warning in optimizationResult.metrics.warnings"
                :key="warning"
                class="warning-item"
              >
                {{ warning }}
              </article>
            </div>
          </template>

          <el-empty
            v-else
            description="执行寻优后，这里会展示落位结果并支持地图联动。"
          />
        </div>
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

type ReviewTab = "placements" | "warnings";

const layoutStore = useLayoutStore();
const { error, loading, materials, obstacles, optimizationResult, projectName, workingCranes } =
  storeToRefs(layoutStore);

const expandedMaterialId = ref("");
const activePlacementName = ref<string | null>(null);
const reviewTab = ref<ReviewTab>("placements");

const formatMetric = (value: number, digits = 0) =>
  new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits > 0 ? Math.min(digits, 1) : 0,
  }).format(value);

const totalWeight = computed(() =>
  materials.value.reduce((sum, item) => sum + item.weight_tons, 0),
);

const highFrequencyCount = computed(() =>
  materials.value.filter((item) => item.handling_frequency >= 1).length,
);

const placedCount = computed(() => optimizationResult.value?.metrics.placed_count ?? 0);

const warningCount = computed(() => optimizationResult.value?.metrics.warnings.length ?? 0);

const placementRate = computed(() => {
  if (!materials.value.length) {
    return 0;
  }

  return Math.round((placedCount.value / materials.value.length) * 100);
});

const reportTitle = computed(() => {
  if (loading.value) {
    return "计算中";
  }

  if (!optimizationResult.value) {
    return "待执行";
  }

  if (!optimizationResult.value.metrics.feasible_layout) {
    return "需复核";
  }

  if (warningCount.value) {
    return "有告警";
  }

  return "可落地";
});

const reportToneClass = computed(() => {
  if (loading.value) {
    return "status-pill--running";
  }

  if (!optimizationResult.value) {
    return "status-pill--idle";
  }

  return reportTitle.value === "可落地"
    ? "status-pill--success"
    : "status-pill--warning";
});

const toolbarCopy = computed(() =>
  optimizationResult.value
    ? "左侧维护物料，右侧逐项复核落位，地图只保留必要标注。"
    : "先整理左侧物料参数，再生成场布方案。",
);

const toolbarStats = computed(() => [
  { label: "塔吊", value: `${workingCranes.value.length} 台` },
  { label: "障碍物", value: `${obstacles.value.length} 项` },
  { label: "物料", value: `${materials.value.length} 项` },
]);

const sortedPlacements = computed(() => {
  const placements = optimizationResult.value?.placements ?? [];
  const rank = (placement: PlacementResult) =>
    placement.status !== "placed" || placement.path_crosses_obstacle ? 1 : 0;

  return [...placements].sort((left, right) => {
    const diff = rank(left) - rank(right);
    if (diff !== 0) {
      return diff;
    }

    return left.material_name.localeCompare(right.material_name, "zh-CN");
  });
});

const placementMap = computed(
  () => new Map(sortedPlacements.value.map((placement) => [placement.material_name, placement])),
);

const hasPlacement = (materialName: string) => placementMap.value.has(materialName);

const focusPlacement = (materialName: string) => {
  if (!placementMap.value.has(materialName)) {
    return;
  }

  activePlacementName.value = materialName;
  reviewTab.value = "placements";
};

const toggleMaterial = (materialId: string, materialName: string) => {
  expandedMaterialId.value = expandedMaterialId.value === materialId ? "" : materialId;
  if (placementMap.value.has(materialName)) {
    activePlacementName.value = materialName;
  }
};

const selectPlacement = (materialName: string) => {
  activePlacementName.value = activePlacementName.value === materialName ? null : materialName;
};

const coordinateLabel = (placement: PlacementResult) =>
  `坐标 ${formatMetric(placement.x, 1)}m / ${formatMetric(placement.y, 1)}m`;

const placementStatusLabel = (placement: PlacementResult) => {
  if (placement.status !== "placed") {
    return "待处理";
  }

  if (placement.path_crosses_obstacle) {
    return "路径受阻";
  }

  return "已落位";
};

const placementTone = (placement: PlacementResult) => {
  if (placement.status !== "placed") {
    return "item-state--muted";
  }

  return placement.path_crosses_obstacle ? "item-state--warning" : "item-state--success";
};

watch(
  materials,
  (items) => {
    if (!items.length) {
      expandedMaterialId.value = "";
      return;
    }

    if (!items.some((item) => item.id === expandedMaterialId.value)) {
      expandedMaterialId.value = items[0].id;
    }
  },
  { immediate: true, deep: true },
);

watch(
  sortedPlacements,
  (placements) => {
    if (!placements.length) {
      activePlacementName.value = null;
      return;
    }

    if (
      activePlacementName.value
      && placements.some((placement) => placement.material_name === activePlacementName.value)
    ) {
      return;
    }

    activePlacementName.value = placements[0].material_name;
  },
  { immediate: true },
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
  background:
    radial-gradient(circle at 0 0, rgba(14, 165, 233, 0.14), transparent 22%),
    linear-gradient(180deg, #06101a 0%, #081521 52%, #0b1824 100%);
}

.dashboard-toolbar,
.panel {
  border: 1px solid rgba(146, 181, 205, 0.12);
  border-radius: 24px;
  background: rgba(8, 18, 28, 0.82);
  box-shadow: var(--panel-shadow);
  backdrop-filter: blur(var(--panel-blur));
  -webkit-backdrop-filter: blur(var(--panel-blur));
}

.dashboard-toolbar {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) auto auto;
  gap: 16px;
  align-items: center;
  padding: 16px 18px;
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

.toolbar-brand h1,
.panel-head h2 {
  margin: 0;
  color: var(--app-text-primary);
  letter-spacing: -0.03em;
}

.toolbar-brand h1 {
  font-size: clamp(1.5rem, 2.2vw, 2rem);
}

.toolbar-copy,
.summary-card p,
.material-copy p,
.placement-item p,
.warning-item {
  margin: 0;
  color: var(--app-text-secondary);
  line-height: 1.5;
}

.toolbar-stats,
.panel-summary {
  display: flex;
  gap: 10px;
}

.toolbar-stat,
.summary-pill,
.summary-card,
.material-item,
.placement-item,
.warning-item,
.field-card {
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.045);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.toolbar-stat,
.summary-pill {
  min-width: 86px;
  padding: 10px 12px;
}

.toolbar-stat span,
.summary-pill span,
.summary-card span,
.field-card span {
  display: block;
  margin-bottom: 6px;
  color: var(--app-text-tertiary);
  font-size: 12px;
}

.toolbar-stat strong,
.summary-pill strong,
.summary-card strong {
  color: var(--app-text-primary);
  font-size: 1.05rem;
}

.toolbar-actions {
  display: grid;
  gap: 10px;
}

.status-pill,
.item-state {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
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

.status-pill--success,
.item-state--success {
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

.status-pill--warning,
.item-state--warning {
  background: rgba(245, 158, 11, 0.14);
  color: #fde68a;
}

.item-state--muted {
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
}

.workspace-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 320px;
  gap: 14px;
}

.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid rgba(146, 181, 205, 0.1);
}

.panel-summary {
  padding: 12px 16px 0;
}

.panel-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 16px 16px;
}

.panel-body::-webkit-scrollbar {
  width: 8px;
}

.panel-body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
}

.material-list,
.placement-list,
.warning-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.material-item {
  overflow: hidden;
  border: 1px solid transparent;
}

.material-item--active {
  border-color: rgba(56, 189, 248, 0.2);
}

.material-row {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.material-main,
.placement-item__head,
.placement-name {
  display: flex;
  align-items: center;
  gap: 10px;
}

.material-copy strong,
.placement-name strong {
  display: block;
  color: var(--app-text-primary);
}

.material-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  flex: 0 0 auto;
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.04);
}

.material-meta {
  display: flex;
  gap: 10px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.material-editor {
  padding: 0 14px 14px;
}

.material-editor__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 10px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.field-card {
  padding: 12px;
}

.field-card--full {
  grid-column: 1 / -1;
}

.panel--canvas {
  padding: 8px;
}

.panel--canvas :deep(.map-shell) {
  flex: 1;
  min-height: 0;
}

.review-tabs {
  display: inline-flex;
  gap: 8px;
  padding: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
}

.tab-button {
  min-height: 30px;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--app-text-secondary);
  font: inherit;
  cursor: pointer;
}

.tab-button--active {
  background: rgba(56, 189, 248, 0.14);
  color: #e0f2fe;
}

.review-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 12px 16px 0;
}

.summary-card {
  padding: 14px;
}

.summary-card--primary {
  grid-column: 1 / -1;
}

.summary-card--primary strong {
  font-size: 1.7rem;
}

.placement-item {
  width: 100%;
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.placement-item--active {
  border-color: rgba(56, 189, 248, 0.24);
  background: rgba(56, 189, 248, 0.08);
}

.placement-item p {
  font-size: 12px;
}

.warning-item {
  padding: 14px;
}

.warning-item--empty {
  color: var(--app-text-secondary);
}

.panel-error {
  margin: 0;
  padding: 0 16px 14px;
  color: #fda4af;
}

:deep(.ghost-input .el-input__wrapper),
:deep(.ghost-number.el-input-number),
:deep(.ghost-number .el-input__wrapper) {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  box-shadow: none;
}

:deep(.ghost-number.el-input-number) {
  width: 100%;
}

:deep(.ghost-input .el-input__wrapper.is-focus),
:deep(.ghost-number .el-input__wrapper.is-focus),
:deep(.ghost-number.el-input-number:focus-within) {
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

:deep(.utility-button--inline.el-button) {
  color: #bae6fd;
}

:deep(.danger-button.el-button) {
  color: #fda4af;
}

:deep(.cta-button.el-button) {
  width: 100%;
  border: 0;
  border-radius: 16px;
  background: linear-gradient(135deg, #38bdf8 0%, #0ea5e9 60%, #0284c7 100%);
  box-shadow:
    0 16px 32px rgba(14, 165, 233, 0.24),
    0 0 24px rgba(56, 189, 248, 0.12);
}

:deep(.el-empty) {
  padding-block: 40px 16px;
}

.expand-enter-active,
.expand-leave-active {
  transition: all 180ms ease;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@media (max-width: 1380px) {
  .dashboard-toolbar {
    grid-template-columns: 1fr;
  }

  .toolbar-stats {
    flex-wrap: wrap;
  }
}

@media (max-width: 1220px) {
  .workspace-grid {
    grid-template-columns: 300px minmax(0, 1fr);
  }

  .panel--review {
    display: none;
  }
}

@media (max-width: 960px) {
  .dashboard-shell {
    height: auto;
    min-height: 100svh;
    overflow: visible;
  }

  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .panel {
    min-height: 420px;
  }
}

@media (max-width: 720px) {
  .dashboard-shell {
    padding: 12px;
  }

  .toolbar-stats,
  .panel-summary,
  .review-summary,
  .field-grid {
    display: grid;
    grid-template-columns: 1fr;
  }

  .panel-head,
  .material-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
