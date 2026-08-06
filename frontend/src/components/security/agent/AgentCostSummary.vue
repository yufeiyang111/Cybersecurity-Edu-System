<template>
  <section class="cost-card">
    <div class="card-head">
      <h2>成本</h2>
      <el-tag v-if="costTag" :type="costTag.tone" size="small">{{ costTag.label }}</el-tag>
    </div>
    <div v-if="loading && !summary" class="cost-card__empty">加载中…</div>
    <template v-else-if="summary">
      <div class="cost-card__grid">
        <div class="cost-cell">
          <span class="cost-cell__value">{{ summary.calls }}</span>
          <span class="cost-cell__label">调用</span>
        </div>
        <div class="cost-cell">
          <span class="cost-cell__value">{{ formatNumber(summary.total_tokens) }}</span>
          <span class="cost-cell__label">Token</span>
        </div>
        <div class="cost-cell">
          <span class="cost-cell__value">{{ formatCost(summary.total_cost) }}</span>
          <span class="cost-cell__label">{{ summary.currency }}</span>
        </div>
      </div>
      <p v-if="summary.cost_source === 'unknown'" class="cost-card__note">
        无价格快照，成本未知（不显示为 0）
      </p>
      <p v-else-if="summary.cost_source === 'estimated'" class="cost-card__note">
        按内置价格目录估算
      </p>
      <p v-else-if="summary.cost_source === 'mixed'" class="cost-card__note">
        部分调用按目录估算，部分无价格
      </p>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  summary: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const costTag = computed(() => {
  const source = props.summary?.cost_source
  if (source === 'unknown') return { tone: 'danger', label: '未知' }
  if (source === 'estimated') return { tone: 'warning', label: '估算' }
  if (source === 'mixed') return { tone: 'warning', label: '混合' }
  if (source === 'none') return { tone: 'info', label: '无调用' }
  return null
})

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
.cost-card {
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
.cost-card__empty { color: #8494a8; font-size: 12.5px; }
.cost-card__grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.cost-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  background: #f8fafc;
  border-radius: 6px;
}
.cost-cell__value { font-size: 14px; font-weight: 700; color: #1f2d3d; font-variant-numeric: tabular-nums; }
.cost-cell__label { font-size: 11.5px; color: #6a7890; }
.cost-card__note { margin: 8px 0 0; font-size: 12px; color: #b45309; }
</style>
