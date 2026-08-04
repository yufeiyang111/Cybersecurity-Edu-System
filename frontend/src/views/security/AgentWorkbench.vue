<template>
  <div class="agent-page">
    <!-- ============ 项目选择入口（/security/agent） ============ -->
    <section v-if="mode === 'home'" class="agent-home">
      <header class="home-head">
        <h1>Agent 工作台</h1>
        <p class="home-sub">选择一个项目，用自然语言描述安全审计目标；Agent 将转化为结构化计划并真实执行确定性扫描工具。</p>
      </header>
      <div v-if="projectsLoading" class="home-skeleton">
        <el-skeleton v-for="index in 3" :key="index" :rows="2" animated />
      </div>
      <el-empty v-else-if="projects.length === 0" description="还没有安全项目，请先创建项目并上传快照">
        <el-button type="primary" @click="router.push('/security/projects')">去创建项目</el-button>
      </el-empty>
      <div v-else class="project-grid">
        <button
          v-for="project in projects"
          :key="project.id"
          class="project-card"
          @click="startConversation(project)"
        >
          <span class="project-card__name">{{ project.name }}</span>
          <span class="project-card__meta">项目 #{{ project.id }} · 开始对话</span>
        </button>
      </div>
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
          <ul>
            <li>每条消息都会创建一个新的 Turn，并复用项目快照执行（无需重复上传）。</li>
            <li>Agent 将真实执行：快照清点 → 基线扫描 → 覆盖分析 → 风险排序。</li>
            <li>多轮对话的 LLM 分析将在接入 Provider 后启用。</li>
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
                <p class="conv-bubble__text">{{ message.text }}</p>
                <div v-if="message.detail && message.detail.length" class="conv-bubble__detail">
                  <div v-for="(line, index) in message.detail" :key="index" class="detail-line">{{ line }}</div>
                </div>
                <button
                  v-if="message.expandable && message.role === 'agent'"
                  class="conv-expand"
                  @click="toggleExpand(message)"
                >
                  {{ message.expanded ? '收起执行明细' : '展开执行明细' }}
                </button>
                <div v-if="message.expanded && message.role === 'agent'" class="conv-detail-panel">
                  <AgentToolCallList :tool-calls="store.toolCalls" :loading="loading" />
                  <AgentStatusTimeline :steps="store.steps" :loading="loading" />
                </div>
              </div>
            </div>
          </div>

          <ChatComposer
            :disabled="sendingMessage"
            :placeholder="composerPlaceholder"
            @send="handleSendMessage"
          />
          <p class="conv-legal">每条消息创建一个新 Turn 并复用当前快照；多轮对话的 LLM 分析将在接入 Provider 后启用。</p>
        </main>

        <!-- 右侧信息面板 -->
        <aside class="conv-side">
          <AgentConnectionStatus
            :connection-state="store.connectionState"
            :last-sequence="store.lastSequence"
            :state-version="store.stateVersion"
            :reasoning-live="store.reasoningLive"
          />
          <AgentPlanGraph :plan="store.plan" :loading="loading" />
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
          <section class="events-card">
            <div class="card-head">
              <h2>事件流</h2>
              <span class="note">{{ store.events.length }} 条（最近）</span>
            </div>
            <div v-if="store.events.length === 0" class="events-empty">暂无事件</div>
            <ul v-else class="events-list">
              <li v-for="event in store.events" :key="event.sequence">
                <span class="events-seq">#{{ event.sequence }}</span>
                <span class="events-type">{{ event.event_type }}</span>
              </li>
            </ul>
          </section>
        </aside>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import AgentConnectionStatus from '@/components/security/agent/AgentConnectionStatus.vue'
