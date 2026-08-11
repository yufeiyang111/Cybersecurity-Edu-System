<template>
  <section class="decision-card">
    <div class="card-head">
      <h2>决策时间线</h2>
      <el-tag v-if="replanCount > 0" type="warning" size="small">
        已重规划 {{ replanCount }} 次
      </el-tag>
    </div>
    <div v-if="loading && !decisions.length" class="decision-card__empty">
      等待决策事件…
    </div>
    <div v-else-if="!decisions.length" class="decision-card__empty">
      暂无重规划决策
    </div>
    <ol v-else class="decision-list">
      <li
        v-for="item in decisions"
        :key="item.id"
        class="decision-item"
      >
        <div class="decision-item__head">
          <el-tag :type="tagType(item)" size="small">{{ tagLabel(item) }}</el-tag>
          <span class="decision-item__version">
            v{{ item.supersedes_version ?? '—' }} → v{{ item.plan_version }}
          </span>
        </div>
        <p class="decision-item__reason">{{ reasonLabel(item.reason_code) }}</p>
        <p v-if="item.detail?.decision_summary" class="decision-item__summary">
          {{ item.detail.decision_summary }}
        </p>
        <p v-if="item.detail?.new_nodes?.length" class="decision-item__nodes">
          新增节点：{{ item.detail.new_nodes.join('、') }}
        </p>
        <span v-if="item.occurred_at" class="decision-item__time">
          {{ formatTime(item.occurred_at) }}
        </span>
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { formatSecurityDate } from '@/features/security/presentation'

const props = defineProps({
  decisions: { type: Array, default: () => [] },
  replanCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false }
})

const REASON_LABELS = {
  high_findings_require_related_review: '高风险 finding 触发相关文件分析',
  user_direction_extends_plan: '用户追加方向，扩展计划',
  failed_route_switched: '失败路线切换',
  strategy_switch: '策略切换'
}

function reasonLabel(code) {
  return REASON_LABELS[code] || code || '未知决策'
}

function tagType(item) {
  if (item.decision_type === 'user_direction') return 'warning'
  if (item.decision_type === 'strategy_switch') return 'info'
  return 'danger'
}

function tagLabel(item) {
  if (item.decision_type === 'user_direction') return '方向追加'
  if (item.decision_type === 'strategy_switch') return '策略切换'
  return '自动重规划'
}

function formatTime(value) {
  return value ? formatSecurityDate(value) : ''
}
</script>

<style scoped lang="scss">
.decision-card {
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

.decision-card__empty {
  color: #8494a8;
  font-size: 12.5px;
}

.decision-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.decision-item {
  border: 1px solid #eef1f6;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fbfcfe;
}

.decision-item__head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.decision-item__version {
  font-size: 12px;
  color: #52627a;
  font-weight: 600;
}

.decision-item__reason {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: #1f2d3d;
  font-weight: 500;
}

.decision-item__summary {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #6a7890;
}

.decision-item__nodes {
  margin: 4px 0 0;
  font-size: 12px;
  color: #52627a;
}

.decision-item__time {
  display: block;
  margin-top: 4px;
  font-size: 11.5px;
  color: #a0aaba;
}
</style>
