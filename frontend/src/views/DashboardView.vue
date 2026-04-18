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
          <button type="button" class="rail-button" @click="leftPanelOpen = true">
            物料
          </button>
          <button type="button" class="rail-button" @click="openAllMaterialsDialog">
            全部
          </button>
        </div>

        <template v-else>
          <section class="panel-section panel-section--fill">
            <input
              ref="materialImportInputRef"
              class="visually-hidden"
              type="file"
              accept=".csv,text/csv"
              @change="handleMaterialImport"
            >

            <div class="panel-head">
              <div class="panel-head__copy">
                <p class="panel-kicker">Materials</p>
                <h2>本阶段物料</h2>
                <p class="panel-head__subtitle">{{ activePhase?.name ?? "未设置阶段" }}</p>
              </div>
              <span :class="['status-pill', phaseStatusToneClass]">
                {{ phaseStatusText(activePhase?.status) }}
              </span>
            </div>

            <div class="material-toolbar">
              <el-button class="utility-button" @click="layoutStore.addMaterial">
                新增物料
              </el-button>
              <el-button class="utility-button" @click="openAllMaterialsDialog">
                全部物料
              </el-button>
              <el-button class="utility-button" @click="openMaterialImport">
                一键导入
              </el-button>
              <el-button class="utility-button" @click="downloadMaterialTemplate">
                示例模板
              </el-button>
            </div>

            <p class="toolbar-hint">
              导入支持 CSV；未填写阶段和目标区时，默认写入当前阶段并自动匹配可落位区域。
            </p>

            <div class="material-action-grid">
              <button
                type="button"
                class="material-action-button"
                @click="materialOverviewDialogOpen = true"
              >
                <div class="material-action-button__copy">
                  <span>阶段概览</span>
                  <strong>{{ activePhase?.name ?? "未设置阶段" }}</strong>
                  <small>{{ activeMaterials.length }} 批物料 · {{ assignableZones.length }} 个目标区</small>
                </div>
                <span class="section-toggle">弹窗查看</span>
              </button>

              <button
                type="button"
                class="material-action-button"
                @click="phaseMaterialsDialogOpen = true"
              >
                <div class="material-action-button__copy">
                  <span>物料列表</span>
                  <strong>本阶段待排布物料</strong>
                  <small>{{ activeMaterials.length ? `${activeMaterials.length} 批可快速切换` : "当前阶段暂无物料" }}</small>
                </div>
                <span class="section-toggle">弹窗查看</span>
              </button>

              <button
                type="button"
                class="material-action-button"
                @click="openMaterialEditorDialog()"
              >
                <div class="material-action-button__copy">
                  <span>当前编辑</span>
                  <strong>{{ selectedMaterial?.name ?? "未选中物料" }}</strong>
                  <small>{{ selectedMaterial ? formatMaterialFootprint(selectedMaterial) : "先从物料列表选择一批物料" }}</small>
                </div>
                <span class="section-toggle">弹窗查看</span>
              </button>
            </div>

            <p v-if="error" class="panel-error">{{ error }}</p>
          </section>
        </template>
      </aside>

      <main class="panel panel--canvas">
        <div class="canvas-frame">
          <CanvasMap :highlight-material-id="selectedMaterialId" />

          <button
            type="button"
            class="stage-plan-float"
            @click="stagePlanDialogOpen = true"
          >
            {{ stagePlanFloatingLabel }}
          </button>
        </div>
      </main>

      <aside :class="['panel panel--right', { 'panel--collapsed': !rightPanelOpen }]">
        <div v-if="!rightPanelOpen" class="collapsed-rail">
          <button type="button" class="rail-button rail-button--primary" @click="rightPanelOpen = true">
            右栏
          </button>
          <button type="button" class="rail-button" @click="decisionDialogOpen = true">
            解释
          </button>
          <button type="button" class="rail-button" @click="actionsDialogOpen = true">
            动作
          </button>
        </div>

        <template v-else>
          <section class="panel-section panel-section--fill">
            <div class="panel-head">
              <div class="panel-head__copy">
                <p class="panel-kicker">Insights</p>
                <h2>右侧信息</h2>
                <p class="panel-head__subtitle">{{ activePhase?.name ?? "未设置阶段" }}</p>
              </div>
            </div>

            <div class="sidebar-action-grid">
              <button
                type="button"
                class="sidebar-action-button"
                @click="resultDialogOpen = true"
              >
                <div class="sidebar-action-button__copy">
                  <span>阶段结论</span>
                  <strong>{{ currentResult ? `${placementRate}% 完成度` : "待生成阶段结论" }}</strong>
                  <small>{{ currentResult ? `${currentResult.metrics.placed_count} / ${activeMaterials.length} 批已落位` : "先执行一次场布计算" }}</small>
                </div>
                <span class="section-toggle">弹窗查看</span>
              </button>

              <button
                type="button"
                class="sidebar-action-button"
                @click="decisionDialogOpen = true"
              >
                <div class="sidebar-action-button__copy">
                  <span>选中物料解释</span>
                  <strong>{{ selectedPlacement?.material_name ?? "未选中物料" }}</strong>
                  <small>{{ selectedPlacement ? `${placementLabel} · ${selectedPlacement.assigned_crane_name || "未分配塔吊"}` : "先选择物料并完成计算" }}</small>
                </div>
                <span class="section-toggle">弹窗查看</span>
              </button>

              <button
                type="button"
                class="sidebar-action-button"
                @click="actionsDialogOpen = true"
              >
                <div class="sidebar-action-button__copy">
                  <span>待办动作</span>
                  <strong>{{ currentResult?.metrics.action_items.length ?? 0 }} 条系统建议</strong>
                  <small>{{ currentResult?.metrics.action_items.length ? "查看需要人工处理的动作项" : "当前阶段暂无系统建议动作" }}</small>
                </div>
                <span class="section-toggle">弹窗查看</span>
              </button>

              <button
                type="button"
                class="sidebar-action-button"
                @click="versionsDialogOpen = true"
              >
                <div class="sidebar-action-button__copy">
                  <span>方案留痕</span>
                  <strong>{{ phaseVersions.length }} 条历史版本</strong>
                  <small>{{ phaseVersions.length ? "查看当前阶段的历史计算结果" : "当前阶段还没有历史版本" }}</small>
                </div>
                <span class="section-toggle">弹窗查看</span>
              </button>
            </div>
          </section>
        </template>
      </aside>
    </div>

    <el-dialog
      v-model="allMaterialsDialogOpen"
      title="全部物料总览"
      class="all-materials-dialog"
      width="92%"
      destroy-on-close
    >
      <div class="dialog-toolbar">
        <el-input
          v-model="materialSearchKeyword"
          class="ghost-input dialog-search"
          placeholder="搜索物料、批次、阶段或目标区"
          clearable
        />
        <p class="dialog-toolbar__meta">
          共 {{ materials.length }} 批，当前筛选 {{ filteredMaterials.length }} 批
        </p>
      </div>

      <div class="table-shell">
        <el-table
          :data="filteredMaterials"
          row-key="id"
          height="460"
          stripe
          class="table-inline"
          empty-text="没有匹配的物料"
        >
          <el-table-column label="物料" min-width="200">
            <template #default="{ row }">
              <div class="dialog-material-cell">
                <div class="material-label">
                  <span class="material-dot" :style="{ background: row.display_color || '#38bdf8' }" />
                  <strong>{{ row.name }}</strong>
                </div>
                <small>{{ row.batch_id || "未分批" }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="阶段" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              {{ phaseName(row.phase_id) }}
            </template>
          </el-table-column>
          <el-table-column prop="category" label="分类" min-width="110" show-overflow-tooltip />
          <el-table-column label="规格" min-width="160">
            <template #default="{ row }">
              {{ formatMaterialFootprint(row) }}
            </template>
          </el-table-column>
          <el-table-column label="重量" min-width="100">
            <template #default="{ row }">
              {{ formatMetric(row.weight_tons, 1) }} t
            </template>
          </el-table-column>
          <el-table-column label="停留" min-width="96">
            <template #default="{ row }">
              {{ formatMetric(row.stay_days, 0) }} 天
            </template>
          </el-table-column>
          <el-table-column label="目标区" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ zoneName(row.target_zone_id) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="88" fixed="right">
            <template #default="{ row }">
              <el-button text class="utility-button utility-button--text" @click="focusMaterial(row.id, row.phase_id)">
                定位
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <el-dialog
      v-model="materialOverviewDialogOpen"
      title="本阶段概览"
      class="material-dialog"
      width="560px"
      destroy-on-close
    >
      <section class="material-dialog-card">
        <div class="material-summary-grid">
          <article class="material-summary-card">
            <span>当前阶段</span>
            <strong>{{ activePhase?.name ?? "未设置" }}</strong>
          </article>
          <article class="material-summary-card">
            <span>本阶段批次</span>
            <strong>{{ activeMaterials.length }} 批</strong>
          </article>
          <article class="material-summary-card">
            <span>全部物料</span>
            <strong>{{ materials.length }} 批</strong>
          </article>
          <article class="material-summary-card">
            <span>可落位目标区</span>
            <strong>{{ assignableZones.length }} 个</strong>
          </article>
        </div>
      </section>
    </el-dialog>

    <el-dialog
      v-model="phaseMaterialsDialogOpen"
      title="本阶段物料"
      class="material-dialog"
      width="760px"
      destroy-on-close
    >
      <section class="material-dialog-card">
        <p class="dialog-toolbar__meta">点击物料后直接进入编辑弹窗。</p>

        <div v-if="activeMaterials.length" class="material-chip-grid material-chip-grid--dialog">
          <button
            v-for="material in activeMaterials"
            :key="material.id"
            type="button"
            :class="['material-chip', { 'material-chip--active': material.id === selectedMaterialId }]"
            @click="openMaterialEditorDialog(material.id)"
          >
            <div class="material-chip__title">
              <span class="material-dot" :style="{ background: material.display_color || '#38bdf8' }" />
              <strong>{{ material.name }}</strong>
            </div>
            <p>{{ material.category }} · {{ formatMetric(material.weight_tons, 1) }} t</p>
            <small>{{ material.batch_id || "未分批" }} · {{ zoneName(material.target_zone_id) }}</small>
          </button>
        </div>
        <article v-else class="empty-card empty-card--compact">
          当前阶段还没有物料，可直接新增或导入模板批量填充。
        </article>
      </section>
    </el-dialog>

    <el-dialog
      v-model="materialEditorDialogOpen"
      title="当前编辑"
      class="material-dialog"
      width="860px"
      destroy-on-close
    >
      <section class="material-dialog-card">
        <div v-if="selectedMaterial" class="editor-block editor-block--dialog">
          <div class="editor-head">
            <div>
              <p class="panel-kicker">Editor</p>
              <h3>{{ selectedMaterial.name }}</h3>
            </div>
            <span :class="['status-pill', selectedPlacement ? placementToneClass : 'status-pill--idle']">
              {{ selectedPlacement ? placementLabel : "未计算" }}
            </span>
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
              <span>长度 (m)</span>
              <el-input-number
                v-model="selectedMaterial.length"
                :min="0.1"
                :step="0.1"
                :controls="false"
                class="ghost-number"
              />
            </label>
            <label class="field-card">
              <span>宽度 (m)</span>
              <el-input-number
                v-model="selectedMaterial.width"
                :min="0.1"
                :step="0.1"
                :controls="false"
                class="ghost-number"
              />
            </label>
            <label class="field-card">
              <span>高度 (m)</span>
              <el-input-number
                v-model="selectedMaterial.height"
                :min="0.1"
                :step="0.1"
                :controls="false"
                class="ghost-number"
              />
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
              <span>周转频次</span>
              <el-input-number
                v-model="selectedMaterial.handling_frequency"
                :min="1"
                :step="1"
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
            <span class="editor-footnote">{{ formatMaterialFootprint(selectedMaterial) }}</span>
            <el-button text class="danger-button" @click="layoutStore.removeMaterial(selectedMaterial.id)">
              删除物料
            </el-button>
          </div>
        </div>
        <article v-else class="empty-card empty-card--compact">
          先在“物料列表”弹窗中选择一批物料，再进入当前编辑。
        </article>
      </section>
    </el-dialog>

    <el-dialog
      v-model="resultDialogOpen"
      title="阶段结论"
      class="material-dialog"
      width="620px"
      destroy-on-close
    >
      <section class="material-dialog-card">
        <div class="summary-grid">
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
    </el-dialog>

    <el-dialog
      v-model="decisionDialogOpen"
      title="选中物料解释"
      class="material-dialog"
      width="860px"
      destroy-on-close
    >
      <section v-if="selectedPlacement" class="material-dialog-card">
        <div class="decision-card decision-card--dialog">
          <div class="decision-head">
            <div class="decision-head__copy">
              <strong>{{ selectedPlacement.material_name }}</strong>
              <p>{{ selectedPlacement.batch_id || "未分批" }} · {{ selectedPlacement.assigned_crane_name || "未分配塔吊" }}</p>
            </div>
            <span :class="['status-pill', placementToneClass]">{{ placementLabel }}</span>
          </div>

          <div class="decision-overview">
            <article class="decision-stat">
              <span>目标区</span>
              <strong>{{ selectedPlacement.target_zone_name || zoneName(selectedPlacement.target_zone_id) }}</strong>
            </article>
            <article class="decision-stat">
              <span>运输距离</span>
              <strong>{{ selectedPlacement.distance != null ? `${formatMetric(selectedPlacement.distance, 1)} m` : "--" }}</strong>
            </article>
            <article class="decision-stat">
              <span>运输成本</span>
              <strong>{{ selectedPlacement.transport_cost != null ? formatMetric(selectedPlacement.transport_cost, 1) : "--" }}</strong>
            </article>
            <article class="decision-stat">
              <span>障碍穿越</span>
              <strong>{{ selectedPlacement.path_crosses_obstacle ? "存在" : "无" }}</strong>
            </article>
          </div>

          <article class="decision-note-card">
            <span>系统解释</span>
            <p class="decision-note">{{ selectedPlacement.decision_note }}</p>
          </article>

          <div class="decision-section">
            <div class="decision-section__head">
              <h3>决策因子</h3>
              <span>{{ selectedPlacement.decision_factors.length }} 项</span>
            </div>

            <div class="tag-list">
              <span
                v-for="factor in selectedPlacement.decision_factors"
                :key="`${factor.label}-${factor.value}`"
                :class="['decision-tag', `decision-tag--${factor.tone}`]"
              >
                {{ factor.label }} · {{ factor.value }}
              </span>
            </div>
          </div>

          <div class="decision-section">
            <div class="decision-section__head">
              <h3>塔吊方案</h3>
              <span>{{ selectedPlacement.crane_options.length }} 组</span>
            </div>

            <div class="option-list">
              <article
                v-for="option in selectedPlacement.crane_options"
                :key="option.crane_id"
                :class="['option-card', { 'option-card--muted': !option.reachable }]"
              >
                <div class="option-card__head">
                  <div class="option-card__copy">
                    <strong>{{ option.crane_name }}</strong>
                    <p>{{ option.reason }}</p>
                  </div>
                  <span :class="['mini-pill', option.reachable ? 'mini-pill--success' : 'mini-pill--warning']">
                    {{ option.reachable ? "可达" : "不可达" }}
                  </span>
                </div>
                <div class="option-card__meta">
                  <small>距离 {{ option.distance != null ? `${formatMetric(option.distance, 1)} m` : "--" }}</small>
                  <small>成本 {{ option.estimated_cost != null ? formatMetric(option.estimated_cost, 1) : "--" }}</small>
                </div>
              </article>
            </div>
          </div>
        </div>
      </section>
      <section v-else class="material-dialog-card">
        <article class="sidebar-empty-card">
          <strong>还没有可解释的物料</strong>
          <p>先在左侧或物料弹窗里选择一批本阶段物料，再执行一次场布计算。</p>
        </article>
      </section>
    </el-dialog>

    <el-dialog
      v-model="actionsDialogOpen"
      title="待办动作"
      class="material-dialog"
      width="760px"
      destroy-on-close
    >
      <section class="material-dialog-card">
        <div v-if="currentResult?.metrics.action_items.length" class="action-list action-list--dialog">
          <article
            v-for="item in currentResult.metrics.action_items"
            :key="item.id"
            :class="['action-card', `action-card--${item.severity}`]"
          >
            <div class="action-card__head">
              <div class="action-card__copy">
                <span class="action-card__kicker">{{ formatActionCategory(item.category) }}</span>
                <strong>{{ item.title }}</strong>
              </div>
              <span :class="['mini-pill', `mini-pill--${item.severity || 'neutral'}`]">
                {{ actionSeverityText(item.severity) }}
              </span>
            </div>
            <p>{{ item.detail }}</p>
          </article>
        </div>
        <article v-else class="sidebar-empty-card">
          当前阶段暂无系统建议动作。
        </article>
      </section>
    </el-dialog>

    <el-dialog
      v-model="versionsDialogOpen"
      title="方案留痕"
      class="material-dialog"
      width="760px"
      destroy-on-close
    >
      <section class="material-dialog-card">
        <div v-if="phaseVersions.length" class="version-list version-list--dialog">
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
        <article v-else class="sidebar-empty-card">
          还没有该阶段的计算版本。
        </article>
      </section>
    </el-dialog>

    <el-dialog
      v-model="stagePlanDialogOpen"
      :title="stagePlanFloatingLabel"
      class="stage-plan-dialog"
      width="560px"
      destroy-on-close
    >
      <section class="stage-plan-dialog-card">
        <p class="panel-kicker">Stage Plan</p>
        <div class="canvas-stage-plan__head">
          <div>
            <h2>{{ activePhase ? `${activePhase.sequence}. ${activePhase.name}` : "阶段详细计划" }}</h2>
            <p>{{ phaseTimelineLabel }}</p>
          </div>
          <span :class="['status-pill', phaseStatusToneClass]">
            {{ phaseStatusText(activePhase?.status) }}
          </span>
        </div>

        <p class="canvas-stage-plan__objective">
          {{ activePhase?.objective || "围绕当前阶段材料、道路净空与塔吊效率生成可执行场布。" }}
        </p>

        <div class="canvas-stage-plan__metrics">
          <article class="canvas-stage-plan__metric">
            <span>本阶段物料</span>
            <strong>{{ activeMaterials.length }} 批</strong>
          </article>
          <article class="canvas-stage-plan__metric">
            <span>可落位区域</span>
            <strong>{{ assignableZones.length }} 个</strong>
          </article>
          <article class="canvas-stage-plan__metric">
            <span>道路/通道约束</span>
            <strong>{{ blockingZoneCount }} 处</strong>
          </article>
          <article class="canvas-stage-plan__metric">
            <span>高优先级物料</span>
            <strong>{{ highPriorityMaterialCount }} 批</strong>
          </article>
        </div>

        <div class="canvas-stage-plan__facts">
          <article
            v-for="fact in stagePlanFacts"
            :key="fact.label"
            class="canvas-stage-plan__fact"
          >
            <span>{{ fact.label }}</span>
            <strong>{{ fact.value }}</strong>
          </article>
        </div>
      </section>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { storeToRefs } from "pinia";

import CanvasMap from "../components/CanvasMap.vue";
import type { MaterialModel, PlacementResult } from "../types/layout";
import { useLayoutStore } from "../stores/layout";

const MATERIAL_TEMPLATE_HEADERS = [
  "name",
  "category",
  "length",
  "width",
  "height",
  "weight_tons",
  "handling_frequency",
  "stay_days",
  "priority_score",
  "batch_id",
  "target_zone_id",
  "phase_id",
  "notes",
  "display_color",
] as const;

type MaterialCsvField = (typeof MATERIAL_TEMPLATE_HEADERS)[number];

const MATERIAL_HEADER_ALIASES: Record<MaterialCsvField, readonly string[]> = {
  name: ["name", "material_name", "物料名称", "名称"],
  category: ["category", "分类"],
  length: ["length", "len", "l", "长度"],
  width: ["width", "w", "宽度"],
  height: ["height", "h", "高度"],
  weight_tons: ["weight_tons", "weight", "重量", "重量_t", "重量t"],
  handling_frequency: ["handling_frequency", "frequency", "handling", "搬运频次", "周转频次"],
  stay_days: ["stay_days", "stay", "停留天数", "停留"],
  priority_score: ["priority_score", "priority", "优先级"],
  batch_id: ["batch_id", "batch", "批次号", "批次"],
  target_zone_id: ["target_zone_id", "zone_id", "目标区", "目标管控区"],
  phase_id: ["phase_id", "phase", "阶段", "阶段id"],
  notes: ["notes", "remark", "备注"],
  display_color: ["display_color", "color", "颜色"],
};

const layoutStore = useLayoutStore();
const {
  activeMaterials,
  activePhase,
  activePhaseId,
  controlZones,
  error,
  hasResult,
  loading,
  materials,
  optimizationResult,
  phaseControlZones,
  phases,
  projectName,
  recentPlanVersions,
} = storeToRefs(layoutStore);

const selectedMaterialId = ref<string | null>(null);
const leftPanelOpen = ref(true);
const rightPanelOpen = ref(false);
const allMaterialsDialogOpen = ref(false);
const materialOverviewDialogOpen = ref(false);
const phaseMaterialsDialogOpen = ref(false);
const materialEditorDialogOpen = ref(false);
const resultDialogOpen = ref(false);
const decisionDialogOpen = ref(false);
const actionsDialogOpen = ref(false);
const versionsDialogOpen = ref(false);
const stagePlanDialogOpen = ref(false);
const materialSearchKeyword = ref("");
const materialImportInputRef = ref<HTMLInputElement | null>(null);

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

const phaseStatusText = (status?: string | null) => {
  if (status === "active") {
    return "进行中";
  }
  if (status === "planned") {
    return "待执行";
  }
  if (status === "completed") {
    return "已完成";
  }
  return status || "未设置";
};

const actionSeverityText = (severity?: string | null) => {
  if (severity === "high") {
    return "高优先";
  }
  if (severity === "medium") {
    return "中优先";
  }
  if (severity === "low") {
    return "低优先";
  }
  return "待处理";
};

const formatActionCategory = (category?: string | null) => {
  if (category === "safety") {
    return "安全";
  }
  if (category === "flow") {
    return "动线";
  }
  if (category === "storage") {
    return "堆场";
  }
  if (category === "crane") {
    return "塔吊";
  }
  if (category === "zone") {
    return "目标区";
  }
  if (!category) {
    return "系统建议";
  }

  return category.replace(/[_-]+/g, " ").trim();
};

const phaseName = (phaseId?: string | null) =>
  phases.value.find((phase) => phase.id === phaseId)?.name ?? "未分配阶段";

const zoneName = (zoneId?: string | null) =>
  controlZones.value.find((zone) => zone.id === zoneId)?.name ?? "未绑定目标区";

const formatMaterialFootprint = (material: MaterialModel) =>
  `${formatMetric(material.length, 1)} × ${formatMetric(material.width, 1)} × ${formatMetric(material.height, 1)} m`;

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

const phaseStatusToneClass = computed(() =>
  activePhase.value?.status === "active" ? "status-pill--running" : "status-pill--idle",
);

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

const phaseSequenceMap = computed(
  () => new Map(phases.value.map((phase) => [phase.id, phase.sequence])),
);

const allMaterialsSorted = computed(() =>
  [...materials.value].sort((left, right) => {
    const leftOrder = phaseSequenceMap.value.get(left.phase_id ?? "") ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = phaseSequenceMap.value.get(right.phase_id ?? "") ?? Number.MAX_SAFE_INTEGER;
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }
    return left.name.localeCompare(right.name, "zh-CN");
  }),
);

