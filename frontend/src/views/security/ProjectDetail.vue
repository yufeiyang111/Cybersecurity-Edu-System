<template>
  <main class="detail-page" v-loading="loading">
    <header class="detail-header">
      <div>
        <el-button text :icon="ArrowLeft" @click="router.push('/security/projects')">返回项目中心</el-button>
        <h1>{{ project?.name || '项目安全概览' }}</h1>
        <p>扫描记录仅展示脱敏证据；原始项目文件不会通过页面公开。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="alert" />

    <section class="summary-grid">
      <article class="summary-card"><span>扫描任务</span><strong>{{ tasks.length }}</strong></article>
      <article class="summary-card"><span>已完成</span><strong>{{ completedTaskCount }}</strong></article>
      <article class="summary-card"><span>风险发现</span><strong>{{ findings.length }}</strong></article>
      <article class="summary-card"><span>高危及以上</span><strong class="risk-number">{{ highRiskCount }}</strong></article>
    </section>

    <section class="content-card">
      <div class="section-heading"><div><h2>扫描任务</h2><p>进行中的任务会自动刷新，离开页面即停止轮询。</p></div></div>
      <el-empty v-if="!loading && tasks.length === 0" description="该项目还没有扫描记录。" />
      <el-table v-else :data="tasks" class="task-table">
        <el-table-column label="任务" width="100"><template #default="{ row }">#{{ row.id }}</template></el-table-column>
        <el-table-column label="状态" width="160"><template #default="{ row }"><ScanStatusTag :status="row.status" /></template></el-table-column>
        <el-table-column label="进度" min-width="160"><template #default="{ row }"><el-progress :percentage="row.progress || 0" :status="row.status === 'failed' ? 'exception' : undefined" /></template></el-table-column>
        <el-table-column label="创建时间" min-width="180"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
        <el-table-column label="操作" width="110"><template #default="{ row }"><el-button text type="primary" @click="loadFindings(row.id)">查看风险</el-button></template></el-table-column>
      </el-table>
    </section>

    <section class="content-card">
      <div class="section-heading"><div><h2>风险概要</h2><p>{{ selectedTaskId ? `任务 #${selectedTaskId} 的证据化发现项` : '选择一条扫描任务查看发现项。' }}</p></div></div>
      <el-empty v-if="!loading && !selectedTaskId" description="请选择扫描任务" />
      <el-empty v-else-if="!loading && findings.length === 0" description="该任务未发现可展示的风险。" />
      <div v-else class="finding-list">
        <article v-for="finding in findings" :key="finding.id" class="finding-item">
          <div class="finding-topline"><FindingSeverityTag :severity="finding.severity" /><strong>{{ finding.rule_id }}</strong><code>{{ finding.file_path }}:{{ finding.start_line }}</code></div>
          <p>{{ finding.message }}</p>
          <div class="finding-meta"><span>{{ finding.cwe_id || '未映射 CWE' }}</span><span>{{ finding.category }}</span><span>置信度：{{ finding.confidence ?? '-' }}</span></div>
          <div v-if="finding.evidences?.length" class="evidence"><span>脱敏证据</span><code>{{ finding.evidences[0].content }}</code></div>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { securityAPI } from '@/api'
import ScanStatusTag from '@/components/security/ScanStatusTag.vue'
import FindingSeverityTag from '@/components/security/FindingSeverityTag.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const tasks = ref([])
const findings = ref([])
const selectedTaskId = ref(null)
const project = ref({ id: Number(route.params.id), name: `项目 #${route.params.id}` })
let pollTimer = null

const completedTaskCount = computed(() => tasks.value.filter((task) => ['completed', 'completed_with_warnings'].includes(task.status)).length)
const highRiskCount = computed(() => findings.value.filter((finding) => ['critical', 'high'].includes(finding.severity)).length)
const hasRunningTasks = computed(() => tasks.value.some((task) => !['completed', 'completed_with_warnings', 'failed', 'canceled'].includes(task.status)))

const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'

const loadFindings = async (taskId) => {
  selectedTaskId.value = taskId
  try {
    const response = await securityAPI.getFindings(taskId)
    findings.value = response.items || []
  } catch (error) {
    errorMessage.value = error.response?.data?.error || '加载风险发现项失败。'
  }
}

const syncPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
  if (hasRunningTasks.value) pollTimer = setInterval(load, 4000)
}

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await securityAPI.getTasks(route.params.id)
    tasks.value = response.items || []
    if (!selectedTaskId.value && tasks.value.length) await loadFindings(tasks.value[0].id)
    if (selectedTaskId.value && tasks.value.some((task) => task.id === selectedTaskId.value)) await loadFindings(selectedTaskId.value)
  } catch (error) {
    errorMessage.value = error.response?.data?.error || '加载扫描任务失败。'
  } finally {
    loading.value = false
    syncPolling()
  }
}

onMounted(load)
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped lang="scss">
.detail-page { min-height:100vh; padding:36px clamp(20px,4vw,64px); background:#f5f7fb; color:#182230; }.detail-header,.summary-grid,.content-card,.alert { max-width:1200px; margin-left:auto; margin-right:auto; }.detail-header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:24px; }.detail-header h1 { margin:8px 0; font-size:32px; }.detail-header p { margin:0; color:#6c7788; }.alert { margin-bottom:16px; }.summary-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:18px; }.summary-card { padding:20px; background:#fff; border:1px solid #e6eaf0; border-radius:12px; }.summary-card span { display:block; color:#718096; font-size:13px; }.summary-card strong { display:block; margin-top:8px; font-size:28px; }.risk-number { color:#d14343; }.content-card { margin-top:18px; padding:24px; border:1px solid #e6eaf0; border-radius:14px; background:#fff; }.section-heading h2 { margin:0; font-size:19px; }.section-heading p { color:#788496; margin:7px 0 20px; }.finding-list { display:grid; gap:12px; }.finding-item { padding:18px; border:1px solid #e7eaf0; border-radius:10px; }.finding-topline { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }.finding-topline code { color:#57647a; background:#f3f5f8; padding:3px 6px; border-radius:4px; }.finding-item p { margin:12px 0; line-height:1.6; }.finding-meta { display:flex; gap:10px; flex-wrap:wrap; color:#758197; font-size:12px; }.evidence { margin-top:14px; padding:10px; display:flex; gap:8px; align-items:flex-start; background:#fff8e6; border-radius:6px; font-size:13px; }.evidence span { white-space:nowrap; color:#8b651a; }.evidence code { overflow-wrap:anywhere; }
@media(max-width:760px){ .summary-grid{grid-template-columns:repeat(2,1fr)}.detail-header{flex-direction:column}.content-card{padding:16px}.task-table{font-size:12px} }
</style>
