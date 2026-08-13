<template>
  <div class="agent-chat-page">
    <header class="ac-head">
      <el-button text :icon="ArrowLeft" @click="goBack">返回</el-button>
      <div class="ac-head__title">
        <span v-if="mode === 'conversation'">{{ conversationTitle }}</span>
        <span v-else>Agent 任务 #{{ runId }}</span>
        <el-tag v-if="store.run" :type="statusMeta.tagType" size="small">{{ statusMeta.label }}</el-tag>
      </div>
      <div class="ac-head__actions">
        <el-button size="small" :loading="actionLoading.pause" :disabled="!store.canPause" @click="handlePause">暂停</el-button>
        <el-button size="small" type="primary" plain :loading="actionLoading.resume" :disabled="!store.canResume" @click="handleResume">恢复</el-button>
        <el-button size="small" type="danger" plain :loading="actionLoading.cancel" :disabled="!store.canCancel" @click="handleCancel">取消</el-button>
        <el-button size="small" :icon="Refresh" :loading="loading" @click="reload">刷新</el-button>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="ac-alert" />

    <div class="ac-layout">
      <main class="ac-main">
        <div ref="threadRef" class="ac-thread">
          <div v-if="loading && !store.run && !conversationMeta" class="ac-skeleton">
            <el-skeleton :rows="6" animated />
          </div>
          <div v-else class="ac-thread-inner">
            <div v-if="mode === 'conversation' && turns.length > 1" class="turn-timeline">
              <span class="turn-timeline__label">Turn 时间线：</span>
              <button
                v-for="turn in turns"
                :key="turn.id"
                class="turn-chip"
                :class="{ 'turn-chip--active': currentRunId === turn.run_id }"
                @click="jumpToTurn(turn)"
              >
                Turn {{ turn.turn_sequence }}
              </button>
            </div>
            <AgentThread
              :user-messages="userMessages"
              :events="store.events"
              :tool-calls="store.toolCalls"
              :reasoning-stream="store.reasoningStream"
              :reasoning-live="store.reasoningLive"
              :reasoning-sensitive-level="store.reasoningSensitiveLevel || 'internal'"
              :llm-analysis="store.llmAnalysis"
              :run="store.run"
              :running="!store.isTerminal && !!store.run"
              :fallback-text="agentFallbackText"
              :fallback-detail="agentFallbackDetail"
              :total-tokens="agentTotalTokens"
            />
          </div>
        </div>

        <ChatComposer
          :disabled="sendingMessage"
          :placeholder="composerPlaceholder"
          @send="handleSendMessage"
        />
        <p class="ac-legal">每条消息创建一个新 Turn 并复用当前快照；Agent 的思考过程与工具调用会实时显示在对话中。</p>
      </main>

      <aside class="ac-side">
        <AgentConnectionStatus
          :connection-state="store.connectionState"
          :last-sequence="store.lastSequence"
          :state-version="store.stateVersion"
          :reasoning-live="store.reasoningLive"
        />
        <AgentPlannerPanel
          :plan="store.plan"
          :fallback-reason="planFallbackReason"
          :loading="loading"
        />
        <AgentProgressCard
          :plan="store.plan"
          :run="store.run"
          :steps="store.steps"
          :tool-calls="store.toolCalls"
          :loading="loading"
        />
        <AgentDecisionTimeline
          :decisions="store.decisions"
          :replan-count="store.run?.replan_count || 0"
          :loading="loading"
        />
        <AgentApprovalQueue
          :items="approvals"
          :loading="approvalsLoading"
          @resolve="resolveApproval"
        />
        <AgentProviderSelector :workspace-id="store.run?.workspace_id || null" />
        <BasePanel
          title="统一时间线"
          subtitle="按事件 sequence 顺序（v2）"
          class="ac-timeline-panel"
        >
          <AgentTimeline
            :items="store.timelineItems"
            :loading="loading"
          />
        </BasePanel>

        <el-collapse v-model="moreOpen" class="ac-more">
          <el-collapse-item name="more" title="更多数据">
            <div class="ac-more__stack">
              <AgentPlanVersionSelector
                :plans="planVersions"
                :current-version="store.run?.plan_version || 0"
                :loading="loading"
                @select="selectPlanVersion"
              />
              <AgentProviderBadge :provider="lastProvider" />
              <AgentPlanGraph :plan="store.plan" :loading="loading" />
              <AgentFindingSummary :metrics="baselineMetrics" :loading="loading" />
              <ProjectSecurityGraph
                :run-id="currentRunId || runId"
                @select-node="selectGraphNode"
                @error="handleGraphError"
              />
              <SecurityGraphNodeDetail
                :node="selectedGraphNode"
                :run-id="currentRunId || runId"
                @show-code="openCodeEvidence"
              />
              <CallChainPanel :run-id="currentRunId || runId" />
              <AgentCoverageOverview
                :summary="coverageSummary"
                :loading="coverageLoading"
                :active-kind="coverageActiveKind"
                @select-kind="selectCoverageKind"
              />
              <AgentCoverageFileTable
                v-if="coverageSummary"
                :files="coverageFiles"
                :total="coverageTotal"
                :loading="coverageLoading"
                :has-more="coverageHasMore"
                @load-more="loadMoreCoverage"
              />
              <AgentCostPanel :summary="costSummary" :invocations="invocations" :loading="costsLoading" />
              <AgentObservationList
                :items="observations"
                :total="observationTotal"
                :loading="observationsLoading"
                @select="openObservation"
              />
              <AgentEventList :events="store.events" />
            </div>
          </el-collapse-item>
        </el-collapse>
      </aside>
    </div>

    <AgentObservationDetail
      :visible="observationVisible"
      :observation="selectedObservation"
      :loading="observationDetailLoading"
      :reviewing="observationReviewing"
      :generating-diff="diffGenerating"
      @close="closeObservation"
      @review="reviewObservation"
      @generate-diff="generateDiff"
    />

    <CodeEvidenceViewer
      :visible="codeVisible"
      :slice="codeSlice"
      @close="closeCodeEvidence"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from '@/features/security/feedback'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import AgentThread from '@/components/security/agent/thread/AgentThread.vue'