const filteredMaterials = computed(() => {
  const keyword = materialSearchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return allMaterialsSorted.value;
  }

  return allMaterialsSorted.value.filter((material) =>
    [
      material.name,
      material.batch_id,
      material.category,
      material.notes,
      phaseName(material.phase_id),
      zoneName(material.target_zone_id),
    ].some((value) => value?.toLowerCase().includes(keyword)),
  );
});

const phaseTimelineLabel = computed(() => {
  if (!activePhase.value) {
    return "时间窗口待配置";
  }
  if (activePhase.value.start_day != null && activePhase.value.end_day != null) {
    return `第 ${activePhase.value.start_day} - ${activePhase.value.end_day} 天`;
  }
  if (activePhase.value.start_day != null) {
    return `第 ${activePhase.value.start_day} 天起`;
  }
  if (activePhase.value.end_day != null) {
    return `截至第 ${activePhase.value.end_day} 天`;
  }
  return "时间窗口待配置";
});

const stagePlanFloatingLabel = computed(() =>
  `${activePhase.value?.name ?? "当前阶段"}详细计划`,
);

const highPriorityMaterialCount = computed(() =>
  activeMaterials.value.filter((material) => material.priority_score >= 1.2).length,
);

const blockingZoneCount = computed(() =>
  phaseControlZones.value.filter((zone) => zone.blocking).length,
);

