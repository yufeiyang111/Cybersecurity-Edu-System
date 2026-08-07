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
            <el-tooltip
              v-if="languagesFor(row).length"
              :content="languagesFor(row).join('、')"
              :disabled="!hasLanguageOverflow(row)"
              placement="top"
            >
              <div class="language-tags" :aria-label="`支持语言：${languagesFor(row).join('、')}`">
                <el-tag
                  v-for="language in visibleLanguagesFor(row)"
                  :key="language"
                  class="language-tag"
                  size="small"
                  effect="plain"
                >
                  {{ language }}
                </el-tag>
                <el-tag v-if="hasLanguageOverflow(row)" class="language-more" size="small" effect="plain">
                  +{{ languagesFor(row).length - visibleLanguagesFor(row).length }}
                </el-tag>
              </div>
            </el-tooltip>
            <span v-else class="muted-value">未识别</span>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="110"><template #default="{ row }"><span class="progress-text" :class="{ 'progress-text--err': row.status === 'failed' }">{{ row.progress || 0 }}%</span></template></el-table-column>
        <el-table-column label="创建时间" min-width="160"><template #default="{ row }"><span class="time">{{ formatSecurityDate(row.created_at) }}</span></template></el-table-column>
        <el-table-column label="操作" min-width="180">
          <template #default="{ row }">
            <div class="task-actions">
              <el-button
                text
                type="primary"
                class="task-action task-action--view"
                :class="{ 'task-action--current': row.id === selectedTaskId }"
                @click="emit('select-task', row.id)"
              >
                {{ row.id === selectedTaskId ? '当前任务' : '查看风险' }}
              </el-button>
              <el-tooltip v-if="canCancel(row)" content="取消未完成的扫描任务" placement="top">
                <el-button
                  class="task-action task-action--icon"
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
                  class="task-action task-action--icon"
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
                  class="task-action task-action--icon task-action--delete"
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
const visibleLanguagesFor = (task) => languagesFor(task).slice(0, 2)
const hasLanguageOverflow = (task) => languagesFor(task).length > visibleLanguagesFor(task).length
const canCancel = (task) => task?.can_cancel ?? !terminalStatuses.has(task?.status)
const canRetry = (task) => task?.can_retry ?? ['failed', 'canceled'].includes(task?.status)
const canDelete = (task) => terminalStatuses.has(task?.status)
const loadingFor = (task, action) => Boolean(props.actionLoading[`${action}:${task.id}`])
const rowClassName = ({ row }) => row.id === props.selectedTaskId ? 'task-table__selected-row' : ''
</script>

<style scoped lang="scss">
.content-card {
  margin-top: 14px;
  padding: 17px 18px;
  overflow: hidden;
  border: 1px solid #dfe6ef;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 3px 12px rgba(21, 40, 75, 0.04);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.content-card:hover {
  border-color: #c4d3e4;
  box-shadow: 0 10px 22px rgba(21, 40, 75, 0.08);
  transform: translateY(-1px);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.card-head h2 {
  margin: 0;
  color: #142238;
  font-size: 14px;
  font-weight: 700;
}

.card-head .note {
  color: #7e8da3;
  font-size: 11px;
}

.table-wrap {
  overflow-x: auto;
}

.table-skeleton {
  padding: 8px 4px 4px;
}

.task-table {
  min-width: 900px;
}

.task-table :deep(th.el-table__cell) {
  color: #7e8da3;
  background: #fbfcfe;
  font-size: 11px;
  font-weight: 700;
}

.task-table :deep(td.el-table__cell) {
  padding: 10px 0;
}

.task-table :deep(.el-table__row) {
  transition: background 0.18s ease;
}

.task-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #f8faff;
}

.mono {
  color: #142238;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 650;
}

.snap-tag {
  padding: 2px 8px;
  border-radius: 4px;
  color: #52627a;
  background: #eef3f9;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.progress-text {
  color: #37465c;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.progress-text--err {
  color: #c94343;
}

.time {
  color: #7e8da3;
  font-size: 11.5px;
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.task-actions :deep(.task-action) {
  min-height: 28px;
  height: 28px;
  margin-left: 0;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #2563eb;
  background: transparent;
  font-family: inherit;
  font-size: 13px;
  font-weight: 400;
  line-height: 1;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.task-actions :deep(.task-action--view:hover) {
  border-color: #bfdbfe;
  color: #1d4ed8;
  background: #eff6ff;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.08);
  transform: translateY(-1px);
}

.task-actions :deep(.task-action--current) {
  border-color: #bfdbfe;
  color: #2563eb;
  background: #eff6ff;
}

.task-actions :deep(.task-action--icon) {
  width: 28px;
  padding: 0;
}

.task-actions :deep(.task-action--icon:hover) {
  border-color: #bfdbfe;
  color: #1d4ed8;
  background: #eff6ff;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.08);
  transform: translateY(-1px);
}

.task-actions :deep(.task-action--delete) {
  color: #d9363e;
}

.task-actions :deep(.task-action--delete:hover) {
  border-color: #fecaca;
  color: #c62832;
  background: #fff1f1;
  box-shadow: 0 4px 10px rgba(201, 67, 67, 0.08);
}

.task-actions :deep(.task-action .el-icon) {
  font-size: 15px;
}

.language-tags {
  display: flex;
  min-width: 0;
  max-width: 230px;
  align-items: center;
  gap: 5px;
  overflow: hidden;
}

.language-tags :deep(.el-tag) {
  min-width: 0;
  border-color: #dfe6ef;
  color: #52627a;
  background: #f5f7fa;
}

.language-tags :deep(.language-tag) {
  max-width: 132px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.language-tags :deep(.language-more) {
  flex: 0 0 auto;
  color: #2563eb;
  background: #eff6ff;
}

.muted-value {
  color: #9aa7b8;
  font-size: 13px;
}

:deep(.task-table__selected-row > td.el-table__cell) {
  background: #eff6ff !important;
}

:deep(.task-table__selected-row > td.el-table__cell:first-child) {
  box-shadow: inset 3px 0 0 #2563eb;
}

@media (max-width: 760px) {
  .content-card {
    padding: 13px 12px;
  }

  .card-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