import AgentApprovalQueue from '@/components/security/agent/AgentApprovalQueue.vue'
import AgentConnectionStatus from '@/components/security/agent/AgentConnectionStatus.vue'
import AgentCostPanel from '@/components/security/agent/AgentCostPanel.vue'
import AgentCoverageFileTable from '@/components/security/agent/AgentCoverageFileTable.vue'
import AgentCoverageOverview from '@/components/security/agent/AgentCoverageOverview.vue'
import AgentDecisionTimeline from '@/components/security/agent/AgentDecisionTimeline.vue'
import AgentEventList from '@/components/security/agent/AgentEventList.vue'
import AgentFindingSummary from '@/components/security/agent/AgentFindingSummary.vue'
import AgentObservationDetail from '@/components/security/agent/AgentObservationDetail.vue'
import AgentObservationList from '@/components/security/agent/AgentObservationList.vue'
import AgentPlanGraph from '@/components/security/agent/AgentPlanGraph.vue'
import AgentPlanVersionSelector from '@/components/security/agent/AgentPlanVersionSelector.vue'
import AgentPlannerPanel from '@/components/security/agent/AgentPlannerPanel.vue'
import AgentProviderSelector from '@/components/security/agent/AgentProviderSelector.vue'
import AgentProgressCard from '@/components/security/agent/AgentProgressCard.vue'
import AgentProviderBadge from '@/components/security/agent/AgentProviderBadge.vue'
import AgentTimeline from '@/components/security/agent/timeline/AgentTimeline.vue'
import { BasePanel } from '@/components/ui'
import CallChainPanel from '@/components/security/agent/CallChainPanel.vue'
import CodeEvidenceViewer from '@/components/security/agent/CodeEvidenceViewer.vue'
import ProjectSecurityGraph from '@/components/security/agent/ProjectSecurityGraph.vue'
import SecurityGraphNodeDetail from '@/components/security/agent/SecurityGraphNodeDetail.vue'
import { agentAPI } from '@/api'
import { useAgentCosts } from '@/composables/security/useAgentCosts'
import { useAgentCoverage } from '@/composables/security/useAgentCoverage'
import { useAgentRun } from '@/composables/security/useAgentRun'
import { agentStatusMeta } from '@/features/security/agent/statusMeta'
import { formatSecurityDate, securityApiErrorMessage } from '@/features/security/presentation'

