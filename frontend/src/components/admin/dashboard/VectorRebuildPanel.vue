<template>
  <div class="vector-rebuild-panel">
    <div class="vector-rebuild-panel__actions">
      <el-button
        type="primary"
        :loading="starting"
        :disabled="isRunning"
        @click="handleStart('vector')"
      >
        <el-icon>
          <Refresh />
        </el-icon>
        重建向量索引
      </el-button>
      <el-button
        type="success"
        :loading="starting"
        :disabled="isRunning"
        @click="handleStart('graph')"
      >
        <el-icon>
          <Share />
        </el-icon>
        仅重建知识图谱
      </el-button>
      <el-button
        type="warning"
        :loading="starting"
        :disabled="isRunning"
        @click="handleStart('all')"
      >
        <el-icon>
          <Refresh />
        </el-icon>
        重建全部索引（向量+图谱）
      </el-button>
      <el-button
        v-if="hasReport"
        type="info"
        plain
        @click="reportVisible = !reportVisible"
      >
        <el-icon>
          <DataAnalysis />
        </el-icon>
        {{ reportVisible ? '收起报告' : '查看重建报告' }}
      </el-button>
    </div>

    <!-- 运行中：真实进度条 -->
    <div v-if="isRunning" class="vector-rebuild-panel__progress">
      <div class="vector-rebuild-panel__progress-head">
        <span class="vector-rebuild-panel__progress-title">
          {{ status.message || '正在重建…' }}
        </span>
        <span class="vector-rebuild-panel__progress-percent">
          {{ progressPercent }}%
        </span>
      </div>
      <el-progress
        :percentage="progressPercent"
        :stroke-width="14"
        :status="progressStatus"
        :text-inside="true"
      />
      <div class="vector-rebuild-panel__progress-meta">
        <template v-if="isVectorStage">
          <span>已处理 {{ status.processed_docs || 0 }} / {{ status.total_docs || 0 }} 个文档</span>
          <span>已写入 {{ status.vector_count || 0 }} 个向量块</span>
        </template>
        <template v-else>
          <span>图谱构建 {{ status.graph_processed_docs || 0 }} / {{ status.total_docs || 0 }} 篇</span>
          <span>已产出 {{ status.graph_nodes || 0 }} 节点 / {{ status.graph_edges || 0 }} 边</span>
        </template>
      </div>
      <div v-if="recentProcessed.length" class="vector-rebuild-panel__progress-list">
        <div
          v-for="item in recentProcessed"
          :key="item.doc_id"
          class="vector-rebuild-panel__progress-item"
        >
          <el-tag size="small" type="success" effect="plain">{{ item.chunks }} 块</el-tag>
          <span class="vector-rebuild-panel__progress-item-title">{{ item.title }}</span>
        </div>
      </div>
    </div>

    <!-- 失败提示 -->
    <el-alert
      v-if="isError"
      :title="status.message || '重建失败'"
      type="error"
      show-icon
      :closable="false"
      class="vector-rebuild-panel__alert"
    />

    <!-- 量化报告 -->
    <div v-if="hasReport && reportVisible" class="vector-rebuild-panel__report">
      <div class="vector-rebuild-panel__report-grid">
        <div class="vector-rebuild-panel__report-item">
          <span class="vector-rebuild-panel__report-value">{{ status.total_docs || 0 }}</span>
          <span class="vector-rebuild-panel__report-label">重建文档数</span>
        </div>
        <div class="vector-rebuild-panel__report-item">
          <span class="vector-rebuild-panel__report-value">{{ status.vector_count || 0 }}</span>
          <span class="vector-rebuild-panel__report-label">向量块总数</span>
        </div>
        <div class="vector-rebuild-panel__report-item">
          <span class="vector-rebuild-panel__report-value">{{ avgChunksPerDoc }}</span>
          <span class="vector-rebuild-panel__report-label">平均每文档块数</span>
        </div>
        <div class="vector-rebuild-panel__report-item">
          <span class="vector-rebuild-panel__report-value">{{ status.chunks_per_doc_max || 0 }}</span>
          <span class="vector-rebuild-panel__report-label">单文档最多块数</span>
        </div>
        <div class="vector-rebuild-panel__report-item">
          <span class="vector-rebuild-panel__report-value">{{ status.graph_nodes || 0 }}</span>
          <span class="vector-rebuild-panel__report-label">图谱节点</span>
        </div>
        <div class="vector-rebuild-panel__report-item">
          <span class="vector-rebuild-panel__report-value">{{ status.graph_edges || 0 }}</span>
          <span class="vector-rebuild-panel__report-label">图谱关系</span>
        </div>
        <div class="vector-rebuild-panel__report-item">
          <span class="vector-rebuild-panel__report-value">{{ elapsedText }}</span>
          <span class="vector-rebuild-panel__report-label">耗时</span>
        </div>
        <div class="vector-rebuild-panel__report-item">
          <span
            class="vector-rebuild-panel__report-value"
            :class="{ 'vector-rebuild-panel__report-value--danger': failedCount > 0 }"
          >
            {{ failedCount }}
          </span>
          <span class="vector-rebuild-panel__report-label">失败文档</span>
        </div>
      </div>

      <div v-if="failedList.length" class="vector-rebuild-panel__failed">
        <div class="vector-rebuild-panel__failed-title">失败明细</div>
        <el-table :data="failedList" size="small" max-height="220">
          <el-table-column prop="id" label="文档ID" width="100" />
          <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
          <el-table-column prop="error" label="错误原因" min-width="220" show-overflow-tooltip />
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import { Refresh, DataAnalysis, Share } from '@element-plus/icons-vue'
import { adminAPI } from '@/api'
import { ElMessage } from 'element-plus'

