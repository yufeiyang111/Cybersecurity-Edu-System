<template>
  <section class="invocation-card">
    <div class="card-head">
      <h2>LLM 调用</h2>
      <span class="invocation-card__note">{{ invocations.length }} 次（最近）</span>
    </div>
    <el-empty
      v-if="!loading && invocations.length === 0"
      description="暂无调用"
      :image-size="48"
    />
    <ul v-else class="invocation-list">
      <li v-for="item in invocations" :key="item.id" class="invocation-row">
        <div class="invocation-row__head">
          <span class="invocation-row__op">{{ operationLabel(item.operation) }}</span>
          <el-tag
            :type="item.status === 'success' ? 'success' : 'danger'"
            size="small"
          >
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
  </section>
</template>

<script setup>
const props = defineProps({
  invocations: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
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

function formatCost(value) {
  const number = Number(value || 0)
  if (number === 0 && props.invocations.some((item) => item.pricing_version === null)) return '未知'
  return number.toFixed(6).replace(/0+$/, '').replace(/\.$/, '') || '0'
}
</script>

<style scoped lang="scss">
.invocation-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.invocation-card__note { color: #6a7890; font-size: 12.5px; }
.invocation-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 260px;
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
