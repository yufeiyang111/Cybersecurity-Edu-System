<template>
  <main class="agent-page">
    <header class="topbar">
      <el-button text :icon="ArrowLeft" @click="goBack">返回</el-button>
      <div class="topbar__title">{{ isRunView ? `Agent 任务 #${route.params.runId}` : `项目 #${projectId} 的 Agent 工作台` }}</div>
      <el-button :icon="Refresh" :loading="loading" @click="reload">刷新</el-button>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="alert" />

    <!-- 项目入口视图：创建任务 -->
    <section v-if="!isRunView" class="create-layout">
      <AgentGoalForm :submitting="creating" @create="handleCreate" />
      <div class="tip-card">
        <h3>运行说明</h3>
        <ul>
          <li>创建后 Agent 将真实执行确定性工具（如快照清点），所有事件持久化并可通过 SSE 实时推送。</li>
          <li>执行中可暂停、恢复或取消；刷新页面后状态与历史事件不丢失。</li>
          <li>基线阶段使用本地策略计划（rule_based_policy），不会冒充真实 LLM。</li>
        </ul>
      </div>
    </section>

    <!-- 运行详情视图 -->
    <section v-else>
      <div v-if="loading && !store.run" class="run-skeleton">
        <el-skeleton :rows="6" animated />
      </div>
      <template v-else-if="store.run">
        <AgentRunHeader
          :run="store.run"
          :store="store"
          :action-loading="actionLoading"
          @pause="handlePause"
          @resume="handleResume"
          @cancel="handleCancel"
        />

        <AgentConnectionStatus
          :connection-state="store.connectionState"
          :last-sequence="store.lastSequence"
          :state-version="store.stateVersion"
          :reasoning-live="store.reasoningLive"
        />

        <div class="run-layout">
          <div class="run-main">
            <AgentStatusTimeline :steps="store.steps" :loading="loading" />
            <AgentToolCallList
              :tool-calls="store.toolCalls"
              :loading="loading"
              :error-message="errorMessage"
            />
          </div>
          <aside class="run-side">
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
      </template>
      <el-empty v-else description="未找到 Agent 任务" />
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import AgentConnectionStatus from '@/components/security/agent/AgentConnectionStatus.vue'
import AgentGoalForm from '@/components/security/agent/AgentGoalForm.vue'
import AgentReasoningStream from '@/components/security/agent/AgentReasoningStream.vue'
import AgentRunHeader from '@/components/security/agent/AgentRunHeader.vue'
import AgentStatusTimeline from '@/components/security/agent/AgentStatusTimeline.vue'
import AgentToolCallList from '@/components/security/agent/AgentToolCallList.vue'
import { useAgentRun } from '@/composables/security/useAgentRun'
import { securityApiErrorMessage } from '@/features/security/presentation'

const route = useRoute()
const router = useRouter()
const { store, loading, errorMessage, actionLoading, loadRun, createRun, pauseRun, resumeRun, cancelRun } = useAgentRun()
const creating = ref(false)

const runId = computed(() => Number(route.params.runId))
const projectId = computed(() => Number(route.params.id))
const isRunView = computed(() => Boolean(route.params.runId))

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
  if (await pauseRun(runId.value)) ElMessage.success('任务已暂停')
}
async function handleResume() {
  if (await resumeRun(runId.value)) ElMessage.success('任务已恢复')
}
async function handleCancel() {
  try {
    await ElMessageBox.confirm('确认取消该 Agent 任务吗？已产生的证据与事件会保留。', '取消 Agent 任务', { type: 'warning' })
    if (await cancelRun(runId.value)) ElMessage.success('任务已取消')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(securityApiErrorMessage(error, '取消任务失败'))
  }
}

const reload = () => {
  if (isRunView.value) loadRun(runId.value)
}

watch(runId, (id) => {
  if (id) loadRun(id)
})

function goBack() {
  if (isRunView.value) router.push(`/security/projects/${store.run?.project_id || ''}/agent`)
  else router.push(`/security/projects/${projectId.value}`)
}

onMounted(() => {
  if (isRunView.value) loadRun(runId.value)
})
</script>

<style scoped lang="scss">
.agent-page { min-height: 100vh; padding: 12px 16px 32px; background: #f4f6f9; color: #1f2d3d; }
.topbar {
  position: sticky; top: 0; z-index: 20;
  display: flex; align-items: center; gap: 12px;
  padding: 8px 0; margin-bottom: 8px;
  background: rgba(244, 246, 249, .94);
  backdrop-filter: blur(8px);
}
.topbar__title { flex: 1; font-size: 15px; font-weight: 600; }
.alert { margin-bottom: 8px; }

.create-layout { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 10px; align-items: start; }
.tip-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.tip-card h3 { margin: 0 0 8px; font-size: 14px; }
.tip-card ul { margin: 0; padding-left: 18px; color: #52627a; font-size: 12.5px; line-height: 1.8; }

.run-skeleton { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 16px; }

.run-layout { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 10px; margin-top: 10px; align-items: start; }
.run-main, .run-side { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.run-side { position: sticky; top: 56px; }

.events-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head .note { color: #6a7890; font-size: 12.5px; }
.events-empty { color: #8494a8; font-size: 12.5px; }
.events-list { list-style: none; margin: 0; padding: 0; max-height: 280px; overflow-y: auto; }
.events-list li { display: flex; gap: 10px; padding: 4px 0; font-size: 12.5px; border-bottom: 1px solid #f4f6f9; }
.events-seq { color: #8494a8; font-variant-numeric: tabular-nums; }
.events-type { color: #1f2d3d; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }

@media (max-width: 960px) {
  .create-layout, .run-layout { grid-template-columns: 1fr; }
  .run-side { position: static; }
}
</style>
