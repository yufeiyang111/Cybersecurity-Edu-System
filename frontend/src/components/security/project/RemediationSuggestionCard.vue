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
      <div class="suggestion-ops">
        <el-button size="small" :icon="ReviewIcon" @click="emit('review', suggestion)">人工审核</el-button>
        <el-button size="small" type="danger" plain :icon="DeleteIcon" :loading="deleting" @click="emit('remove', suggestion)">删除</el-button>
      </div>
    </div>
  </article>
</template>

<script setup>
import AiSecurityInsight from './AiSecurityInsight.vue'
import CitationList from './CitationList.vue'
import PatchDiffViewer from './PatchDiffViewer.vue'
import { Check as ReviewIcon, Delete as DeleteIcon } from '@element-plus/icons-vue'
import { formatSecurityDate, reviewStateLabel, reviewStateTagType } from '@/features/security/presentation'

defineProps({
  suggestion: { type: Object, required: true },
  deleting: { type: Boolean, default: false }
})

const emit = defineEmits(['copy-patch', 'review', 'remove'])
</script>

<style scoped lang="scss">
.suggestion-card { padding: 12px 14px; border: 1px solid #d9e9dd; border-radius: 6px; background: #f7fbf8; }
.suggestion-header, .suggestion-footer { display: flex; gap: 12px; align-items: center; justify-content: space-between; }
.suggestion-header strong { color: #1f2d3d; font-size: 13.5px; }
.suggestion-header span, .suggestion-footer span { display: block; margin-top: 2px; color: #6a7890; font-size: 12px; line-height: 1.55; }
.rationale { margin: 10px 0 0; color: #37465c; font-size: 13px; line-height: 1.65; }
.steps { margin: 8px 0 0; padding-left: 22px; color: #52627a; font-size: 13px; line-height: 1.6; }
.steps li + li { margin-top: 4px; }
.suggestion-footer { margin-top: 12px; padding-top: 10px; border-top: 1px solid #e2e7ee; }
.suggestion-ops { display: flex; gap: 8px; }
@media (max-width: 760px) { .suggestion-header, .suggestion-footer { align-items: flex-start; flex-direction: column; } }
</style>