const route = useRoute()
const router = useRouter()
const { store, loading, errorMessage, actionLoading, loadRun, pauseRun, resumeRun, cancelRun } = useAgentRun()
const currentRunId = ref(null)
const {
  loading: coverageLoading,
  summary: coverageSummary,
  files: coverageFiles,
  total: coverageTotal,
  activeKind: coverageActiveKind,
  loadCoverage,
  loadMore: loadMoreCoverage,
  hasMore: coverageHasMore
} = useAgentCoverage(() => currentRunId.value)
const {
  loading: costsLoading,
  summary: costSummary,
  invocations,
  loadCosts
} = useAgentCosts(() => currentRunId.value)
const sendingMessage = ref(false)
const threadRef = ref(null)
const conversationMeta = ref(null)
const conversationMessages = ref([])
const turns = ref([])
const turnRuns = ref({})
const planVersions = ref([])
const observations = ref([])
const observationTotal = ref(0)
const observationsLoading = ref(false)
const selectedObservation = ref(null)
const observationDetailLoading = ref(false)
const observationVisible = ref(false)
const observationReviewing = ref(false)
const diffGenerating = ref(false)
const approvals = ref([])
const approvalsLoading = ref(false)
const selectedGraphNode = ref(null)
const codeVisible = ref(false)
const codeSlice = ref(null)
const moreOpen = ref([])

function selectGraphNode(node) {
  selectedGraphNode.value = node
}

function handleGraphError(message) {
  if (message) ElMessage.error(message)
}

function openCodeEvidence(slice) {
  codeSlice.value = slice
  codeVisible.value = true
}

function closeCodeEvidence() {
  codeVisible.value = false
  codeSlice.value = null
}

async function loadPlanVersions(runIdValue) {
  if (!runIdValue) return
  try {
    const response = await agentAPI.getRunPlans(runIdValue)
    planVersions.value = response.items || []
  } catch (error) {
    planVersions.value = []
  }
}

async function loadObservations(runIdValue) {
  if (!runIdValue) return
  observationsLoading.value = true
  try {
    const response = await agentAPI.getObservations(runIdValue, {
      page: 1,
      page_size: 20
    })
    observations.value = response.items || []
    observationTotal.value = response.total || 0
  } catch (error) {
    observations.value = []
    observationTotal.value = 0
  } finally {
    observationsLoading.value = false
  }
}

async function openObservation(item) {
  if (!item || !currentRunId.value) return
  observationVisible.value = true
  observationDetailLoading.value = true
  selectedObservation.value = item
  try {
    const response = await agentAPI.getObservation(currentRunId.value, item.id)
    selectedObservation.value = response.observation
  } catch (error) {
    selectedObservation.value = item
  } finally {
    observationDetailLoading.value = false
  }
}

function closeObservation() {
  observationVisible.value = false
  selectedObservation.value = null
}

async function loadApprovals(runIdValue) {
  if (!runIdValue) return
  approvalsLoading.value = true
  try {
    const response = await agentAPI.getRunApprovals(runIdValue)
    approvals.value = response.items || []
  } catch (error) {
    approvals.value = []
  } finally {
    approvalsLoading.value = false
  }
}

async function resolveApproval(item, decision, comment) {
  const targetId = currentRunId.value || runId.value
  try {
    const response = await agentAPI.resolveApproval(targetId, item.id, {
      decision,
      comment
    })
    ElMessage.success(decision === 'approved' ? '已批准，任务继续执行' : '已拒绝')
    loadApprovals(targetId)
    if (decision === 'approved') {
      loadRun(targetId)
    }
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '审批操作失败'))
  }
}

async function reviewObservation(item, decision, comment) {
  const targetId = currentRunId.value || runId.value
  observationReviewing.value = true
  try {
    const response = await agentAPI.reviewObservation(targetId, item.id, {
      decision,
      comment
    })
    selectedObservation.value = response.observation
    loadObservations(targetId)
    ElMessage.success('审核已记录')
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '审核失败'))
  } finally {
    observationReviewing.value = false
  }
}

