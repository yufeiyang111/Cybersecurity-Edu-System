<template>
  <section class="history">
    <div class="hist-head">
      <div>
        <h2>最近扫描记录</h2>
        <p>最近 6 次扫描任务的状态与发现数量。</p>
      </div>
    </div>

    <el-empty v-if="!loading && scans.length === 0" description="还没有扫描记录" :image-size="80" />

    <div v-else class="hist-list" v-loading="loading">
      <article
        v-for="scan in scans"
        :key="scan.task_id"
        class="hist-item"
        @click="$emit('open-scan', scan)"
      >
        <span class="hist-icon" :class="`h-${stateKind(scan.status)}`">
          <el-icon><Document /></el-icon>
        </span>
        <div class="hist-main">
          <div class="t">{{ scan.project_name }}</div>
          <div class="m">{{ languageLabel(scan.language) }} · {{ formatDate(scan.created_at) }}</div>
        </div>
        <div class="hist-stats">
          <span>发现 <b class="h-findings">{{ scan.findings_count ?? 0 }}</b> 条</span>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { Document } from '@element-plus/icons-vue'
import { languageMeta } from '@/features/security/languageMeta'

defineProps({
  scans: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

defineEmits(['open-scan'])

const RUNNING_STATUSES = new Set(['created', 'validating', 'snapshotting', 'scanning'])

const stateKind = (status) => {
  if (RUNNING_STATUSES.has(status)) return 'run'
  if (status === 'failed' || status === 'canceled') return 'fail'
  return 'done'
}

const languageLabel = (language) => languageMeta(language).label

const formatDate = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
</script>

<style scoped lang="scss">
.history {
  margin-top: 24px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 18px;
}

.hist-head {
  margin-bottom: 14px;

  h2 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: #0f172a;
  }

  p {
    margin: 4px 0 0;
    font-size: 12.5px;
    color: #475569;
  }
}

.hist-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hist-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;

  &:hover {
    background: #f8fafc;
    border-color: #bfdbfe;
  }
}

.hist-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #f1f5f9;
  color: #475569;

  .el-icon {
    font-size: 16px;
  }
}

.h-run {
  background: #dbeafe;
  color: #2563eb;
  animation: breathe 1.6s ease-in-out infinite;
}

.h-fail {
  background: #fee2e2;
  color: #dc2626;
}

.h-done {
  background: #dcfce7;
  color: #16a34a;
}

@keyframes breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.hist-main {
  flex: 1;
  min-width: 0;

  .t {
    font-size: 13.5px;
    font-weight: 600;
    color: #0f172a;
  }

  .m {
    margin-top: 1px;
    font-size: 12px;
    color: #94a3b8;
  }
}

.hist-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #475569;
  white-space: nowrap;

  b {
    font-size: 13px;
    font-variant-numeric: tabular-nums;
  }
}

.h-findings {
  color: #0f172a;
}
</style>
