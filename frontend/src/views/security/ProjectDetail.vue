<template>
  <main class="detail-page">
    <header class="topbar">
      <el-button text :icon="ArrowLeft" @click="router.push('/security/projects')">返回项目中心</el-button>
      <div class="actions">
        <el-button plain @click="router.push('/security/knowledge')">安全知识库</el-button>
        <el-button type="primary" :icon="Refresh" :loading="rescanLoading" @click="handleRescan">重新扫描</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="alert" />

    <div class="detail-layout">
      <div class="detail-main">
        <div class="head-card">
      <div class="head-title">
        <h1>{{ project.name }}</h1>
        <span class="status" :class="`status--${scanState.kind}`">{{ scanState.label }}</span>
      </div>
      <div class="head-meta">
        <template v-if="selectedTask">
          快照 #{{ selectedTask.snapshot_id }}<span class="meta-sep">·</span>语言 {{ languageLabel }}<span class="meta-sep">·</span>最近任务 {{ formatSecurityDate(selectedTask.created_at) }}
        </template>
        <template v-else>暂无扫描记录</template>
      </div>
    </div>

    <div class="stats">
      <template v-if="loading || findingsLoading">
        <div v-for="index in 5" :key="index" class="stat stat--skeleton"><el-skeleton animated :rows="2" /></div>
      </template>
      <template v-else>
        <div class="stat">
          <div class="num" :class="avgRiskScore !== null && avgRiskScore >= 60 ? 'num--red' : ''">{{ avgRiskScore !== null ? Math.round(avgRiskScore) : '-' }}</div>
          <div class="lbl">综合风险分</div>
        </div>
        <div class="stat">
          <div class="num num--red">{{ highRiskCount }}</div>
          <div class="lbl">高危及以上发现</div>
        </div>
        <div class="stat">
          <div class="num">{{ findingsTotal }}</div>
          <div class="lbl">风险发现总数</div>
        </div>
        <div class="stat">
          <div class="num num--green">{{ suggestionStats.total ? `${suggestionStats.reviewed} / ${suggestionStats.total}` : '0 / 0' }}</div>
          <div class="lbl">修复建议已审核</div>
        </div>
        <div class="stat">
          <div class="num">{{ tasks.length }}</div>
          <div class="lbl">扫描任务</div>
        </div>
      </template>
    </div>

    <ScanTaskTable
      :tasks="tasks"
      :loading="loading"
      :selected-task-id="selectedTaskId"
      :action-loading="taskActionLoading"
      @select-task="loadFindings"
      @cancel-task="handleCancelTask"
      @retry-task="handleRetryTask"
    />

    <section class="card">
      <div class="card-head">
        <h2>风险发现</h2>
        <div class="card-head__side">
          <span class="note">{{ selectedTaskId ? '任务 #' + selectedTaskId + ' 的证据化发现项，建议须人工审核' : '选择一条扫描任务查看发现项' }}</span>
          <el-radio-group
            v-if="selectedTaskId"
            class="findings-sort"
            :model-value="findingsSort"
            size="small"
            aria-label="发现项排序方式"
            @update:model-value="setFindingsSort"
          >
            <el-radio-button value="default">默认排序</el-radio-button>
            <el-radio-button value="risk">风险评分</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div class="notice">
        AI 修复建议仅供人工审阅：页面只展示服务端返回的建议、引用和受限 Diff，系统不会执行、应用、提交或推送任何代码。
      </div>

      <div v-if="findingsLoading" class="workbench" aria-label="风险发现加载中">
        <div class="finding-list finding-list--skeleton">
          <el-skeleton v-for="index in 4" :key="index" :rows="3" animated />
        </div>
        <div class="panel panel--skeleton">
          <el-skeleton :rows="8" animated />
        </div>
      </div>
      <el-empty v-else-if="!selectedTaskId" description="请选择扫描任务" />
      <el-empty v-else-if="findings.length === 0" description="该任务未发现可展示的风险。" />
      <div v-else class="workbench">
        <div ref="findingListElement" class="finding-list" role="list" aria-label="风险发现列表">
          <FindingListItem
            v-for="finding in findings"
            :key="finding.id"
            :finding="finding"
            :suggestion-ready="finding.suggestion_count > 0"
            :selected="selectedFindingId === finding.id"
            @select="selectFinding"
          />
          <button
            v-if="findingsHasMore"
            class="load-more"
            :disabled="findingsLoadingMore"
            @click="loadMoreFindings"
          >
            {{ findingsLoadingMore ? '加载中…' : `加载更多发现项（已显示 ${findings.length} / ${findingsTotal}）` }}
          </button>
        </div>
        <div class="panel">
          <FindingDetailPanel
            :finding="selectedFinding"
            :suggestions="suggestionsFor(selectedFinding?.id)"
            :suggestions-loaded="Boolean(suggestionsLoaded[selectedFinding?.id])"
            :suggestion-total="selectedFinding ? (suggestionsTotal[selectedFinding.id] ?? selectedFinding.suggestion_count ?? 0) : 0"
            :suggestions-has-more="Boolean(selectedFinding && suggestionsTotal[selectedFinding.id] > suggestionsFor(selectedFinding.id).length)"
            :suggestions-loading-more="Boolean(suggestionsLoadingMore[selectedFinding?.id])"
            :loading="Boolean(suggestionLoading[selectedFinding?.id])"
            :error-message="suggestionErrors[selectedFinding?.id]"
            @generate="handleGenerateSuggestion"
            @load-suggestions="loadSuggestions"
            @load-more-suggestions="loadMoreSuggestions"
            @copy-patch="copyPatch"
            @review="openReviewDialog"
          />
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>依赖与软件成分分析</h2>
        <div class="card-head__side">
          <span v-if="selectedTask" class="note">范围：当前任务快照 #{{ selectedTask.snapshot_id }}</span>
          <button class="dep-toggle" @click="dependenciesExpanded = !dependenciesExpanded">{{ dependenciesExpanded ? '收起' : '展开' }}</button>
        </div>
      </div>

      <el-collapse-transition>
        <div v-show="dependenciesExpanded" class="dep-body">
          <el-empty v-if="!selectedTask" description="选择扫描任务后查看该快照的依赖库存与 SCA 结果。" />
          <template v-else>
            <ScaScanStatusCard :status="scaStatus" />
            <div class="dep-layout">
              <div class="mini-card">
                <h3>依赖库存</h3>
                <DependencyInventoryTable
                  :dependencies="dependencies"
                  :loading="dependenciesLoading"
                  :loading-more="dependenciesLoadingMore"
                  :error="dependenciesError"
                  :has-more="dependenciesHasMore"
                  :total="dependenciesTotal"
                  @load-more="loadMoreDependencies"
                />
              </div>
              <div class="mini-card">
                <h3>SCA 风险</h3>
                <ScaFindingList
                  :findings="scaFindings"
                  :loading="dependenciesLoading"
                  @select-finding="focusFinding"
                />
              </div>
            </div>
          </template>
        </div>
      </el-collapse-transition>
    </section>

      <aside class="detail-side" aria-label="项目设置">
        <ExclusionRulesPanel
          :project-id="route.params.id"
          :can-edit="true"
          :rescan-loading="rescanLoading"
          @rescan="handleRescan"
        />
      </aside>
      </div>
    </div>

    <p class="foot-note">所有修复建议均须人工审核；系统不会自动执行、应用、提交或推送任何代码。</p>

    <RemediationReviewDialog
      v-model="reviewDialogVisible"
      :suggestion="selectedSuggestion"
      :submitting="reviewSubmitting"
      @submit="submitReview"
    />
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import DependencyInventoryTable from '@/components/security/dependencies/DependencyInventoryTable.vue'
import ScaFindingList from '@/components/security/dependencies/ScaFindingList.vue'
import ScaScanStatusCard from '@/components/security/dependencies/ScaScanStatusCard.vue'
import ExclusionRulesPanel from '@/components/security/project/ExclusionRulesPanel.vue'
import FindingDetailPanel from '@/components/security/project/FindingDetailPanel.vue'
import FindingListItem from '@/components/security/project/FindingListItem.vue'
import RemediationReviewDialog from '@/components/security/project/RemediationReviewDialog.vue'
import ScanTaskTable from '@/components/security/project/ScanTaskTable.vue'
import { useProjectDependencies } from '@/composables/security/useProjectDependencies'
import { useProjectScanTasks } from '@/composables/security/useProjectScanTasks'
import { useRemediationSuggestions } from '@/composables/security/useRemediationSuggestions'
import { formatSecurityDate, securityApiErrorMessage } from '@/features/security/presentation'