import AgentCoverageFileTable from '@/components/security/agent/AgentCoverageFileTable.vue'
import AgentCoverageOverview from '@/components/security/agent/AgentCoverageOverview.vue'
import AgentFindingSummary from '@/components/security/agent/AgentFindingSummary.vue'
import AgentGoalForm from '@/components/security/agent/AgentGoalForm.vue'
import AgentPlanGraph from '@/components/security/agent/AgentPlanGraph.vue'
import AgentReasoningStream from '@/components/security/agent/AgentReasoningStream.vue'
import AgentStatusTimeline from '@/components/security/agent/AgentStatusTimeline.vue'
import AgentToolCallList from '@/components/security/agent/AgentToolCallList.vue'
import { agentAPI, securityAPI } from '@/api'
import { useAgentCoverage } from '@/composables/security/useAgentCoverage'
import { useAgentRun } from '@/composables/security/useAgentRun'
import { agentStatusMeta } from '@/features/security/agent/statusMeta'
import { formatSecurityDate, securityApiErrorMessage } from '@/features/security/presentation'

const route = useRoute()
const router = useRouter()
const { store, loading, errorMessage, actionLoading, loadRun, createRun, pauseRun, resumeRun, cancelRun } = useAgentRun()
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
const creating = ref(false)
const sendingMessage = ref(false)
const threadRef = ref(null)
const projects = ref([])
const projectsLoading = ref(false)
const conversationMeta = ref(null)
const conversationMessages = ref([])
const conversationTotal = ref(0)
const turns = ref([])
const currentRunId = ref(null)

const runId = computed(() => Number(route.params.runId))
const projectId = computed(() => Number(route.params.id))
const conversationId = computed(() => Number(route.params.conversationId))
const mode = computed(() =>
  conversationId.value ? 'conversation' : runId.value ? 'run' : projectId.value ? 'project' : 'home'
)

const statusMeta = computed(() => agentStatusMeta(store.run?.status))

const conversationTitle = computed(() => {
  if (!conversationMeta.value) return `Agent 会话 #${conversationId.value}`
  return conversationMeta.value.title || `Agent 会话 #${conversationId.value}`
})

const baselineMetrics = computed(() => {
  if (store.scanSummary) return store.scanSummary
  const call = store.toolCalls.find((item) => item.tool_name === 'run_baseline_scan')
  return call?.metrics || null
})

const composerPlaceholder = computed(() => {
  if (mode.value === 'project') return '输入第一条安全审计目标'
  if (!store.run && !conversationMeta.value) return '输入安全审计目标'
  if (store.isTerminal || !store.run) return '继续输入目标，创建新 Turn（LLM 分析接入后回复）'
  return 'Agent 执行中…可输入补充指令'
})

const conversation = computed(() => {
  const items = []
  if (mode.value === 'conversation') {
    for (const message of conversationMessages.value) {
      if (message.role !== 'user') continue
      const turn = turns.value.find((item) => item.input_message_id === message.id)
      items.push({
        key: `conv-msg-${message.id}`,
        role: 'user',
        text: message.content,
        time: formatSecurityDate(message.created_at),
        turnSeq: turn?.turn_sequence || null
      })
    }
  } else {
    const stored = store.messages || []
    for (const message of stored) {
      if (message.role !== 'user') continue
      items.push({
        key: `msg-${message.id}`,
        role: 'user',
        text: message.content,
        time: formatSecurityDate(message.created_at)
      })
    }
  }
  if (store.run) {
    items.push({
      key: 'agent-run',
      role: 'agent',
      text: agentReplyText(),
      time: store.run.finished_at ? formatSecurityDate(store.run.finished_at) : '',
      detail: agentReplyDetail(),
      expandable: store.steps.length > 0 || store.toolCalls.length > 0,
      expanded: false
    })
  }
  return items
})

function agentReplyText() {
  if (!store.run) return ''
  const status = statusMeta.value.label
  if (!store.isTerminal) return `正在执行：${status}。Agent 正在调用确定性工具分析快照。`
  const scanSummary = store.scanSummary || baselineMetrics.value
  const findings = scanSummary?.findings_count ?? 0
  const covered = coverageSummary.value ? `${coverageSummary.value.total_files} 个文件完成覆盖` : '覆盖报告生成中'
  return `执行完成（${status}）：基线扫描产出 ${findings} 个发现，${covered}。`
}

