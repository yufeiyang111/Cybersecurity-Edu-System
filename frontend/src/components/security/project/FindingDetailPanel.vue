<template>
  <section class="finding-detail-panel" :class="{ 'finding-detail-panel--empty': !finding }">
    <template v-if="finding">
      <div class="fdp-topline">
        <FindingSeverityTag :severity="finding.severity" />
        <RiskScoreBadge :risk="finding.risk" />
        <code>{{ finding.rule_id }}</code>
        <span v-if="finding.cwe_id">{{ finding.cwe_id }}</span>
        <span v-if="finding.cve_id">{{ finding.cve_id }}</span>
        <span class="fdp-status">{{ finding.status }}</span>
      </div>
      <p class="fdp-message">{{ finding.message }}</p>
      <div class="fdp-meta">
        <span>{{ finding.category?.toUpperCase() || 'UNKNOWN' }}</span>
        <code>{{ finding.file_path }}:{{ finding.start_line }}</code>
        <span>置信度：{{ confidenceLabel }}</span>
      </div>
      <div v-if="finding.evidence?.[0]?.content" class="fdp-evidence">
        <span>脱敏证据</span>
        <code>{{ finding.evidence[0].content }}</code>
      </div>

      <el-button v-if="finding.risk" text size="small" class="fdp-factor-toggle" @click="factorsVisible = !factorsVisible">
        {{ factorsVisible ? '收起风险因子' : '展开风险因子' }}
      </el-button>
      <RiskFactorPanel v-if="factorsVisible" :risk="finding.risk" />

      <div class="fdp-actions">
        <el-button type="primary" size="small" :loading="loading" @click="emit('generate', finding)">生成修复建议</el-button>
        <el-button text type="primary" size="small" :loading="loading" @click="emit('load-suggestions', finding.id)">刷新历史建议</el-button>
      </div>
      <el-alert v-if="errorMessage" type="error" :title="errorMessage" :closable="false" show-icon class="fdp-suggestion-error" />
      <p v-else-if="suggestionsLoaded && suggestions.length === 0" class="fdp-empty-suggestions">暂未生成修复建议。</p>

      <div v-if="suggestions.length" class="fdp-suggestion-list">
        <RemediationSuggestionCard
          v-for="suggestion in suggestions"
          :key="suggestion.id"
          :suggestion="suggestion"
          @copy-patch="emit('copy-patch', $event)"
          @review="emit('review', $event)"
        />
      </div>
    </template>
    <el-empty v-else description="从左侧选择一条风险发现查看详情。" />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import FindingSeverityTag from '@/components/security/FindingSeverityTag.vue'
import RemediationSuggestionCard from './RemediationSuggestionCard.vue'
import RiskFactorPanel from './RiskFactorPanel.vue'
import RiskScoreBadge from './RiskScoreBadge.vue'

const props = defineProps({
  finding: { type: Object, default: null },
  suggestions: { type: Array, default: () => [] },
  suggestionsLoaded: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
})

const emit = defineEmits(['generate', 'load-suggestions', 'copy-patch', 'review'])
const factorsVisible = ref(false)
const confidenceLabel = computed(() => typeof props.finding?.confidence === 'number'
  ? `${Math.round(props.finding.confidence * 100)}%`
  : '服务端未提供')
</script>

<style scoped lang="scss">
.finding-detail-panel { padding: 20px; border: 1px solid #d9e2ec; border-radius: 14px; background: #fff; }
.finding-detail-panel--empty { display: flex; align-items: center; justify-content: center; min-height: 240px; }
.fdp-topline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fdp-topline code, .fdp-meta code { color: #334e68; background: #eef3f8; padding: 3px 6px; border-radius: 4px; font-size: 12px; overflow-wrap: anywhere; }
.fdp-topline span { color: #627d98; font-size: 12px; }
.fdp-status { text-transform: capitalize; }
.fdp-message { margin: 12px 0; color: #243b53; line-height: 1.65; }
.fdp-meta { display: flex; gap: 10px; flex-wrap: wrap; color: #627d98; font-size: 12px; }
.fdp-evidence { margin-top: 14px; padding: 10px; display: flex; gap: 8px; align-items: flex-start; background: #fff8e6; border-radius: 8px; font-size: 13px; }
.fdp-evidence span { white-space: nowrap; color: #8b651a; }
.fdp-evidence code { color: #624b13; overflow-wrap: anywhere; }
.fdp-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
.fdp-factor-toggle { margin: 10px 0 0; padding: 0; }
.fdp-suggestion-error { margin-top: 12px; }
.fdp-empty-suggestions { margin: 14px 0 0; color: #627d98; font-size: 13px; }
.fdp-suggestion-list { display: grid; gap: 12px; margin-top: 16px; }
</style>