const route = useRoute()
const router = useRouter()
const project = { id: Number(route.params.id), name: `项目 #${route.params.id}` }
const reviewDialogVisible = ref(false)
const reviewSubmitting = ref(false)
const selectedSuggestion = ref(null)
const selectedFindingId = ref(null)
const findingListElement = ref(null)
const dependenciesExpanded = ref(false)
const selectedFinding = computed(
  () => findings.value.find((finding) => finding.id === selectedFindingId.value) || null
)
const {
  suggestionsLoaded,
  suggestionLoading,
  suggestionErrors,
  suggestionsTotal,
  suggestionsLoadingMore,
  suggestionsFor,
  loadSuggestions,
  loadMoreSuggestions,
  generateSuggestion,
  reviewSuggestion
} = useRemediationSuggestions()
const {
  loading,
  findingsLoading,
  findingsLoadingMore,
  errorMessage,
  tasks,
  findings,
  findingsStats,
  findingsTotal,
  findingsHasMore,
  selectedTaskId,
  taskActionLoading,
  selectedTask,
  completedTaskCount,
  highRiskCount,
  avgRiskScore,
  hasRunningTasks,
  findingsSort,
  load,
  loadFindings,
  loadMoreFindings,
  setFindingsSort,
  cancelTask,
  retryTask,
  rescan,
  rescanLoading,
  stopPolling
} = useProjectScanTasks(() => route.params.id)
const {
  dependencies,
  dependenciesLoading,
  dependenciesLoadingMore,
  dependenciesError,
  dependenciesTotal,
  dependenciesHasMore,
  scaFindings,
  scaStatus,
  loadDependencies,
  loadMoreDependencies,
  clearDependencies
} = useProjectDependencies(() => route.params.id)

