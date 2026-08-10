<template>
  <div class="agent-page">
    <!-- ============ 项目选择入口（/security/agent） ============ -->
    <section v-if="mode === 'home'" class="agent-home">
      <AgentWorkbenchHeader
        :total-projects="projects.length"
        :running-count="runningProjectCount"
        :attention-count="attentionProjectCount"
        :loading="projectsLoading"
        @refresh="loadProjects"
        @create="focusSelectedProject"
      />
      <div v-if="projectsLoading" class="home-skeleton">
        <el-skeleton v-for="index in 3" :key="index" :rows="2" animated />
      </div>
      <el-empty v-else-if="projects.length === 0" description="还没有安全项目，请先创建项目并上传快照">
        <el-button type="primary" @click="router.push('/security/projects')">去创建项目</el-button>
      </el-empty>
      <template v-else>
        <AgentProjectFilters
          v-model:filter="projectFilter"
          v-model:search="projectSearch"
          v-model:language="projectLanguage"
          v-model:sort="projectSort"
          :projects="projects"
        />
        <div class="home-layout">
          <AgentProjectTable
            :projects="filteredProjects"
            :selected-project-id="selectedProject?.id"
            :loading="projectsLoading"
            @select="selectProject"
            @start="startAudit"
            @view="openProject"
          />
          <AgentProjectInspector
            ref="inspectorRef"
            :project="selectedProject"
            :submitting="creating"
            :conversations="conversations"
            :conversations-loading="conversationsLoading"
            @start="startAudit"
            @view="openProject"
            @open-conversation="openConversation"
          />
        </div>
      </template>
    </section>

    <!-- ============ 项目入口（/security/projects/:id/agent） ============ -->
    <section v-else-if="mode === 'project'" class="agent-project">
      <header class="project-head">
        <el-button text :icon="ArrowLeft" @click="goBack">返回</el-button>
        <div class="project-head__title">项目 #{{ projectId }} 的 Agent 工作台</div>
      </header>
      <div class="project-layout">
        <AgentGoalForm :submitting="creating" @create="handleCreate" />
        <div class="tip-card">
          <h3>运行说明</h3>
          <ul class="tip-list">
            <li class="tip-item">
              <span class="tip-item__icon tip-item__icon--blue">
                <BaseIcon name="refresh" :size="14" />
              </span>
              <span>每条消息都会创建一个新的 Turn，并复用项目快照执行（无需重复上传）。</span>
            </li>
            <li class="tip-item">
              <span class="tip-item__icon tip-item__icon--green">
                <BaseIcon name="activity" :size="14" />
              </span>
              <span>Agent 将真实执行：快照清点 → 基线扫描 → 覆盖分析 → 风险排序。</span>
            </li>
            <li class="tip-item">
              <span class="tip-item__icon tip-item__icon--yellow">
                <BaseIcon name="zap" :size="14" />
              </span>
              <span>多轮对话由 LLM 驱动：模型基于扫描证据实时推理并给出分析结论。</span>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- ============ 会话 / 任务视图（conversation 或 run 模式） ============ -->
    <section v-else class="agent-conversation">
      <header class="conv-head">
        <el-button text :icon="ArrowLeft" @click="goBack">返回</el-button>
        <div class="conv-head__title">
          <span v-if="mode === 'conversation'">{{ conversationTitle }}</span>
          <span v-else>Agent 任务 #{{ runId }}</span>
          <el-tag v-if="store.run" :type="statusMeta.tagType" size="small">{{ statusMeta.label }}</el-tag>
        </div>
        <div class="conv-head__actions">
          <el-button size="small" :loading="actionLoading.pause" :disabled="!store.canPause" @click="handlePause">暂停</el-button>
          <el-button size="small" type="primary" plain :loading="actionLoading.resume" :disabled="!store.canResume" @click="handleResume">恢复</el-button>
          <el-button size="small" type="danger" plain :loading="actionLoading.cancel" :disabled="!store.canCancel" @click="handleCancel">取消</el-button>
          <el-button size="small" :icon="Refresh" :loading="loading" @click="reload">刷新</el-button>
        </div>
      </header>

      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="conv-alert" />

      <div class="conv-layout">
        <!-- 对话流 -->
        <main class="conv-main">
          <div v-if="loading && !store.run && !conversationMeta" class="conv-skeleton">
            <el-skeleton :rows="6" animated />
          </div>
          <div v-else ref="threadRef" class="conv-thread">
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
            <div v-for="message in conversation" :key="message.key" class="conv-message" :class="`conv-message--${message.role}`">
              <div class="conv-bubble">
                <div class="conv-bubble__head">
                  <span class="conv-bubble__role">{{ message.role === 'user' ? '你' : 'Agent' }}</span>
                  <span v-if="message.time" class="conv-bubble__time">{{ message.time }}</span>
                  <span v-if="message.turnSeq" class="conv-bubble__time">Turn {{ message.turnSeq }}</span>
                </div>
                <p v-if="message.role === 'user'" class="conv-bubble__text">{{ message.text }}</p>
                <template v-else>
                  <p class="conv-bubble__text">{{ message.text }}</p>
                  <div v-if="message.llmAnalysis" class="conv-bubble__analysis">
                    <div class="analysis-head">
                      <BaseIcon name="zap" :size="13" />
                      <span>LLM 分析</span>
                    </div>
                    <ChatMarkdown :content="message.llmAnalysis" />
                  </div>
                  <div v-if="message.detail && message.detail.length" class="conv-bubble__detail">
                    <div v-for="(line, index) in message.detail" :key="index" class="detail-line">
                      <template v-if="line.kind === 'severity'">
                        <BaseBadge v-if="line.counts.critical" type="red">严重 {{ line.counts.critical }}</BaseBadge>
                        <BaseBadge v-if="line.counts.high" type="orange">高危 {{ line.counts.high }}</BaseBadge>
                        <BaseBadge v-if="line.counts.medium" type="yellow">中危 {{ line.counts.medium }}</BaseBadge>
                        <BaseBadge v-if="line.counts.low" type="blue">低危 {{ line.counts.low }}</BaseBadge>
                        <BaseBadge v-if="line.counts.info" type="gray">信息 {{ line.counts.info }}</BaseBadge>
                      </template>
                      <template v-else-if="line.kind === 'coverage'">
                        <span class="detail-label">覆盖</span>
                        <span class="detail-value">{{ line.text }}</span>
                      </template>
                      <template v-else-if="line.kind === 'task'">
                        <span class="detail-label">任务</span>
                        <span class="detail-value">#{{ line.text }}</span>
                      </template>
                      <template v-else-if="line.kind === 'languages'">
                        <span class="detail-label">语言</span>
                        <span class="detail-value">{{ line.text }}</span>
                      </template>
                      <template v-else>
                        {{ line }}
                      </template>
                    </div>
                  </div>
                  <div v-if="message.toolCalls && message.toolCalls.length" class="tool-chips">
                    <span
                      v-for="call in message.toolChips"
                      :key="call.id"
                      class="tool-chip"
                      :class="`tool-chip--${call.status}`"
                      :title="call.tool_name"
                    >
                      {{ call.label }}
                    </span>
                  </div>
                  <button
                    v-if="message.expandable"
                    class="conv-expand"
                    @click="toggleExpand(message)"
                  >
                    {{ message.expanded ? '收起执行明细' : '展开执行明细' }}
                  </button>
                  <div v-if="message.expanded" class="conv-detail-panel">
                    <AgentToolCallList :tool-calls="message.toolCalls" :loading="false" />
                    <AgentStatusTimeline :steps="message.steps" :loading="false" />
                  </div>
                </template>
              </div>
            </div>
          </div>

          <ChatComposer
            :disabled="sendingMessage"
            :placeholder="composerPlaceholder"
            @send="handleSendMessage"
          />
          <p class="conv-legal">每条消息创建一个新 Turn 并复用当前快照；Agent 会基于扫描证据执行 LLM 分析并给出结论。</p>
        </main>

        <!-- 右侧信息面板 -->
        <aside class="conv-side">
          <AgentConnectionStatus
            :connection-state="store.connectionState"
            :last-sequence="store.lastSequence"
            :state-version="store.stateVersion"
            :reasoning-live="store.reasoningLive"
          />
          <AgentProviderBadge :provider="store.lastProvider" />
          <AgentPlannerPanel
            :plan="store.plan"
            :fallback-reason="planFallbackReason"
            :loading="loading"
          />
          <AgentPlanGraph :plan="store.plan" :loading="loading" />
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
          <CodeEvidenceViewer
            :visible="codeVisible"
            :slice="codeSlice"
            @close="closeCodeEvidence"
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
          <AgentFindingSummary
            :metrics="baselineMetrics"
            :loading="loading"
          />
          <AgentReasoningStream :text="store.reasoningStream" :live="store.reasoningLive" />
          <AgentCostPanel :summary="costSummary" :invocations="invocations" :loading="costsLoading" />
          <AgentEventList :events="store.events" />
        </aside>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from '@/features/security/feedback'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatMarkdown from '@/components/chat/ChatMarkdown.vue'
