<template>
  <el-tag :type="type" effect="dark" size="small">{{ label }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  severity: { type: String, required: true }
})

const definitions = {
  critical: ['danger', '严重'],
  high: ['danger', '高危'],
  medium: ['warning', '中危'],
  low: ['success', '低危'],
  info: ['info', '提示']
}

const type = computed(() => definitions[props.severity]?.[0] || 'info')
const label = computed(() => definitions[props.severity]?.[1] || props.severity)
</script>
