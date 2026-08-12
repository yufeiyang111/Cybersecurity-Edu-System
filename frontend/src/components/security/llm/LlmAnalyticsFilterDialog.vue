<template>
  <el-dialog
    v-model="visible"
    title="模型分析筛选"
    width="min(560px, calc(100vw - 32px))"
    destroy-on-close
  >
    <div class="filter-body">
      <p class="filter-subtitle">按时间范围和用户筛选模型分析视图。</p>

      <div class="section">
        <div class="section-title">快速范围</div>
        <div class="quick-buttons">
          <button
            v-for="item in quickRanges"
            :key="item.value"
            class="quick-button"
            :class="{ active: activeQuick === item.value }"
            @click="applyQuick(item)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <div class="section">
        <div class="section-title">自定义时间范围</div>
        <div class="date-grid">
          <div class="date-row">
            <label class="date-label" for="filter-start">起始时间</label>
            <div class="date-input">
              <BaseIcon name="calendar" :size="15" />
              <input
                id="filter-start"
                v-model="localStart"
                type="datetime-local"
                aria-label="起始时间"
                @change="onManualChange"
              />
            </div>
          </div>
          <div class="date-row">
            <label class="date-label" for="filter-end">结束时间</label>
            <div class="date-input">
              <BaseIcon name="calendar" :size="15" />
              <input
                id="filter-end"
                v-model="localEnd"
                type="datetime-local"
                aria-label="结束时间"
                @change="onManualChange"
              />
            </div>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">图表设置</div>
        <div class="granularity-row">
          <label class="granularity-label" for="filter-granularity">时间粒度</label>
          <select
            id="filter-granularity"
            v-model="localGranularity"
            class="granularity-select"
          >
            <option value="hour">小时</option>
            <option value="day">天</option>
            <option value="week">周</option>
            <option value="month">月</option>
          </select>
        </div>
      </div>
    </div>

    <template #footer>
      <BaseButton @click="reset">重置</BaseButton>
      <BaseButton variant="primary" @click="apply">应用筛选器</BaseButton>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { BaseButton, BaseIcon } from '@/components/ui'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  granularity: { type: String, default: 'hour' },
  timeRange: { type: String, default: '' },
  start: { type: String, default: '' },
  end: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'apply'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const quickRanges = [
  { value: '1d', label: '1天', days: 1 },
  { value: '7d', label: '7天', days: 7 },
  { value: '14d', label: '14天', days: 14 },
  { value: '29d', label: '29天', days: 29 }
]

const DEFAULT_RANGE = '1d'
const activeQuick = ref(DEFAULT_RANGE)
const localGranularity = ref('hour')
const localStart = ref('')
const localEnd = ref('')

const formatDateTime = (date) => {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const computeRange = (days) => {
  const now = new Date()
  const start = new Date(now.getTime() - days * 24 * 60 * 60 * 1000)
  return { start: formatDateTime(start), end: formatDateTime(now) }
}

const applyQuick = (item) => {
  activeQuick.value = item.value
  const range = computeRange(item.days)
  localStart.value = range.start
  localEnd.value = range.end
}

const onManualChange = () => {
  activeQuick.value = ''
}

const reset = () => {
  activeQuick.value = DEFAULT_RANGE
  localGranularity.value = 'hour'
  const range = computeRange(quickRanges.find((item) => item.value === DEFAULT_RANGE).days)
  localStart.value = range.start
  localEnd.value = range.end
}

const syncFromParent = () => {
  localGranularity.value = props.granularity || 'hour'
  const matched = quickRanges.find((item) => item.value === props.timeRange)
  if (matched) {
    activeQuick.value = matched.value
    const range = computeRange(matched.days)
    localStart.value = range.start
    localEnd.value = range.end
  } else if (props.start || props.end) {
    activeQuick.value = ''
    localStart.value = props.start ? props.start.replace(' ', 'T') : ''
    localEnd.value = props.end ? props.end.replace(' ', 'T') : ''
  } else {
    reset()
  }
}

const apply = () => {
  emit('apply', {
    time_range: activeQuick.value || null,
    start: localStart.value.replace('T', ' '),
    end: localEnd.value.replace('T', ' '),
    granularity: localGranularity.value
  })
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      syncFromParent()
    }
  }
)
</script>

<style scoped lang="scss">
.filter-body {
  padding-bottom: 4px;
}

.filter-subtitle {
  margin: 0 0 16px;
  color: #64748b;
  font-size: 13px;
}

.section {
  margin-bottom: 18px;
}

.section-title {
  margin-bottom: 8px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
}

.quick-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-button {
  height: 32px;
  padding: 0 16px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.quick-button:hover {
  border-color: #2563eb;
  color: #2563eb;
}

.quick-button.active {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.date-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.date-row {
  display: grid;
  grid-template-columns: 84px 1fr;
  align-items: center;
  gap: 10px;
}

.date-label,
.granularity-label {
  color: #475569;
  font-size: 13px;
}

.date-input {
  position: relative;
  display: flex;
  align-items: center;
  color: #64748b;
}

.date-input :deep(.ui-icon) {
  position: absolute;
  left: 10px;
}

.date-input input {
  width: 100%;
  height: 34px;
  padding: 0 10px 0 34px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  outline: none;
  background: #fff;
  color: #0f172a;
  font-size: 13px;
}

.date-input input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.granularity-row {
  display: grid;
  grid-template-columns: 84px 1fr;
  align-items: center;
  gap: 10px;
}

.granularity-select {
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

.granularity-select:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

@media (max-width: 480px) {
  .date-row,
  .granularity-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