const starting = ref(false)
const status = ref({})
const reportVisible = ref(false)
let pollTimer = null

const isRunning = computed(() => status.value.status === 'running')
const isError = computed(() => status.value.status === 'error')
const isVectorStage = computed(() => {
  if (status.value.mode === 'graph') return false
  if (status.value.mode === 'all') return status.value.stage !== 'graph'
  return true
})
const hasReport = computed(() =>
  status.value.status === 'success' || status.value.status === 'error'
)
const progressPercent = computed(() =>
  Math.min(Number(status.value.progress_percent || 0), 100)
)
const progressStatus = computed(() => {
  if (isError.value) return 'exception'
  return progressPercent.value >= 100 ? 'success' : 'active'
})
const recentProcessed = computed(() => status.value.recent_processed || [])
const failedList = computed(() => status.value.failed_docs || [])
const failedCount = computed(() => failedList.value.length)
const avgChunksPerDoc = computed(() =>
  status.value.chunks_per_doc_avg != null
    ? Number(status.value.chunks_per_doc_avg).toFixed(2)
    : '0.00'
)
const elapsedText = computed(() => {
  const sec = Number(status.value.elapsed_seconds || 0)
  if (sec < 60) return `${sec.toFixed(1)} 秒`
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return `${m} 分 ${s} 秒`
})

const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(pollStatus, 1000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const pollStatus = async () => {
  try {
    const res = await adminAPI.getVectorRebuildStatus()
    status.value = res.status || {}
    if (status.value.status === 'success' || status.value.status === 'error') {
      stopPolling()
      if (status.value.status === 'success') {
        reportVisible.value = true
        ElMessage.success(status.value.message || '重建完成')
      } else {
        ElMessage.error(status.value.message || '重建失败')
      }
    }
  } catch (error) {
    stopPolling()
    ElMessage.error('获取重建进度失败')
  }
}

const handleStart = async (mode) => {
  starting.value = true
  try {
    const res = await adminAPI.startVectorRebuildTask({ mode })
    status.value = res.status || {}
    reportVisible.value = false
    startPolling()
  } catch (error) {
    if (error.response && error.response.status === 409) {
      ElMessage.warning('已有重建任务正在运行，请等待其完成')
    } else {
      ElMessage.error('启动重建任务失败')
    }
  } finally {
    starting.value = false
  }
}

onBeforeUnmount(stopPolling)
</script>

<style lang="scss" scoped>
.vector-rebuild-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;

  &__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  &__progress {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    border: 1px solid #e6e8eb;
    border-radius: 8px;
    background: #fafbfc;

    &-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    &-title {
      font-size: 13px;
      color: #606266;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &-percent {
      font-size: 16px;
      font-weight: 700;
      color: #2563eb;
      font-variant-numeric: tabular-nums;
    }

    &-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 20px;
      font-size: 12px;
      color: #909399;
    }

    &-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-top: 4px;
    }

    &-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: #606266;

      &-title {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }

  &__alert {
    margin-top: 2px;
  }

  &__report {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 14px;
    border: 1px solid #e6e8eb;
    border-radius: 8px;
    background: #fafbfc;

    &-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;

      @media (max-width: 768px) {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    &-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding: 10px 12px;
      background: #fff;
      border: 1px solid #e6e8eb;
      border-radius: 8px;
    }

    &-value {
      font-size: 20px;
      font-weight: 700;
      color: #1f2937;
      font-variant-numeric: tabular-nums;

      &--danger {
        color: #f56c6c;
      }
    }

    &-label {
      font-size: 12px;
      color: #909399;
    }
  }

  &__failed {
    display: flex;
    flex-direction: column;
    gap: 8px;

    &-title {
      font-size: 13px;
      font-weight: 600;
      color: #f56c6c;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .vector-rebuild-panel :deep(.el-progress__bar) {
    transition: none;
  }
}
</style>