async function generateDiff(item) {
  const targetId = currentRunId.value || runId.value
  diffGenerating.value = true
  try {
    const response = await agentAPI.generateRemediationDiff(targetId, item.id)
    const detail = await agentAPI.getObservation(targetId, item.id)
    selectedObservation.value = detail.observation
    ElMessage.success(`修复 Diff 已生成（${response.file_paths?.length || 0} 个文件）`)
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '生成修复 Diff 失败'))
  } finally {
    diffGenerating.value = false
  }
}

function selectPlanVersion(version) {
  const plan = planVersions.value.find((item) => item.plan_version === version)
  if (!plan) return
  ElMessage.info(
    `v${plan.plan_version}：${plan.nodes.length} 节点，` +
      (plan.decision_summary ? plan.decision_summary.slice(0, 60) : '')
  )
}

const runId = computed(() => Number(route.params.runId))
const conversationId = computed(() => Number(route.params.conversationId))
const mode = computed(() => (conversationId.value ? 'conversation' : 'run'))

const statusMeta = computed(() => agentStatusMeta(store.run?.status))

const lastProvider = computed(() => {
  if (store.lastProvider) return store.lastProvider
  const latest = invocations.value?.[0]
  if (latest?.provider_name) {
    return { provider: latest.provider_name, model: latest.model || null }
  }
  return null
})

const conversationTitle = computed(() => {
  if (!conversationMeta.value) return `Agent 会话 #${conversationId.value}`
  return conversationMeta.value.title || `Agent 会话 #${conversationId.value}`
})

const baselineMetrics = computed(() => {
  if (store.scanSummary) return store.scanSummary
  const call = store.toolCalls.find((item) => item.tool_name === 'run_baseline_scan')
  return call?.metrics || null
})

const planFallbackReason = computed(() => {
  const latest = [...store.events]
    .reverse()
    .find((event) => event.event_type === 'plan.created')
  return latest?.payload?.fallback_reason || ''
})

const composerPlaceholder = computed(() => {
  if (!store.run && !conversationMeta.value) return '输入安全审计目标'
  if (store.isTerminal || !store.run) return '继续输入目标，创建新 Turn，Agent 将执行 LLM 分析并回复'
  return 'Agent 执行中…可输入补充指令'
})

// ------------------------------------------------------------------ conversation

const userMessages = computed(() => {
  const items = []
  if (mode.value === 'conversation') {
    for (const turn of turns.value) {
      const message = conversationMessages.value.find(
        (item) => item.id === turn.input_message_id
      )
      if (message) {
        items.push({
          key: `conv-msg-${message.id}`,
          text: message.content,
          time: formatSecurityDate(message.created_at)
        })
      }
    }
    return items
  }
  for (const message of store.messages || []) {
    if (message.role === 'user') {
      items.push({
        key: `msg-${message.id}`,
        text: message.content,
        time: formatSecurityDate(message.created_at)
      })
    }
  }
  return items
})

const agentFallbackText = computed(() => {
  const run = store.run || {}
  if (!run.id) return ''
  const status = agentStatusMeta(run.status).label
  const findings = store.scanSummary?.findings_count ?? 0
  return `执行完成（${status}）：基线扫描产出 ${findings} 个发现。`
})

const agentFallbackDetail = computed(() => {
  const items = []
  const scanSummary = store.scanSummary
  if (scanSummary) {
    items.push({ kind: 'task', text: scanSummary.task_id })
    const counts = scanSummary.severity_counts || {}
    items.push({ kind: 'severity', counts })
    if (scanSummary.languages?.length) {
      items.push({ kind: 'languages', text: scanSummary.languages.join(', ') })
    }
  }
  return items
})

const agentTotalTokens = computed(() => {
  return (invocations.value || []).reduce((sum, item) => {
    return sum + (Number(item.total_tokens) || 0)
  }, 0)
})

let conversationLoadSequence = 0

