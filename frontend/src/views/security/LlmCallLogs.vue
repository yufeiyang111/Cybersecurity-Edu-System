<template>
  <main class="llm-page">
    <header class="page-header"><div><h1>通用日志</h1><p>查看所有模型调用的详细日志记录，支持按时间、模型、分组筛选。</p></div><div class="actions"><BaseButton @click="load"><BaseIcon name="refresh" :size="14" />刷新</BaseButton><BaseButton variant="primary" @click="search"><BaseIcon name="search" :size="14" />搜索</BaseButton></div></header>
    <div v-if="errorMessage" class="page-error"><BaseIcon name="alert-triangle" :size="16" />{{ errorMessage }}</div>
    <LlmLogFilterBar :filters="filters" @search="search" @reset="reset" @view="search" />
    <LlmLogMetricChips :summary="summary" />
    <BasePanel class="table-panel"><template #default><LlmCallLogTable :logs="logs" :loading="loading" /></template><template #footer><LlmLogPagination :pagination="pagination" @change-page="changePage" @change-per-page="changePerPage" /></template></BasePanel>
  </main>
</template>

<script setup>
import { onMounted } from 'vue'
import { BaseButton, BaseIcon, BasePanel } from '@/components/ui'
import LlmCallLogTable from '@/components/security/llm/LlmCallLogTable.vue'
import LlmLogFilterBar from '@/components/security/llm/LlmLogFilterBar.vue'
import LlmLogMetricChips from '@/components/security/llm/LlmLogMetricChips.vue'
import LlmLogPagination from '@/components/security/llm/LlmLogPagination.vue'
import { useLlmLogs } from '@/composables/security/useLlmLogs'

const { logs, summary, pagination, filters, loading, errorMessage, load, search, reset, changePage, changePerPage } = useLlmLogs()
onMounted(load)
</script>

<style scoped lang="scss">
.llm-page{min-height:100vh;padding:28px 32px 70px;background:#f8fafc;color:#0f172a}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}.page-header h1{margin:0;font-size:20px}.page-header p{margin:5px 0 0;color:#475569;font-size:13px}.actions{display:flex;gap:8px}.page-error{display:flex;align-items:center;gap:8px;padding:11px 14px;margin-bottom:14px;border:1px solid #fecaca;border-radius:7px;background:#fef2f2;color:#dc2626;font-size:13px}.table-panel :deep(.ui-panel__body){padding:0}.table-panel :deep(.ui-panel__footer){padding:0 12px}@media(max-width:900px){.llm-page{padding:22px 20px 60px}}@media(max-width:640px){.llm-page{padding:18px 12px 50px}.page-header{align-items:flex-start;flex-direction:column}.actions{width:100%;justify-content:flex-end}}
</style>