import AgentConnectionStatus from '@/components/security/agent/AgentConnectionStatus.vue'
import AgentCostPanel from '@/components/security/agent/AgentCostPanel.vue'
import AgentCoverageFileTable from '@/components/security/agent/AgentCoverageFileTable.vue'
import AgentCoverageOverview from '@/components/security/agent/AgentCoverageOverview.vue'
import AgentEventList from '@/components/security/agent/AgentEventList.vue'
import AgentFindingSummary from '@/components/security/agent/AgentFindingSummary.vue'
import AgentGoalForm from '@/components/security/agent/AgentGoalForm.vue'
import AgentPlanGraph from '@/components/security/agent/AgentPlanGraph.vue'
import AgentPlannerPanel from '@/components/security/agent/AgentPlannerPanel.vue'
import AgentProviderBadge from '@/components/security/agent/AgentProviderBadge.vue'
import AgentReasoningStream from '@/components/security/agent/AgentReasoningStream.vue'
import AgentStatusTimeline from '@/components/security/agent/AgentStatusTimeline.vue'
import AgentToolCallList from '@/components/security/agent/AgentToolCallList.vue'
import AgentWorkbenchHeader from '@/components/security/agent/home/AgentWorkbenchHeader.vue'
import AgentProjectFilters from '@/components/security/agent/home/AgentProjectFilters.vue'
import AgentProjectInspector from '@/components/security/agent/home/AgentProjectInspector.vue'
import AgentProjectTable from '@/components/security/agent/home/AgentProjectTable.vue'
import CallChainPanel from '@/components/security/agent/CallChainPanel.vue'
import CodeEvidenceViewer from '@/components/security/agent/CodeEvidenceViewer.vue'
import ProjectSecurityGraph from '@/components/security/agent/ProjectSecurityGraph.vue'
import SecurityGraphNodeDetail from '@/components/security/agent/SecurityGraphNodeDetail.vue'
import { BaseBadge, BaseIcon } from '@/components/ui'
import { agentAPI, securityAPI } from '@/api'
import { useAgentCosts } from '@/composables/security/useAgentCosts'
import { useAgentCoverage } from '@/composables/security/useAgentCoverage'
import { useAgentConversations } from '@/composables/security/useAgentConversations'
import { useAgentRun } from '@/composables/security/useAgentRun'
import { agentStatusMeta, toolNameLabel } from '@/features/security/agent/statusMeta'
import { languageMeta } from '@/features/security/languageMeta'
import { formatSecurityDate, securityApiErrorMessage } from '@/features/security/presentation'