async function loadConversation(conversationIdValue) {
  const sequence = ++conversationLoadSequence
  errorMessage.value = ''
  try {
    const [metaResponse, messagesResponse] = await Promise.all([
      agentAPI.getConversation(conversationIdValue),
      agentAPI.getConversationMessages(conversationIdValue, { page: 1, page_size: 50 })
    ])
    if (sequence !== conversationLoadSequence) return
    conversationMeta.value = metaResponse.conversation || null
    turns.value = metaResponse.conversation?.turns || []
    conversationMessages.value = messagesResponse.items || []

    const runTurns = turns.value.filter((turn) => turn.run_id)
    const payloads = await Promise.all(
      runTurns.map((turn) => agentAPI.getRun(turn.run_id).catch(() => null))
    )
    if (sequence !== conversationLoadSequence) return
    const nextRuns = {}
    runTurns.forEach((turn, index) => {
      if (payloads[index]) nextRuns[turn.run_id] = payloads[index]
    })
    turnRuns.value = nextRuns

    const latestRunTurn = runTurns[runTurns.length - 1]
    if (latestRunTurn?.run_id) {
      currentRunId.value = latestRunTurn.run_id
      loadRun(latestRunTurn.run_id)
      loadPlanVersions(latestRunTurn.run_id)
      loadObservations(latestRunTurn.run_id)
      loadApprovals(latestRunTurn.run_id)
    } else {
      currentRunId.value = null
    }
    await nextTickScroll()
  } catch (error) {
    if (sequence !== conversationLoadSequence) return
    errorMessage.value = securityApiErrorMessage(error, '加载会话失败。')
  }
}

async function handleSendMessage({ text }) {
  const content = (text || '').trim()
  if (!content || sendingMessage.value) return
  sendingMessage.value = true
  try {
    if (mode.value === 'conversation') {
      const clientMessageId = generateClientMessageId()
      const response = await agentAPI.postConversationMessage(conversationId.value, {
        content,
        client_message_id: clientMessageId
      })
      if (response.run) {
        await loadConversation(conversationId.value)
      }
    } else if (runId.value) {
      const response = await agentAPI.sendMessage(
        runId.value,
        content,
        generateClientMessageId()
      )
      await loadRun(runId.value)
      await loadPlanVersions(runId.value)
      if (response.message && !store.messages.some((item) => item.id === response.message.id)) {
        store.messages = [...(store.messages || []), response.message]
      }
    }
    await nextTickScroll()
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '发送消息失败'))
  } finally {
    sendingMessage.value = false
  }
}

function generateClientMessageId() {
  const random = Math.random().toString(36).slice(2, 10)
  return `msg-${Date.now().toString(36)}-${random}`
}

function jumpToTurn(turn) {
  if (!turn.run_id) return
  currentRunId.value = turn.run_id
  loadRun(turn.run_id)
  loadPlanVersions(turn.run_id)
  loadObservations(turn.run_id)
  loadApprovals(turn.run_id)
  loadCoverage('')
  nextTickScroll()
}

async function nextTickScroll() {
  await nextTick()
  const el = threadRef.value
  if (!el) return
  const threshold = 120
  const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  if (isNearBottom) {
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }
}

// ------------------------------------------------------------------ run actions

async function handlePause() {
  if (await pauseRun(currentRunId.value || runId.value)) ElMessage.success('任务已暂停')
}

async function handleResume() {
  if (await resumeRun(currentRunId.value || runId.value)) ElMessage.success('任务已恢复')
}

async function handleCancel() {
  const targetId = currentRunId.value || runId.value
  try {
    await ElMessageBox.confirm('确认取消该 Agent 任务吗？已产生的证据与事件会保留。', '取消 Agent 任务', { type: 'warning' })
    if (await cancelRun(targetId)) ElMessage.success('任务已取消')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(securityApiErrorMessage(error, '取消任务失败'))
  }
}

function selectCoverageKind(kind) {
  loadCoverage(kind)
}

const reload = () => {
  if (mode.value === 'conversation') loadConversation(conversationId.value)
  else if (runId.value) loadRun(runId.value)
}

