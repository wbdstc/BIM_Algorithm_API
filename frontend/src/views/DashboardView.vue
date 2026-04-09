<template>
  <div class="dashboard-shell">
    <aside class="sidebar-shell">
      <div class="sidebar-header">
        <p class="sidebar-kicker">BIM SMART SITE / AI LAYOUT</p>
        <h1>BIM 智慧工地 AI 场布</h1>
        <p class="sidebar-summary">
          录入场地边界和物料参数，执行 AI 场布寻优，并在右侧画布中查看坐标落位与塔吊覆盖关系。
        </p>

        <div class="sidebar-stats">
          <div class="stat-chip">
            <span>塔吊</span>
            <strong>{{ workingCranes.length }}</strong>
          </div>
          <div class="stat-chip">
            <span>障碍物</span>
            <strong>{{ obstacles.length }}</strong>
          </div>
          <div class="stat-chip">
            <span>物料</span>
            <strong>{{ materials.length }}</strong>
          </div>
        </div>
      </div>

      <section class="sidebar-section">
        <div class="section-head">
          <div>
            <p class="section-eyebrow">Site Envelope</p>
            <h2>场地边界</h2>
          </div>
          <span class="section-unit">单位：m</span>
        </div>

        <div class="boundary-grid">
          <label class="field-card">
            <span>Min X</span>
            <el-input-number
              v-model="siteBoundary.min_x"
              :step="1"
              :controls="false"
              class="ghost-number"
            />
          </label>
          <label class="field-card">
            <span>Max X</span>
            <el-input-number
              v-model="siteBoundary.max_x"
              :step="1"
              :controls="false"
              class="ghost-number"
            />
          </label>
          <label class="field-card">
            <span>Min Y</span>
            <el-input-number
              v-model="siteBoundary.min_y"
              :step="1"
              :controls="false"
              class="ghost-number"
            />
          </label>
          <label class="field-card">
            <span>Max Y</span>
            <el-input-number
              v-model="siteBoundary.max_y"
              :step="1"
              :controls="false"
              class="ghost-number"
            />
          </label>
        </div>
      </section>

      <section class="sidebar-section">
        <div class="section-head section-head--stack">
          <div>
            <p class="section-eyebrow">Material Setup</p>
            <h2>物料输入表单</h2>
          </div>
          <el-button class="utility-button" @click="layoutStore.addMaterial">新增物料</el-button>
        </div>

        <div class="material-list">
          <article v-for="material in materials" :key="material.id" class="material-card">
            <div class="material-card__head">
              <div class="material-meta">
                <div
                  class="color-badge"
                  :style="{ background: material.display_color || '#38bdf8' }"
                />
                <el-input
                  v-model="material.name"
                  placeholder="输入物料名称"
                  class="ghost-input"
                />
              </div>
              <el-button
                text
                class="danger-button"
                @click="layoutStore.removeMaterial(material.id)"
              >
                删除
              </el-button>
            </div>

            <div class="dimension-grid">
              <label class="metric-card">
                <span>长度</span>
                <el-input-number
                  v-model="material.length"
                  :min="1"
                  :step="0.5"
                  :controls="false"
                  class="ghost-number"
                />
                <small>m</small>
              </label>
              <label class="metric-card">
                <span>宽度</span>
                <el-input-number
                  v-model="material.width"
                  :min="1"
                  :step="0.5"
                  :controls="false"
                  class="ghost-number"
                />
                <small>m</small>
              </label>
              <label class="metric-card">
                <span>高度</span>
                <el-input-number
                  v-model="material.height"
                  :min="1"
                  :step="0.5"
                  :controls="false"
                  class="ghost-number"
                />
                <small>m</small>
              </label>
              <label class="metric-card">
                <span>重量</span>
                <el-input-number
                  v-model="material.weight_tons"
                  :min="0.5"
                  :step="0.5"
                  :controls="false"
                  class="ghost-number"
                />
                <small>t</small>
              </label>
            </div>

            <div class="material-extra">
              <label class="field-card">
                <span>搬运频次</span>
                <el-input-number
                  v-model="material.handling_frequency"
                  :min="0.2"
                  :step="0.1"
                  :controls="false"
                  class="ghost-number"
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
            </div>
          </article>
        </div>
      </section>

      <section class="sidebar-section sidebar-section--accent">
        <div class="section-head section-head--vertical">
          <div>
            <p class="section-eyebrow">Optimization Engine</p>
            <h2>执行 AI 场布寻优</h2>
          </div>
          <p class="section-copy">
            提交参数后，遗传算法会完成坐标选址、可行性判断与塔吊智能分配。
          </p>
        </div>

        <el-button
          type="primary"
          size="large"
          class="cta-button"
          :loading="loading"
          @click="layoutStore.optimizeLayout"
        >
          执行 AI 场布寻优
        </el-button>

        <p v-if="error" class="error-text">{{ error }}</p>
      </section>

      <section class="sidebar-section">
        <div class="section-head">
          <div>
            <p class="section-eyebrow">Execution Report</p>
            <h2>优化执行报告</h2>
          </div>
          <strong class="report-state">{{ reportTitle }}</strong>
        </div>

        <el-empty v-if="!optimizationResult" description="等待执行优化" />

        <template v-else>
          <div class="report-kpis">
            <div class="report-kpi">
              <span>总成本</span>
              <strong>{{ optimizationResult.metrics.total_cost.toFixed(2) }}</strong>
            </div>
            <div class="report-kpi">
              <span>成功布置</span>
              <strong>{{ optimizationResult.metrics.placed_count }}</strong>
            </div>
            <div class="report-kpi">
              <span>不可达</span>
              <strong>{{ optimizationResult.metrics.unplaced_count }}</strong>
            </div>
          </div>

          <div class="report-list">
            <article
              v-for="placement in optimizationResult.placements"
              :key="placement.material_id"
              class="report-item"
            >
              <div class="report-item__head">
                <div class="report-item__name">
                  <div
                    class="color-badge"
                    :style="{ background: placement.display_color || '#38bdf8' }"
                  />
                  <strong>{{ placement.material_name }}</strong>
                </div>
                <span class="report-badge">{{ placement.status }}</span>
              </div>
              <p>
                坐标 ({{ placement.x }}, {{ placement.y }}) · 塔吊
                {{ placement.assigned_crane_name || "未分配" }}
              </p>
              <p>搬运成本 {{ placement.transport_cost ?? "--" }}</p>
            </article>
          </div>

          <div v-if="optimizationResult.metrics.warnings.length" class="warning-box">
            <h3>告警信息</h3>
            <p v-for="warning in optimizationResult.metrics.warnings" :key="warning">
              {{ warning }}
            </p>
          </div>
        </template>
      </section>
    </aside>

    <main class="workspace-panel">
      <CanvasMap />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from "vue";
