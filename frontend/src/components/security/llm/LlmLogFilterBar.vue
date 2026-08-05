<template>
  <section class="filter-panel">
    <div class="filter-row">
      <label class="date-field"><BaseIcon name="calendar" :size="15" /><input v-model="localStart" type="datetime-local" aria-label="开始时间" /></label>
      <label class="date-field"><BaseIcon name="calendar" :size="15" /><input v-model="localEnd" type="datetime-local" aria-label="结束时间" /></label>
      <input v-model.trim="filters.model" class="filter-input" placeholder="模型名称" />
      <select v-model="filters.operation" class="filter-select"><option value="">所有类型</option><option value="qa">问答</option><option value="suggestion">追问建议</option><option value="remediation">修复建议</option><option value="health_check">连通性测试</option></select>
      <div class="filter-actions"><BaseButton variant="ghost" @click="$emit('reset')">重置</BaseButton><BaseButton variant="primary" @click="apply"><BaseIcon name="search" :size="14" />搜索</BaseButton><BaseButton @click="$emit('view')"><BaseIcon name="eye" :size="14" />查看</BaseButton></div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseButton, BaseIcon } from '@/components/ui'

const props = defineProps({ filters: { type: Object, required: true } })
const emit = defineEmits(['search', 'reset', 'view'])
const localStart = computed({ get: () => props.filters.start, set: (value) => { props.filters.start = value } })
const localEnd = computed({ get: () => props.filters.end, set: (value) => { props.filters.end = value } })
const apply = () => emit('search')
</script>

<style scoped lang="scss">
.filter-panel { padding: 14px 16px; margin-bottom: 16px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; }
.filter-row { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.date-field { flex: 1 1 240px; position: relative; display: flex; align-items: center; min-width: 220px; color: #64748b; }
.date-field :deep(.ui-icon) { position: absolute; left: 10px; }
.date-field input, .filter-input, .filter-select { width: 100%; height: 34px; border: 1px solid #e2e8f0; border-radius: 6px; outline: none; background: #fff; color: #0f172a; font-size: 12px; }
.date-field input { padding: 0 8px 0 32px; } .filter-input { flex: 0 1 150px; padding: 0 10px; } .filter-select { flex: 0 1 140px; padding: 0 8px; }
.date-field input:focus, .filter-input:focus, .filter-select:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37, 99, 235, .12); }
.filter-actions { display: flex; gap: 6px; margin-left: auto; }
@media (max-width: 760px) { .date-field, .filter-input, .filter-select { flex-basis: 100%; } .filter-actions { margin-left: 0; } }
</style>
