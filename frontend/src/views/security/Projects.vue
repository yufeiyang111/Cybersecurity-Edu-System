<template>
  <main class="security-page">
    <div class="page-title">
      <h1>代码漏洞扫描工作台</h1>
    </div>

    <el-alert v-if="pageError" :title="pageError" type="error" show-icon :closable="false" class="page-alert" />

    <WorkbenchOverviewCards
      :totals="overview.totals"
      :total-projects="overview.totalProjects"
      :total-scans="overview.totalScans"
      :loading="loading"
    />

    <section class="project-section" v-loading="loading">
      <div class="toolbar">
        <div class="toolbar-title">
          <h2>我的项目</h2>
          <span class="count-badge">{{ projects.length }} 个项目</span>
        </div>
        <div class="toolbar-actions">
          <div class="search-box">
            <el-icon class="search-icon"><Search /></el-icon>
            <input
              v-model.trim="searchText"
              type="text"
              placeholder="搜索项目名称或说明"
              data-test="project-search"
            />
          </div>
          <el-select v-model="statusFilter" class="filter-select" placeholder="全部项目" data-test="project-filter">
            <el-option label="全部项目" value="all" />
            <el-option label="扫描中" value="running" />
            <el-option label="扫描完成" value="done" />
            <el-option label="未扫描" value="none" />
          </el-select>
          <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
        </div>
      </div>

      <el-empty v-if="!loading && projects.length === 0" description="还没有安全项目，先创建一个项目开始扫描。" :image-size="96">
        <div class="empty-actions">
          <el-button type="primary" @click="showCreateDialog = true">新建项目</el-button>
          <el-button :icon="GithubIcon" @click="openGitHubImport()">从 GitHub 导入</el-button>
        </div>
      </el-empty>

      <div v-else-if="filteredProjects.length === 0" class="no-result">没有符合条件的项目，换个关键词试试。</div>

      <div v-else class="project-list">
        <template v-for="project in filteredProjects" :key="project.id">
          <ProjectCard
            :project="project"
            :expanded="expandedProjectId === project.id"
            @toggle="togglePanel(project)"
            @view="openProject(project.id)"
            @github="openGitHubImport(project)"
            @upload="openUpload(project)"
            @rename="openRename(project)"
            @remove="confirmRemove(project)"
          />
          <ProjectVulnPanel
            v-if="expandedProjectId === project.id"
            :project="project"
            :findings="panelFindings"
            :loading="panelLoading"
            @close="expandedProjectId = null"
            @open-detail="openProject(project.id)"
          />
        </template>
      </div>
    </section>

    <RecentScanList :scans="overview.recentScans" :loading="loading" @open-scan="openScan" />

    <div
      ref="fabEl"
      class="ai-fab"
      :style="fabStyle"
      :class="{ 'is-dragging': isDragging }"
    >
      <div class="ai-bubble">
        <template v-if="aiRiskCount > 0">
          检测到 <b>{{ aiRiskCount }}</b> 个高危及以上漏洞，点击向 AI 安全助手咨询修复建议。
        </template>
        <template v-else>
          暂无高危及以上风险，点击向 <b>AI 安全助手</b> 提问，获取扫描结果解读与安全知识。
        </template>
      </div>
      <button
        class="ai-avatar"
        type="button"
        title="AI 安全助手"
        @click="onAvatarClick"
        @mousedown.prevent="onMouseDown"
        @touchstart.prevent="onTouchStart"
      >
        <el-icon><MagicStick /></el-icon>
      </button>
    </div>

    <el-dialog v-model="showCreateDialog" title="新建安全项目" width="min(440px, calc(100vw - 32px))" destroy-on-close>
      <el-form label-position="top" @submit.prevent="createProject">
        <el-form-item label="项目名称" required>
          <el-input v-model.trim="projectName" maxlength="200" show-word-limit placeholder="例如 payment-service" @keyup.enter="createProject" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" :disabled="!projectName" @click="createProject">创建项目</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRenameDialog" title="重命名项目" width="min(440px, calc(100vw - 32px))" destroy-on-close>
      <el-form label-position="top" @submit.prevent="renameProject">
        <el-form-item label="项目名称" required>
          <el-input v-model.trim="renameName" maxlength="200" show-word-limit placeholder="例如 payment-service" @keyup.enter="renameProject" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" :loading="renaming" :disabled="!renameName || renameName === renameTarget?.name" @click="renameProject">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showUploadDialog" title="上传 ZIP 项目包" width="min(560px, calc(100vw - 32px))" destroy-on-close @closed="resetUpload">
      <el-alert type="warning" :closable="false" show-icon>
        <template #title>系统不会执行压缩包内的代码</template>
        仅提取允许的 UTF-8 源码、配置和依赖清单用于静态分析。压缩包受大小、解压体积、文件数和路径安全限制约束。
      </el-alert>
      <el-form label-position="top" class="upload-form" @submit.prevent="submitScan">
        <el-form-item label="目标项目">
          <el-input :model-value="selectedProject?.name || ''" disabled />
        </el-form-item>
        <el-form-item label="ZIP 项目包" required>
          <input ref="archiveInput" data-test="archive-input" class="native-file-input" type="file" accept=".zip,application/zip" @change="onArchiveSelected" />
          <p class="file-help">仅支持 .zip。浏览器限制仅用于体验，后端会再次校验压缩包安全性。</p>
          <p v-if="selectedArchive" class="selected-file">已选择：{{ selectedArchive.name }}</p>
        </el-form-item>
        <el-alert v-if="uploadError" :title="uploadError" type="error" show-icon :closable="false" />
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="showUploadDialog = false">取消</el-button>
        <el-button data-test="submit-scan" type="primary" :loading="submitting" :disabled="!selectedArchive" @click="submitScan">开始受控扫描</el-button>
      </template>
    </el-dialog>

    <GitHubImportDialog
      v-model="showGitHubImportDialog"
      :projects="projects"
      :initial-project-id="githubImportProjectId"
      :loading="githubImportLoading"
      :error="githubImportError"
      @submit="handleGitHubImport"
    />
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from '@/features/security/feedback'
import { MagicStick, Refresh, Search } from '@element-plus/icons-vue'
import { securityAPI } from '@/api'
import GitHubImportDialog from '@/components/security/import/GitHubImportDialog.vue'
import ProjectCard from '@/components/security/project/ProjectCard.vue'
import ProjectVulnPanel from '@/components/security/project/ProjectVulnPanel.vue'
import RecentScanList from '@/components/security/project/RecentScanList.vue'
import WorkbenchOverviewCards from '@/components/security/project/WorkbenchOverviewCards.vue'
import { useProjectImport } from '@/composables/security/useProjectImport'
import { useFabDrag } from '@/composables/security/useFabDrag'
import { securityApiErrorMessage } from '@/features/security/presentation'
import { GithubIcon } from '@/components/icons'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const creating = ref(false)
const submitting = ref(false)
const pageError = ref('')
const uploadError = ref('')
const projects = ref([])
const overview = ref({ totals: { critical: 0, high: 0, medium: 0 }, totalProjects: 0, totalScans: 0, recentScans: [] })
const projectName = ref('')
const showCreateDialog = ref(false)
const showRenameDialog = ref(false)
const renameTarget = ref(null)
const renameName = ref('')
const renaming = ref(false)
const showUploadDialog = ref(false)
const showGitHubImportDialog = ref(false)
const selectedProject = ref(null)
const selectedArchive = ref(null)
const archiveInput = ref(null)
const githubImportProjectId = ref(null)
const searchText = ref('')
const statusFilter = ref('all')
const expandedProjectId = ref(null)
const panelFindings = ref([])
const panelLoading = ref(false)
const {
  githubImportLoading,
  githubImportError,
  resetGitHubImport,
  importGitHubSnapshot
} = useProjectImport()

