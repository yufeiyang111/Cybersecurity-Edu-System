<template>
  <section class="content-card">
    <div class="card-head">
      <h2>项目快照</h2>
      <span class="note">快照为只读代码基线，删除后关联任务与风险发现一并移除</span>
    </div>
    <div v-if="loading" class="table-skeleton">
      <el-skeleton :rows="3" animated />
    </div>
    <el-empty v-else-if="snapshots.length === 0" description="该项目还没有代码快照。" />
    <div v-else class="table-wrap">
      <el-table :data="snapshots" class="snapshot-table">
        <el-table-column label="快照" min-width="90">
          <template #default="{ row }">
            <span class="mono">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.source_type === 'github' ? 'primary' : 'info'">
              {{ row.source_type === 'github' ? 'GitHub' : 'ZIP 上传' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="文件数" min-width="90">
          <template #default="{ row }">
            <span class="num-text">{{ row.file_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="任务数" min-width="90">
          <template #default="{ row }">
            <span class="num-text">{{ row.task_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="160">
          <template #default="{ row }">
            <span class="time">{{ formatSecurityDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="100">
          <template #default="{ row }">
            <el-tooltip content="删除快照及其任务与风险发现" placement="top">
              <el-button
                text
                type="danger"
                :icon="DeleteIcon"
                :loading="loadingFor(row.id)"
                :aria-label="`删除快照 ${row.id}`"
                @click="emit('delete-snapshot', row)"
              >
                删除
              </el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { Delete as DeleteIcon } from '@element-plus/icons-vue'
import { formatSecurityDate } from '@/features/security/presentation'

const props = defineProps({
  snapshots: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  actionLoading: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['delete-snapshot'])

const loadingFor = (snapshotId) => Boolean(props.actionLoading[snapshotId])
</script>

<style scoped lang="scss">
.content-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  margin-top: 8px;
  padding: 14px 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.card-head h2 {
  margin: 0;
  color: #1f2d3d;
  font-size: 15px;
  font-weight: 600;
}

.card-head .note {
  color: #6a7890;
  font-size: 12.5px;
}

.table-wrap {
  overflow-x: auto;
}

.table-skeleton {
  padding: 8px 4px 4px;
}

.snapshot-table {
  min-width: 640px;
}

.snapshot-table :deep(th.el-table__cell) {
  background: #fafbfd;
  color: #6a7890;
  font-size: 12.5px;
  font-weight: 600;
}

.snapshot-table :deep(td.el-table__cell) {
  padding: 9px 0;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #37465c;
  font-weight: 600;
}

.num-text {
  color: #37465c;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.time {
  color: #8494a8;
  font-size: 12.5px;
}

@media (max-width: 760px) {
  .content-card {
    padding: 12px;
  }

  .card-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
