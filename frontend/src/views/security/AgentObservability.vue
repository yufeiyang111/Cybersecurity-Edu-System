<template>
  <div class="obs-page">
    <header class="obs-head">
      <h1>Agent 运维</h1>
      <div class="obs-head__actions">
        <el-select v-model="days" size="small" style="width: 110px" @change="loadAll">
          <el-option label="近 7 天" :value="7" />
          <el-option label="近 30 天" :value="30" />
          <el-option label="近 90 天" :value="90" />
        </el-select>
        <el-button size="small" :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon class="obs-alert" />

    <template v-if="overview">
      <section class="obs-cards">
        <div class="obs-card">
          <span class="obs-card__label">运行总数</span>
          <span class="obs-card__value">{{ overview.run_counts.total }}</span>
          <span class="obs-card__sub">
            {{ statusSummary }}
          </span>
        </div>
        <div class="obs-card">
          <span class="obs-card__label">LLM 调用成本</span>
          <span class="obs-card__value">${{ overview.llm.total_cost.toFixed(4) }}</span>
          <span class="obs-card__sub">{{ overview.llm.total_tokens }} tokens</span>
        </div>
        <div class="obs-card">
          <span class="obs-card__label">待审批</span>
          <span class="obs-card__value" :class="{ 'obs-card__value--warn': overview.pending_approvals > 0 }">
            {{ overview.pending_approvals }}
          </span>
          <span class="obs-card__sub">审批队列</span>
        </div>
        <div class="obs-card">
          <span class="obs-card__label">观察结论</span>
          <span class="obs-card__value">{{ overview.observations }}</span>
          <span class="obs-card__sub">Deep Review 产出</span>
        </div>
      </section>

      <section class="obs-panels">
        <div class="obs-panel">
          <h2>运行状态分布</h2>
          <div v-if="!Object.keys(overview.run_counts.by_status).length" class="obs-empty">
            暂无运行
          </div>
          <el-table v-else :data="statusRows" size="small" border>
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="count" label="数量" width="120" />
          </el-table>
        </div>

        <div class="obs-panel">
          <h2>工具调用统计</h2>
          <div v-if="!overview.tools.tools.length" class="obs-empty">暂无工具调用</div>
          <el-table v-else :data="overview.tools.tools" size="small" border>
            <el-table-column prop="tool_name" label="工具" />
            <el-table-column prop="calls" label="调用" width="90" />
            <el-table-column prop="failed" label="失败" width="90">
              <template #default="{ row }">
                <span :class="{ 'obs-fail': row.failed > 0 }">{{ row.failed }}</span>
              </template>
            </el-table-column>
            <el-table-column label="失败率" width="90">
              <template #default="{ row }">
                {{ row.calls ? ((row.failed / row.calls) * 100).toFixed(1) : 0 }}%
              </template>
            </el-table-column>
            <el-table-column prop="latency_ms" label="平均延迟(ms)" width="120">
              <template #default="{ row }">
                {{ row.latency_ms != null ? row.latency_ms : '—' }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <section class="obs-panel">
        <h2>运行列表</h2>
        <el-table :data="runs" size="small" border>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="goal_text" label="目标" min-width="220" show-overflow-tooltip />
          <el-table-column label="状态" width="150">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              <el-tag v-if="row.approval_pending" size="small" type="warning" class="obs-run-approval">
                待审批
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Token" width="100">
            <template #default="{ row }">{{ row.total_tokens || 0 }}</template>
          </el-table-column>
          <el-table-column label="成本" width="110">
            <template #default="{ row }">${{ Number(row.total_cost || 0).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openRun(row.id)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { agentAPI, securityAPI } from '@/api'
import { agentStatusMeta } from '@/features/security/agent/statusMeta'
import { formatSecurityDate, securityApiErrorMessage } from '@/features/security/presentation'

const router = useRouter()
const workspaceId = ref(null)
const days = ref(7)
const overview = ref(null)
const runs = ref([])
const loading = ref(false)
const errorMessage = ref('')

const statusRows = computed(() =>
  Object.entries(overview.value?.run_counts?.by_status || {}).map(([status, count]) => ({
    status,
    count
  }))
)

const statusSummary = computed(() => {
  const byStatus = overview.value?.run_counts?.by_status || {}
  const completed = byStatus.completed || 0
  const failed = byStatus.failed || 0
  return `完成 ${completed} / 失败 ${failed}`
})

function statusLabel(status) {
  return agentStatusMeta(status)?.label || status
}

function statusTagType(status) {
  const meta = agentStatusMeta(status)
  if (meta?.tagType) return meta.tagType
  return 'info'
}

function formatTime(value) {
  return value ? formatSecurityDate(value) : ''
}

async function loadWorkspace() {
  try {
    const response = await securityAPI.getMyWorkspace()
    workspaceId.value = response.workspace?.id
  } catch (error) {
    errorMessage.value = securityApiErrorMessage(error, '加载工作区失败')
  }
}

async function loadAll() {
  if (!workspaceId.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    const [overviewResponse, runsResponse] = await Promise.all([
      agentAPI.getObservabilityOverview({
        workspace_id: workspaceId.value,
        days: days.value
      }),
      agentAPI.getObservabilityRuns({
        workspace_id: workspaceId.value,
        page: 1,
        page_size: 20
      })
    ])
    overview.value = overviewResponse.overview
    runs.value = runsResponse.items || []
  } catch (error) {
    errorMessage.value = securityApiErrorMessage(error, '加载运维数据失败')
  } finally {
    loading.value = false
  }
}

function openRun(runId) {
  router.push(`/security/agent-runs/${runId}`)
}

onMounted(async () => {
  await loadWorkspace()
  loadAll()
})
</script>

<style scoped lang="scss">
.obs-page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1200px;
  margin: 0 auto;
}

.obs-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.obs-head h1 {
  margin: 0;
  font-size: 18px;
}

.obs-head__actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.obs-alert {
  margin-bottom: 4px;
}

.obs-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.obs-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.obs-card__label {
  font-size: 12.5px;
  color: #6a7890;
}

.obs-card__value {
  font-size: 24px;
  font-weight: 700;
  color: #1f2d3d;
}

.obs-card__value--warn {
  color: #b45309;
}

.obs-card__sub {
  font-size: 12px;
  color: #a0aaba;
}

.obs-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.obs-panel {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 10px;
  padding: 14px 16px;
}

.obs-panel h2 {
  margin: 0 0 10px;
  font-size: 15px;
}

.obs-empty {
  color: #8494a8;
  font-size: 12.5px;
  padding: 12px 0;
  text-align: center;
}

.obs-fail {
  color: #dc2626;
  font-weight: 600;
}

.obs-run-approval {
  margin-left: 4px;
}

@media (max-width: 960px) {
  .obs-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .obs-panels {
    grid-template-columns: 1fr;
  }
}
</style>
