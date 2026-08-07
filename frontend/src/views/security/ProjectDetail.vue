<template>
  <main class="detail-page">
    <header class="topbar">
      <nav class="breadcrumbs" aria-label="项目位置">
        <el-button text :icon="ArrowLeft" class="breadcrumb-link" @click="router.push('/security/projects')">项目总览</el-button>
        <el-icon class="breadcrumb-separator"><ArrowRight /></el-icon>
        <span>项目详情</span>
        <el-icon class="breadcrumb-separator"><ArrowRight /></el-icon>
        <strong>项目 #{{ route.params.id }}</strong>
      </nav>
      <div class="actions">
        <el-button plain :icon="Promotion" @click="router.push(`/security/projects/${route.params.id}/agent`)">Agent 工作台</el-button>
        <el-button plain @click="router.push('/security/knowledge')">安全知识库</el-button>
        <el-button type="primary" :icon="Refresh" :loading="rescanLoading" @click="handleRescan">重新扫描</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="alert" />

    <div class="detail-layout">
      <div class="detail-main">
        <ProjectOverviewHeader
          :project="project"
          :scan-state="scanState"
          :selected-task="selectedTask"
          :language-label="languageLabel"
          :recent-task-label="recentTaskLabel"
          :avg-risk-score="avgRiskScore"
        />

        <ProjectMetricGrid
          :loading="loading"
          :findings-loading="findingsLoading"
          :avg-risk-score="avgRiskScore"
          :high-risk-count="highRiskCount"
          :findings-total="findingsTotal"
          :suggestion-stats="suggestionStats"
          :task-count="tasks.length"
        />

        <ScanTaskTable
          :tasks="tasks"
          :loading="loading"
          :selected-task-id="selectedTaskId"
          :action-loading="taskActionLoading"
          @select-task="loadFindings"
          @cancel-task="handleCancelTask"
          @retry-task="handleRetryTask"
          @delete-task="handleDeleteTask"
        />

        <SnapshotPanel
          :snapshots="snapshots"
          :loading="snapshotsLoading"
          :action-loading="snapshotActionLoading"
          @delete-snapshot="handleDeleteSnapshot"
        />

        <section class="card">
          <div class="card-head">
            <h2>风险发现</h2>
            <div class="card-head__side">
              <span class="note">{{ selectedTaskId ? '任务 #' + selectedTaskId + ' 的风险发现' : '选择一条扫描任务查看发现项' }}</span>
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
            修复建议仅供人工审核，系统不会自动执行、应用、提交或推送代码。
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
                :deleting-suggestion-id="deletingSuggestionId"
                @generate="handleGenerateSuggestion"
                @load-suggestions="loadSuggestions"
                @load-more-suggestions="loadMoreSuggestions"
                @copy-patch="copyPatch"
                @review="openReviewDialog"
                @remove="handleRemoveSuggestion"
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
      </div>

      <aside class="detail-side" aria-label="项目设置">
        <ExclusionRulesPanel
          :project-id="route.params.id"
          :can-edit="true"
          :rescan-loading="rescanLoading"
          @rescan="handleRescan"
        />
      </aside>
    </div>

    <p class="foot-note">修复建议须人工审核，系统不会自动执行、应用、提交或推送代码。</p>

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
import { ElMessage, ElMessageBox } from '@/features/security/feedback'
import { ArrowLeft, ArrowRight, Promotion, Refresh } from '@element-plus/icons-vue'
import DependencyInventoryTable from '@/components/security/dependencies/DependencyInventoryTable.vue'
import ScaFindingList from '@/components/security/dependencies/ScaFindingList.vue'
import ScaScanStatusCard from '@/components/security/dependencies/ScaScanStatusCard.vue'
import ExclusionRulesPanel from '@/components/security/project/ExclusionRulesPanel.vue'
import FindingDetailPanel from '@/components/security/project/FindingDetailPanel.vue'
import FindingListItem from '@/components/security/project/FindingListItem.vue'
import ProjectMetricGrid from '@/components/security/project/ProjectMetricGrid.vue'
import ProjectOverviewHeader from '@/components/security/project/ProjectOverviewHeader.vue'
import RemediationReviewDialog from '@/components/security/project/RemediationReviewDialog.vue'
import ScanTaskTable from '@/components/security/project/ScanTaskTable.vue'
import SnapshotPanel from '@/components/security/project/SnapshotPanel.vue'
import { useProjectDependencies } from '@/composables/security/useProjectDependencies'
import { useProjectScanTasks } from '@/composables/security/useProjectScanTasks'
import { useProjectSnapshots } from '@/composables/security/useProjectSnapshots'
import { useRemediationSuggestions } from '@/composables/security/useRemediationSuggestions'
import { formatSecurityDate, securityApiErrorMessage } from '@/features/security/presentation'

