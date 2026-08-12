<template>
  <main class="llm-page">
    <header class="page-header">
      <div>
        <h1>模型调用分析</h1>
        <p>模型调用量、Token 消耗与缓存命中情况的统计。</p>
      </div>
      <div class="actions">
        <BaseButton @click="preferencesOpen = true">
          <BaseIcon name="settings" :size="14" />
          偏好设置
        </BaseButton>
        <BaseButton variant="ghost" @click="filterOpen = true">
          <BaseIcon name="filter" :size="14" />
          筛选
        </BaseButton>
      </div>
    </header>

    <LlmAnalyticsToolbar v-model="activeTab" />

    <div v-if="errorMessage" class="page-error">
      <BaseIcon name="alert-triangle" :size="16" />
      {{ errorMessage }}
    </div>

    <LlmSummaryBand :summary="analytics.summary" />
    <LlmUsageChart
      :analytics="analytics"
      :loading="loading"
      :default-chart-type="preferences.analytics_chart_type || 'bar'"
    />
    <LlmModelChart
      :analytics="analytics"
      :loading="loading"
      :mode="preferences.analytics_model_chart || 'trend'"
    />
    <template v-if="activeTab === 'models'">
      <LlmBreakdownPanel
        title="模型调用分析"
        name-label="模型"
        :rows="modelRows"
        :summary="analytics.summary"
      />
    </template>
    <template v-else>
      <LlmBreakdownPanel
        title="分流"
        name-label="供应商"
        :rows="providerRows"
        :summary="analytics.summary"
      />
    </template>

    <LlmAnalyticsFilterDialog
      v-model="filterOpen"
      :granularity="filters.granularity"
      :time-range="filters.time_range"
      :start="filters.start"
      :end="filters.end"
      @apply="applyFilters"
    />

    <LlmAnalyticsPreferencesDialog
      v-model="preferencesOpen"
      :preferences="preferences"
      :saving="preferencesSaving"
      @save="savePreferences"
    />
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { authAPI } from '@/api'
import { BaseButton, BaseIcon } from '@/components/ui'
import LlmAnalyticsToolbar from '@/components/security/llm/LlmAnalyticsToolbar.vue'
import LlmAnalyticsFilterDialog from '@/components/security/llm/LlmAnalyticsFilterDialog.vue'
import LlmAnalyticsPreferencesDialog from '@/components/security/llm/LlmAnalyticsPreferencesDialog.vue'
import LlmBreakdownPanel from '@/components/security/llm/LlmBreakdownPanel.vue'
import LlmModelChart from '@/components/security/llm/LlmModelChart.vue'
import LlmSummaryBand from '@/components/security/llm/LlmSummaryBand.vue'
import LlmUsageChart from '@/components/security/llm/LlmUsageChart.vue'
import { useLlmAnalytics } from '@/composables/security/useLlmAnalytics'

const { analytics, loading, errorMessage, filters, load } = useLlmAnalytics()
const activeTab = ref('models')
const filterOpen = ref(false)
const preferencesOpen = ref(false)
const preferencesSaving = ref(false)
const preferences = reactive({
  analytics_time_range: '1d',
  analytics_time_granularity: 'hour',
  analytics_chart_type: 'bar',
  analytics_model_chart: 'trend'
})

const modelRows = computed(() => (analytics.value.models || []).map((item) => ({
  name: item.model || '未知模型',
  calls: item.calls,
  tokens: item.tokens,
  cache_hit_rate: item.cache_hit_rate
})))

const providerRows = computed(() => (analytics.value.providers || []).map((item) => ({
  name: item.provider_name || '未知供应商',
  calls: item.calls,
  tokens: item.tokens,
  cache_hit_rate: item.cache_hit_rate
})))

const applyFilters = (payload) => {
  Object.assign(filters, {
    time_range: payload.time_range || '',
    start: payload.start || '',
    end: payload.end || '',
    granularity: payload.granularity || 'hour'
  })
  filterOpen.value = false
  load()
}

const savePreferences = async (payload) => {
  preferencesSaving.value = true
  try {
    const response = await authAPI.updatePreferences(payload)
    Object.assign(preferences, response.preferences || payload)
    Object.assign(filters, {
      time_range: response.preferences?.analytics_time_range || payload.analytics_time_range,
      granularity: response.preferences?.analytics_time_granularity || payload.analytics_time_granularity,
      start: '',
      end: ''
    })
    preferencesOpen.value = false
    ElMessage.success('偏好设置已保存')
    load()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '保存偏好设置失败')
  } finally {
    preferencesSaving.value = false
  }
}

onMounted(async () => {
  try {
    const response = await authAPI.getPreferences()
    Object.assign(preferences, response.preferences || {})
    Object.assign(filters, {
      time_range: response.preferences?.analytics_time_range || '1d',
      granularity: response.preferences?.analytics_time_granularity || 'hour'
    })
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载偏好设置失败')
  }
  load()
})
</script>

<style scoped lang="scss">
.llm-page {
  min-height: 100vh;
  padding: 28px 32px 70px;
  background: #ffffff;
  color: #0f172a;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
}

.page-header h1 {
  margin: 0;
  font-size: 20px;
}

.page-header p {
  margin: 5px 0 0;
  color: #475569;
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 8px;
}

.page-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  margin-bottom: 14px;
  border: 1px solid #fecaca;
  border-radius: 7px;
  background: #fef2f2;
  color: #dc2626;
  font-size: 13px;
}

@media (max-width: 900px) {
  .llm-page {
    padding: 22px 20px 60px;
  }
}

@media (max-width: 640px) {
  .llm-page {
    padding: 18px 12px 50px;
  }

  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
