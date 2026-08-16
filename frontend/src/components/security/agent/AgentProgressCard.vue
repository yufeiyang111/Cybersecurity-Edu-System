<template>
  <section class="progress-card">
    <div class="card-head">
      <h2>执行概览</h2>
      <el-tag
        :type="statusMeta.tagType"
        size="small"
      >
        {{ statusMeta.label }}
      </el-tag>
    </div>

    <div
      v-if="loading && !plan"
      class="progress-card__empty"
    >
      计划生成中…
    </div>

    <template v-else>
      <div
        v-if="totalNodes > 0"
        class="progress-bar-wrap"
      >
        <el-progress
          :percentage="percent"
          :aria-label="progressAriaLabel"
          :stroke-width="10"
          :show-text="false"
          :status="percent >= 100 ? 'success' : undefined"
        />
        <div class="progress-meta">
          <span>已完成 {{ completedNodes }} / {{ totalNodes }} 个计划节点</span>
          <span v-if="failedNodes > 0">失败 {{ failedNodes }}</span>
          <span>{{ percent }}%</span>
        </div>
      </div>

      <div
        v-if="showRuntimeMetrics"
        class="runtime-metrics"
      >
        <div class="runtime-metric">
          <span class="runtime-metric__label">{{ modelActivity.label }}</span>
          <strong class="runtime-metric__value">{{ modelActivity.value }}</strong>
          <small>{{ modelActivity.hint }}</small>
        </div>
        <div class="runtime-metric">
          <span class="runtime-metric__label">工具调用</span>
          <strong class="runtime-metric__value">{{ statistics.tool_call_total }}</strong>
          <small>
            成功 {{ statistics.tool_call_succeeded }} · 失败 {{ statistics.tool_call_failed }}
          </small>
        </div>
        <div class="runtime-metric">
          <span class="runtime-metric__label">Observation</span>
          <strong class="runtime-metric__value">{{ statistics.observation_total }}</strong>
          <small>
            代码证据 {{ statistics.observation_with_code_evidence }} · 未核验 {{ statistics.observation_unverified }}
          </small>
        </div>
        <div class="runtime-metric">
          <span class="runtime-metric__label">重规划</span>
          <strong class="runtime-metric__value">{{ statistics.replan_total }}</strong>
          <small>
            待审批 {{ statistics.approval_pending }} · 警告 {{ statistics.warning_total }}
          </small>
        </div>
      </div>

      <p
        v-else
        class="progress-card__empty"
      >
        暂未产生可审计的执行记录。
      </p>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { agentStatusMeta } from '@/features/security/agent/statusMeta'
import {
  resolveModelActivityMetric,
  resolveRunStatistics
} from '@/features/security/agent/runStatistics'

const props = defineProps({
  plan: {
    type: Object,
    default: null
  },
  run: {
    type: Object,
    default: null
  },
  stats: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const statusMeta = computed(() => agentStatusMeta(props.run?.status))
const statistics = computed(() => {
  return resolveRunStatistics({
    stats: props.stats,
    run: props.run,
    plan: props.plan
  })
})
const modelActivity = computed(() => {
  return resolveModelActivityMetric({
    run: props.run,
    statistics: statistics.value
  })
})
const totalNodes = computed(() => statistics.value.plan_node_total)
const completedNodes = computed(() => statistics.value.plan_node_completed)
const failedNodes = computed(() => statistics.value.plan_node_failed)
const percent = computed(() => {
  if (totalNodes.value === 0) {
    return 0
  }
  return Math.round((completedNodes.value / totalNodes.value) * 100)
})
const progressAriaLabel = computed(() => {
  return `计划节点完成 ${completedNodes.value} / ${totalNodes.value}，当前 ${percent.value}%`
})

const showRuntimeMetrics = computed(() => {
  return Boolean(props.run || props.plan || props.stats)
})
</script>

<style scoped lang="scss">
.progress-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 10px;
  padding: 14px 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.card-head h2 {
  margin: 0;
  color: #1f2937;
  font-size: 15px;
  font-weight: 600;
}

.progress-card__empty {
  margin: 0;
  color: #52627a;
  font-size: 12.5px;
}

.progress-bar-wrap {
  margin-bottom: 12px;
}

.progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
  color: #52627a;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.runtime-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.runtime-metric {
  min-width: 0;
  padding: 9px 10px;
  background: #f8fafc;
  border: 1px solid #edf1f5;
  border-radius: 6px;
}

.runtime-metric__label {
  color: #52627a;
  font-size: 11.5px;
}

.runtime-metric__value {
  margin: 3px 0;
  color: #1f2937;
  font-size: 18px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.runtime-metric small {
  display: block;
  overflow: hidden;
  color: #52627a;
  font-size: 11px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 767px) {
  .progress-card {
    padding: 12px;
  }

  .runtime-metrics {
    grid-template-columns: 1fr;
  }

  .progress-meta {
    flex-wrap: wrap;
  }
}
</style>