const route = useRoute()
const router = useRouter()
const { store, loading, errorMessage, actionLoading, loadRun, pauseRun, resumeRun, cancelRun } = useAgentRun()
const selectedProject = ref(null)
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
  conversations,
  loading: conversationsLoading
} = useAgentConversations(() => selectedProject.value?.id)
const {
  loading: costsLoading,
  summary: costSummary,
  invocations,
  loadCosts
} = useAgentCosts(() => currentRunId.value)
const creating = ref(false)
const sendingMessage = ref(false)
const threadRef = ref(null)
const projects = ref([])
const projectsLoading = ref(false)
const conversationMeta = ref(null)
const conversationMessages = ref([])
const conversationTotal = ref(0)
const turns = ref([])
const turnRuns = ref({})
const projectFilter = ref('all')
const projectSearch = ref('')
const projectLanguage = ref('all')
const projectSort = ref('recent')
const inspectorRef = ref(null)
const selectedGraphNode = ref(null)
const codeVisible = ref(false)
const codeSlice = ref(null)

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

const runId = computed(() => Number(route.params.runId))
const projectId = computed(() => Number(route.params.id))
const conversationId = computed(() => Number(route.params.conversationId))
const mode = computed(() =>
  conversationId.value ? 'conversation' : runId.value ? 'run' : projectId.value ? 'project' : 'home'
)

