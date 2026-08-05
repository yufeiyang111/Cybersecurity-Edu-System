<template>
  <div class="metric-chips"><span class="metric-chip"><BaseIcon name="dollar" :size="14" />用量 <strong>¥{{ Number(summary.total_cost || 0).toFixed(4) }}</strong></span><span class="metric-chip"><BaseIcon name="activity" :size="14" />RPM <strong>{{ Number(summary.rpm || 0).toFixed(2) }}</strong></span><span class="metric-chip"><BaseIcon name="zap" :size="14" />TPM <strong>{{ Math.round(summary.tpm || 0).toLocaleString('zh-CN') }}</strong></span></div>
</template>

<script setup>
import { BaseIcon } from '@/components/ui'
defineProps({ summary: { type: Object, default: () => ({}) } })
</script>

<style scoped lang="scss">
.metric-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.metric-chip { display: inline-flex; align-items: center; gap: 6px; padding: 7px 10px; border: 1px solid #e2e8f0; border-radius: 6px; color: #475569; font-size: 12px; } .metric-chip :deep(.ui-icon) { color: #2563eb; } .metric-chip strong { color: #0f172a; }
</style>
