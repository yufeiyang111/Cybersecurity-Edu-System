<template>
  <section class="progress-card">
    <div class="card-head">
      <h2>完成度</h2>
      <el-tag :type="statusMeta.tagType" size="small">{{ statusMeta.label }}</el-tag>
    </div>

    <div v-if="loading && !plan" class="progress-card__empty">计划生成中…</div>

    <template v-else>
      <div v-if="totalNodes > 0" class="progress-bar-wrap">
        <el-progress
          :percentage="percent"
          :stroke-width="10"
          :show-text="false"
          :status="percent >= 100 ? 'success' : undefined"
        />
        <div class="progress-meta">
          <span>已完成 {{ doneNodes }} / {{ totalNodes }} 个节点</span>
          <span>{{ percent }}%</span>
        </div>
      </div>

      <div v-if="nodeItems.length" class="node-list">
        <div
          v-for="item in nodeItems"
          :key="item.node_key"
          class="node-row"
          :class="`node-row--${item.status}`"
        >
          <span class="node-dot" aria-hidden="true" />
          <span class="node-title">{{ item.title }}</span>
          <span class="node-status">{{ item.statusLabel }}</span>
        </div>
      </div>

      <div v-if="stepCount" class="step-meta">
        执行步骤 {{ stepDone }} / {{ stepCount }}
      </div>
      <div v-if="toolCount" class="step-meta">
        工具调用 {{ toolCount }} 次
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { agentStatusMeta, stepStatusMetaOf } from '@/features/security/agent/statusMeta'

const props = defineProps({
  plan: { type: Object, default: null },
  run: { type: Object, default: null },
  steps: { type: Array, default: () => [] },
  toolCalls: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const statusMeta = computed(() => agentStatusMeta(props.run?.status))

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
    status: node.status,
    statusLabel: nodeStatusLabel(node.status)
  }))
})

const totalNodes = computed(() => nodeItems.value.length)
const doneNodes = computed(() =>
  nodeItems.value.filter((item) => ['succeeded', 'completed'].includes(item.status)).length
)
const percent = computed(() => {
  if (totalNodes.value === 0) return 0
  return Math.round((doneNodes.value / totalNodes.value) * 100)
})

const stepCount = computed(() => props.steps.length)
const stepDone = computed(() =>
  props.steps.filter((step) => step.status === 'completed').length
)
const toolCount = computed(() => props.toolCalls.length)

function nodeStatusLabel(status) {
  if (status === 'running') return '执行中'
  if (status === 'succeeded' || status === 'completed') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'ready') return '就绪'
  if (status === 'blocked') return '阻塞'
  if (status === 'skipped') return '跳过'
  return stepStatusMetaOf(status).label
}
</script>

<style scoped lang="scss">
.progress-card {
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

.card-head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.progress-card__empty {
  color: #8494a8;
  font-size: 12.5px;
}

.progress-bar-wrap {
  margin-bottom: 10px;
}

.progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 12px;
  color: #6a7890;
  font-variant-numeric: tabular-nums;
}

.node-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.node-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}

.node-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}

.node-row--running .node-dot {
  background: #2563eb;
  animation: node-pulse 1.2s infinite ease-in-out;
}

.node-row--succeeded .node-dot,
.node-row--completed .node-dot {
  background: #16a34a;
}

.node-row--failed .node-dot {
  background: #dc2626;
}

.node-row--ready .node-dot,
.node-row--pending .node-dot {
  background: #c2ccd9;
}

.node-row--blocked .node-dot {
  background: #d97706;
}

.node-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #1f2d3d;
}

.node-status {
  color: #8494a8;
  font-size: 11.5px;
  flex: none;
}

.step-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #8494a8;
  font-variant-numeric: tabular-nums;
}

@keyframes node-pulse {
  0%, 100% {
    opacity: 0.4;
  }
  50% {
    opacity: 1;
  }
}
</style>