const statusMeta = computed(() => agentStatusMeta(store.run?.status))

const runningProjectCount = computed(() => projects.value.filter((project) => project.is_running).length)
const attentionProjectCount = computed(() => projects.value.filter((project) => riskTotal(project) > 0).length)

const filteredProjects = computed(() => {
  const keyword = projectSearch.value.trim().toLowerCase()
  let items = projects.value.filter((project) => {
    if (projectFilter.value === 'running' && !project.is_running) return false
    if (projectFilter.value === 'attention' && riskTotal(project) === 0) return false
    if (projectFilter.value === 'unscanned' && project.last_scan_at) return false
    if (projectLanguage.value !== 'all' && languageMeta(project.language).key !== projectLanguage.value) return false
    if (!keyword) return true
    return `${project.name} ${project.description || ''}`.toLowerCase().includes(keyword)
  })

  return [...items].sort((left, right) => {
    if (projectSort.value === 'name') return String(left.name).localeCompare(String(right.name))
    if (projectSort.value === 'risk') return riskTotal(right) - riskTotal(left)
    return new Date(right.last_scan_at || 0).getTime() - new Date(left.last_scan_at || 0).getTime()
  })
})

function riskTotal(project) {
  return ['critical', 'high', 'medium', 'low', 'info'].reduce((total, level) => total + Number(project?.vulns?.[level] || 0), 0)
}

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
  if (mode.value === 'project') return '输入第一条安全审计目标'
  if (!store.run && !conversationMeta.value) return '输入安全审计目标'
  if (store.isTerminal || !store.run) return '继续输入目标，创建新 Turn，Agent 将执行 LLM 分析并回复'
  return 'Agent 执行中…可输入补充指令'
})

const conversation = computed(() => {
  const items = []
  if (mode.value === 'conversation') {
    // 多轮：按 Turn 顺序交错展示 用户消息 + Agent 回复
    for (const turn of turns.value) {
      const message = conversationMessages.value.find(
        (item) => item.id === turn.input_message_id
      )
      if (message) {
        items.push({
          key: `conv-msg-${message.id}`,
          role: 'user',
          text: message.content,
          time: formatSecurityDate(message.created_at),
          turnSeq: turn.turn_sequence
        })
      }
      const payload = turnRuns.value[turn.run_id]
      if (payload) {
        items.push(agentMessage(payload, turn))
      }
    }
    return items
  }

  // run 模式：按消息顺序交错，最后补充实时 LLM 分析
  const stored = store.messages || []
  for (const message of stored) {
    if (message.role === 'user') {
      items.push({
        key: `msg-${message.id}`,
        role: 'user',
        text: message.content,
        time: formatSecurityDate(message.created_at)
      })
    } else {
      items.push(agentMessageForStore(message))
    }
  }
  if (store.run && !items.some((item) => item.role === 'agent')) {
    items.push(agentMessageForStore(null))
  }
  return items
})

function agentMessage(payload, turn) {
  const run = payload.run || {}
  const analysis = (payload.messages || []).find(
    (message) => message.role === 'agent' && message.message_type === 'llm_analysis'
  )
  return {
    key: `agent-turn-${turn?.id || run.id}`,
    role: 'agent',
    text: agentReplyText(run, payload.scan_summary),
    time: run.finished_at ? formatSecurityDate(run.finished_at) : '',
    turnSeq: turn?.turn_sequence || null,
    llmAnalysis: analysis?.content || null,
    detail: agentReplyDetail(payload.scan_summary),
    toolCalls: payload.tool_calls || [],
    toolChips: toolChipsOf(payload.tool_calls || []),
    steps: payload.steps || [],
    expandable: (payload.tool_calls?.length || 0) + (payload.steps?.length || 0) > 0,
    expanded: false
  }
}

