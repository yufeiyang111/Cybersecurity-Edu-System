<template>
  <main class="security-page">
    <section class="hero">
      <div>
        <p class="eyebrow">CYBERGUARD SECURITY WORKBENCH</p>
        <h1>项目安全工作台</h1>
        <p>以项目快照为边界统一管理受控代码导入、静态扫描和人工审核；系统不会安装、构建或执行你的项目代码。</p>
      </div>
      <div class="hero-actions">
        <el-button plain @click="router.push('/security/knowledge')">安全知识治理</el-button>
        <el-button plain :icon="Link" @click="openGitHubImport()">从 GitHub 导入</el-button>
        <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">新建项目</el-button>
      </div>
    </section>

    <section class="security-boundary">
      <el-icon><Connection /></el-icon>
      <div>
        <strong>受控分析边界</strong>
        <span>支持 ZIP 上传和公开 GitHub 仓库快照导入。系统仅进行静态分析，不会克隆、安装依赖、构建或运行任何导入代码。</span>
      </div>
    </section>

    <el-alert v-if="pageError" :title="pageError" type="error" show-icon :closable="false" class="page-alert" />

    <section class="projects-section" v-loading="loading">
      <div class="section-heading">
        <div>
          <h2>我的项目</h2>
          <p>每次导入均创建独立快照和可追溯的扫描任务。</p>
        </div>
        <el-button text type="primary" :icon="Refresh" @click="loadProjects">刷新</el-button>
      </div>

      <el-empty v-if="!loading && projects.length === 0" description="还没有安全项目，先创建一个项目开始扫描。">
        <div class="empty-actions">
          <el-button type="primary" @click="showCreateDialog = true">新建项目</el-button>
          <el-button :icon="Link" @click="openGitHubImport()">从 GitHub 导入</el-button>
        </div>
      </el-empty>

      <div v-else class="project-grid">
        <article v-for="project in projects" :key="project.id" class="project-card">
          <div class="project-card__header">
            <el-icon class="project-icon"><FolderOpened /></el-icon>
            <div class="project-card__title">
              <h3>{{ project.name }}</h3>
              <p>{{ project.description || '尚未填写项目说明' }}</p>
            </div>
          </div>
          <div class="project-card__actions">
            <el-button @click="openProject(project.id)">查看任务</el-button>
            <el-button :icon="Link" @click="openGitHubImport(project)">GitHub 导入</el-button>
            <el-button type="primary" @click="openUpload(project)">上传 ZIP 扫描</el-button>
          </div>
        </article>
      </div>
    </section>

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
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Connection, FolderOpened, Link, Plus, Refresh } from '@element-plus/icons-vue'
import { securityAPI } from '@/api'
import GitHubImportDialog from '@/components/security/import/GitHubImportDialog.vue'
import { useProjectImport } from '@/composables/security/useProjectImport'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const submitting = ref(false)
const pageError = ref('')
const uploadError = ref('')
const projects = ref([])
const projectName = ref('')
const showCreateDialog = ref(false)
const showUploadDialog = ref(false)
const showGitHubImportDialog = ref(false)
const selectedProject = ref(null)
const selectedArchive = ref(null)
const archiveInput = ref(null)
const githubImportProjectId = ref(null)
const {
  githubImportLoading,
  githubImportError,
  resetGitHubImport,
  importGitHubSnapshot
} = useProjectImport()

const loadProjects = async () => {
  loading.value = true
  pageError.value = ''
  try {
    const response = await securityAPI.listProjects()
    projects.value = response.items || []
  } catch (error) {
    pageError.value = error.response?.data?.error || '加载安全项目失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

const createProject = async () => {
  if (!projectName.value || creating.value) return

  creating.value = true
  try {
    const response = await securityAPI.createProject({ name: projectName.value })
    projects.value.unshift(response.project)
    projectName.value = ''
    showCreateDialog.value = false
    ElMessage.success('安全项目已创建')
    openUpload(response.project)
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '创建项目失败')
  } finally {
    creating.value = false
  }
}

const openProject = (projectId) => router.push(`/security/projects/${projectId}`)

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
    ElMessage.success(`扫描任务 #${response.task.id} 已创建`)
    showUploadDialog.value = false
    openProject(selectedProject.value.id)
  } catch (error) {
    uploadError.value = error.response?.data?.error || '上传或创建扫描任务失败。'
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

onMounted(loadProjects)
</script>

<style scoped lang="scss">
.security-page { min-height: 100vh; padding: 40px clamp(20px, 4vw, 64px); background: #f6f8fb; color: #102a43; }
.hero { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; max-width: 1200px; margin: 0 auto 20px; }
.hero-actions, .empty-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.hero-actions { justify-content: flex-end; }
.eyebrow { margin: 0 0 8px; color: #0e9384; font-size: 12px; letter-spacing: .12em; font-weight: 700; }
h1 { margin: 0; font-size: clamp(30px, 4vw, 42px); letter-spacing: -.025em; }
.hero p:not(.eyebrow) { color: #486581; line-height: 1.7; max-width: 720px; }
.security-boundary { max-width: 1200px; margin: 0 auto 28px; display: flex; gap: 12px; padding: 16px 18px; border: 1px solid #b7ead7; border-radius: 14px; background: #effcf6; color: #155c48; }
.security-boundary .el-icon { font-size: 22px; margin-top: 2px; }
.security-boundary strong, .security-boundary span { display: block; }
.security-boundary span { margin-top: 4px; color: #36715f; line-height: 1.5; }
.projects-section { max-width: 1200px; min-height: 280px; margin: 0 auto; padding: 28px; background: #fff; border: 1px solid #d9e2ec; border-radius: 16px; box-shadow: 0 12px 30px rgba(16, 42, 67, .06); }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
.section-heading h2 { margin: 0; font-size: 20px; }
.section-heading p { margin: 7px 0 0; color: #627d98; }
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.project-card { border: 1px solid #d9e2ec; border-radius: 14px; padding: 20px; background: #fff; transition: box-shadow .2s ease, transform .2s ease; }
.project-card:hover { box-shadow: 0 10px 22px rgba(16, 42, 67, .08); transform: translateY(-2px); }
.project-card__header { display: flex; gap: 12px; min-height: 86px; }
.project-icon { flex: 0 0 auto; font-size: 27px; color: #0e9384; margin-top: 2px; }
.project-card h3 { margin: 0; font-size: 17px; }
.project-card p { margin: 7px 0 0; color: #627d98; line-height: 1.5; }
.project-card__actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; margin-top: 18px; }
.upload-form { margin-top: 18px; }
.native-file-input { display: block; width: 100%; padding: 10px; border: 1px dashed #9fb3c8; border-radius: 8px; background: #f8fbfc; }
.file-help { margin: 8px 0 0; color: #627d98; font-size: 12px; line-height: 1.5; }
.selected-file { color: #087f5b; font-size: 13px; }
.page-alert { max-width: 1200px; margin: 0 auto 16px; }
@media (max-width: 680px) {
  .hero { flex-direction: column; }
  .hero-actions { justify-content: flex-start; }
  .projects-section { padding: 18px; }
  .project-card__actions { justify-content: flex-start; }
}
</style>
