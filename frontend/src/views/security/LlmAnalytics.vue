<template>
  <main class="llm-page"><header class="page-header"><div><h1>模型调用分析</h1><p>查看模型调用量、Token 消耗和缓存命中情况的详细统计数据。</p></div><div class="actions"><BaseButton><BaseIcon name="settings" :size="14" />偏好设置</BaseButton><BaseButton><BaseIcon name="filter" :size="14" />筛选</BaseButton></div></header><LlmAnalyticsToolbar /><div v-if="errorMessage" class="page-error"><BaseIcon name="alert-triangle" :size="16" />{{ errorMessage }}</div><LlmSummaryBand :summary="analytics.summary" /><LlmUsageChart :analytics="analytics" :loading="loading" /><LlmModelBreakdown :models="analytics.models" :summary="analytics.summary" /></main>
</template>

<script setup>
import { onMounted } from 'vue'
import { BaseButton, BaseIcon } from '@/components/ui'
import LlmAnalyticsToolbar from '@/components/security/llm/LlmAnalyticsToolbar.vue'
import LlmModelBreakdown from '@/components/security/llm/LlmModelBreakdown.vue'
import LlmSummaryBand from '@/components/security/llm/LlmSummaryBand.vue'
import LlmUsageChart from '@/components/security/llm/LlmUsageChart.vue'
import { useLlmAnalytics } from '@/composables/security/useLlmAnalytics'

const { analytics, loading, errorMessage, load } = useLlmAnalytics()
onMounted(load)
</script>

<style scoped lang="scss">
.llm-page{min-height:100vh;padding:28px 32px 70px;background:#f8fafc;color:#0f172a}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:16px}.page-header h1{margin:0;font-size:20px}.page-header p{margin:5px 0 0;color:#475569;font-size:13px}.actions{display:flex;gap:8px}.page-error{display:flex;align-items:center;gap:8px;padding:11px 14px;margin-bottom:14px;border:1px solid #fecaca;border-radius:7px;background:#fef2f2;color:#dc2626;font-size:13px}@media(max-width:900px){.llm-page{padding:22px 20px 60px}}@media(max-width:640px){.llm-page{padding:18px 12px 50px}.page-header{align-items:flex-start;flex-direction:column}.actions{width:100%;justify-content:flex-end}}
</style>
