<template>
  <main class="detail-page" v-loading="loading">
    <header class="detail-header">
      <div>
        <el-button text :icon="ArrowLeft" @click="router.push('/security/projects')">返回项目中心</el-button>
        <p class="page-eyebrow">PROJECT SECURITY WORKBENCH</p>
        <h1>{{ project.name }}</h1>
        <p>扫描记录仅展示脱敏证据；Agent 只能提出受限修复材料，所有建议均必须经过人工审核。</p>
      </div>
      <div class="header-actions">
        <el-button plain @click="router.push('/security/knowledge')">安全知识治理</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="alert" />

    <section class="summary-grid" aria-label="当前风险概要">
      <article class="summary-card"><span>扫描任务</span><strong>{{ tasks.length }}</strong></article>
      <article class="summary-card"><span>已完成</span><strong>{{ completedTaskCount }}</strong></article>
      <article class="summary-card"><span>风险发现</span><strong>{{ findings.length }}</strong></article>
      <article class="summary-card"><span>高危及以上</span><strong class="risk-number">{{ highRiskCount }}</strong></article>
      <article class="summary-card">
        <span>平均风险分</span>
        <strong :class="{ 'risk-number': avgRiskScore >= 60 }">{{ avgRiskScore !== null ? avgRiskScore.toFixed(1) : '-' }}</strong>
      </article>
    </section>

    <ScanTaskTable :tasks="tasks" :loading="loading" :selected-task-id="selectedTaskId" :action-loading="taskActionLoading" @select-task="loadFindings" @cancel-task="handleCancelTask" @retry-task="handleRetryTask" />

    <section class="workbench-section content-card">
      <div class="section-heading">
        <div>
          <p class="section-eyebrow">FINDINGS AND CONTEXTUAL AI</p>
          <h2>风险发现与 AI 修复建议</h2>
          <p>{{ selectedTaskId ? `任务 #${selectedTaskId} 的证据化发现项。建议必须人工审核，页面不会提供自动应用补丁。` : '选择一条扫描任务查看发现项。' }}</p>
        </div>
        <el-radio-group
          v-if="selectedTaskId"
          class="findings-sort"
          :model-value="findingsSort"
          size="small"
          aria-label="发现项排序方式"
          @update:model-value="setFindingsSort"
        >
          <el-radio-button value="default">默认</el-radio-button>
          <el-radio-button value="risk">风险评分</el-radio-button>
        </el-radio-group>
      </div>
      <el-alert type="warning" :closable="false" show-icon class="agent-boundary" title="AI 修复建议仅供人工审阅">
        页面只展示服务端返回的建议、RAG 引用和受限 Diff；系统不会执行、应用、提交或推送任何代码。
      </el-alert>
      <el-empty v-if="!loading && !selectedTaskId" description="请选择扫描任务" />
      <el-empty v-else-if="!loading && findings.length === 0" description="该任务未发现可展示的风险。" />
      <div v-else class="finding-workbench">
        <div ref="findingListElement" class="finding-list" role="list" aria-label="风险发现列表">
          <FindingListItem
            v-for="finding in findings"
            :key="finding.id"
            :finding="finding"
            :selected="selectedFindingId === finding.id"
            @select="selectFinding"
          />
        </div>
        <div class="finding-panel">
          <FindingDetailPanel
            :finding="selectedFinding"
            :suggestions="suggestionsFor(selectedFinding?.id)"
            :suggestions-loaded="Boolean(suggestionsLoaded[selectedFinding?.id])"
            :loading="Boolean(suggestionLoading[selectedFinding?.id])"
            :error-message="suggestionErrors[selectedFinding?.id]"
            @generate="handleGenerateSuggestion"
            @load-suggestions="loadSuggestions"
            @copy-patch="copyPatch"
            @review="openReviewDialog"
          />
        </div>
      </div>
    </section>

    <section class="workbench-section dependency-section">
      <div class="section-heading">
        <div>
          <p class="section-eyebrow">SNAPSHOT DEPENDENCIES</p>
          <h2>依赖与软件成分分析</h2>
          <p>依赖库存和风险均严格以当前选中扫描任务的快照为范围。</p>
        </div>
        <el-tag v-if="selectedTask" effect="plain">快照 #{{ selectedTask.snapshot_id }}</el-tag>
      </div>

      <el-empty v-if="!selectedTask" description="选择扫描任务后查看该快照的依赖库存与 SCA 结果。" />
      <template v-else>
        <ScaScanStatusCard :status="scaStatus" />
        <div class="dependency-layout">
          <DependencyInventoryTable
            :dependencies="dependencies"
            :loading="dependenciesLoading"
            :error="dependenciesError"
          />
          <ScaFindingList
            :findings="scaFindings"
            :loading="dependenciesLoading"
            @select-finding="focusFinding"
          />
        </div>
      </template>
    </section>

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
import FindingDetailPanel from '@/components/security/project/FindingDetailPanel.vue'
import FindingListItem from '@/components/security/project/FindingListItem.vue'
import RemediationReviewDialog from '@/components/security/project/RemediationReviewDialog.vue'
import ScanTaskTable from '@/components/security/project/ScanTaskTable.vue'
import { useProjectDependencies } from '@/composables/security/useProjectDependencies'
import { useProjectScanTasks } from '@/composables/security/useProjectScanTasks'
import { useRemediationSuggestions } from '@/composables/security/useRemediationSuggestions'
import { securityApiErrorMessage } from '@/features/security/presentation'