function agentReplyDetail() {
  const lines = []
  const scanSummary = store.scanSummary || baselineMetrics.value
  if (scanSummary) {
    lines.push(`扫描任务 #${scanSummary.task_id}：${scanSummary.findings_count} 个发现`)
    const counts = scanSummary.severity_counts || {}
    lines.push(`严重 ${counts.critical ?? 0} · 高危 ${counts.high ?? 0} · 中危 ${counts.medium ?? 0} · 低危 ${counts.low ?? 0}`)
    if (scanSummary.languages?.length) lines.push(`识别语言：${scanSummary.languages.join(', ')}`)
  }
  return lines
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
    const latestRunTurn = [...turns.value].reverse().find((turn) => turn.run_id)
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
        conversationMessages.value = [...conversationMessages.value, response.message]
        currentRunId.value = response.run.id
        await loadRun(response.run.id)
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

async function startConversation(project) {
  creating.value = true
  try {
    const response = await agentAPI.createConversation(project.id, { title: `${project.name} 安全审计` })
    ElMessage.success('会话已创建')
    router.push(`/security/agent-conversations/${response.conversation.id}`)
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '创建会话失败'))
  } finally {
    creating.value = false
  }
}

async function nextTickScroll() {
  await nextTick()
  threadRef.value?.scrollTo({ top: threadRef.value.scrollHeight, behavior: 'smooth' })
}

// ------------------------------------------------------------------ run actions

async function handleCreate({ goal, mode }) {
  if (creating.value) return
  creating.value = true
  try {
    const run = await createRun(projectId.value, goal, mode)
    if (run) {
      ElMessage.success(`Agent 任务 #${run.id} 已创建`)
      router.push(`/security/agent-runs/${run.id}`)
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
      loadCoverage('')
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
.agent-page { min-height: 100vh; background: #f4f6f9; color: #1f2d3d; }

/* ===== 首页（项目选择） ===== */
.agent-home { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
.home-head h1 { margin: 0 0 6px; font-size: 24px; }
.home-sub { margin: 0 0 24px; color: #6a7890; font-size: 14px; line-height: 1.7; }
.home-skeleton { display: flex; flex-direction: column; gap: 10px; }
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.project-card {
  display: flex; flex-direction: column; gap: 4px;
  background: #fff; border: 1px solid #e2e7ee; border-radius: 10px;
  padding: 14px 16px; cursor: pointer; text-align: left;
  transition: border-color .15s ease, box-shadow .15s ease;
}
.project-card:hover { border-color: #2563eb; box-shadow: 0 2px 8px rgba(37, 99, 235, .08); }
.project-card__name { font-size: 14px; font-weight: 600; }
.project-card__meta { color: #8494a8; font-size: 12px; }

/* ===== 项目入口 ===== */
.agent-project { padding: 12px 16px 32px; }
.project-head { display: flex; align-items: center; gap: 8px; padding: 8px 0; }
.project-head__title { font-size: 15px; font-weight: 600; }
.project-layout { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 10px; align-items: start; }
.tip-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.tip-card h3 { margin: 0 0 8px; font-size: 14px; }
.tip-card ul { margin: 0; padding-left: 18px; color: #52627a; font-size: 12.5px; line-height: 1.8; }

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
.conv-bubble__detail { margin-top: 6px; display: flex; flex-direction: column; gap: 2px; color: #52627a; font-size: 12.5px; }
.detail-line { padding-left: 10px; border-left: 2px solid #dbeafe; }
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
.events-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head .note { color: #6a7890; font-size: 12.5px; }
.events-empty { color: #8494a8; font-size: 12.5px; }
.events-list { list-style: none; margin: 0; padding: 0; max-height: 220px; overflow-y: auto; }
.events-list li { display: flex; gap: 10px; padding: 4px 0; font-size: 12.5px; border-bottom: 1px solid #f4f6f9; }
.events-seq { color: #8494a8; font-variant-numeric: tabular-nums; }
.events-type { color: #1f2d3d; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }

@media (max-width: 960px) {
  .conv-layout { grid-template-columns: 1fr; }
  .conv-side { border-left: 0; border-top: 1px solid #e2e7ee; }
  .project-layout { grid-template-columns: 1fr; }
}
</style>
