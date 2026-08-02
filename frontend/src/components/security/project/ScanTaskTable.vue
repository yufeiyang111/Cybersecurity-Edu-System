<template>
  <section class="content-card">
    <div class="section-heading">
      <div>
        <p class="section-eyebrow">SNAPSHOT SCANS</p>
        <h2>扫描任务</h2>
        <p>进行中的任务自动刷新；选择任务查看快照风险与依赖。</p>
      </div>
    </div>
    <div v-if="loading" class="table-skeleton">
      <el-skeleton :rows="3" animated />
    </div>
    <el-empty v-else-if="tasks.length === 0" description="该项目还没有扫描记录。" />
    <div v-else class="table-wrap">
      <el-table :data="tasks" class="task-table" :row-class-name="rowClassName">
        <el-table-column label="任务" min-width="92"><template #default="{ row }">#{{ row.id }}</template></el-table-column>
        <el-table-column label="快照" min-width="100"><template #default="{ row }">#{{ row.snapshot_id }}</template></el-table-column>
        <el-table-column label="状态" min-width="150"><template #default="{ row }"><ScanStatusTag :status="row.status" /></template></el-table-column>
        <el-table-column label="检测语言" min-width="190">
          <template #default="{ row }">
            <div v-if="languagesFor(row).length" class="language-tags">
              <el-tag v-for="language in languagesFor(row)" :key="language" size="small" effect="plain">{{ language }}</el-tag>
            </div>
            <span v-else class="muted-value">未识别</span>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="160"><template #default="{ row }"><el-progress :percentage="row.progress || 0" :status="row.status === 'failed' ? 'exception' : undefined" /></template></el-table-column>
        <el-table-column label="创建时间" min-width="180"><template #default="{ row }">{{ formatSecurityDate(row.created_at) }}</template></el-table-column>
        <el-table-column label="操作" min-width="220">
          <template #default="{ row }">
            <div class="task-actions">
              <el-button text type="primary" @click="emit('select-task', row.id)">{{ row.id === selectedTaskId ? '当前任务' : '查看风险' }}</el-button>
              <el-tooltip v-if="canCancel(row)" content="取消未完成的扫描任务" placement="top">
                <el-button
                  text
                  type="warning"
                  :icon="Close"
                  :loading="loadingFor(row, 'cancel')"
                  :aria-label="`取消任务 ${row.id}`"
                  @click="emit('cancel-task', row)"
                />
              </el-tooltip>
              <el-tooltip v-if="canRetry(row)" content="重新派发失败或已取消的任务" placement="top">
                <el-button
                  text
                  type="success"
                  :icon="Refresh"
                  :loading="loadingFor(row, 'retry')"
                  :aria-label="`重试任务 ${row.id}`"
                  @click="emit('retry-task', row)"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { Close, Refresh } from '@element-plus/icons-vue'
import ScanStatusTag from '@/components/security/ScanStatusTag.vue'
import { formatSecurityDate } from '@/features/security/presentation'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  selectedTaskId: { type: [Number, String], default: null },
  actionLoading: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['select-task', 'cancel-task', 'retry-task'])

const terminalStatuses = new Set(['completed', 'completed_with_warnings', 'failed', 'canceled'])
const languagesFor = (task) => {
  const languages = task?.summary?.languages
  return Array.isArray(languages) ? languages : []
}
const canCancel = (task) => task?.can_cancel ?? !terminalStatuses.has(task?.status)
const canRetry = (task) => task?.can_retry ?? ['failed', 'canceled'].includes(task?.status)
const loadingFor = (task, action) => Boolean(props.actionLoading[`${action}:${task.id}`])
const rowClassName = ({ row }) => row.id === props.selectedTaskId ? 'task-table__selected-row' : ''
</script>

<style scoped lang="scss">
.content-card { max-width: 1200px; margin: 18px auto 0; padding: 24px; border: 1px solid #d9e2ec; border-radius: 16px; background: #fff; box-shadow: 0 10px 24px rgba(16, 42, 67, .04); }
.section-eyebrow { margin: 0 0 6px; color: #0e9384; font-size: 11px; font-weight: 700; letter-spacing: .09em; }
.section-heading h2 { margin: 0; color: #102a43; font-size: 19px; }
.section-heading p:last-child { margin: 7px 0 20px; color: #627d98; line-height: 1.6; }
.table-wrap { overflow-x: auto; }
.table-skeleton { padding: 8px 4px 4px; }
.task-table { min-width: 980px; }
.task-actions { display: flex; align-items: center; gap: 4px; }
.language-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.muted-value { color: #829ab1; font-size: 13px; }
:deep(.task-table__selected-row > td.el-table__cell) { background: #eefcf7 !important; }
@media (max-width: 760px) { .content-card { padding: 16px; }.task-table { font-size: 12px; } }
</style>