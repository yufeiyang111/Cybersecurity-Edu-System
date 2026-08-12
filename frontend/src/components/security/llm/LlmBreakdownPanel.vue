<template>
  <section class="breakdown-panel">
    <header>
      <BaseIcon name="chart" :size="16" />
      {{ title }}
      <span>总计：{{ totalCalls }}</span>
    </header>
    <div class="breakdown-row heading">
      <strong>{{ nameLabel }}</strong>
      <strong>调用次数</strong>
      <strong>占比</strong>
      <strong>总 Token</strong>
      <strong>缓存命中率</strong>
    </div>
    <div v-for="item in rows" :key="item.name" class="breakdown-row">
      <span>{{ item.name || '未知' }}</span>
      <span>{{ item.calls }}</span>
      <span>{{ percent(item.calls) }}</span>
      <span class="token-cell">{{ formatInteger(item.tokens) }}</span>
      <span class="hit-cell">{{ hitRate(item.cache_hit_rate) }}</span>
    </div>
    <div v-if="!rows.length" class="empty">暂无调用数据</div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'
import { formatInteger } from '@/features/security/llm/format'

const props = defineProps({
  title: { type: String, default: '调用分析' },
  nameLabel: { type: String, default: '名称' },
  rows: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) }
})

const totalCalls = computed(() => props.summary.total_calls || props.rows.reduce((sum, item) => sum + Number(item.calls || 0), 0))
const percent = (value) => totalCalls.value ? `${((Number(value || 0) / totalCalls.value) * 100).toFixed(1)}%` : '0%'
const hitRate = (value) => (value === null || value === undefined ? '—' : `${Number(value).toFixed(1)}%`)
</script>

<style scoped lang="scss">
.breakdown-panel {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  transition: box-shadow 0.35s ease;
}

.breakdown-panel:hover {
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.07);
}

.breakdown-panel header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 13px 16px;
  border-bottom: 1px solid #e2e8f0;
  color: #0f172a;
  font-size: 14px;
  font-weight: 600;
}

.breakdown-panel header :deep(.ui-icon) {
  color: #2563eb;
}

.breakdown-panel header span {
  margin-left: 4px;
  color: #475569;
  font-size: 12px;
  font-weight: 400;
}

.breakdown-row {
  display: grid;
  grid-template-columns: 1.6fr 0.7fr 0.7fr 0.9fr 0.9fr;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  color: #475569;
  font-size: 12px;
  transition: background 0.3s ease;
}

.breakdown-row:last-child {
  border-bottom: 0;
}

.breakdown-row:not(.heading):hover {
  background: #f8fafc;
}

.breakdown-row.heading {
  color: #475569;
  font-weight: 600;
  background: #f1f5f9;
}

.breakdown-row strong {
  font-weight: 600;
}

.token-cell {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  color: #0f172a;
}

.hit-cell {
  color: #16a34a;
  font-weight: 600;
}

.empty {
  padding: 40px;
  text-align: center;
  color: #94a3b8;
}

@media (max-width: 900px) {
  .breakdown-row {
    grid-template-columns: 1.3fr 0.6fr 0.6fr 0.8fr 0.8fr;
    padding: 11px 12px;
  }
}

@media (max-width: 640px) {
  .breakdown-row {
    grid-template-columns: 1.2fr 0.55fr 0.55fr 0.7fr 0.7fr;
    padding: 10px 10px;
    font-size: 11px;
  }
}
</style>
