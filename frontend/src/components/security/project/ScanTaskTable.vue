<template>
  <section class="content-card">
    <div class="card-head">
      <h2>扫描任务</h2>
      <span class="note">进行中的任务自动刷新，选择任务查看对应快照</span>
    </div>
    <div v-if="loading" class="table-skeleton">
      <el-skeleton :rows="3" animated />
    </div>
    <el-empty v-else-if="tasks.length === 0" description="该项目还没有扫描记录。" />
    <div v-else class="table-wrap">
      <el-table :data="tasks" class="task-table" :row-class-name="rowClassName">
        <el-table-column label="任务" min-width="76"><template #default="{ row }"><span class="mono">#{{ row.id }}</span></template></el-table-column>
        <el-table-column label="快照" min-width="88"><template #default="{ row }"><span class="snap-tag">#{{ row.snapshot_id }}</span></template></el-table-column>
        <el-table-column label="状态" min-width="130"><template #default="{ row }"><ScanStatusTag :status="row.status" /></template></el-table-column>
        <el-table-column label="语言" min-width="170">
          <template #default="{ row }">
            <div v-if="languagesFor(row).length" class="language-tags">
              <el-tag v-for="language in languagesFor(row)" :key="language" size="small" effect="plain">{{ language }}</el-tag>
            </div>
            <span v-else class="muted-value">未识别</span>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="110"><template #default="{ row }"><span class="progress-text" :class="{ 'progress-text--err': row.status === 'failed' }">{{ row.progress || 0 }}%</span></template></el-table-column>
        <el-table-column label="创建时间" min-width="160"><template #default="{ row }"><span class="time">{{ formatSecurityDate(row.created_at) }}</span></template></el-table-column>
        <el-table-column label="操作" min-width="180">
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
              <el-tooltip v-if="canDelete(row)" content="删除已结束的任务及其风险发现" placement="top">
                <el-button
                  text
                  type="danger"
                  :icon="Delete"
                  :loading="loadingFor(row, 'delete')"
                  :aria-label="`删除任务 ${row.id}`"
                  @click="emit('delete-task', row)"
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
import { Close, Delete, Refresh } from '@element-plus/icons-vue'
import ScanStatusTag from '@/components/security/ScanStatusTag.vue'
import { formatSecurityDate } from '@/features/security/presentation'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  selectedTaskId: { type: [Number, String], default: null },
  actionLoading: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['select-task', 'cancel-task', 'retry-task', 'delete-task'])

const terminalStatuses = new Set(['completed', 'completed_with_warnings', 'failed', 'canceled'])
const languagesFor = (task) => {
  const languages = task?.summary?.languages
  return Array.isArray(languages) ? languages : []
}
const canCancel = (task) => task?.can_cancel ?? !terminalStatuses.has(task?.status)
const canRetry = (task) => task?.can_retry ?? ['failed', 'canceled'].includes(task?.status)
const canDelete = (task) => terminalStatuses.has(task?.status)
const loadingFor = (task, action) => Boolean(props.actionLoading[`${action}:${task.id}`])
const rowClassName = ({ row }) => row.id === props.selectedTaskId ? 'task-table__selected-row' : ''
</script>

<style scoped lang="scss">
.content-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; margin-top: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.card-head h2 { margin: 0; color: #1f2d3d; font-size: 15px; font-weight: 600; }
.card-head .note { color: #6a7890; font-size: 12.5px; }
.table-wrap { overflow-x: auto; }
.table-skeleton { padding: 8px 4px 4px; }
.task-table { min-width: 900px; }
.task-table :deep(th.el-table__cell) { background: #fafbfd; color: #6a7890; font-size: 12.5px; font-weight: 600; }
.task-table :deep(td.el-table__cell) { padding: 9px 0; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #37465c; font-weight: 600; }
.snap-tag { background: #eef3f9; color: #52627a; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.progress-text { color: #37465c; font-size: 13px; font-variant-numeric: tabular-nums; }
.progress-text--err { color: #d43b3b; }
.time { color: #8494a8; font-size: 12.5px; }
.task-actions { display: flex; align-items: center; gap: 4px; }
.language-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.language-tags :deep(.el-tag) { background: #f1f4f8; border-color: #e2e7ee; color: #52627a; }
.muted-value { color: #9aa7b8; font-size: 13px; }
:deep(.task-table__selected-row > td.el-table__cell) { background: #f2f8ff !important; }
@media (max-width: 760px) { .content-card { padding: 12px; }.card-head { flex-direction: column; align-items: flex-start; } }
</style>