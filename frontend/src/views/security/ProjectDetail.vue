<template>
  <main class="detail-page">
    <header class="detail-header">
      <div>
        <el-button text :icon="ArrowLeft" @click="router.push('/security/projects')">返回项目中心</el-button>
        <p class="page-eyebrow">PROJECT SECURITY WORKBENCH</p>
        <h1>{{ project.name }}</h1>
        <p>仅展示脱敏证据；所有修复建议必须人工审核。</p>
      </div>
      <div class="header-actions">
        <el-button plain @click="router.push('/security/knowledge')">安全知识治理</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="alert" />

    <section class="summary-grid" aria-label="当前风险概要">
      <template v-if="loading || findingsLoading">
        <article v-for="index in 5" :key="index" class="summary-card summary-card--skeleton">
          <el-skeleton animated :rows="2" />
        </article>
      </template>
      <template v-else>
        <article class="summary-card"><span>扫描任务</span><strong>{{ tasks.length }}</strong></article>
        <article class="summary-card"><span>已完成</span><strong>{{ completedTaskCount }}</strong></article>
        <article class="summary-card"><span>风险发现</span><strong>{{ findings.length }}</strong></article>
        <article class="summary-card"><span>高危及以上</span><strong class="risk-number">{{ highRiskCount }}</strong></article>
        <article class="summary-card">
          <span>平均风险分</span>
          <strong :class="{ 'risk-number': avgRiskScore >= 60 }">{{ avgRiskScore !== null ? avgRiskScore.toFixed(1) : '-' }}</strong>
        </article>
      </template>
    </section>

    <ScanTaskTable :tasks="tasks" :loading="loading" :selected-task-id="selectedTaskId" :action-loading="taskActionLoading" @select-task="loadFindings" @cancel-task="handleCancelTask" @retry-task="handleRetryTask" />

    <section class="workbench-section content-card">
      <div class="section-heading">
        <div>
          <p class="section-eyebrow">FINDINGS AND CONTEXTUAL AI</p>
          <h2>风险发现与 AI 修复建议</h2>
          <p>{{ selectedTaskId ? `任务 #${selectedTaskId} 的证据化发现项，建议必须人工审核。` : '选择一条扫描任务查看发现项。' }}</p>
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
      <div v-if="findingsLoading" class="finding-workbench" aria-label="风险发现加载中">
        <div class="finding-list finding-list--skeleton">
          <el-skeleton v-for="index in 4" :key="index" :rows="3" animated />
        </div>
        <div class="finding-panel finding-panel--skeleton">
          <el-skeleton :rows="8" animated />
        </div>
      </div>
      <el-empty v-else-if="!selectedTaskId" description="请选择扫描任务" />
      <el-empty v-else-if="findings.length === 0" description="该任务未发现可展示的风险。" />
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
          <p>依赖库存和风险严格以当前选中扫描任务的快照为范围。</p>
        </div>
        <div class="dependency-heading-actions">
          <el-tag v-if="selectedTask" effect="plain">快照 #{{ selectedTask.snapshot_id }}</el-tag>
          <el-button size="small" text type="primary" :icon="dependenciesExpanded ? ArrowUp : ArrowDown" @click="dependenciesExpanded = !dependenciesExpanded">
            {{ dependenciesExpanded ? '收起' : '展开' }}
          </el-button>
        </div>
      </div>

      <el-collapse-transition>
        <div v-show="dependenciesExpanded">
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
        </div>
      </el-collapse-transition>
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
import { ArrowDown, ArrowLeft, ArrowUp, Refresh } from '@element-plus/icons-vue'
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
const dependenciesExpanded = ref(false)
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
  findingsLoading,
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
.detail-page { min-height: 100vh; padding: 24px clamp(20px, 4vw, 64px); background: #f6f8fb; color: #102a43; }
.detail-header, .summary-grid, .content-card, .dependency-section, .alert { max-width: 1200px; margin-left: auto; margin-right: auto; }
.detail-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 18px;
  padding: 12px 14px 12px;
  margin-left: auto;
  margin-right: auto;
  margin-top: -12px;
  background: rgba(246, 248, 251, .92);
  backdrop-filter: blur(8px);
  border-radius: 12px;
}
.detail-header h1 { margin: 6px 0 0; font-size: clamp(24px, 4vw, 36px); letter-spacing: -.025em; }
.detail-header > div > p:last-child { max-width: 720px; margin: 8px 0 0; color: #486581; line-height: 1.65; }
.page-eyebrow, .section-eyebrow { margin: 12px 0 0; color: #0e9384; font-size: 11px; font-weight: 700; letter-spacing: .1em; }
.header-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.alert { margin-bottom: 16px; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 18px; }
.summary-card { padding: 14px 18px; border: 1px solid #d9e2ec; border-radius: 12px; background: #fff; box-shadow: 0 8px 20px rgba(16, 42, 67, .04); }
.summary-card--skeleton { padding: 18px; }
.summary-card span { display: block; color: #627d98; font-size: 12px; }
.summary-card strong { display: block; margin-top: 4px; color: #102a43; font-size: 24px; }
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
.finding-list--skeleton,
.finding-panel--skeleton { align-content: start; }
.finding-list--skeleton { gap: 12px; }
.finding-panel--skeleton { padding: 24px; background: #fff; border: 1px solid #d9e2ec; border-radius: 14px; }
.finding-list::-webkit-scrollbar,
.finding-panel::-webkit-scrollbar { width: 6px; }
.finding-list::-webkit-scrollbar-thumb,
.finding-panel::-webkit-scrollbar-thumb { background: #c8d4de; border-radius: 3px; }
.finding-list::-webkit-scrollbar-thumb:hover,
.finding-panel::-webkit-scrollbar-thumb:hover { background: #9fb3c8; }
.finding-list::-webkit-scrollbar-track,
.finding-panel::-webkit-scrollbar-track { background: transparent; }
.finding-list,
.finding-panel { scrollbar-width: thin; scrollbar-color: #c8d4de transparent; }
.dependency-heading-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.dependency-layout { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(300px, .9fr); gap: 16px; margin-top: 16px; }
@media (max-width: 900px) {
  .dependency-layout { grid-template-columns: 1fr; }
  .finding-workbench { grid-template-columns: 1fr; }
  .finding-list { max-height: 40vh; }
  .finding-panel { max-height: none; overflow: visible; }
}
@media (max-width: 760px) { .summary-grid { grid-template-columns: repeat(2, 1fr); }.detail-header { flex-direction: column; }.header-actions { justify-content: flex-start; }.workbench-section { padding: 16px; } }</style>
