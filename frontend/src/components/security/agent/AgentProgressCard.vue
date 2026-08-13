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
import { agentStatusMeta } from '@/features/security/agent/statusMeta'

const props = defineProps({
  plan: { type: Object, default: null },
  run: { type: Object, default: null },
  steps: { type: Array, default: () => [] },
  toolCalls: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const statusMeta = computed(() => agentStatusMeta(props.run?.status))

const nodeItems = computed(() => {
  const nodes = props.plan?.nodes || []
  return nodes.map((node) => ({
    node_key: node.node_key,
    status: node.status
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

.step-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #8494a8;
  font-variant-numeric: tabular-nums;
}
</style>
