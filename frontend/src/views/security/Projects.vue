<template>
  <main class="security-page">
    <section class="hero">
      <div>
        <p class="eyebrow">CYBERGUARD SECURITY WORKBENCH</p>
        <h1>项目安全工作台</h1>
        <p>上传 ZIP 项目包后，系统只做受控静态分析：不会安装、构建或执行你的项目代码。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">新建项目</el-button>
    </section>

    <section class="security-boundary">
      <el-icon><Connection /></el-icon>
      <div>
        <strong>安全边界</strong>
        <span>当前支持 Python 基线规则：命令注入、危险 YAML 反序列化、Flask Debug 与硬编码敏感信息检测。</span>
      </div>
    </section>

    <el-alert v-if="pageError" :title="pageError" type="error" show-icon :closable="false" class="page-alert" />

    <section class="projects-section" v-loading="loading">
      <div class="section-heading">
        <div>
          <h2>我的项目</h2>
          <p>每次上传均创建独立快照和可追溯扫描任务。</p>
        </div>
        <el-button text type="primary" :icon="Refresh" @click="loadProjects">刷新</el-button>
      </div>

      <el-empty v-if="!loading && projects.length === 0" description="还没有安全项目，先创建一个项目开始扫描。">
        <el-button type="primary" @click="showCreateDialog = true">新建项目</el-button>
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
            <el-button type="primary" @click="openUpload(project)">上传 ZIP 扫描</el-button>
          </div>
        </article>
      </div>
    </section>

    <el-dialog v-model="showCreateDialog" title="新建安全项目" width="440px" destroy-on-close>
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

    <el-dialog v-model="showUploadDialog" title="上传 ZIP 项目包" width="560px" destroy-on-close @closed="resetUpload">
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
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { FolderOpened, Plus, Refresh } from '@element-plus/icons-vue'
import { securityAPI } from '@/api'

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
const selectedProject = ref(null)
const selectedArchive = ref(null)
const archiveInput = ref(null)

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
    router.push(`/security/projects/${selectedProject.value.id}`)
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
.security-page { min-height: 100vh; padding: 40px clamp(20px, 4vw, 64px); background: #f5f7fb; color: #182230; }
.hero { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; max-width: 1200px; margin: 0 auto 20px; }
.eyebrow { margin: 0 0 8px; color: #147d64; font-size: 12px; letter-spacing: .12em; font-weight: 700; }
h1 { margin: 0; font-size: clamp(30px, 4vw, 42px); } .hero p:not(.eyebrow) { color: #5c687a; line-height: 1.7; max-width: 720px; }
.security-boundary { max-width: 1200px; margin: 0 auto 28px; display: flex; gap: 12px; padding: 16px 18px; border: 1px solid #b7ead7; border-radius: 12px; background: #effcf6; color: #155c48; }
.security-boundary .el-icon { font-size: 22px; margin-top: 2px; } .security-boundary strong, .security-boundary span { display: block; } .security-boundary span { margin-top: 4px; color: #36715f; line-height: 1.5; }
.projects-section { max-width: 1200px; min-height: 280px; margin: 0 auto; padding: 28px; background: #fff; border: 1px solid #e7eaf0; border-radius: 16px; box-shadow: 0 10px 30px rgba(20, 33, 61, .06); }
.section-heading { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:24px; } .section-heading h2 { margin:0; font-size:20px; } .section-heading p { margin:7px 0 0; color:#778397; }
.project-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:16px; }.project-card { border:1px solid #e5e9f1; border-radius:12px; padding:20px; background:#fff; }.project-card__header { display:flex; gap:12px; min-height:86px; }.project-icon { flex:0 0 auto; font-size:27px; color:#1976d2; margin-top:2px; }.project-card h3 { margin:0; font-size:17px; }.project-card p { margin:7px 0 0; color:#788496; line-height:1.5; }.project-card__actions { display:flex; gap:8px; justify-content:flex-end; margin-top:18px; }
.upload-form { margin-top:18px; }.native-file-input { display:block; width:100%; padding:10px; border:1px dashed #9caabd; border-radius:8px; background:#fafbfd; }.file-help { margin:8px 0 0; color:#778397; font-size:12px; line-height:1.5; }.selected-file { color:#23725e; font-size:13px; }.page-alert { max-width:1200px; margin:0 auto 16px; }
@media (max-width: 680px) { .hero { flex-direction:column; }.projects-section { padding:18px; }.project-card__actions { flex-wrap:wrap; justify-content:flex-start; } }
</style>