const route = useRoute()
const router = useRouter()
const project = { id: Number(route.params.id), name: `项目 #${route.params.id}` }
const reviewDialogVisible = ref(false)
const reviewSubmitting = ref(false)
const selectedSuggestion = ref(null)
const selectedFindingId = ref(null)
const deletingSuggestionId = ref(null)
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
  reviewSuggestion,
  removeSuggestion
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
  deleteTask,
  rescan,
  rescanLoading,
  stopPolling
} = useProjectScanTasks(() => route.params.id)
const {
  loading: snapshotsLoading,
  snapshots,
  actionLoading: snapshotActionLoading,
  load: loadSnapshots,
  remove: removeSnapshot
} = useProjectSnapshots(() => route.params.id)
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
const recentTaskLabel = computed(() => (
  selectedTask.value ? formatSecurityDate(selectedTask.value.created_at) : ''
))
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
const handleDeleteTask = async (task) => {
  try {
    await ElMessageBox.confirm(
      `确定删除任务 #${task.id} 吗？其风险发现、证据与修复建议将一并删除，且无法恢复。`,
      '删除扫描任务',
      { type: 'warning', confirmButtonText: '删除' }
    )
    if (await deleteTask(task.id)) ElMessage.success('扫描任务已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(securityApiErrorMessage(error, '删除扫描任务失败'))
    }
  }
}

