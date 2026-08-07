<template>
  <section class="cost-panel">
    <el-collapse v-model="active">
      <el-collapse-item name="summary" title="成本与 LLM 调用">
        <div class="cost-panel__summary">
          <div class="cost-cell">
            <span class="cost-cell__value">{{ summary ? summary.calls : '-' }}</span>
            <span class="cost-cell__label">调用</span>
          </div>
          <div class="cost-cell">
            <span class="cost-cell__value">{{ summary ? formatNumber(summary.total_tokens) : '-' }}</span>
            <span class="cost-cell__label">Token</span>
          </div>
          <div class="cost-cell">
            <span class="cost-cell__value">{{ summary ? formatCost(summary.total_cost) : '-' }}</span>
            <span class="cost-cell__label">{{ summary?.currency || 'USD' }}</span>
          </div>
          <el-tag v-if="costTag" :type="costTag.tone" size="small" class="cost-panel__tag">
            {{ costTag.label }}
          </el-tag>
        </div>
        <p v-if="summary?.cost_source === 'unknown'" class="cost-panel__note">
          无价格快照，成本未知（不显示为 0）
        </p>
        <p v-else-if="summary?.cost_source === 'estimated'" class="cost-panel__note">
          按内置价格目录估算
        </p>
        <ul v-if="invocations.length" class="cost-panel__list">
          <li v-for="item in invocations" :key="item.id" class="invocation-row">
            <div class="invocation-row__head">
              <span class="invocation-row__op">{{ operationLabel(item.operation) }}</span>
              <el-tag :type="item.status === 'success' ? 'success' : 'danger'" size="small">
                {{ item.status }}
              </el-tag>
            </div>
            <div class="invocation-row__meta">
              <span class="invocation-row__provider">{{ item.provider_name }}</span>
              <span v-if="item.model" class="invocation-row__model">{{ item.model }}</span>
            </div>
            <div class="invocation-row__stats">
              <span class="invocation-row__stat">{{ item.total_tokens }} tokens</span>
              <span class="invocation-row__stat">{{ formatCost(item.total_cost) }} {{ item.currency }}</span>
              <span v-if="item.usage_source" class="invocation-row__source">
                {{ sourceLabel(item.usage_source) }}
              </span>
            </div>
            <div v-if="item.warning_code" class="invocation-row__warning">
              {{ item.warning_code }}
            </div>
          </li>
        </ul>
        <span v-else-if="!loading" class="cost-panel__empty">暂无调用</span>
      </el-collapse-item>
    </el-collapse>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  summary: { type: Object, default: null },
  invocations: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const active = ref(['summary'])

const costTag = computed(() => {
  const source = props.summary?.cost_source
  if (source === 'unknown') return { tone: 'danger', label: '成本未知' }
  if (source === 'estimated') return { tone: 'warning', label: '估算' }
  if (source === 'mixed') return { tone: 'warning', label: '混合' }
  if (source === 'none') return { tone: 'info', label: '无调用' }
  return null
})

const OPERATION_LABELS = {
  planner: '规划',
  agent_analysis: '分析',
  unknown: '调用'
}

function operationLabel(operation) {
  return OPERATION_LABELS[operation] || operation || '调用'
}

function sourceLabel(source) {
  if (source === 'provider_reported') return '官方用量'
  if (source === 'estimated') return '估算用量'
  return '来源未知'
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function formatCost(value) {
  const number = Number(value || 0)
  if (number === 0 && props.summary?.cost_source === 'unknown') return '未知'
  return number.toFixed(6).replace(/0+$/, '').replace(/\.$/, '') || '0'
}
</script>

<style scoped lang="scss">
.cost-panel { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 6px 16px; }
.cost-panel :deep(.el-collapse) { border: 0; }
.cost-panel :deep(.el-collapse-item__header) { font-size: 15px; font-weight: 600; color: #1f2d3d; }
.cost-panel :deep(.el-collapse-item__wrap) { border: 0; }
.cost-panel__summary {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.cost-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  padding: 6px 12px;
  background: #f8fafc;
  border-radius: 6px;
}
.cost-cell__value { font-size: 14px; font-weight: 700; color: #1f2d3d; font-variant-numeric: tabular-nums; }
.cost-cell__label { font-size: 11.5px; color: #6a7890; }
.cost-panel__tag { margin-left: auto; }
.cost-panel__note { margin: 0 0 8px; font-size: 12px; color: #b45309; }
.cost-panel__empty { color: #8494a8; font-size: 12.5px; }
.cost-panel__list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 240px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.invocation-row {
  border: 1px solid #eef2f7;
  border-radius: 6px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.invocation-row__head { display: flex; align-items: center; justify-content: space-between; }
.invocation-row__op { font-size: 12.5px; font-weight: 600; color: #1f2d3d; }
.invocation-row__meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.invocation-row__provider { font-size: 12px; color: #2563eb; }
.invocation-row__model { font-size: 11.5px; color: #6a7890; }
.invocation-row__stats { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.invocation-row__stat { font-size: 11.5px; color: #52627a; font-variant-numeric: tabular-nums; }
.invocation-row__source {
  font-size: 11px;
  color: #b45309;
  background: #fef9c3;
  border-radius: 999px;
  padding: 0 6px;
}
.invocation-row__warning { font-size: 11.5px; color: #dc2626; }
</style>
