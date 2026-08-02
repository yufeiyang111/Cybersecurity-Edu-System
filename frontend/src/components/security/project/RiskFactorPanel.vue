<template>
  <div v-if="risk" class="risk-factor-panel" :aria-label="`风险因子面板：${risk.explanation}`">
    <p class="risk-explanation">{{ risk.explanation }}</p>
    <div class="factor-list">
      <div v-for="factor in risk.factors" :key="factor.name" class="factor-row">
        <span class="factor-name" :title="factor.explanation">{{ factorLabel(factor.name) }}</span>
        <span class="factor-bar" :aria-hidden="true">
          <span
            class="factor-fill"
            :style="{ width: fillPercent(factor), background: scoreColor(factor.contribution * 100) }"
          />
        </span>
        <span class="factor-contribution">{{ (factor.contribution * 100).toFixed(1) }}</span>
        <span class="factor-weight">w{{ (factor.weight * 100).toFixed(0) }}%</span>
        <p class="factor-explanation">{{ factor.explanation }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { riskFactorLabel, riskScoreColor } from '@/features/security/presentation'

defineProps({
  risk: { type: Object, default: null }
})

const factorLabel = riskFactorLabel
const scoreColor = riskScoreColor
const fillPercent = (factor) => `${Math.max(0, Math.min(100, factor.contribution * 100))}%`
</script>

<style scoped lang="scss">
.risk-factor-panel { margin-top: 14px; padding: 14px; border: 1px dashed #c4d3e0; border-radius: 10px; background: #f9fbfd; }
.risk-explanation { margin: 0 0 12px; color: #486581; font-size: 13px; line-height: 1.6; }
.factor-list { display: grid; gap: 10px; }
.factor-row { display: grid; grid-template-columns: 88px minmax(0, 1fr) 40px 48px; gap: 8px; align-items: center; }
.factor-name { color: #334e68; font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.factor-bar { height: 8px; border-radius: 4px; background: #e6eef5; overflow: hidden; }
.factor-fill { display: block; height: 100%; border-radius: 4px; transition: width .3s ease; }
.factor-contribution { color: #243b53; font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.factor-weight { color: #829ab1; font-size: 11px; text-align: right; white-space: nowrap; }
.factor-explanation { grid-column: 1 / -1; margin: 2px 0 0; color: #627d98; font-size: 12px; line-height: 1.55; }
</style>
