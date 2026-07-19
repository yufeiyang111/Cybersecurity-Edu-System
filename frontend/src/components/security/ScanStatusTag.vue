<template>
  <el-tag :type="type" effect="light" size="small">{{ label }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true }
})

const definitions = {
  created: ['info', '等待校验'],
  validating: ['warning', '校验中'],
  snapshotting: ['warning', '创建快照'],
  scanning: ['primary', '扫描中'],
  completed: ['success', '已完成'],
  completed_with_warnings: ['warning', '完成（有警告）'],
  failed: ['danger', '失败'],
  canceled: ['info', '已取消']
}

const type = computed(() => definitions[props.status]?.[0] || 'info')
const label = computed(() => definitions[props.status]?.[1] || props.status)
</script>
