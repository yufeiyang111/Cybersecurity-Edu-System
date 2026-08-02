<template>
  <section class="ai-security-insight" aria-label="AI Security Insight">
    <div class="ai-security-insight__header">
      <div>
        <p>AI SECURITY INSIGHT</p>
        <h4>服务端生成的上下文研判</h4>
      </div>
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
.ai-security-insight { margin-top: 16px; padding: 16px; border: 1px solid #b7ead7; border-radius: 12px; background: linear-gradient(135deg, #f3fffb, #f8fcff); }
.ai-security-insight__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.ai-security-insight__header p { margin: 0 0 5px; color: #0e9384; font-size: 11px; font-weight: 700; letter-spacing: .1em; }
h4 { margin: 0; color: #102a43; font-size: 15px; }
.insight-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 16px 0 0; }
.insight-facts div { padding: 10px; border-radius: 8px; background: rgba(255, 255, 255, .72); }
dt { color: #627d98; font-size: 11px; }
dd { margin: 5px 0 0; color: #243b53; font-size: 13px; font-weight: 600; line-height: 1.45; }
.insight-warnings { margin-top: 14px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.insight-warnings strong { margin-right: 3px; color: #7c5d14; font-size: 12px; }
@media (max-width: 620px) { .insight-facts { grid-template-columns: 1fr; } }
</style>
