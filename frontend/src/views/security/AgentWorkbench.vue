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
          <div class="home-side">
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
            <AgentFeatureFlagPanel
              v-if="selectedProject"
              :workspace-id="selectedWorkspaceId"
              :resolved="featureFlagsResolved"
              :overrides="featureFlagsOverrides"
              :loading="featureFlagsLoading"
              :saving="featureFlagsSaving"
              :access-denied="featureFlagsAccessDenied"
              :error-message="featureFlagsErrorMessage"
              @save="saveV3FeatureFlags"
              @reset="resetV3FeatureFlagOverrides"
            />
          </div>
        </div>
      </template>
    </section>

    <!-- ============ 项目入口（/security/projects/:id/agent） ============ -->
    <section v-else class="agent-project">
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
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from '@/features/security/feedback'
import { ArrowLeft } from '@element-plus/icons-vue'
import AgentGoalForm from '@/components/security/agent/AgentGoalForm.vue'
import AgentWorkbenchHeader from '@/components/security/agent/home/AgentWorkbenchHeader.vue'
import AgentFeatureFlagPanel from '@/components/security/agent/home/AgentFeatureFlagPanel.vue'
import AgentProjectFilters from '@/components/security/agent/home/AgentProjectFilters.vue'
import AgentProjectInspector from '@/components/security/agent/home/AgentProjectInspector.vue'
import AgentProjectTable from '@/components/security/agent/home/AgentProjectTable.vue'
import { BaseIcon } from '@/components/ui'
import { agentAPI, securityAPI } from '@/api'
import { useAgentConversations } from '@/composables/security/useAgentConversations'
import { useAgentFeatureFlags } from '@/composables/security/useAgentFeatureFlags'
import { languageMeta } from '@/features/security/languageMeta'
import { securityApiErrorMessage } from '@/features/security/presentation'

const route = useRoute()
const router = useRouter()
const selectedProject = ref(null)
const {
  conversations,
  loading: conversationsLoading
} = useAgentConversations(() => selectedProject.value?.id)
const creating = ref(false)
const projects = ref([])
const projectsLoading = ref(false)
const projectFilter = ref('all')
const projectSearch = ref('')
const projectLanguage = ref('all')
const projectSort = ref('recent')
const inspectorRef = ref(null)
const selectedWorkspaceId = computed(() => {
  const workspaceId = Number(selectedProject.value?.workspace_id)
  return Number.isInteger(workspaceId) && workspaceId > 0 ? workspaceId : null
})
const {
  loading: featureFlagsLoading,
  saving: featureFlagsSaving,
  accessDenied: featureFlagsAccessDenied,
  errorMessage: featureFlagsErrorMessage,
  resolved: featureFlagsResolved,
  overrides: featureFlagsOverrides,
  saveV3Flags,
  resetV3Overrides
} = useAgentFeatureFlags(() => selectedWorkspaceId.value)

const projectId = computed(() => Number(route.params.id))
const mode = computed(() => (projectId.value ? 'project' : 'home'))

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

async function saveV3FeatureFlags(flags) {
  const saved = await saveV3Flags(flags)
  if (saved) {
    ElMessage.success('Harness V3 开关已保存；后续新建任务将使用该快照。')
    return
  }
  if (featureFlagsErrorMessage.value) {
    ElMessage.error(featureFlagsErrorMessage.value)
  }
}

async function resetV3FeatureFlagOverrides() {
  const restored = await resetV3Overrides()
  if (restored) {
    ElMessage.success('已恢复 Harness V3 的工作区默认值。')
    return
  }
  if (featureFlagsErrorMessage.value) {
    ElMessage.error(featureFlagsErrorMessage.value)
  }
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
    const conversationIdValue = created?.conversation?.id
    if (!conversationIdValue) {
      ElMessage.error('创建会话失败：响应缺少会话数据')
      return null
    }
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

function generateClientMessageId() {
  const random = Math.random().toString(36).slice(2, 10)
  return `msg-${Date.now().toString(36)}-${random}`
}

async function handleCreate({ goal, mode: auditMode, budget }) {
  if (creating.value) return
  creating.value = true
  try {
    const conversation = await createConversationTurn(projectId.value, goal, auditMode, budget)
    if (conversation) {
      ElMessage.success('会话已创建')
      router.push(`/security/agent-conversations/${conversation.id}`)
    }
  } finally {
    creating.value = false
  }
}

function openConversation(conversation) {
  if (conversation?.id) router.push(`/security/agent-conversations/${conversation.id}`)
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
  router.push('/security/projects')
}

onMounted(() => {
  if (mode.value === 'home') loadProjects()
})
</script>

<style scoped lang="scss">
.agent-page { height: calc(100vh - 60px); overflow: hidden; background: #ffffff; color: #172033; }

/* ===== 首页（项目选择） ===== */
.agent-home { height: 100%; display: flex; flex-direction: column; padding: 24px 28px 28px; }
.home-layout { display: grid; grid-template-columns: minmax(0, 1fr) 346px; flex: 1 1 auto; min-height: 0; gap: 16px; align-items: stretch; }
.home-side { display: grid; grid-template-rows: minmax(0, 1fr) auto; min-height: 0; gap: 12px; }
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

@media (max-width: 960px) {
  .project-layout { grid-template-columns: 1fr; }
  .home-layout { grid-template-columns: 1fr; overflow-y: auto; }
  .home-side { grid-template-rows: auto; }
  .agent-home { height: auto; min-height: calc(100vh - 60px); overflow: visible; }
}

@media (max-width: 720px) {
  .agent-home { padding: 20px 16px 24px; }
}
</style>
