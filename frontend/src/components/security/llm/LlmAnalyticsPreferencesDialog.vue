<template>
  <el-dialog
    v-model="visible"
    title="偏好设置"
    width="min(560px, calc(100vw - 32px))"
    destroy-on-close
  >
    <div class="pref-body">
      <p class="pref-subtitle">设置模型分析的默认时间范围和图表。</p>

      <div class="section">
        <div class="section-title">模型分析默认设置</div>
        <div class="pref-row">
          <label class="pref-label" for="pref-time-range">默认时间范围</label>
          <select
            id="pref-time-range"
            v-model="form.analytics_time_range"
            class="pref-select"
          >
            <option value="1d">1天</option>
            <option value="7d">7天</option>
            <option value="14d">14天</option>
            <option value="29d">29天</option>
          </select>
        </div>
        <div class="pref-row">
          <label class="pref-label" for="pref-granularity">默认时间粒度</label>
          <select
            id="pref-granularity"
            v-model="form.analytics_time_granularity"
            class="pref-select"
          >
            <option value="hour">小时</option>
            <option value="day">天</option>
            <option value="week">周</option>
            <option value="month">月</option>
          </select>
        </div>
        <div class="pref-row">
          <label class="pref-label" for="pref-chart-type">默认消耗分布图</label>
          <select
            id="pref-chart-type"
            v-model="form.analytics_chart_type"
            class="pref-select"
          >
            <option value="bar">柱状图</option>
            <option value="area">面积图</option>
          </select>
        </div>
        <div class="pref-row">
          <label class="pref-label" for="pref-model-chart">默认模型调用图</label>
          <select
            id="pref-model-chart"
            v-model="form.analytics_model_chart"
            class="pref-select"
          >
            <option value="trend">调用趋势</option>
            <option value="distribution">调用次数分布</option>
            <option value="ranking">调用次数排行</option>
          </select>
        </div>
      </div>
    </div>

    <template #footer>
      <BaseButton @click="visible = false">取消</BaseButton>
      <BaseButton variant="primary" :disabled="saving" @click="save">
        {{ saving ? '保存中...' : '保存设置' }}
      </BaseButton>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { BaseButton } from '@/components/ui'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  preferences: { type: Object, default: null },
  saving: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'save'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const form = reactive({
  analytics_time_range: '1d',
  analytics_time_granularity: 'hour',
  analytics_chart_type: 'bar',
  analytics_model_chart: 'trend'
})

const syncForm = (preferences) => {
  if (!preferences) return
  form.analytics_time_range = preferences.analytics_time_range || '1d'
  form.analytics_time_granularity = preferences.analytics_time_granularity || 'hour'
  form.analytics_chart_type = preferences.analytics_chart_type || 'bar'
  form.analytics_model_chart = preferences.analytics_model_chart || 'trend'
}

watch(
  () => props.preferences,
  (preferences) => syncForm(preferences),
  { deep: true, immediate: true }
)

watch(
  () => props.modelValue,
  (open) => {
    if (open) syncForm(props.preferences)
  }
)

const save = () => emit('save', { ...form })
</script>

<style scoped lang="scss">
.pref-body {
  padding-bottom: 4px;
}

.pref-subtitle {
  margin: 0 0 16px;
  color: #64748b;
  font-size: 13px;
}

.section {
  margin-bottom: 4px;
}

.section-title {
  margin-bottom: 12px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
}

.pref-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.pref-label {
  color: #475569;
  font-size: 13px;
}

.pref-select {
  width: 100%;
  height: 34px;
  padding: 0 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  outline: none;
  background: #fff;
  color: #0f172a;
  font-size: 13px;
}

.pref-select:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

@media (max-width: 480px) {
  .pref-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