const scanState = computed(() => {
  if (hasRunningTasks.value) return { kind: 'run', label: '扫描中' }
  if (tasks.value.length) return { kind: 'ok', label: '扫描完成' }
  return { kind: 'none', label: '暂无记录' }
})
const languageLabel = computed(() => {
  const languages = selectedTask.value?.summary?.languages
  return Array.isArray(languages) && languages.length ? languages.join(' / ') : '未识别'
})
const suggestionStats = computed(() => {
  const stats = findingsStats.value
  if (stats?.suggestion_total !== undefined) {
    return { total: stats.suggestion_total, reviewed: stats.suggestion_reviewed ?? 0 }
  }
  const all = findings.value.flatMap((finding) => suggestionsFor(finding.id))
  const reviewed = all.filter((item) => ['accepted', 'rejected', 'needs_revision'].includes(item.review_state)).length
  return { reviewed, total: all.length }
})

watch([selectedTask, findings], ([task, currentFindings]) => {
  if (!task) {
    clearDependencies()
    return
  }
  if (!currentFindings.length) {
    selectedFindingId.value = null
  } else if (!currentFindings.some((finding) => finding.id === selectedFindingId.value)) {
    selectedFindingId.value = currentFindings[0].id
  }
  loadDependencies(task.snapshot_id, currentFindings, task.summary)
})

const selectFinding = (finding) => {
  selectedFindingId.value = finding.id
}

const handleCancelTask = async (task) => {
  try {
    await ElMessageBox.confirm(`确认取消任务 #${task.id} 吗？已产生的证据会保留。`, "取消扫描任务", { type: "warning" })
    if (await cancelTask(task.id)) ElMessage.success("扫描任务已取消")
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(securityApiErrorMessage(error, "取消扫描任务失败"))
  }
}

const handleRetryTask = async (task) => {
  try {
    await ElMessageBox.confirm(`确认重新派发任务 #${task.id} 吗？系统会复用不可变快照。`, "重试扫描任务", { type: "info" })
    if (await retryTask(task.id)) ElMessage.success("扫描任务已重新派发")
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(securityApiErrorMessage(error, "重新派发扫描任务失败"))
  }

}
const handleRescan = async () => {
  try {
    await ElMessageBox.confirm(
      '重新扫描将基于项目最近一次快照发起全新扫描，无需重新上传代码。确定继续吗？',
      '重新扫描',
      { type: 'warning', confirmButtonText: '开始扫描' }
    )
    if (await rescan()) ElMessage.success('重新扫描任务已创建，正在后台运行')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(securityApiErrorMessage(error, '重新扫描失败'))
  }
}

const handleGenerateSuggestion = async (finding) => {
  const suggestion = await generateSuggestion(finding)
  if (suggestion) ElMessage.success('修复建议已生成，等待人工审核')
}

const copyPatch = async (patchDiff) => {
  if (!patchDiff) return
  try {
    await navigator.clipboard.writeText(patchDiff)
    ElMessage.success('Diff 已复制；请在独立分支中人工验证。')
  } catch {
    ElMessage.error('无法访问剪贴板，请手动复制 Diff。')
  }
}

const focusFinding = async (findingId) => {
  selectedFindingId.value = findingId
  await nextTick()
  const target = findingListElement.value?.querySelector(`#finding-${findingId}`)
  target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  target?.focus({ preventScroll: true })
}

const openReviewDialog = (suggestion) => {
  selectedSuggestion.value = suggestion
  reviewDialogVisible.value = true
}

const submitReview = async ({ reviewState, comment }) => {
  if (!selectedSuggestion.value || reviewSubmitting.value) return

  reviewSubmitting.value = true
  try {
    await reviewSuggestion(selectedSuggestion.value.id, { review_state: reviewState, comment })
    reviewDialogVisible.value = false
    ElMessage.success('审核决定已记录')
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '提交审核失败'))
  } finally {
    reviewSubmitting.value = false
  }
}

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