import { storeToRefs } from "pinia";

import CanvasMap from "../components/CanvasMap.vue";
import { useLayoutStore } from "../stores/layout";

const layoutStore = useLayoutStore();
const { error, loading, materials, obstacles, optimizationResult, siteBoundary, workingCranes } =
  storeToRefs(layoutStore);

const reportTitle = computed(() => {
  if (!optimizationResult.value) {
    return "待执行";
  }

  return optimizationResult.value.metrics.feasible_layout ? "方案可落地" : "需人工复核";
});
onMounted(() => {
  void layoutStore.loadProjectSnapshot();
});
</script>

<style scoped>
.dashboard-shell {
  display: grid;
  grid-template-columns: 400px minmax(0, 1fr);
  gap: 20px;
  min-height: 100vh;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.12), transparent 20%),
    radial-gradient(circle at 12% 40%, rgba(124, 58, 237, 0.1), transparent 18%),
    linear-gradient(160deg, #020617 0%, #081120 40%, #0f172a 100%);
}

.sidebar-shell {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: calc(100vh - 40px);
  overflow: auto;
  padding: 18px;
  border-radius: 28px;
  background: rgba(9, 15, 28, 0.78);
  box-shadow: var(--panel-shadow);
  backdrop-filter: blur(var(--panel-blur));
  -webkit-backdrop-filter: blur(var(--panel-blur));
}

.sidebar-shell::-webkit-scrollbar {
  width: 8px;
}

.sidebar-shell::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.2);
}

