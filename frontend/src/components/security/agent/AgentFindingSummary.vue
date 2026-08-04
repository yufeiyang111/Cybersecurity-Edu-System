<template>
  <section class="finding-card">
    <div class="card-head">
      <h2>扫描发现</h2>
      <span v-if="summary" class="note">{{ summary.findings_count }} 个发现</span>
    </div>
    <el-empty v-if="!loading && !summary" description="基线扫描完成后显示发现摘要" :image-size="56" />
    <div v-else-if="summary" class="finding-body">
      <div class="severity-row">
        <span v-for="level in severityOrder" :key="level" class="severity-chip" :class="`severity-chip--${level}`">
          <b>{{ severityCount(level) }}</b>
          <span>{{ severityLabel(level) }}</span>
        </span>
      </div>
      <div v-if="top.length" class="top-list">
        <div v-for="item in top" :key="item.id" class="top-item">
          <el-tag :type="severityTag(item.severity)" size="small">{{ item.severity }}</el-tag>
          <span class="top-item__rule">{{ item.rule_id }}</span>
          <span class="top-item__path" :title="item.file_path">{{ item.file_path }}:{{ item.start_line }}</span>
        </div>
      </div>
      <p v-if="top.length && summary.findings_count > top.length" class="more-note">
        仅显示前 {{ top.length }} 个，完整列表见右侧工具调用明细
      </p>
    </div>
    <div v-else class="finding-skeleton"><el-skeleton :rows="3" animated /></div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  metrics: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const severityOrder = ['critical', 'high', 'medium', 'low', 'info']
const severityLabels = { critical: '严重', high: '高危', medium: '中危', low: '低危', info: '提示' }
const severityTags = { critical: 'danger', high: 'danger', medium: 'warning', low: 'success', info: 'info' }

const summary = computed(() => {
  if (!props.metrics?.task_id) return null
  return {
    findings_count: props.metrics.findings_count || 0,
    severity_counts: props.metrics.severity_counts || {}
  }
})

const top = computed(() => props.metrics?.top_findings || [])

function severityCount(level) {
  return summary.value?.severity_counts?.[level] ?? 0
}
function severityLabel(level) {
  return severityLabels[level] || level
}
function severityTag(level) {
  return severityTags[level] || 'info'
}
</script>

<style scoped lang="scss">
.finding-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head .note { color: #6a7890; font-size: 12.5px; }
.finding-skeleton { padding: 4px 0; }
.severity-row { display: flex; gap: 8px; flex-wrap: wrap; }
.severity-chip {
  display: flex; flex-direction: column; align-items: center; gap: 1px;
  min-width: 64px; padding: 6px 10px; border-radius: 6px; font-size: 12px;
}
.severity-chip b { font-size: 17px; font-variant-numeric: tabular-nums; }
.severity-chip--critical { background: #fef2f2; color: #b42318; }
.severity-chip--high { background: #fff7ed; color: #c2410c; }
.severity-chip--medium { background: #fffbeb; color: #b54708; }
.severity-chip--low { background: #f0fdf9; color: #0e9384; }
.severity-chip--info { background: #f8fafc; color: #64748b; }
.top-list { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto; }
.top-item { display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
.top-item__rule { color: #1f2d3d; font-weight: 600; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.top-item__path { color: #6a7890; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.more-note { margin: 8px 0 0; color: #8494a8; font-size: 12px; }
</style>
