<template>
  <section class="ai-security-insight" aria-label="AI Security Insight">
    <div class="ai-security-insight__header">
      <h4>服务端生成的上下文研判</h4>
      <el-tag type="success" effect="light">需人工审核</el-tag>
    </div>

    <dl class="insight-facts">
      <div>
        <dt>生成来源</dt>
        <dd>{{ providerLabel }}</dd>
      </div>
      <div>
        <dt>置信度</dt>
        <dd>{{ confidenceLabel }}</dd>
      </div>
      <div>
        <dt>知识引用</dt>
        <dd>{{ citationLabel }}</dd>
      </div>
      <div>
        <dt>补丁材料</dt>
        <dd>{{ patchLabel }}</dd>
      </div>
    </dl>

    <div v-if="suggestion.warning_codes?.length" class="insight-warnings">
      <strong>服务端安全提示</strong>
      <el-tag
        v-for="warning in suggestion.warning_codes"
        :key="warning"
        type="warning"
        size="small"
        effect="light"
        :title="warning"
      >{{ warningCodeLabel(warning) }}</el-tag>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { warningCodeLabel } from '@/features/security/warningCodes'

const props = defineProps({
  suggestion: { type: Object, required: true }
})

const providerLabel = computed(() => {
  const provider = props.suggestion.provider || '服务端未提供'
  return props.suggestion.model ? `${provider} · ${props.suggestion.model}` : provider
})

const confidenceLabel = computed(() => {
  const confidence = props.suggestion.confidence
  return typeof confidence === 'number' ? `${Math.round(confidence * 100)}%` : '服务端未提供'
})

const citationLabel = computed(() => {
  const count = props.suggestion.citations?.length || 0
  return count ? `提供 ${count} 条 RAG 引用` : '本次建议未提供 RAG 引用'
})

const patchLabel = computed(() => props.suggestion.patch_diff
  ? '已提供受限 Unified Diff，仍需人工验证'
  : '未提供可审阅补丁')
</script>

<style scoped lang="scss">
.ai-security-insight { margin-top: 10px; padding: 12px 14px; border: 1px solid #c3e6d4; border-radius: 6px; background: #f4fbf7; }
.ai-security-insight__header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h4 { margin: 0; color: #1f2d3d; font-size: 14px; }
.insight-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 10px 0 0; }
.insight-facts div { padding: 8px 10px; border-radius: 6px; background: rgba(255, 255, 255, .8); }
dt { color: #6a7890; font-size: 11px; }
dd { margin: 3px 0 0; color: #37465c; font-size: 12.5px; font-weight: 600; line-height: 1.45; }
.insight-warnings { margin-top: 10px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.insight-warnings strong { margin-right: 3px; color: #7c5d14; font-size: 12px; }
@media (max-width: 620px) { .insight-facts { grid-template-columns: 1fr; } }
</style>