function agentMessageForStore(message) {
  const run = store.run || {}
  const analysis = message?.content || store.llmAnalysis || null
  const toolCalls = store.toolCalls || []
  const steps = store.steps || []
  return {
    key: `agent-msg-${message?.id || 'live'}`,
    role: 'agent',
    text: agentReplyText(run, store.scanSummary),
    time: run.finished_at ? formatSecurityDate(run.finished_at) : '',
    turnSeq: null,
    llmAnalysis: analysis,
    detail: agentReplyDetail(store.scanSummary),
    toolCalls,
    toolChips: toolChipsOf(toolCalls),
    steps,
    expandable: toolCalls.length + steps.length > 0,
    expanded: false
  }
}

function agentReplyText(run, scanSummary) {
  if (!run) return ''
  const status = agentStatusMeta(run.status).label
  const findings = scanSummary?.findings_count ?? 0
  return `执行完成（${status}）：基线扫描产出 ${findings} 个发现。`
}

function agentReplyDetail(scanSummary) {
  const items = []
  if (scanSummary) {
    items.push({ kind: 'task', text: scanSummary.task_id })
    const counts = scanSummary.severity_counts || {}
    items.push({ kind: 'severity', counts })
    if (scanSummary.languages?.length) items.push({ kind: 'languages', text: scanSummary.languages.join(', ') })
  }
  return items
}

function toolChipsOf(toolCalls) {
  return (toolCalls || []).slice(0, 8).map((call) => ({
    id: call.id,
    label: toolNameLabel(call.tool_name),
    status: call.status === 'succeeded' ? 'succeeded' : call.status === 'failed' ? 'failed' : 'running',
    tool_name: call.tool_name
  }))
}

function toggleExpand(message) {
  message.expanded = !message.expanded
}

// ------------------------------------------------------------------ conversation

async function loadConversation(conversationIdValue) {
  errorMessage.value = ''
  try {
    const [metaResponse, messagesResponse] = await Promise.all([
      agentAPI.getConversation(conversationIdValue),
      agentAPI.getConversationMessages(conversationIdValue, { page: 1, page_size: 50 })
    ])
    conversationMeta.value = metaResponse.conversation
    turns.value = metaResponse.conversation.turns || []
    conversationMessages.value = messagesResponse.items || []
    conversationTotal.value = messagesResponse.pagination?.total || 0

    // 并行加载每个 Turn 的 Run 详情，保证时间线按轮次交错展示
    const runTurns = turns.value.filter((turn) => turn.run_id)
    const payloads = await Promise.all(
      runTurns.map((turn) => agentAPI.getRun(turn.run_id).catch(() => null))
    )
    const nextRuns = {}
    runTurns.forEach((turn, index) => {
      if (payloads[index]) nextRuns[turn.run_id] = payloads[index]
    })
    turnRuns.value = nextRuns

    const latestRunTurn = runTurns[runTurns.length - 1]
    if (latestRunTurn?.run_id) {
      currentRunId.value = latestRunTurn.run_id
      loadRun(latestRunTurn.run_id)
    } else {
      currentRunId.value = null
    }
    await nextTickScroll()
  } catch (error) {
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
    } else if (mode.value === 'run' && runId.value) {
      const response = await agentAPI.sendMessage(runId.value, content)
      store.messages = [...(store.messages || []), response.message]
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
  loadCoverage('')
}

function selectProject(project) {
  selectedProject.value = project
}

async function focusSelectedProject() {
  selectedProject.value = selectedProject.value || filteredProjects.value[0] || projects.value[0] || null
  await nextTick()
  inspectorRef.value?.focusGoal()
}

function openProject(project) {
  if (project?.id) router.push(`/security/projects/${project.id}`)
}

async function startAudit(payload) {
  const project = payload?.project || payload
  const goal = payload?.goal || '检查项目安全风险'
  const auditMode = payload?.mode || 'baseline'
  if (!project || creating.value) return
  if (!project.latest_snapshot_id) {
    ElMessage.warning('项目暂无可用快照，请先上传 ZIP 或导入 GitHub 项目')
    return
  }
  creating.value = true
  try {
    const conversation = await createConversationTurn(project.id, goal, auditMode)
    if (conversation) {
      ElMessage.success('会话已创建')
      router.push(`/security/agent-conversations/${conversation.id}`)
    }
  } finally {
    creating.value = false
  }
}

async function createConversationTurn(projectIdValue, goal, auditMode, budget) {
  try {
    const created = await agentAPI.createConversation(projectIdValue, { title: goal.slice(0, 200) })
    const conversationIdValue = created.conversation.id
    await agentAPI.postConversationMessage(conversationIdValue, {
      content: goal,
      mode: auditMode,
      budget: budget || {},
      client_message_id: generateClientMessageId()
    })
    return { id: conversationIdValue }
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '创建会话失败'))
    return null
  }
}

