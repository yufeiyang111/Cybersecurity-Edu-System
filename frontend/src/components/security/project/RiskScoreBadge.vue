<template>
  <el-tooltip v-if="hasRisk" placement="top" :content="risk.explanation || '风险说明缺失'" class="risk-badge">
    <span class="risk-badge-inner">
      <span class="risk-score" :style="{ color: scoreColor }">{{ formattedScore }}</span>
      <el-tag :type="priorityMeta.tagType" effect="dark" size="small">{{ priorityMeta.label }}</el-tag>
      <span class="risk-policy">{{ risk.policy_version }}</span>
    </span>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { riskPriorityMeta, riskScoreColor } from '@/features/security/presentation'

const props = defineProps({
  risk: { type: Object, default: null }
})

const hasRisk = computed(() => Boolean(props.risk && typeof props.risk.score === 'number'))
const formattedScore = computed(() => (hasRisk.value ? props.risk.score.toFixed(1) : '--'))
const priorityMeta = computed(() => riskPriorityMeta(props.risk?.priority))
const scoreColor = computed(() => riskScoreColor(props.risk?.score || 0))
</script>

<style scoped lang="scss">
.risk-badge-inner { display: inline-flex; align-items: center; gap: 6px; }
.risk-score { font-size: 15px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -.02em; }
.risk-policy { color: #829ab1; font-size: 11px; }
</style>
