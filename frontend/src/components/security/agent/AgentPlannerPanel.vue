<template>
  <section class="planner-card">
    <div class="card-head">
      <h2>计划</h2>
      <span
        v-if="plannerMeta"
        class="planner-badge"
        :class="`planner-badge--${plannerMeta.tagType}`"
      >
        {{ plannerMeta.label }}
      </span>
      <span v-else class="planner-badge planner-badge--info">未生成</span>
    </div>

    <div v-if="loading && !plan" class="planner-card__empty">计划生成中…</div>

    <template v-else-if="plan">
      <p v-if="plan.objective" class="planner-card__objective">{{ plan.objective }}</p>

      <div v-if="fallbackReason" class="planner-card__fallback">
        <span class="planner-card__fallback-icon" aria-hidden="true">⚠</span>
        {{ fallbackReason }}
      </div>

      <div v-if="nodeItems.length" class="planner-card__nodes">
        <div
          v-for="item in nodeItems"
          :key="item.node_key"
          class="plan-node"
          :class="`plan-node--${item.status}`"
        >
          <span class="plan-node__icon" aria-hidden="true">
            <svg
              v-if="item.status === 'succeeded'"
              viewBox="0 0 24 24"
              fill="none"
              stroke-width="2.4"
            >
              <path d="M5 13l4 4 10-10" />
            </svg>
            <svg
              v-else-if="item.status === 'failed' || item.status === 'blocked'"
              viewBox="0 0 24 24"
              fill="none"
              stroke-width="2.4"
            >
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
            <svg
              v-else-if="item.status === 'running'"
              viewBox="0 0 24 24"
              fill="none"
              stroke-width="2"
            >
              <circle cx="12" cy="12" r="4" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke-width="2">
              <circle cx="12" cy="12" r="7" />
            </svg>
          </span>
          <span class="plan-node__title">{{ item.title }}</span>
          <span v-if="item.toolName" class="plan-node__tool">{{ item.toolName }}</span>
          <span class="plan-node__status">{{ item.statusLabel }}</span>
        </div>
      </div>

      <div v-if="plan.completion_criteria?.length" class="planner-card__block">
        <span class="planner-card__label">完成条件</span>
        <ul class="planner-card__list">
          <li v-for="(item, index) in plan.completion_criteria" :key="index">{{ item }}</li>
        </ul>
      </div>

      <p v-if="plan.decision_summary" class="planner-card__summary">
        {{ plan.decision_summary }}
      </p>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { plannerSourceLabel, toolNameLabel } from '@/features/security/agent/statusMeta'

const props = defineProps({
  plan: { type: Object, default: null },
  fallbackReason: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

const plannerMeta = computed(() => {
  if (!props.plan?.planner_source) return null
  return plannerSourceLabel(props.plan.planner_source) || null
})

const nodeTitles = {
  inventory: '清点快照',
  baseline_scan: '基线扫描',
  coverage_analysis: '覆盖分析',
  risk_ranking: '风险排序',
  report: '运行摘要'
}

const nodeItems = computed(() => {
  const nodes = props.plan?.nodes || []
  return nodes.map((node) => ({
    node_key: node.node_key,
    title: nodeTitles[node.node_key] || node.title || node.node_key,
    toolName: node.tool_name ? toolNameLabel(node.tool_name) : '',
    status: node.status,
    statusLabel: nodeStatusLabel(node.status)
  }))
})

function nodeStatusLabel(status) {
  const labels = {
    pending: '等待',
    ready: '就绪',
    running: '执行中',
    succeeded: '完成',
    failed: '失败',
    blocked: '阻塞',
    skipped: '跳过',
    canceled: '已取消'
  }
  return labels[status] || status || ''
}
</script>

<style scoped lang="scss">
.planner-card {
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

.planner-badge {
  font-size: 11.5px;
  font-weight: 600;
  border-radius: 999px;
  padding: 2px 10px;
}

.planner-badge--success {
  background: #ecfdf5;
  color: #047857;
}

.planner-badge--warning {
  background: #fef3c7;
  color: #b45309;
}

.planner-badge--info {
  background: #eef2f7;
  color: #6a7890;
}

.planner-card__empty {
  color: #8494a8;
  font-size: 12.5px;
}

.planner-card__objective {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #1f2d3d;
  line-height: 1.5;
}

.planner-card__fallback {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 10px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #fef9c3;
  color: #854d0e;
  font-size: 12px;
  line-height: 1.5;
}

.planner-card__fallback-icon {
  flex: none;
}

.planner-card__nodes {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 10px;
}

.plan-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 6px;
  font-size: 12.5px;
}

.plan-node:hover {
  background: #f8fafc;
}

.plan-node__icon {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  flex: none;
}

.plan-node__icon svg {
  width: 13px;
  height: 13px;
  stroke: #8494a8;
}

.plan-node--succeeded .plan-node__icon svg {
  stroke: #047857;
}

.plan-node--failed .plan-node__icon svg,
.plan-node--blocked .plan-node__icon svg {
  stroke: #b91c1c;
}

.plan-node--running .plan-node__icon svg {
  stroke: #2563eb;
  animation: node-pulse 1.4s infinite ease-in-out;
}

.plan-node__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #334155;
  font-weight: 500;
}

.plan-node__tool {
  font-size: 11.5px;
  color: #8494a8;
  flex: none;
}

.plan-node__status {
  font-size: 11.5px;
  color: #6a7890;
  flex: none;
}

.plan-node--succeeded .plan-node__status {
  color: #047857;
}

.plan-node--failed .plan-node__status,
.plan-node--blocked .plan-node__status {
  color: #b91c1c;
}

.plan-node--running .plan-node__status {
  color: #2563eb;
}

.planner-card__block {
  margin-bottom: 8px;
}

.planner-card__label {
  font-size: 12px;
  font-weight: 600;
  color: #6a7890;
}

.planner-card__list {
  margin: 4px 0 0;
  padding-left: 16px;
  font-size: 12.5px;
  color: #52627a;
  line-height: 1.6;
}

.planner-card__summary {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: #52627a;
  border-left: 2px solid #e2e7ee;
  padding-left: 10px;
}

@keyframes node-pulse {
  0%,
  100% {
    opacity: 0.4;
  }
  50% {
    opacity: 1;
  }
}
</style>
