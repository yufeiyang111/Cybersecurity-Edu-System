<template>
  <article :id="`finding-${finding.id}`" class="finding-item" :class="{ 'finding-item--focused': focused }" tabindex="-1">
    <div class="finding-topline">
      <FindingSeverityTag :severity="finding.severity" />
      <code>{{ finding.rule_id }}</code>
      <span v-if="finding.cwe_id">{{ finding.cwe_id }}</span>
      <span v-if="finding.cve_id">{{ finding.cve_id }}</span>
      <span class="finding-status">{{ finding.status }}</span>
    </div>
    <p>{{ finding.message }}</p>
    <div class="finding-meta">
      <span>{{ finding.category?.toUpperCase() || 'UNKNOWN' }}</span>
      <code>{{ finding.file_path }}:{{ finding.start_line }}</code>
      <span>置信度：{{ confidenceLabel }}</span>
    </div>
    <div v-if="finding.evidence?.[0]?.content" class="evidence">
      <span>脱敏证据</span>
      <code>{{ finding.evidence[0].content }}</code>
    </div>

    <div class="finding-actions">
      <el-button type="primary" size="small" :loading="loading" @click="emit('generate', finding)">生成修复建议</el-button>
      <el-button text type="primary" size="small" :loading="loading" @click="emit('load-suggestions', finding.id)">刷新历史建议</el-button>
    </div>
    <el-alert v-if="errorMessage" type="error" :title="errorMessage" :closable="false" show-icon class="suggestion-error" />
    <p v-else-if="suggestionsLoaded && suggestions.length === 0" class="empty-suggestions">暂未生成修复建议。</p>

    <div v-if="suggestions.length" class="suggestion-list">
      <RemediationSuggestionCard
        v-for="suggestion in suggestions"
        :key="suggestion.id"
        :suggestion="suggestion"
        @copy-patch="emit('copy-patch', $event)"
        @review="emit('review', $event)"
      />
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import FindingSeverityTag from '@/components/security/FindingSeverityTag.vue'
import RemediationSuggestionCard from './RemediationSuggestionCard.vue'

const props = defineProps({
  finding: { type: Object, required: true },
  suggestions: { type: Array, default: () => [] },
  suggestionsLoaded: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  focused: { type: Boolean, default: false }
})

const emit = defineEmits(['generate', 'load-suggestions', 'copy-patch', 'review'])
const confidenceLabel = computed(() => typeof props.finding.confidence === 'number'
  ? `${Math.round(props.finding.confidence * 100)}%`
  : '服务端未提供')
</script>

<style scoped lang="scss">
.finding-item { padding: 20px; border: 1px solid #d9e2ec; border-radius: 14px; background: #fff; transition: box-shadow .2s ease, border-color .2s ease; }
.finding-item--focused { border-color: #0e9384; box-shadow: 0 0 0 3px rgba(14, 147, 132, .16); }
.finding-topline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.finding-topline code, .finding-meta code { color: #334e68; background: #eef3f8; padding: 3px 6px; border-radius: 4px; font-size: 12px; overflow-wrap: anywhere; }
.finding-topline span { color: #627d98; font-size: 12px; }
.finding-status { text-transform: capitalize; }
.finding-item > p { margin: 12px 0; color: #243b53; line-height: 1.65; }
.finding-meta { display: flex; gap: 10px; flex-wrap: wrap; color: #627d98; font-size: 12px; }
.evidence { margin-top: 14px; padding: 10px; display: flex; gap: 8px; align-items: flex-start; background: #fff8e6; border-radius: 8px; font-size: 13px; }
.evidence span { white-space: nowrap; color: #8b651a; }
.evidence code { color: #624b13; overflow-wrap: anywhere; }
.finding-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
.suggestion-error { margin-top: 12px; }
.empty-suggestions { margin: 14px 0 0; color: #627d98; font-size: 13px; }
.suggestion-list { display: grid; gap: 12px; margin-top: 16px; }
</style>
