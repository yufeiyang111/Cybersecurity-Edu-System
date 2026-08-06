<template>
  <div class="table-scroll">
    <table class="log-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>令牌</th>
          <th>模型</th>
          <th>流</th>
          <th>Tokens</th>
          <th>耗时</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody v-if="loading">
        <tr v-for="index in 6" :key="index" class="skeleton-row">
          <td colspan="7"><span /></td>
        </tr>
      </tbody>
      <tbody v-else-if="logs.length">
        <tr v-for="log in logs" :key="log.id">
          <td>
            <span class="date">{{ formatLogDate(log.created_at) }}</span>
            <span class="sub">{{ log.status === 'success' ? '消耗' : log.warning_code || '调用失败' }}</span>
          </td>
          <td>
            <span class="token-group">
              <span class="token-symbol">◆</span>
              {{ log.provider_name }}
            </span>
            <span class="sub">{{ log.operation }}</span>
          </td>
          <td>
            <span class="model-tag">
              <span class="model-mark">G</span>
              {{ log.model || '未知模型' }}
            </span>
          </td>
          <td>
            <span :class="log.streaming ? 'flow-yes' : 'flow-no'">{{ log.streaming ? '是' : '否' }}</span>
          </td>
          <td>
            <span class="token-line">{{ formatInteger(log.input_tokens) }} / {{ formatInteger(log.output_tokens) }}</span>
            <span class="sub">缓存：<span class="cache-tag" :class="`cache-tag--${cacheTone(log.cache_status)}`">{{ cacheLabel(log.cache_status) }} {{ formatInteger(log.cached_input_tokens) }}</span></span>
          </td>
          <td>
            <span class="latency">
              首字 {{ formatDuration(log.first_token_latency_ms) }}
              <span>耗时 {{ formatDuration(log.latency_ms) }}</span>
            </span>
          </td>
          <td>
            <span class="detail">{{ log.operation }} · {{ log.warning_code || 'ok' }}</span>
          </td>
        </tr>
      </tbody>
      <tbody v-else>
        <tr>
          <td colspan="7" class="empty-cell">当前筛选条件下暂无调用日志</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { formatDuration, formatInteger, formatLogDate } from '@/features/security/llm/format'

defineProps({
  logs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const CACHE_LABELS = {
  hit: '命中',
  write_only: '写入',
  miss: '未命中',
  not_reported: '未报告',
  disabled: '禁用'
}

const cacheLabel = (status) => CACHE_LABELS[status] || '—'
const cacheTone = (status) => {
  if (status === 'hit') return 'hit'
  if (status === 'write_only') return 'write'
  if (status === 'miss') return 'miss'
  return 'none'
}
</script>

<style scoped lang="scss">
.table-scroll {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 1000px;
  border-collapse: collapse;
  table-layout: fixed;
}

th,
td {
  padding: 12px 10px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: middle;
}

th {
  height: 44px;
  color: #94a3b8;
  background: #f1f5f9;
  font-size: 12px;
}

td {
  height: 74px;
  color: #475569;
  font-size: 12px;
}

tbody tr:hover {
  background: #f8fafc;
}

tr:last-child td {
  border-bottom: 0;
}

th:nth-child(1),
td:nth-child(1) {
  width: 15%;
}

th:nth-child(2),
td:nth-child(2) {
  width: 16%;
}

th:nth-child(3),
td:nth-child(3) {
  width: 14%;
}

th:nth-child(4),
td:nth-child(4) {
  width: 8%;
}

th:nth-child(5),
td:nth-child(5) {
  width: 14%;
}

th:nth-child(6),
td:nth-child(6) {
  width: 14%;
}

th:nth-child(7),
td:nth-child(7) {
  width: 19%;
}

.date,
.token-line {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.sub {
  display: block;
  margin-top: 5px;
  color: #94a3b8;
  font-size: 10px;
}

.token-group {
  font-weight: 600;
  color: #0f172a;
}

.token-symbol {
  display: inline-block;
  margin-right: 6px;
  color: #2563eb;
}

.model-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 7px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
}

.model-mark {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #2563eb;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.flow-yes {
  color: #16a34a;
  font-weight: 600;
}

.flow-no {
  color: #94a3b8;
}

.latency {
  color: #475569;
  line-height: 1.55;
}

.latency span {
  display: block;
  color: #94a3b8;
  font-size: 10px;
}

.detail {
  color: #94a3b8;
  font-size: 11px;
}

.cache-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
}

.cache-tag--hit {
  background: #dcfce7;
  color: #16a34a;
}

.cache-tag--write {
  background: #fef9c3;
  color: #ca8a04;
}

.cache-tag--miss {
  background: #fee2e2;
  color: #dc2626;
}

.cache-tag--none {
  background: #f1f5f9;
  color: #94a3b8;
}

.empty-cell {
  text-align: center;
  height: 220px;
  color: #94a3b8;
}

.skeleton-row td {
  height: 68px;
}

.skeleton-row span {
  display: block;
  height: 14px;
  border-radius: 4px;
  background: #f1f5f9;
  animation: skeleton 1.4s ease-in-out infinite alternate;
}

@keyframes skeleton {
  from {
    opacity: 0.55;
  }
  to {
    opacity: 1;
  }
}
</style>
