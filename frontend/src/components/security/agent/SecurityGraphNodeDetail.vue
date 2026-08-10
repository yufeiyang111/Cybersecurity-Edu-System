<template>
  <section v-if="node" class="node-card">
    <div class="card-head">
      <h2>节点详情</h2>
      <el-tag size="small" :type="typeTag(node.nodeType)">{{ typeLabel(node.nodeType) }}</el-tag>
    </div>
    <div class="node-card__label">{{ node.label }}</div>
    <div class="node-card__row" v-if="node.filePath">
      <span class="node-card__key">文件</span>
      <span class="node-card__value">{{ node.filePath }}</span>
    </div>
    <div class="node-card__actions">
      <el-button
        v-if="node.filePath"
        size="small"
        plain
        @click="requestSlice"
      >
        查看源码证据
      </el-button>
    </div>
    <div v-if="sliceError" class="node-card__error">{{ sliceError }}</div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { agentAPI } from '@/api'
import { useProjectSecurityGraph } from '@/composables/security/useProjectSecurityGraph'

const props = defineProps({
  node: { type: Object, default: null },
  runId: { type: Number, default: null }
})

const emit = defineEmits(['show-code'])

const sliceError = ref('')
const { nodeMeta } = useProjectSecurityGraph(() => props.runId)

const TYPE_TAG = {
  route: 'primary',
  middleware: 'warning',
  service: 'success',
  repository: 'warning',
  model: 'success',
  function: 'info',
  dependency: 'warning',
  external_call: 'danger',
  file: 'info'
}

const typeTag = computed(() => (type) => TYPE_TAG[type] || 'info')
const typeLabel = computed(() => (type) => nodeMeta(type).label)

async function requestSlice() {
  if (!props.runId || !props.node?.filePath) return
  sliceError.value = ''
  try {
    const response = await agentAPI.getGraphCodeSlice(props.runId, {
      file: props.node.filePath,
      start_line: 1,
      end_line: 50,
      reason: '图节点证据查看'
    })
    emit('show-code', response)
  } catch (error) {
    sliceError.value = error?.response?.data?.error || '源码读取失败'
  }
}
</script>

<style scoped lang="scss">
.node-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.node-card__label {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
  margin-bottom: 6px;
  word-break: break-all;
}
.node-card__row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12.5px;
  margin-bottom: 4px;
}
.node-card__key { color: #8494a8; flex: none; }
.node-card__value { color: #52627a; word-break: break-all; }
.node-card__actions { margin-top: 8px; }
.node-card__error { color: #b91c1c; font-size: 12.5px; margin-top: 6px; }
</style>
