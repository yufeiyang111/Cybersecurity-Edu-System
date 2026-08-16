<template>
  <div>
    <div
      v-if="safeMetrics.hypothesisCount"
      class="attack-path-metrics__grid"
    >
      <div>
        <span>代码证据覆盖</span>
        <strong>{{ formatRate(safeMetrics.codeEvidenceCoverage) }}</strong>
      </div>
      <div>
        <span>证据不足率</span>
        <strong>{{ formatRate(safeMetrics.evidenceInsufficientRate) }}</strong>
      </div>
      <div>
        <span>预算停止率</span>
        <strong>{{ formatRate(safeMetrics.budgetExhaustionRate) }}</strong>
      </div>
      <div>
        <span>每候选 Deep Review</span>
        <strong>{{ costLabel }}</strong>
      </div>
    </div>

    <p
      v-if="safeMetrics.skillCounts.length"
      class="attack-path-metrics__skills"
    >
      技能覆盖：
      <span
        v-for="skill in safeMetrics.skillCounts"
        :key="skill.skillKey"
      >
        {{ skill.skillKey }} × {{ skill.candidateCount }}
      </span>
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  metrics: {
    type: Object,
    default: () => ({}),
  },
})

const safeMetrics = computed(() => {
  const source = props.metrics || {}
  return {
    hypothesisCount: nonNegativeInteger(source.hypothesisCount),
    skillCounts: Array.isArray(source.skillCounts) ? source.skillCounts : [],
    codeEvidenceCoverage: rate(source.codeEvidenceCoverage),
    evidenceInsufficientRate: rate(source.evidenceInsufficientRate),
    budgetExhaustionRate: rate(source.budgetExhaustionRate),
    deepReviewCost: source.deepReviewCost || {},
  }
})
const costLabel = computed(() => {
  const cost = safeMetrics.value.deepReviewCost
  if (!cost.costKnown || !Number.isFinite(cost.averagePerHypothesis)) {
    return cost.callCount ? '价格未知' : '暂无调用'
  }
  return `$${cost.averagePerHypothesis.toFixed(4)}`
})

function formatRate(value) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

function nonNegativeInteger(value) {
  return Number.isInteger(value) && value >= 0 ? value : 0
}

function rate(value) {
  return typeof value === 'number' && value >= 0 && value <= 1 ? value : null
}
</script>

<style scoped lang="scss">
.attack-path-metrics__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.attack-path-metrics__grid div {
  padding: 9px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
}

.attack-path-metrics__grid span {
  display: block;
  color: #64748b;
  font-size: 11px;
}

.attack-path-metrics__grid strong {
  display: block;
  margin-top: 4px;
  color: #1e293b;
  font-size: 13px;
}

.attack-path-metrics__skills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  margin: 0 0 10px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.attack-path-metrics__skills span {
  color: #475569;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

@media (max-width: 768px) {
  .attack-path-metrics__grid {
    grid-template-columns: 1fr;
  }
}
</style>