const RUNNING_STATUSES = new Set(['created', 'validating', 'snapshotting', 'scanning'])

const aiRiskCount = computed(
  () => (overview.value.totals.critical || 0) + (overview.value.totals.high || 0)
)

const {
  fabEl,
  isDragging,
  didDrag,
  fabStyle,
  onMouseDown,
  onTouchStart
} = useFabDrag()

const onAvatarClick = () => {
  if (didDrag.value) return
  router.push('/qa')
}

const filteredProjects = computed(() => {
  let items = projects.value
  if (searchText.value) {
    const keyword = searchText.value.toLowerCase()
    items = items.filter((project) => {
      const name = (project.name || '').toLowerCase()
      const description = (project.description || '').toLowerCase()
      return name.includes(keyword) || description.includes(keyword)
    })
  }
  if (statusFilter.value === 'running') {
    items = items.filter((project) => RUNNING_STATUSES.has(project.scan_status))
  } else if (statusFilter.value === 'done') {
    items = items.filter((project) => ['completed', 'completed_with_warnings'].includes(project.scan_status))
  } else if (statusFilter.value === 'none') {
    items = items.filter((project) => !project.scan_status)
  }
  return items
})

const loadAll = async () => {
  loading.value = true
  pageError.value = ''
  try {
    const [projectsResponse, overviewResponse] = await Promise.all([
      securityAPI.listProjects(),
      securityAPI.getWorkbenchOverview()
    ])
    projects.value = projectsResponse.data?.items || projectsResponse.items || []
    const payload = overviewResponse.data || overviewResponse
    overview.value = {
      totals: payload.totals || { critical: 0, high: 0, medium: 0 },
      totalProjects: payload.total_projects ?? payload.totalProjects ?? 0,
      totalScans: payload.total_scans ?? payload.totalScans ?? 0,
      recentScans: payload.recent_scans || []
    }
  } catch (error) {
    pageError.value = securityApiErrorMessage(error, '加载安全工作台失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

const createProject = async () => {
  if (!projectName.value || creating.value) return

  creating.value = true
  try {
    const response = await securityAPI.createProject({ name: projectName.value })
    projects.value.unshift(response.data?.project || response.project)
    projectName.value = ''
    showCreateDialog.value = false
    ElMessage.success('安全项目已创建')
    openUpload(response.data?.project || response.project)
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '创建项目失败'))
  } finally {
    creating.value = false
  }
}

const togglePanel = async (project) => {
  if (expandedProjectId.value === project.id) {
    expandedProjectId.value = null
    return
  }
  expandedProjectId.value = project.id
  panelFindings.value = []
  panelLoading.value = true
  try {
    if (!project.latest_task_id) {
      panelFindings.value = []
      return
    }
    const response = await securityAPI.getFindings(project.latest_task_id, { limit: 50 })
    panelFindings.value = response.data?.items || response.items || []
  } catch (error) {
    panelFindings.value = []
    ElMessage.error(securityApiErrorMessage(error, '加载漏洞详情失败'))
  } finally {
    panelLoading.value = false
  }
}

const openProject = (projectId) => router.push(`/security/projects/${projectId}`)

const openRename = (project) => {
  renameTarget.value = project
  renameName.value = project.name
  showRenameDialog.value = true
}

const renameProject = async () => {
  if (!renameTarget.value || !renameName.value || renaming.value) return
  renaming.value = true
  try {
    const response = await securityAPI.updateProject(renameTarget.value.id, { name: renameName.value })
    const updated = response.data?.project || response.project
    const index = projects.value.findIndex((project) => project.id === updated.id)
    if (index !== -1) projects.value.splice(index, 1, { ...projects.value[index], ...updated })
    showRenameDialog.value = false
    ElMessage.success('项目已重命名')
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '重命名项目失败'))
  } finally {
    renaming.value = false
  }
}