const stagePlanFacts = computed(() => {
  const assignableZoneNames = assignableZones.value.map((zone) => zone.name);
  const blockingZoneNames = phaseControlZones.value.filter((zone) => zone.blocking).map((zone) => zone.name);

  return [
    {
      label: "目标区安排",
      value: assignableZoneNames.length
        ? assignableZoneNames.slice(0, 3).join("、")
        : "当前阶段暂无可落位的目标区",
    },
    {
      label: "净空要求",
      value: blockingZoneNames.length
        ? `${blockingZoneNames.slice(0, 2).join("、")}${blockingZoneNames.length > 2 ? " 等" : ""}需保持通行`
        : "当前阶段未配置阻断型通道",
    },
    {
      label: "资源重点",
      value: highPriorityMaterialCount.value
        ? `${highPriorityMaterialCount.value} 批高优先级物料需优先靠近目标区`
        : "当前阶段以常规周转物料为主",
    },
  ];
});

const normalizeHeader = (value: string) =>
  value
    .replace(/^\uFEFF/, "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");

const parseCsvRows = (text: string) => {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    const nextCharacter = text[index + 1];

    if (character === "\"") {
      if (inQuotes && nextCharacter === "\"") {
        currentCell += "\"";
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (character === "," && !inQuotes) {
      currentRow.push(currentCell);
      currentCell = "";
      continue;
    }

    if ((character === "\n" || character === "\r") && !inQuotes) {
      if (character === "\r" && nextCharacter === "\n") {
        index += 1;
      }
      currentRow.push(currentCell);
      rows.push(currentRow);
      currentRow = [];
      currentCell = "";
      continue;
    }

    currentCell += character;
  }

  if (currentCell.length > 0 || currentRow.length > 0) {
    currentRow.push(currentCell);
    rows.push(currentRow);
  }

  return rows.filter((row) => row.some((cell) => cell.trim().length > 0));
};

const resolveColumnIndex = (headers: string[], key: MaterialCsvField) => {
  const aliases = MATERIAL_HEADER_ALIASES[key].map(normalizeHeader);
  return headers.findIndex((header) => aliases.includes(normalizeHeader(header)));
};

const readCell = (row: string[], index: number) =>
  (index >= 0 ? row[index] : "").trim();

const readNumber = (value: string, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const defaultZoneIdForPhase = (phaseId?: string | null) =>
  controlZones.value.find((zone) => !zone.blocking && (!zone.phase_id || zone.phase_id === phaseId))?.id ?? null;

const resolvePhaseId = (value: string) => {
  const normalized = value.trim();
  if (normalized && phases.value.some((phase) => phase.id === normalized)) {
    return normalized;
  }
  return activePhaseId.value ?? phases.value[0]?.id ?? null;
};

const resolveTargetZoneId = (value: string, phaseId: string | null) => {
  const normalized = value.trim();
  if (
    normalized
    && controlZones.value.some(
      (zone) => zone.id === normalized && !zone.blocking && (!zone.phase_id || zone.phase_id === phaseId),
    )
  ) {
    return normalized;
  }
  return defaultZoneIdForPhase(phaseId);
};

const buildImportedMaterials = (text: string): MaterialModel[] => {
  const rows = parseCsvRows(text);
  if (rows.length < 2) {
    throw new Error("导入文件缺少表头或数据行，请先下载示例模板。");
  }

  const headers = rows[0];
  const nameIndex = resolveColumnIndex(headers, "name");
  if (nameIndex === -1) {
    throw new Error("导入文件缺少 name/物料名称 列。");
  }

  const indices = {
    category: resolveColumnIndex(headers, "category"),
    length: resolveColumnIndex(headers, "length"),
    width: resolveColumnIndex(headers, "width"),
    height: resolveColumnIndex(headers, "height"),
    weight_tons: resolveColumnIndex(headers, "weight_tons"),
    handling_frequency: resolveColumnIndex(headers, "handling_frequency"),
    stay_days: resolveColumnIndex(headers, "stay_days"),
    priority_score: resolveColumnIndex(headers, "priority_score"),
    batch_id: resolveColumnIndex(headers, "batch_id"),
    target_zone_id: resolveColumnIndex(headers, "target_zone_id"),
    phase_id: resolveColumnIndex(headers, "phase_id"),
    notes: resolveColumnIndex(headers, "notes"),
    display_color: resolveColumnIndex(headers, "display_color"),
  };

  const imported = rows
    .slice(1)
    .filter((row) => row.some((cell) => cell.trim().length > 0))
    .map((row, index) => {
      const phaseId = resolvePhaseId(readCell(row, indices.phase_id));
      const targetZoneId = resolveTargetZoneId(readCell(row, indices.target_zone_id), phaseId);
      const materialName = readCell(row, nameIndex) || `导入物料 ${index + 1}`;

      return {
        id: `material-${crypto.randomUUID()}`,
        name: materialName,
        category: readCell(row, indices.category) || "general",
        length: Math.max(readNumber(readCell(row, indices.length), 4.5), 0.1),
        width: Math.max(readNumber(readCell(row, indices.width), 2.5), 0.1),
        height: Math.max(readNumber(readCell(row, indices.height), 1), 0.1),
        weight_tons: Math.max(readNumber(readCell(row, indices.weight_tons), 2.5), 0.1),
        handling_frequency: Math.max(readNumber(readCell(row, indices.handling_frequency), 1), 1),
        phase_id: phaseId,
        batch_id: readCell(row, indices.batch_id) || `IMP-${Date.now()}-${index + 1}`,
        priority_score: Math.max(readNumber(readCell(row, indices.priority_score), 1), 0.2),
        stay_days: Math.max(readNumber(readCell(row, indices.stay_days), 3), 1),
        target_zone_id: targetZoneId,
        notes: readCell(row, indices.notes) || null,
        display_color: readCell(row, indices.display_color) || null,
      } satisfies MaterialModel;
    });

  if (!imported.length) {
    throw new Error("导入文件没有可用数据行。");
  }

  return imported;
};

const escapeCsv = (value: string) => {
  if (/["\n,\r]/.test(value)) {
    return `"${value.replace(/"/g, "\"\"")}"`;
  }
  return value;
};

const openAllMaterialsDialog = () => {
  materialSearchKeyword.value = "";
  allMaterialsDialogOpen.value = true;
};

const openMaterialEditorDialog = (materialId?: string | null) => {
  if (materialId) {
    selectedMaterialId.value = materialId;
  } else if (!selectedMaterialId.value && activeMaterials.value.length) {
    selectedMaterialId.value = activeMaterials.value[0].id;
  }

  phaseMaterialsDialogOpen.value = false;
  materialEditorDialogOpen.value = true;
};

const focusMaterial = (materialId: string, phaseId?: string | null) => {
  if (phaseId && phaseId !== activePhaseId.value) {
    layoutStore.setActivePhase(phaseId);
  }
  leftPanelOpen.value = true;
  selectedMaterialId.value = materialId;
  allMaterialsDialogOpen.value = false;
};

const handlePhaseChange = (phaseId: string) => {
  layoutStore.setActivePhase(phaseId);
};

const openMaterialImport = () => {
  materialImportInputRef.value?.click();
};

const handleMaterialImport = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const [file] = input.files ?? [];

  if (!file) {
    return;
  }

  try {
    const importedMaterials = buildImportedMaterials(await file.text());
    layoutStore.appendImportedMaterials(importedMaterials);

    const currentPhaseMaterial = importedMaterials.find((material) => material.phase_id === activePhaseId.value);
    if (currentPhaseMaterial) {
      selectedMaterialId.value = currentPhaseMaterial.id;
    }

    ElMessage.success(`已导入 ${importedMaterials.length} 批物料`);
  } catch (importError) {
    const message = importError instanceof Error ? importError.message : "物料导入失败，请检查模板格式。";
    ElMessage.error(message);
  } finally {
    input.value = "";
  }
};

const downloadMaterialTemplate = () => {
  const defaultZoneId = assignableZones.value[0]?.id ?? "";
  const activePhaseValue = activePhaseId.value ?? "";

  const rows = [
    [...MATERIAL_TEMPLATE_HEADERS],
    [
      "钢筋成捆区",
      "rebar",
      "12",
      "3",
      "1.2",
      "6.5",
      "3",
      "5",
      "1.4",
      "RB-01",
      defaultZoneId,
      activePhaseValue,
      "靠近钢筋加工和塔吊主覆盖区",
      "#38BDF8",
    ],
    [
      "模板周转区",
      "formwork",
      "8",
      "4",
      "2.4",
      "3.2",
      "2",
      "4",
      "1.1",
      "FW-01",
      defaultZoneId,
      activePhaseValue,
      "避免覆盖道路和卸料通道",
      "#14B8A6",
    ],
  ];

  const csvContent = rows
    .map((row) => row.map((value) => escapeCsv(String(value))).join(","))
    .join("\r\n");

  const blob = new Blob([`\uFEFF${csvContent}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `material-import-template-${activePhaseValue || "current"}.csv`;
  link.click();
  URL.revokeObjectURL(url);
};

watch(
  activeMaterials,
  (phaseMaterials) => {
    if (!phaseMaterials.length) {
      selectedMaterialId.value = null;
      return;
    }

    if (
      !selectedMaterialId.value
      || !phaseMaterials.some((material) => material.id === selectedMaterialId.value)
    ) {
      selectedMaterialId.value = phaseMaterials[0].id;
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
.material-chip,
.material-summary-card,
.summary-card,
.decision-card,
.action-card,
.version-card,
.option-card,
.empty-card,
.stage-plan-float,
.stage-plan-dialog-card {
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
.editor-head h3,
.canvas-stage-plan__head h2 {
  margin: 0;
  color: var(--app-text-primary);
  letter-spacing: -0.03em;
}

.toolbar-copy p,
.panel-head__subtitle,
.material-chip p,
.summary-card p,
.decision-note,
.action-card p,
.version-card p,
.option-card p,
.empty-card,
.version-card small,
.material-chip small,
.canvas-stage-plan__head p,
.canvas-stage-plan__objective,
.toolbar-hint,
.editor-footnote {
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
.field-card span,
.material-summary-card span,
.canvas-stage-plan__metric span,
.canvas-stage-plan__fact span {
  display: block;
  margin-bottom: 6px;
  color: var(--app-text-tertiary);
  font-size: 12px;
}

.toolbar-stat strong,
.summary-card strong,
.material-summary-card strong,
.canvas-stage-plan__metric strong,
.canvas-stage-plan__fact strong {
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
}

.panel--left {
  overflow: hidden;
}

.panel--right {
  overflow: auto;
}

.panel--canvas {
  padding: 8px;
}

.canvas-frame {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
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

.panel-section--right-block {
  flex: 0 0 auto;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

.panel-head__copy {
  min-width: 0;
}

.panel-head__stack {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.panel-head__subtitle {
  font-size: 13px;
}

.panel-head__hint {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.5;
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

.material-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-hint {
  font-size: 12px;
}

.material-action-grid,
.sidebar-action-grid {
  display: grid;
  gap: 10px;
}

.material-action-button,
.sidebar-action-button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 14px;
  border: 1px solid rgba(146, 181, 205, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--app-text-primary);
  text-align: left;
  cursor: pointer;
}

.material-action-button:hover,
.sidebar-action-button:hover {
  border-color: rgba(56, 189, 248, 0.24);
  background: rgba(56, 189, 248, 0.08);
}

.material-action-button__copy,
.sidebar-action-button__copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.material-action-button__copy span,
.material-action-button__copy small,
.sidebar-action-button__copy span,
.sidebar-action-button__copy small {
  color: var(--app-text-secondary);
}

.material-action-button__copy span,
.sidebar-action-button__copy span {
  font-size: 12px;
}

.material-action-button__copy strong,
.sidebar-action-button__copy strong {
  color: var(--app-text-primary);
}

.material-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.material-summary-card {
  padding: 12px;
}

.material-chip-grid,
.action-list,
.version-list,
.option-list {
  display: grid;
  gap: 10px;
}

.material-chip-grid {
  grid-template-columns: repeat(auto-fit, minmax(142px, 1fr));
  max-height: 260px;
  overflow: auto;
  padding-right: 4px;
}

.material-chip-grid--dialog {
  max-height: none;
}

.action-list,
.version-list,
.option-list {
  grid-template-columns: 1fr;
}

.action-list,
.version-list {
  max-height: 220px;
  overflow: auto;
  padding-right: 4px;
}

.action-list--dialog,
.version-list--dialog {
  max-height: none;
}

.material-chip {
  width: 100%;
  display: grid;
  gap: 8px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
}

.material-chip--active {
  border-color: rgba(56, 189, 248, 0.28);
  background: rgba(56, 189, 248, 0.08);
}

.material-chip__title,
.version-card__head,
.decision-head,
.option-card__head,
.dialog-material-cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.dialog-material-cell {
  flex-direction: column;
  align-items: flex-start;
}

.material-label {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.material-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.04);
  flex: 0 0 auto;
}

.editor-block,
.decision-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  overflow: auto;
}

.editor-block {
  max-height: 380px;
}

.editor-block--dialog {
  max-height: none;
}

.decision-card--dialog {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  overflow: visible;
}

.editor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.editor-footnote {
  font-size: 12px;
}

.summary-grid,
.canvas-stage-plan__metrics,
.canvas-stage-plan__facts {
  display: grid;
  gap: 10px;
}

.summary-grid,
.canvas-stage-plan__metrics {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.canvas-stage-plan__facts {
  grid-template-columns: 1fr;
}

.summary-card,
.canvas-stage-plan__metric,
.canvas-stage-plan__fact {
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.045);
}

.summary-card--primary {
  grid-column: 1 / -1;
}

.summary-card--primary strong {
  font-size: 1.8rem;
}

.stage-plan-float {
  position: absolute;
  right: 18px;
  bottom: 18px;
  z-index: 4;
  min-height: 46px;
  max-width: calc(100% - 36px);
  padding: 0 18px;
  border: 1px solid rgba(56, 189, 248, 0.2);
  background: rgba(5, 14, 24, 0.86);
  color: var(--app-text-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.stage-plan-float:hover {
  background: rgba(8, 18, 28, 0.96);
}

.stage-plan-dialog-card {
  display: grid;
  gap: 14px;
  padding: 18px;
  background: rgba(5, 14, 24, 0.72);
}

.canvas-stage-plan__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.canvas-stage-plan__head .status-pill {
  width: auto;
  min-width: 88px;
}

.canvas-stage-plan__objective {
  color: var(--app-text-primary);
}

.decision-head {
  align-items: flex-start;
}

.decision-head__copy {
  display: grid;
  gap: 4px;
}

.decision-head p {
  margin-top: 4px;
}

.decision-overview {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.decision-stat,
.decision-note-card {
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.045);
}

.decision-stat span,
.decision-note-card span,
.action-card__kicker {
  display: block;
  margin-bottom: 6px;
  color: var(--app-text-tertiary);
  font-size: 12px;
}

.decision-stat strong {
  color: var(--app-text-primary);
}

.decision-note-card {
  display: grid;
  gap: 6px;
}

.decision-note {
  color: var(--app-text-primary);
}

.decision-section {
  display: grid;
  gap: 10px;
}

.decision-section__head,
.action-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.decision-section__head span {
  color: var(--app-text-secondary);
  font-size: 12px;
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

.sidebar-empty-card {
  display: grid;
  gap: 8px;
  padding: 16px;
  border: 1px solid rgba(146, 181, 205, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
}

.sidebar-empty-card strong {
  color: var(--app-text-primary);
}

.sidebar-empty-card p {
  margin: 0;
  color: var(--app-text-secondary);
  line-height: 1.6;
}

.option-card {
  display: grid;
  gap: 10px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
}

.option-card__copy {
  display: grid;
  gap: 4px;
}

.option-card__copy p {
  margin: 0;
}

.option-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--app-text-secondary);
}

.action-card {
  display: grid;
  gap: 10px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
}

.action-card__copy {
  display: grid;
  gap: 4px;
}

.action-card__copy strong {
  color: var(--app-text-primary);
}

.mini-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.mini-pill--success {
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

.mini-pill--warning,
.mini-pill--medium {
  background: rgba(245, 158, 11, 0.14);
  color: #fde68a;
}

.mini-pill--high {
  background: rgba(239, 68, 68, 0.14);
  color: #fecaca;
}

.mini-pill--low,
.mini-pill--neutral {
  background: rgba(255, 255, 255, 0.06);
  color: var(--app-text-secondary);
}

.empty-card--compact {
  font-size: 13px;
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

.dialog-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.dialog-search {
  flex: 1;
}

.dialog-toolbar__meta {
  min-width: max-content;
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.table-shell {
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid rgba(146, 181, 205, 0.12);
}

.material-dialog-card {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid rgba(146, 181, 205, 0.12);
  border-radius: 24px;
  background: rgba(5, 14, 24, 0.72);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
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

:deep(.utility-button--text.el-button) {
  min-height: 28px;
  padding-inline: 10px;
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

:deep(.all-materials-dialog .el-dialog) {
  max-width: 1120px;
  border-radius: 24px;
  background: rgba(8, 18, 28, 0.96);
  box-shadow: var(--panel-shadow);
}

:deep(.all-materials-dialog .el-dialog__header),
:deep(.all-materials-dialog .el-dialog__body) {
  padding-inline: 20px;
}

:deep(.all-materials-dialog .el-dialog__title),
:deep(.all-materials-dialog .el-table),
:deep(.all-materials-dialog .el-table th.el-table__cell),
:deep(.all-materials-dialog .el-table tr),
:deep(.all-materials-dialog .el-table td.el-table__cell) {
  color: var(--app-text-primary);
}

:deep(.all-materials-dialog .el-table),
:deep(.all-materials-dialog .el-table__inner-wrapper),
:deep(.all-materials-dialog .el-table__body-wrapper),
:deep(.all-materials-dialog .el-table tr),
:deep(.all-materials-dialog .el-table__header-wrapper) {
  background: rgba(8, 18, 28, 0.9);
}

:deep(.all-materials-dialog .el-table th.el-table__cell),
:deep(.all-materials-dialog .el-table td.el-table__cell) {
  background: transparent;
  border-bottom-color: rgba(148, 163, 184, 0.12);
}

:deep(.all-materials-dialog .el-table__fixed-right::before),
:deep(.all-materials-dialog .el-table::before) {
  background: rgba(148, 163, 184, 0.12);
}

:deep(.material-dialog .el-dialog),
:deep(.stage-plan-dialog .el-dialog) {
  border-radius: 24px;
  background: rgba(8, 18, 28, 0.96);
  box-shadow: var(--panel-shadow);
}

:deep(.material-dialog .el-dialog__header),
:deep(.material-dialog .el-dialog__body),
:deep(.stage-plan-dialog .el-dialog__header),
:deep(.stage-plan-dialog .el-dialog__body) {
  padding-inline: 20px;
}

:deep(.material-dialog .el-dialog__title),
:deep(.stage-plan-dialog .el-dialog__title) {
  color: var(--app-text-primary);
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

@media (max-width: 1180px) {
  .field-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
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

  .material-chip-grid,
  .version-list,
  .action-list {
    max-height: none;
  }

  .canvas-frame {
    min-height: 720px;
  }

  .stage-plan-float {
    right: 12px;
    bottom: 12px;
  }
}

@media (max-width: 720px) {
  .dashboard-shell {
    padding: 12px;
  }

  .summary-grid,
  .decision-overview,
  .field-grid,
  .material-summary-grid,
  .canvas-stage-plan__metrics {
    grid-template-columns: 1fr;
  }

  .dialog-toolbar,
  .editor-actions,
  .canvas-stage-plan__head,
  .panel-head,
  .decision-section__head,
  .action-card__head {
    flex-direction: column;
    align-items: stretch;
  }

  .canvas-frame {
    min-height: auto;
    display: grid;
    gap: 12px;
  }

  .stage-plan-float {
    right: 12px;
    bottom: 12px;
    max-width: calc(100% - 24px);
    padding-inline: 14px;
  }
}
</style>
