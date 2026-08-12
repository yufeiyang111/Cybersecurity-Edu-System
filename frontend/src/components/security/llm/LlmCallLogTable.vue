<template>
  <div class="table-scroll">
    <table class="log-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>令牌</th>
          <th>模型</th>
          <th>流</th>
          <th>
            <el-tooltip
              content="输入 Tokens：发送给模型的请求（prompt）令牌数；输出 Tokens：模型生成的回复（completion）令牌数"
              placement="top"
            >
              <span class="th-tokens">Tokens 输入/输出</span>
            </el-tooltip>
          </th>
          <th>
            <el-tooltip
              content="缓存命中率：命中缓存的输入令牌数 ÷ 总输入令牌数（命中越高，成本与延迟越低）"
              placement="top"
            >
              <span class="th-tokens">缓存命中率</span>
            </el-tooltip>
          </th>
          <th>耗时</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody v-if="loading">
        <tr v-for="index in 6" :key="index" class="skeleton-row">
          <td colspan="8"><span /></td>
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
            <span class="token-line">
              <span class="token-label">输入</span>
              {{ formatInteger(log.input_tokens) }}
              <span class="token-sep">/</span>
              <span class="token-label">输出</span>
              {{ formatInteger(log.output_tokens) }}
            </span>
            <span class="sub">缓存：<span class="cache-tag" :class="`cache-tag--${cacheTone(log.cache_status)}`">{{ cacheLabel(log.cache_status) }} {{ formatInteger(log.cached_input_tokens) }}</span></span>
          </td>
          <td>
            <span class="cache-rate" :class="`cache-rate--${cacheRateTone(log)}`">{{ cacheRateText(log) }}</span>
            <span class="sub">命中 {{ formatInteger(log.cached_input_tokens) }} / 输入 {{ formatInteger(log.input_tokens) }}</span>
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
          <td colspan="8" class="empty-cell">当前筛选条件下暂无调用日志</td>
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

const cacheRate = (log) => {
  const status = log.cache_status
  if (status === 'not_reported' || status === 'disabled') return null
  const total = Number(log.input_tokens) || 0
  const cached = Number(log.cached_input_tokens) || 0
  if (total <= 0) return null
  return Math.round((cached / total) * 1000) / 10
}

const cacheRateText = (log) => {
  const rate = cacheRate(log)
  if (rate === null) return '—'
  return `${rate}%`
}

const cacheRateTone = (log) => {
  const rate = cacheRate(log)
  if (rate === null) return 'none'
  if (rate >= 50) return 'high'
  if (rate > 0) return 'mid'
  return 'zero'
}
</script>

<style scoped lang="scss">
.table-scroll {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 1120px;
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
  width: 14%;
}

th:nth-child(2),
td:nth-child(2) {
  width: 15%;
}

th:nth-child(3),
td:nth-child(3) {
  width: 13%;
}

th:nth-child(4),
td:nth-child(4) {
  width: 7%;
}

th:nth-child(5),
td:nth-child(5) {
  width: 13%;
}

th:nth-child(6),
td:nth-child(6) {
  width: 12%;
}

th:nth-child(7),
td:nth-child(7) {
  width: 12%;
}

th:nth-child(8),
td:nth-child(8) {
  width: 14%;
}

.date,
.token-line {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.th-tokens {
  cursor: help;
  border-bottom: 1px dashed #94a3b8;
}

.token-label {
  color: #94a3b8;
  font-size: 10px;
  font-weight: 400;
}

.token-sep {
  margin: 0 4px;
  color: #cbd5e1;
}

.cache-rate {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.cache-rate--high {
  background: #dcfce7;
  color: #16a34a;
}

.cache-rate--mid {
  background: #fef9c3;
  color: #ca8a04;
}

.cache-rate--zero {
  background: #fee2e2;
  color: #dc2626;
}

.cache-rate--none {
  background: #f1f5f9;
  color: #94a3b8;
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
