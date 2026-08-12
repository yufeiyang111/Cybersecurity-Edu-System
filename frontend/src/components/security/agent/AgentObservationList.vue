<template>
  <section class="observation-card">
    <div class="card-head">
      <h2>观察结论</h2>
      <el-tag v-if="items.length" type="info" size="small">
        {{ total }} 条
      </el-tag>
    </div>
    <div v-if="loading && !items.length" class="observation-card__empty">
      观察加载中…
    </div>
    <div v-else-if="!items.length" class="observation-card__empty">
      暂无观察结论（Deep Review 产出后显示）
    </div>
    <ul v-else class="observation-list">
      <li
        v-for="item in items"
        :key="item.id"
        class="observation-item"
        @click="$emit('select', item)"
      >
        <div class="observation-item__head">
          <el-tag :type="statusTagType(item.status)" size="small">
            {{ statusLabel(item.status) }}
          </el-tag>
          <span class="observation-item__confidence">{{ confidenceLabel(item.confidence) }}</span>
          <span v-if="item.cwe_id" class="observation-item__cwe">{{ item.cwe_id }}</span>
        </div>
        <p class="observation-item__title">{{ item.title }}</p>
        <p class="observation-item__summary">{{ item.summary }}</p>
        <div class="observation-item__meta">
          <span>{{ (item.locations || []).length }} 个位置</span>
          <span>{{ (item.citations || []).length }} 条引用</span>
          <span v-if="(item.proof_gaps || []).length" class="observation-item__gaps">
            {{ (item.proof_gaps || []).length }} 个证据缺口
          </span>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup>
const props = defineProps({
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  loading: { type: Boolean, default: false }
})

defineEmits(['select'])

const STATUS_LABELS = {
  unverified: '未验证',
  confirmed: '已确认',
  rejected: '已驳回',
  needs_more_evidence: '待补证据'
}

const CONFIDENCE_LABELS = {
  low: '低置信',
  medium: '中置信',
  high: '高置信'
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

function statusTagType(status) {
  if (status === 'confirmed') return 'success'
  if (status === 'rejected') return 'info'
  if (status === 'needs_more_evidence') return 'warning'
  return 'primary'
}

function confidenceLabel(confidence) {
  return CONFIDENCE_LABELS[confidence] || confidence
}
</script>

<style scoped lang="scss">
.observation-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.card-head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.observation-card__empty {
  color: #8494a8;
  font-size: 12.5px;
}

.observation-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.observation-item {
  border: 1px solid #eef1f6;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fbfcfe;
  cursor: pointer;
}

.observation-item:hover {
  border-color: #2563eb;
}

.observation-item__head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.observation-item__confidence {
  font-size: 12px;
  color: #6a7890;
}

.observation-item__cwe {
  font-size: 11.5px;
  color: #9aa6ba;
  background: #f0f2f6;
  border-radius: 4px;
  padding: 1px 6px;
}

.observation-item__title {
  margin: 6px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: #1f2d3d;
}

.observation-item__summary {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #52627a;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.observation-item__meta {
  display: flex;
  gap: 10px;
  margin-top: 6px;
  font-size: 11.5px;
  color: #a0aaba;
}

.observation-item__gaps {
  color: #b45309;
}
</style>