<style scoped lang="scss">
.detail-page { min-height: 100vh; padding: 12px 16px 32px; background: #f4f6f9; color: #1f2d3d; }

/* 顶部操作栏 */
.topbar {
  position: sticky; top: 0; z-index: 20;
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 8px 0; margin-bottom: 8px;
  background: rgba(244, 246, 249, .94);
  backdrop-filter: blur(8px);
}
.actions { display: flex; gap: 8px; align-items: center; }
.alert { margin-bottom: 8px; }

/* 主内容 + 右侧设置栏 */
.detail-layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 8px; align-items: start; }
.detail-main { min-width: 0; }
.detail-side { position: sticky; top: 56px; min-width: 0; }

/* 项目信息头卡 */
.head-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.head-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.head-title h1 { margin: 0; font-size: 18px; font-weight: 600; letter-spacing: 0; }
.status { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.status--ok { background: #e8f6ee; color: #1c8a4d; }
.status--run { background: #e8f1fb; color: #1d4ed8; }
.status--none { background: #eef2f7; color: #6a7890; }
.head-meta { margin-top: 6px; color: #6a7890; font-size: 13px; }
.meta-sep { margin: 0 8px; color: #c2ccd9; }

/* 统计卡 */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-top: 8px; }
.stat { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 10px 14px; }
.stat--skeleton { padding: 12px 14px; }
.stat .num { font-size: 22px; font-weight: 700; line-height: 1.2; color: #1f2d3d; font-variant-numeric: tabular-nums; }
.stat .num--red { color: #d43b3b; }
.stat .num--green { color: #1c8a4d; }
.stat .lbl { color: #6a7890; font-size: 12.5px; margin-top: 1px; }

/* 内容卡 */
.card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; margin-top: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head__side { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.card-head__side .note { color: #6a7890; font-size: 12.5px; }
.findings-sort :deep(.el-radio-button__inner) { padding: 6px 12px; font-size: 12.5px; }

.notice {
  display: flex; gap: 8px; align-items: flex-start;
  background: #fffbf0; border: 1px solid #f0dfae; border-radius: 6px;
  color: #7c5c12; font-size: 12.5px; padding: 8px 12px; margin-bottom: 10px;
}

/* 风险工作台 */
.workbench { display: grid; grid-template-columns: minmax(300px, 380px) minmax(0, 1fr); gap: 10px; align-items: start; }
.finding-list {
  display: flex; flex-direction: column; gap: 6px;
  max-height: 560px; min-height: 200px;
  overflow-y: auto; padding-right: 4px;
}
.finding-list--skeleton, .panel--skeleton { align-content: start; }
.load-more {
  display: block; width: 100%; margin-top: 2px;
  border: 1px dashed #c2ccd9; border-radius: 6px;
  background: #fafbfd; color: #52627a; font-size: 12.5px;
  padding: 8px 0; cursor: pointer;
}
.load-more:hover:not(:disabled) { border-color: #0b7fd1; color: #0b7fd1; }
.load-more:disabled { cursor: default; opacity: .6; }
.finding-list::-webkit-scrollbar, .panel :deep(.finding-detail-panel)::-webkit-scrollbar { width: 6px; }
.finding-list::-webkit-scrollbar-thumb, .panel :deep(.finding-detail-panel)::-webkit-scrollbar-thumb { background: #ccd5e0; border-radius: 3px; }
.finding-list::-webkit-scrollbar-track, .panel :deep(.finding-detail-panel)::-webkit-scrollbar-track { background: transparent; }
.panel { border: 1px solid #e2e7ee; border-radius: 8px; background: #fff; overflow: hidden; }
.panel--skeleton { padding: 14px; }

/* 依赖区 */
.dep-toggle { border: 0; background: none; color: #0b7fd1; font-size: 13px; cursor: pointer; padding: 0; }
.dep-body { padding-top: 2px; }
.dep-layout { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(300px, .9fr); gap: 10px; margin-top: 10px; }
.mini-card { border: 1px solid #e2e7ee; border-radius: 6px; padding: 12px; }
.mini-card h3 { margin: 0 0 8px; font-size: 13.5px; font-weight: 600; }

.foot-note { margin: 14px auto 0; text-align: center; color: #8494a8; font-size: 12px; }

@media (max-width: 960px) {
  .workbench, .dep-layout { grid-template-columns: 1fr; }
  .finding-list { max-height: 40vh; }
  .detail-layout { grid-template-columns: 1fr; }
  .detail-side { position: static; }
}
@media (max-width: 760px) {
  .detail-page { padding: 10px 10px 24px; }
  .stats { grid-template-columns: repeat(2, 1fr); }
  .card-head { flex-direction: column; align-items: flex-start; }
}
</style>