const route = useRoute()
const router = useRouter()
const project = { id: Number(route.params.id), name: `项目 #${route.params.id}` }
const reviewDialogVisible = ref(false)
const reviewSubmitting = ref(false)
const selectedSuggestion = ref(null)
const selectedFindingId = ref(null)
const findingListElement = ref(null)
const selectedFinding = computed(
  () => findings.value.find((finding) => finding.id === selectedFindingId.value) || null
)
const {
  suggestionsLoaded,
  suggestionLoading,
  suggestionErrors,
  suggestionsFor,
  loadSuggestions,
  preloadForFindings,
  generateSuggestion,
  reviewSuggestion
} = useRemediationSuggestions()
const {
  loading,
  errorMessage,
  tasks,
  findings,
  selectedTaskId,
  taskActionLoading,
  selectedTask,
  completedTaskCount,
  highRiskCount,
  avgRiskScore,
  findingsSort,
  load,
  loadFindings,
  setFindingsSort,
  cancelTask,
  retryTask,
  stopPolling
} = useProjectScanTasks(() => route.params.id, { onFindingsChanged: preloadForFindings })
const {
  dependencies,
  dependenciesLoading,
  dependenciesError,
  scaFindings,
  scaStatus,
  loadDependencies,
  clearDependencies
} = useProjectDependencies(() => route.params.id)

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
.detail-page { min-height: 100vh; padding: 36px clamp(20px, 4vw, 64px); background: #f6f8fb; color: #102a43; }
.detail-header, .summary-grid, .content-card, .dependency-section, .alert { max-width: 1200px; margin-left: auto; margin-right: auto; }
.detail-header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 22px; }
.detail-header h1 { margin: 6px 0 0; font-size: clamp(28px, 4vw, 40px); letter-spacing: -.025em; }
.detail-header > div > p:last-child { max-width: 720px; margin: 10px 0 0; color: #486581; line-height: 1.65; }
.page-eyebrow, .section-eyebrow { margin: 12px 0 0; color: #0e9384; font-size: 11px; font-weight: 700; letter-spacing: .1em; }
.header-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.alert { margin-bottom: 16px; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; margin-bottom: 18px; }
.summary-card { padding: 20px; border: 1px solid #d9e2ec; border-radius: 14px; background: #fff; box-shadow: 0 8px 20px rgba(16, 42, 67, .04); }
.summary-card span { display: block; color: #627d98; font-size: 13px; }
.summary-card strong { display: block; margin-top: 8px; color: #102a43; font-size: 28px; }
.summary-card .risk-number { color: #b42318; }
.workbench-section { margin-top: 18px; padding: 24px; border: 1px solid #d9e2ec; border-radius: 16px; background: #fff; box-shadow: 0 10px 24px rgba(16, 42, 67, .04); }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.section-heading h2 { margin: 7px 0 0; font-size: 20px; }
.section-heading > div > p:last-child { margin: 7px 0 0; color: #627d98; line-height: 1.6; }
.agent-boundary { margin-bottom: 16px; }
.finding-workbench {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.finding-list {
  display: grid;
  gap: 10px;
  max-height: calc(100vh - 380px);
  min-height: 300px;
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-gutter: stable;
}
.finding-panel {
  max-height: calc(100vh - 380px);
  min-height: 300px;
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-gutter: stable;
}
.dependency-layout { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(300px, .9fr); gap: 16px; margin-top: 16px; }
@media (max-width: 900px) {
  .dependency-layout { grid-template-columns: 1fr; }
  .finding-workbench { grid-template-columns: 1fr; }
  .finding-list { max-height: 40vh; }
  .finding-panel { max-height: none; overflow: visible; }
}
@media (max-width: 760px) { .summary-grid { grid-template-columns: repeat(2, 1fr); }.detail-header { flex-direction: column; }.header-actions { justify-content: flex-start; }.workbench-section { padding: 16px; } }
</style>