function goBack() {
  if (mode.value === 'conversation') {
    const projectId = conversationMeta.value?.project_id
    if (projectId) {
      router.push(`/security/projects/${projectId}/agent`)
    } else {
      router.push('/security/projects')
    }
  } else if (runId.value) {
    const projectId = store.run?.project_id
    if (projectId) {
      router.push(`/security/projects/${projectId}/agent`)
    } else {
      router.push('/security/agent')
    }
  } else {
    router.push('/security/agent')
  }
}

// 实时 SSE 数据到达时自动滚动到底部
watch(
  () => [
    store.reasoningStream,
    store.toolCalls.length,
    store.llmAnalysis,
    store.run?.status
  ],
  () => {
    nextTickScroll()
  }
)

watch(
  () => store.toolCalls.length,
  (length, previous) => {
    if (length <= previous) return
    const latest = store.toolCalls[store.toolCalls.length - 1]
    if (latest?.tool_name === 'run_deep_review' && latest.status === 'succeeded') {
      loadObservations(currentRunId.value || runId.value)
    }
  }
)

watch(conversationId, (id) => {
  if (id) loadConversation(id)
})

watch(runId, (id) => {
  if (id) {
    loadRun(id)
    loadPlanVersions(id)
    loadObservations(id)
    loadApprovals(id)
  }
})

watch(
  () => store.isTerminal,
  (terminal) => {
    if (terminal && currentRunId.value) {
      if (mode.value === 'conversation') {
        loadConversation(conversationId.value)
      }
      loadCoverage('')
      loadCosts()
      nextTickScroll()
    }
  }
)

onMounted(() => {
  if (mode.value === 'conversation') loadConversation(conversationId.value)
  else if (runId.value) {
    loadRun(runId.value)
    loadPlanVersions(runId.value)
    loadObservations(runId.value)
    loadApprovals(runId.value)
  }
})
</script>

<style scoped lang="scss">
.agent-chat-page {
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--chat-canvas);
  color: var(--chat-ink);
  font-family: var(--chat-font-family);
}

.ac-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #e2e7ee;
  flex: 0 0 auto;
}

.ac-head__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ac-head__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ac-alert {
  margin: 8px 16px 0;
  flex: 0 0 auto;
}

.ac-layout {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  min-height: 0;
  overflow: hidden;
}

.ac-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.ac-thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.ac-thread-inner {
  max-width: var(--chat-content-width);
  width: 100%;
  margin: 0 auto;
  padding: 12px 20px calc(8px * var(--chat-space-scale));
  flex: 1;
}

.ac-skeleton {
  padding: 20px;
}

.ac-legal {
  flex: 0 0 auto;
  text-align: center;
  color: var(--chat-hollow);
  font-size: 12px;
  padding: 0 20px 12px;
}

/* Turn 时间线 */
.turn-timeline {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 6px 10px;
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  background: var(--chat-canvas);
  font-size: 12px;
  color: var(--chat-hollow);
  margin-top: 10px;
}

.turn-timeline__label {
  font-weight: 600;
}

.turn-chip {
  border: 1px solid var(--chat-hairline-strong);
  background: var(--chat-canvas);
  color: var(--chat-muted);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
}

.turn-chip:hover {
  border-color: var(--chat-accent);
  color: var(--chat-accent);
}

.turn-chip--active {
  background: var(--chat-accent-soft);
  border-color: var(--chat-accent-border);
  color: var(--chat-accent);
  font-weight: 600;
}

/* 右侧面板 */
.ac-side {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 10px 24px;
  overflow-y: auto;
  min-height: 0;
  background: #f4f6f9;
  border-left: 1px solid #e2e7ee;
}

.ac-more {
  border: 0;
  background: #fff;
  border-radius: 8px;
  padding: 0 14px;
}

.ac-more :deep(.el-collapse-item__header) {
  border-bottom: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
  height: 44px;
}

.ac-more :deep(.el-collapse-item__wrap) {
  border-bottom: 0;
}

.ac-more__stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 12px;
}

@media (max-width: 960px) {
  .ac-layout {
    grid-template-columns: 1fr;
  }

  .ac-side {
    border-left: 0;
    border-top: 1px solid #e2e7ee;
  }
}

@media (max-width: 720px) {
  .ac-head__actions .el-button {
    display: none;
  }

  .ac-thread-inner {
    padding: 10px 12px;
  }
}
</style>