const handleDeleteSnapshot = async (snapshot) => {
  try {
    await ElMessageBox.confirm(
      `确定删除快照 #${snapshot.id} 吗？其全部扫描任务、风险发现与磁盘代码目录将一并删除，且无法恢复。`,
      '删除项目快照',
      { type: 'warning', confirmButtonText: '删除' }
    )
    if (await removeSnapshot(snapshot)) ElMessage.success('项目快照已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(securityApiErrorMessage(error, '删除项目快照失败'))
    }
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

const handleRemoveSuggestion = async (suggestion) => {
  try {
    await ElMessageBox.confirm(
      `确定删除建议 #${suggestion.id} 吗？删除后无法恢复。`,
      '删除修复建议',
      { type: 'warning', confirmButtonText: '删除' }
    )
    deletingSuggestionId.value = suggestion.id
    await removeSuggestion(suggestion)
    ElMessage.success('修复建议已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(securityApiErrorMessage(error, '删除修复建议失败'))
    }
  } finally {
    deletingSuggestionId.value = null
  }
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

onMounted(() => {
  load()
  loadSnapshots()
})
onBeforeUnmount(stopPolling)
</script>

<style scoped lang="scss">
.detail-page {
  min-height: 100vh;
  padding: 20px 24px 40px;
  color: #142238;
  background: #f7f8fa;
  font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}

.detail-page :deep(.el-button),
.detail-page :deep(.el-table),
.detail-page :deep(.el-tag),
.detail-page :deep(.el-radio-button__inner),
.detail-page :deep(.el-input__inner) {
  font-family: inherit;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  max-width: 1540px;
  margin: 0 auto 14px;
  padding: 4px 0 12px;
  background: rgba(247, 248, 250, 0.96);
  backdrop-filter: blur(8px);
}

.breadcrumbs {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  color: #7e8da3;
  font-size: 12px;
}

.breadcrumb-link {
  flex: 0 0 auto;
  padding-left: 0;
  color: #52627a;
  font-size: 13px;
  font-weight: 600;
}

.breadcrumb-link:hover {
  color: #2563eb;
}

.breadcrumb-separator {
  flex: 0 0 auto;
  color: #a9b6c7;
  font-size: 13px;
}

.breadcrumbs > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.breadcrumbs > strong {
  overflow: hidden;
  color: #142238;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.actions :deep(.el-button) {
  border-color: #dce4ee;
  color: #52627a;
  background: #ffffff;
  transition: border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.actions :deep(.el-button:hover) {
  border-color: #a9c5fa;
  color: #2563eb;
  box-shadow: 0 5px 13px rgba(37, 99, 235, 0.08);
  transform: translateY(-1px);
}

.detail-page :deep(.el-button--primary) {
  border-color: #2563eb;
  color: #ffffff;
  background: #2563eb;
}

.detail-page :deep(.el-button--primary:hover),
.detail-page :deep(.el-button--primary:focus) {
  border-color: #1d4ed8;
  color: #ffffff;
  background: #1d4ed8;
}

.alert {
  max-width: 1540px;
  margin: 0 auto 14px;
}

.detail-layout {
  display: grid;
  max-width: 1540px;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 14px;
  align-items: start;
  margin: 0 auto;
}

.detail-main {
  min-width: 0;
}

.detail-side {
  position: sticky;
  top: 83px;
  min-width: 0;
}

.card {
  margin-top: 14px;
  padding: 17px 18px;
  overflow: hidden;
  border: 1px solid #dfe6ef;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 3px 12px rgba(21, 40, 75, 0.04);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.card:hover {
  border-color: #c4d3e4;
  box-shadow: 0 10px 22px rgba(21, 40, 75, 0.08);
  transform: translateY(-1px);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.card-head h2 {
  margin: 0;
  color: #142238;
  font-size: 14px;
  font-weight: 700;
}

.card-head__side {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.card-head__side .note {
  color: #7e8da3;
  font-size: 11px;
}

.findings-sort :deep(.el-radio-button__inner) {
  padding: 5px 10px;
  border-color: #dce4ee;
  color: #52627a;
  background: #ffffff;
  font-size: 11px;
}

.findings-sort :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  border-color: #2563eb;
  color: #ffffff;
  background: #2563eb;
  box-shadow: -1px 0 0 0 #2563eb;
}

.notice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
  padding: 9px 11px;
  border: 1px solid #f0d39b;
  border-radius: 7px;
  color: #866221;
  background: #fff7e8;
  font-size: 11.5px;
  line-height: 1.6;
}

.workbench {
  display: grid;
  grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.finding-list {
  display: flex;
  min-height: 200px;
  max-height: 560px;
  flex-direction: column;
  gap: 7px;
  overflow-y: auto;
  padding-right: 4px;
}

.finding-list--skeleton,
.panel--skeleton {
  align-content: start;
}

.load-more {
  display: block;
  width: 100%;
  margin-top: 2px;
  padding: 8px 0;
  border: 1px dashed #c2ccd9;
  border-radius: 7px;
  color: #52627a;
  background: #fbfcfe;
  font-size: 11.5px;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.load-more:hover:not(:disabled) {
  border-color: #2563eb;
  color: #2563eb;
  box-shadow: 0 5px 12px rgba(37, 99, 235, 0.07);
}

.load-more:disabled {
  cursor: default;
  opacity: 0.6;
}

.finding-list::-webkit-scrollbar,
.panel :deep(.finding-detail-panel)::-webkit-scrollbar {
  width: 6px;
}

.finding-list::-webkit-scrollbar-thumb,
.panel :deep(.finding-detail-panel)::-webkit-scrollbar-thumb {
  border-radius: 3px;
  background: #ccd5e0;
}

.finding-list::-webkit-scrollbar-track,
.panel :deep(.finding-detail-panel)::-webkit-scrollbar-track {
  background: transparent;
}

.panel {
  overflow: hidden;
  border: 1px solid #dfe6ef;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 3px 12px rgba(21, 40, 75, 0.04);
}

.panel--skeleton {
  padding: 14px;
}

.dep-toggle {
  padding: 0;
  border: 0;
  color: #2563eb;
  background: none;
  font-size: 12px;
  cursor: pointer;
}

.dep-body {
  padding-top: 2px;
}

.dep-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(300px, 0.9fr);
  gap: 11px;
  margin-top: 11px;
}

.mini-card {
  padding: 12px;
  border: 1px solid #dfe6ef;
  border-radius: 8px;
  background: #ffffff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.mini-card:hover {
  border-color: #c4d3e4;
  box-shadow: 0 7px 16px rgba(21, 40, 75, 0.06);
}

.mini-card h3 {
  margin: 0 0 8px;
  color: #142238;
  font-size: 12.5px;
  font-weight: 700;
}

.foot-note {
  max-width: 1540px;
  margin: 16px auto 0;
  color: #7e8da3;
  font-size: 11px;
  text-align: center;
}

@media (max-width: 1100px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }

  .detail-side {
    position: static;
  }
}

@media (max-width: 960px) {
  .workbench,
  .dep-layout {
    grid-template-columns: 1fr;
  }

  .finding-list {
    max-height: 40vh;
  }
}

@media (max-width: 760px) {
  .detail-page {
    padding: 14px 12px 28px;
  }

  .topbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 9px;
    padding-bottom: 10px;
  }

  .actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .actions :deep(.el-button) {
    flex: 1 1 calc(50% - 4px);
    margin-left: 0;
  }

  .card-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .card-head__side {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
