<template>
  <el-dialog
    :model-value="visible"
    title="源码证据"
    width="720px"
    class="code-evidence"
    @update:model-value="handleClose"
  >
    <div v-if="slice" class="evidence">
      <div class="evidence__head">
        <span class="evidence__file">{{ slice.file_path }}</span>
        <span class="evidence__range">第 {{ slice.start_line }}-{{ slice.end_line }} 行</span>
      </div>
      <pre class="evidence__code"><code v-for="(line, index) in slice.lines" :key="index">{{ slice.start_line + index }}  {{ line }}
</code></pre>
    </div>
    <div v-else class="evidence__empty">没有可显示的源码片段</div>
  </el-dialog>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  slice: { type: Object, default: null }
})

const emit = defineEmits(['close'])

function handleClose(value) {
  if (!value) emit('close')
}
</script>

<style scoped lang="scss">
.evidence__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12.5px;
  color: #52627a;
}
.evidence__file { font-weight: 600; word-break: break-all; }
.evidence__code {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 12.5px;
  line-height: 1.7;
  overflow-x: auto;
  max-height: 420px;
  overflow-y: auto;
  margin: 0;
}
.evidence__empty { color: #8494a8; font-size: 13px; }
</style>
