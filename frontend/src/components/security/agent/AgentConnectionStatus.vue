<template>
  <div class="connection-bar">
    <el-tag :type="meta.tagType" size="small">{{ meta.label }}</el-tag>
    <span class="connection-bar__meta">事件序号 {{ lastSequence }}</span>
    <span class="connection-bar__meta">状态版本 v{{ stateVersion }}</span>
    <span v-if="reasoningLive" class="connection-bar__reasoning">思维链实时展示中</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { connectionStateMetaOf } from '@/features/security/agent/statusMeta'

const props = defineProps({
  connectionState: { type: String, default: 'connecting' },
  lastSequence: { type: Number, default: 0 },
  stateVersion: { type: Number, default: 0 },
  reasoningLive: { type: Boolean, default: false }
})

const meta = computed(() => connectionStateMetaOf(props.connectionState))
</script>

<style scoped lang="scss">
.connection-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 14px;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  background: #fff;
  color: #52627a;
  font-size: 12.5px;
}

.connection-bar :deep(.el-tag--info) {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #52627a;
}

.connection-bar__meta {
  font-variant-numeric: tabular-nums;
}

.connection-bar__reasoning {
  color: #0b7fd1;
}
</style>