const confirmRemove = async (project) => {
  try {
    await ElMessageBox.confirm(
      `确定删除项目「${project.name}」吗？其全部快照、扫描任务和风险发现将被一并删除，且无法恢复。`,
      '删除项目',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }
  try {
    await securityAPI.deleteProject(project.id)
    projects.value = projects.value.filter((item) => item.id !== project.id)
    if (expandedProjectId.value === project.id) expandedProjectId.value = null
    ElMessage.success('项目已删除')
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '删除项目失败'))
  }
}

const openScan = (scan) => router.push(`/security/projects/${scan.project_id}`)

const openUpload = (project) => {
  selectedProject.value = project
  uploadError.value = ''
  showUploadDialog.value = true
}

const openGitHubImport = (project = null) => {
  githubImportProjectId.value = project?.id ?? projects.value[0]?.id ?? null
  resetGitHubImport()
  showGitHubImportDialog.value = true
}

const handleGitHubImport = async ({ projectId, repositoryUrl }) => {
  const result = await importGitHubSnapshot(projectId, repositoryUrl)
  if (!result) return

  ElMessage.success(`已创建 GitHub 快照与扫描任务 #${result.task.id}`)
  showGitHubImportDialog.value = false
  openProject(projectId)
}

const onArchiveSelected = (event) => {
  uploadError.value = ''
  const [file] = event.target.files || []
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.zip')) {
    selectedArchive.value = null
    uploadError.value = '请选择 ZIP 项目压缩包。'
    event.target.value = ''
    return
  }
  selectedArchive.value = file
}