async function nextTickScroll() {
  await nextTick()
  threadRef.value?.scrollTo({ top: threadRef.value.scrollHeight, behavior: 'smooth' })
}

// ------------------------------------------------------------------ run actions

async function handleCreate({ goal, mode, budget }) {
  if (creating.value) return
  creating.value = true
  try {
    const conversation = await createConversationTurn(projectId.value, goal, mode, budget)
    if (conversation) {
      ElMessage.success('会话已创建')
      router.push(`/security/agent-conversations/${conversation.id}`)
    }
  } finally {
    creating.value = false
  }
}

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
  else if (mode.value === 'home') loadProjects()
}

async function loadProjects() {
  projectsLoading.value = true
  try {
    const response = await securityAPI.listProjects()
    projects.value = response.items || []
    if (!selectedProject.value || !projects.value.some((project) => project.id === selectedProject.value.id)) {
      selectedProject.value = projects.value[0] || null
    }
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '加载项目失败'))
  } finally {
    projectsLoading.value = false
  }
}

function goBack() {
  if (mode.value === 'conversation') router.push(`/security/projects/${conversationMeta.value?.project_id || ''}/agent`)
  else if (runId.value) router.push(`/security/projects/${store.run?.project_id || ''}/agent`)
  else router.push('/security/projects')
}

watch(conversationId, (id) => {
  if (id) loadConversation(id)
})

watch(runId, (id) => {
  if (id) loadRun(id)
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
  else if (mode.value === 'run') loadRun(runId.value)
  else if (mode.value === 'home') loadProjects()
})
</script>

