<template>
  <article class="suggestion-card">
    <div class="suggestion-header">
      <div>
        <strong>建议 #{{ suggestion.id }}</strong>
        <span>生成于 {{ formatSecurityDate(suggestion.created_at) }}</span>
      </div>
      <el-tag :type="reviewStateTagType(suggestion.review_state)" effect="light">{{ reviewStateLabel(suggestion.review_state) }}</el-tag>
    </div>

    <AiSecurityInsight :suggestion="suggestion" />
    <p class="rationale">{{ suggestion.rationale }}</p>
    <ol v-if="suggestion.remediation_steps?.length" class="steps"><li v-for="step in suggestion.remediation_steps" :key="step">{{ step }}</li></ol>
    <CitationList :citations="suggestion.citations" />
    <PatchDiffViewer :patch-diff="suggestion.patch_diff" @copy="emit('copy-patch', $event)" />

    <div class="suggestion-footer">
      <span>建议仅供人工审阅，系统不会自动应用、执行、提交或推送补丁。</span>
      <el-button size="small" @click="emit('review', suggestion)">人工审核</el-button>
    </div>
  </article>
</template>

<script setup>
import AiSecurityInsight from './AiSecurityInsight.vue'
import CitationList from './CitationList.vue'
import PatchDiffViewer from './PatchDiffViewer.vue'
import { formatSecurityDate, reviewStateLabel, reviewStateTagType } from '@/features/security/presentation'

defineProps({
  suggestion: { type: Object, required: true }
})

const emit = defineEmits(['copy-patch', 'review'])
</script>

<style scoped lang="scss">
.suggestion-card { padding: 18px; border: 1px solid #b7ead7; border-radius: 14px; background: #fbfffd; }
.suggestion-header, .suggestion-footer { display: flex; gap: 12px; align-items: center; justify-content: space-between; }
.suggestion-header span, .suggestion-footer span { display: block; margin-top: 4px; color: #627d98; font-size: 12px; line-height: 1.55; }
.rationale { margin: 16px 0 0; color: #243b53; line-height: 1.65; }
.steps { margin: 10px 0 0; padding-left: 22px; color: #334e68; line-height: 1.6; }
.steps li + li { margin-top: 5px; }
.suggestion-footer { margin-top: 16px; padding-top: 14px; border-top: 1px solid #d9e2ec; }
@media (max-width: 760px) { .suggestion-header, .suggestion-footer { align-items: flex-start; flex-direction: column; } }
</style>