const submitScan = async () => {
  if (!selectedProject.value || !selectedArchive.value || submitting.value) return

  submitting.value = true
  uploadError.value = ''
  try {
    const formData = new FormData()
    formData.append('archive', selectedArchive.value)
    const response = await securityAPI.uploadSnapshot(selectedProject.value.id, formData)
    ElMessage.success(`扫描任务 #${response.data?.task?.id ?? response.task.id} 已创建`)
    showUploadDialog.value = false
    openProject(selectedProject.value.id)
  } catch (error) {
    uploadError.value = securityApiErrorMessage(error, '上传或创建扫描任务失败。')
  } finally {
    submitting.value = false
  }
}

const resetUpload = () => {
  selectedProject.value = null
  selectedArchive.value = null
  uploadError.value = ''
  if (archiveInput.value) archiveInput.value.value = ''
}

const handleQueryAction = () => {
  if (route.query.action === 'new') {
    showCreateDialog.value = true
  } else if (route.query.action === 'import') {
    openGitHubImport()
  }
}

onMounted(async () => {
  await loadAll()
  handleQueryAction()
})
</script>

<style scoped lang="scss">
.security-page {
  width: 100%;
  box-sizing: border-box;
  padding: 28px 32px 48px;
}

.page-title {
  h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    color: #0f172a;
  }
}

.page-alert {
  margin-top: 16px;
}

.project-section {
  margin-top: 18px;
  min-height: 120px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;

  .toolbar-title {
    display: flex;
    align-items: center;
    gap: 10px;

    h2 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: #0f172a;
    }

    .count-badge {
      font-size: 12px;
      font-weight: 500;
      color: #2563eb;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 999px;
      padding: 2px 10px;
    }
  }

  .toolbar-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
}

.search-box {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 240px;
  height: 33px;
  padding: 0 11px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  transition: border-color 0.15s, box-shadow 0.15s;

  &:focus-within {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  }

  .search-icon {
    font-size: 14px;
    color: #94a3b8;
  }

  input {
    border: none;
    outline: none;
    flex: 1;
    font-size: 13px;
    color: #0f172a;
    background: transparent;
    min-width: 0;

    &::placeholder {
      color: #94a3b8;
    }
  }
}

.filter-select {
  width: 130px;

  :deep(.el-select__wrapper) {
    min-height: 33px;
    border-radius: 6px;
  }
}

.project-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.no-result {
  margin-top: 24px;
  text-align: center;
  color: #94a3b8;
  padding: 40px 0;
  font-size: 13px;
}

.empty-actions {
  display: flex;
  gap: 10px;
}

.upload-form {
  margin-top: 18px;
}

.native-file-input {
  display: block;
  width: 100%;
  padding: 10px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
}

.file-help {
  margin: 8px 0 0;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.5;
}

.selected-file {
  color: #16a34a;
  font-size: 13px;
}

.ai-fab {
  position: fixed;
  left: 0;
  top: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  cursor: grab;
  touch-action: none;

  &.is-dragging {
    cursor: grabbing;
    user-select: none;

    .ai-bubble {
      visibility: hidden;
    }
  }

  .ai-bubble {
    max-width: 320px;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px 12px 4px 12px;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
    padding: 12px 14px;
    font-size: 12.5px;
    color: #475569;
    line-height: 1.65;
    pointer-events: none;

    b {
      color: #dc2626;
    }
  }

  .ai-avatar {
    width: 42px;
    height: 42px;
    min-width: 42px;
    min-height: 42px;
    border-radius: 50%;
    border: none;
    background: #2563eb;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
    transition: transform 0.15s ease;
    flex-shrink: 0;

    &:hover {
      transform: scale(1.06);
    }
  }
}

@media (max-width: 720px) {
  .security-page {
    padding: 20px 16px;
  }

  .search-box {
    width: 100%;
  }
}
</style>