<style scoped lang="scss">
.agent-page { height: calc(100vh - 60px); overflow: hidden; background: #ffffff; color: #172033; }

/* ===== 首页（项目选择） ===== */
.agent-home { height: 100%; display: flex; flex-direction: column; padding: 24px 28px 28px; }
.home-layout { display: grid; grid-template-columns: minmax(0, 1fr) 346px; flex: 1 1 auto; min-height: 0; gap: 16px; align-items: stretch; }
.home-skeleton { display: flex; flex-direction: column; gap: 10px; }

/* ===== 项目入口 ===== */
.agent-project { padding: 12px 16px 32px; }
.project-head { display: flex; align-items: center; gap: 8px; padding: 8px 0; }
.project-head__title { font-size: 15px; font-weight: 600; }
.project-layout { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 10px; align-items: start; }
.tip-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.tip-card h3 { margin: 0 0 10px; font-size: 14px; }
.tip-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.tip-item { display: flex; align-items: flex-start; gap: 10px; color: #52627a; font-size: 12.5px; line-height: 1.6; }
.tip-item__icon { display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 6px; flex: none; margin-top: 1px; }
.tip-item__icon--blue { background: #eff6ff; color: #2563eb; }
.tip-item__icon--green { background: #dcfce7; color: #16a34a; }
.tip-item__icon--yellow { background: #fef9c3; color: #ca8a04; }

/* ===== 对话视图 ===== */
.agent-conversation { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
.conv-head {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 16px; background: #fff; border-bottom: 1px solid #e2e7ee;
  flex: 0 0 auto;
}
.conv-head__title { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 600; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conv-head__actions { display: flex; align-items: center; gap: 8px; }
.conv-alert { margin: 8px 16px 0; flex: 0 0 auto; }
.conv-layout { flex: 1; display: grid; grid-template-columns: minmax(0, 1fr) 380px; min-height: 0; }
.conv-main { display: flex; flex-direction: column; min-width: 0; background: #fff; }
.conv-thread {
  flex: 1; overflow-y: auto; padding: 20px 16px;
  display: flex; flex-direction: column; gap: 14px;
}
.conv-skeleton { padding: 20px; }
.conv-message { display: flex; }
.conv-message--user { justify-content: flex-end; }
.conv-message--agent { justify-content: flex-start; }
.conv-bubble {
  max-width: 720px; padding: 10px 14px; border-radius: 10px; font-size: 13.5px; line-height: 1.6;
}
.conv-message--user .conv-bubble { background: #eff6ff; border: 1px solid #dbeafe; color: #1e3a8a; }
.conv-message--agent .conv-bubble { background: #fff; border: 1px solid #e2e7ee; color: #1f2d3d; }
.conv-bubble__head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.conv-bubble__role { font-size: 12px; font-weight: 700; color: #2563eb; }
.conv-message--user .conv-bubble__role { color: #1d4ed8; }
.conv-bubble__time { color: #94a3b8; font-size: 11.5px; }
.conv-bubble__text { margin: 0; white-space: pre-wrap; word-break: break-word; }
.conv-bubble__analysis {
  margin-top: 8px;
  padding: 8px 10px;
  border: 1px solid #dbeafe;
  border-radius: 6px;
  background: #f5f9ff;
}
.analysis-head {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
}
.conv-bubble__analysis :deep(.chat-markdown) {
  font-size: 13px;
  line-height: 1.65;
  color: #1f2d3d;
}
.conv-bubble__analysis :deep(.chat-markdown h1),
.conv-bubble__analysis :deep(.chat-markdown h2),
.conv-bubble__analysis :deep(.chat-markdown h3),
.conv-bubble__analysis :deep(.chat-markdown h4) {
  font-size: 14px;
  margin: 10px 0 6px;
}
.conv-bubble__analysis :deep(.chat-markdown ul),
.conv-bubble__analysis :deep(.chat-markdown ol) {
  margin: 6px 0;
  padding-left: 20px;
}
.conv-bubble__analysis :deep(.chat-markdown p) { margin: 6px 0; }
.conv-bubble__analysis :deep(.chat-markdown code) {
  font-size: 12px;
  padding: 1px 5px;
}
.tool-chips {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.tool-chip {
  font-size: 11.5px;
  border-radius: 999px;
  padding: 2px 10px;
  border: 1px solid #c2ccd9;
  color: #52627a;
  background: #fff;
  cursor: default;
}
.tool-chip--succeeded { border-color: #bbf7d0; background: #f0fdf4; color: #15803d; }
.tool-chip--failed { border-color: #fecaca; background: #fef2f2; color: #b91c1c; }
.tool-chip--running { border-color: #bfdbfe; background: #eff6ff; color: #1d4ed8; }
.conv-bubble__detail {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-left: 10px;
  border-left: 2px solid #dbeafe;
}

.detail-label {
  font-size: 11.5px;
  font-weight: 600;
  color: #6a7890;
  flex: none;
}

.detail-value {
  font-size: 12.5px;
  color: #1f2d3d;
  font-variant-numeric: tabular-nums;
}
.conv-expand {
  margin-top: 8px; border: 0; background: none; color: #0b7fd1; font-size: 12.5px; cursor: pointer; padding: 0;
}
.conv-detail-panel { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.conv-legal { flex: 0 0 auto; text-align: center; color: #94a3b8; font-size: 12px; padding: 6px 0; }

/* Turn 时间线 */
.turn-timeline {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 6px 10px; border: 1px solid #e2e7ee; border-radius: 8px; background: #fafbfd;
  font-size: 12px; color: #6a7890;
}
.turn-timeline__label { font-weight: 600; }
.turn-chip {
  border: 1px solid #c2ccd9; background: #fff; color: #52627a;
  border-radius: 999px; padding: 2px 10px; font-size: 12px; cursor: pointer;
}
.turn-chip:hover { border-color: #0b7fd1; color: #0b7fd1; }
.turn-chip--active { background: #eff6ff; border-color: #2563eb; color: #2563eb; font-weight: 600; }

/* 右侧面板 */
.conv-side {
  display: flex; flex-direction: column; gap: 10px; padding: 10px 10px 24px;
  overflow-y: auto; background: #f4f6f9; border-left: 1px solid #e2e7ee;
}

@media (max-width: 960px) {
  .conv-layout { grid-template-columns: 1fr; }
  .conv-side { border-left: 0; border-top: 1px solid #e2e7ee; }
  .project-layout { grid-template-columns: 1fr; }
  .home-layout { grid-template-columns: 1fr; overflow-y: auto; }
  .agent-home { height: auto; min-height: calc(100vh - 60px); overflow: visible; }
}

@media (max-width: 720px) {
  .agent-home { padding: 20px 16px 24px; }
}
</style>
