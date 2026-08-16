<template>
  <section class="approval-card">
    <div class="card-head">
      <h2>审批请求</h2>
      <el-tag v-if="pendingCount > 0" type="warning" size="small">
        {{ pendingCount }} 待处理
      </el-tag>
    </div>
    <div v-if="loading && !items.length" class="approval-card__empty">
      审批加载中…
    </div>
    <div v-else-if="!items.length" class="approval-card__empty">
      暂无审批请求
    </div>
    <ul v-else class="approval-list">
      <li
        v-for="item in items"
        :key="item.id"
        class="approval-item"
        :class="{ 'approval-item--pending': item.status === 'pending' }"
      >
        <div class="approval-item__head">
          <el-tag :type="statusTagType(item.status)" size="small">
            {{ statusLabel(item.status) }}
          </el-tag>
          <el-tag :type="riskTagType(item.risk_level)" size="small">
            {{ riskLabel(item.risk_level) }}
          </el-tag>
          <span class="approval-item__type">{{ operationLabel(item.operation_type) }}</span>
        </div>
        <p class="approval-item__reason">{{ item.reason }}</p>
        <p v-if="item.run_goal" class="approval-item__goal">任务：{{ item.run_goal }}</p>
        <div class="approval-item__actions" v-if="item.status === 'pending' && item.can_resolve">
          <el-input
            v-model="comments[item.id]"
            size="small"
            placeholder="审批意见（可选）"
            class="approval-item__comment"
          />
          <el-button
            size="small"
            type="primary"
            :loading="resolving[item.id]"
            @click="$emit('resolve', item, 'approved', comments[item.id] || '')"
          >
            批准
          </el-button>
          <el-button
            size="small"
            type="danger"
            plain
            :loading="resolving[item.id]"
            @click="$emit('resolve', item, 'rejected', comments[item.id] || '')"
          >
            拒绝
          </el-button>
        </div>
        <p v-else-if="item.decision_comment" class="approval-item__decision">
          意见：{{ item.decision_comment }}
        </p>
        <span v-if="item.expires_at" class="approval-item__expires">
          截止 {{ formatTime(item.expires_at) }}
        </span>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { formatSecurityDate } from '@/features/security/presentation'

const props = defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

defineEmits(['resolve'])

const comments = ref({})
const resolving = ref({})

const pendingCount = computed(
  () => props.items.filter((item) => item.status === 'pending').length
)

const STATUS_LABELS = {
  pending: '待处理',
  approved: '已批准',
  rejected: '已拒绝',
  expired: '已过期',
  canceled: '已取消'
}

const RISK_LABELS = {
  low: '低风险',
  medium: '中风险',
  high: '高风险'
}

const OPERATION_LABELS = {
  budget_increase: '预算追加',
  remote_source_send: '远程源码发送',
  remediation_generation: '修复建议生成'
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

function statusTagType(status) {
  if (status === 'approved') return 'success'
  if (status === 'rejected' || status === 'expired') return 'info'
  return 'warning'
}

function riskTagType(risk) {
  if (risk === 'high') return 'danger'
  if (risk === 'medium') return 'warning'
  return 'info'
}

function riskLabel(risk) {
  return RISK_LABELS[risk] || risk
}

function operationLabel(type) {
  return OPERATION_LABELS[type] || type
}

function formatTime(value) {
  return value ? formatSecurityDate(value) : ''
}
</script>

<style scoped lang="scss">
.approval-card {
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

.approval-card__empty {
  color: #52627a;
  font-size: 12.5px;
}

.approval-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.approval-item {
  border: 1px solid #eef1f6;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fbfcfe;
}

.approval-item--pending {
  border-color: #fde68a;
  background: #fffbeb;
}

.approval-item__head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.approval-item__type {
  font-size: 12.5px;
  font-weight: 600;
  color: #1f2d3d;
}

.approval-item__reason {
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: #52627a;
}

.approval-item__goal {
  margin: 4px 0 0;
  font-size: 12px;
  color: #52627a;
}

.approval-item__actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  align-items: center;
}

.approval-item__comment {
  flex: 1;
  min-width: 0;
}

.approval-item__decision {
  margin: 6px 0 0;
  font-size: 12px;
  color: #52627a;
}

.approval-item__expires {
  display: block;
  margin-top: 4px;
  font-size: 11.5px;
  color: #64748b;
}
</style>
