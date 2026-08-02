<template>
  <div v-if="seconds !== null" class="chat-thinking">
    <div class="ct-toggle" :class="{ open }" @click="open = !open">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M9 6l6 6-6 6" /></svg>
      已思考 {{ seconds }} 秒
    </div>
    <div v-if="open" class="ct-panel">
      <div class="ct-row">
        <span class="ct-label">检索来源</span>
        <span>{{ sourceCount }} 篇文档</span>
      </div>
      <div v-if="avgSimilarity !== null" class="ct-row">
        <span class="ct-label">平均相似度</span>
        <span>{{ avgSimilarity }}%</span>
      </div>
      <div v-if="confidence !== null" class="ct-row">
        <span class="ct-label">回答置信度</span>
        <span>{{ (confidence * 100).toFixed(0) }}%</span>
      </div>
      <div v-if="modelName" class="ct-row">
        <span class="ct-label">模型</span>
        <span>{{ modelName }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  seconds: { type: Number, default: null },
  sources: { type: Array, default: () => [] },
  confidence: { type: Number, default: null },
  modelName: { type: String, default: '' }
})

const open = ref(false)

const sourceCount = computed(() => (props.sources || []).length)
const avgSimilarity = computed(() => {
  const list = props.sources || []
  if (!list.length) return null
  const sum = list.reduce((acc, s) => acc + (Number(s.similarity) || 0), 0)
  return Math.round((sum / list.length) * 100)
})
</script>

<style lang="scss" scoped>
.chat-thinking { margin-bottom: 6px; }
.ct-toggle {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--chat-hollow);
  cursor: pointer; padding: 4px 0;
  user-select: none;
  svg { width: 13px; height: 13px; stroke: var(--chat-hollow); transition: transform .15s; }
  &.open svg { transform: rotate(90deg); }
}
.ct-panel {
  border-left: 2px solid var(--chat-hairline);
  padding: 2px 0 2px 14px;
  margin-top: 4px;
}
.ct-row {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  font-size: 13px; color: var(--chat-hollow); line-height: 1.7;
  .ct-label { flex-shrink: 0; }
}
</style>