.sidebar-header {
  padding: 8px 6px 20px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.sidebar-kicker,
.section-eyebrow,
.section-unit,
.report-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.sidebar-kicker,
.section-eyebrow {
  margin: 0 0 10px;
  color: #7dd3fc;
}

.sidebar-header h1,
.section-head h2 {
  margin: 0;
  color: var(--app-text-primary);
  letter-spacing: -0.03em;
}

.sidebar-header h1 {
  font-size: clamp(2rem, 3vw, 2.7rem);
  line-height: 1.04;
}

.sidebar-summary,
.section-copy,
.report-item p {
  margin: 0;
  color: var(--app-text-secondary);
  line-height: 1.6;
}

.sidebar-summary {
  margin-top: 12px;
  max-width: 34ch;
}

.sidebar-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.stat-chip {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.035);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.stat-chip span,
.field-card span,
.metric-card span,
.report-kpi span {
  display: block;
  margin-bottom: 8px;
  color: var(--app-text-tertiary);
  font-size: 12px;
}

.stat-chip strong,
.report-kpi strong {
  font-size: 1.4rem;
  line-height: 1;
}

.sidebar-section {
  padding: 18px 6px 20px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.sidebar-section:last-child {
  border-bottom: 0;
  padding-bottom: 6px;
}

.sidebar-section--accent {
  padding: 18px;
  border-radius: 22px;
  border-bottom: 0;
  background:
    linear-gradient(135deg, rgba(56, 189, 248, 0.08), transparent 42%),
    rgba(255, 255, 255, 0.03);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.section-head,
.material-card__head,
.report-item__head,
.report-item__name,
.material-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.section-head,
.material-card__head,
.report-item__head {
  justify-content: space-between;
}

.section-head--stack {
  align-items: flex-start;
}

.section-head--vertical {
  flex-direction: column;
  align-items: flex-start;
}

.section-unit {
  color: var(--app-text-tertiary);
}

.boundary-grid,
.material-extra {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.boundary-grid {
  margin-top: 16px;
}

.field-card,
.metric-card,
.material-card,
.report-item,
.report-kpi {
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.field-card,
.metric-card {
  padding: 12px;
}

.material-list,
.report-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.material-list {
  margin-top: 16px;
}

.material-card {
  padding: 14px;
}

.material-meta {
  min-width: 0;
  flex: 1;
}

.dimension-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.metric-card small {
  display: block;
  margin-top: 6px;
  color: var(--app-text-quaternary);
  font-size: 11px;
}

.material-extra {
  margin-top: 10px;
}

.color-badge {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  flex: 0 0 auto;
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.04);
}

.cta-button {
  width: 100%;
  margin-top: 16px;
}

.section-copy {
  max-width: 34ch;
}

.error-text {
  margin: 10px 0 0;
  color: #fda4af;
}

.report-state {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(56, 189, 248, 0.08);
  color: #dbeafe;
  font-size: 12px;
  font-weight: 600;
}

.report-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0 14px;
}

.report-kpi,
.report-item {
  padding: 14px;
}

.report-item__name strong {
  font-size: 14px;
}

.report-item p + p {
  margin-top: 6px;
}

.report-badge {
  color: #a5b4fc;
}

.warning-box {
  margin-top: 12px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(251, 146, 60, 0.1);
  color: #fdba74;
}

.warning-box h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.warning-box p {
  margin: 0;
}

.warning-box p + p {
  margin-top: 6px;
}

.workspace-panel {
  min-width: 0;
}

:deep(.ghost-input .el-input__wrapper),
:deep(.ghost-number.el-input-number),
:deep(.ghost-number .el-input__wrapper) {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  box-shadow: none;
  transition:
    background 200ms ease,
    box-shadow 200ms ease;
}

:deep(.ghost-number.el-input-number) {
  width: 100%;
}

:deep(.ghost-input .el-input__wrapper:hover),
:deep(.ghost-number .el-input__wrapper:hover),
:deep(.ghost-number.el-input-number:hover) {
  background: rgba(255, 255, 255, 0.065);
}

:deep(.ghost-input .el-input__wrapper.is-focus),
:deep(.ghost-number .el-input__wrapper.is-focus),
:deep(.ghost-number.el-input-number:focus-within) {
  background: rgba(15, 23, 42, 0.88);
  box-shadow:
    0 0 0 1px rgba(96, 165, 250, 0.6),
    0 0 0 5px rgba(59, 130, 246, 0.1);
}

:deep(.ghost-input .el-input__inner),
:deep(.ghost-number .el-input__inner) {
  color: var(--app-text-primary);
}

:deep(.ghost-input .el-input__inner::placeholder),
:deep(.ghost-number .el-input__inner::placeholder) {
  color: var(--app-text-quaternary);
}

:deep(.utility-button.el-button),
:deep(.danger-button.el-button) {
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--app-text-primary);
  box-shadow: none;
}

:deep(.utility-button.el-button:hover),
:deep(.danger-button.el-button:hover) {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

:deep(.danger-button.el-button) {
  color: #fda4af;
}

:deep(.cta-button.el-button) {
  position: relative;
  overflow: hidden;
  border: 0;
  border-radius: 16px;
  color: white;
  background: linear-gradient(135deg, #38bdf8 0%, #2563eb 50%, #7c3aed 100%);
  box-shadow:
    0 18px 36px rgba(37, 99, 235, 0.28),
    0 0 28px rgba(59, 130, 246, 0.16);
  transition:
    transform 220ms ease,
    box-shadow 220ms ease;
}

:deep(.cta-button.el-button::after) {
  content: "";
  position: absolute;
  inset: 1px;
  border-radius: 15px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.2), transparent 40%);
}

:deep(.cta-button.el-button > span) {
  position: relative;
  z-index: 1;
}

:deep(.cta-button.el-button:hover) {
  transform: translateY(-1px);
  box-shadow:
    0 22px 44px rgba(76, 29, 149, 0.28),
    0 0 32px rgba(56, 189, 248, 0.2);
}

:deep(.el-empty) {
  padding-block: 24px 18px;
}

:deep(.el-empty__description p) {
  color: var(--app-text-secondary);
}

@media (max-width: 1260px) {
  .dashboard-shell {
    grid-template-columns: 1fr;
  }

  .sidebar-shell {
    max-height: none;
  }
}

@media (max-width: 860px) {
  .dashboard-shell {
    padding: 14px;
  }

  .sidebar-stats,
  .report-kpis,
  .boundary-grid,
  .material-extra,
  .dimension-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .section-head {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .sidebar-stats,
  .report-kpis,
  .boundary-grid,
  .material-extra,
  .dimension-grid {
    grid-template-columns: 1fr;
  }

  .material-card__head,
  .report-item__head {
    align-items: flex-start;
    flex-direction: column;
  }

  .material-meta {
    width: 100%;
  }
}
</style>
