<template>
  <section class="finding-detail-panel" :class="{ 'finding-detail-panel--empty': !finding }">
    <template v-if="finding">
      <div class="fdp-head">
        <h3>{{ finding.file_path }}:{{ finding.start_line }}</h3>
        <span class="fdp-risk">风险分 {{ riskScoreText }}</span>
      </div>
      <div class="panel-body">
        <div class="fdp-topline">
          <FindingSeverityTag :severity="finding.severity" />
          <code>{{ finding.rule_id }}</code>
          <span v-if="finding.cwe_id">{{ finding.cwe_id }}</span>
          <span v-if="finding.cve_id">{{ finding.cve_id }}</span>
          <span class="fdp-status">{{ finding.status }}</span>
        </div>
        <p class="fdp-message">{{ finding.message }}</p>
        <div class="fdp-meta">
          <span>{{ finding.category?.toUpperCase() || '未知类型' }}</span>
          <span>置信度：{{ confidenceLabel }}</span>
        </div>

        <div v-if="finding.risk?.factors?.length" class="facts">
          <span v-for="factor in finding.risk.factors" :key="factor.name" class="fact">{{ factorLabel(factor.name) }}</span>
        </div>

        <div v-if="finding.evidence?.[0]?.content" class="code-block">
          <div class="cb-head">
            <span>脱敏证据</span>
            <span>{{ finding.file_path }}:{{ finding.start_line }}</span>
          </div>
          <pre>{{ finding.evidence[0].content }}</pre>
        </div>

        <el-button v-if="finding.risk" text size="small" class="fdp-factor-toggle" @click="factorsVisible = !factorsVisible">
          {{ factorsVisible ? '收起风险因子' : '展开风险因子' }}
        </el-button>
        <RiskFactorPanel v-if="factorsVisible" :risk="finding.risk" />

        <div class="fdp-actions">
          <el-button type="primary" size="small" :loading="loading" @click="emit('generate', finding)">生成修复建议</el-button>
          <el-button text type="primary" size="small" :loading="loading" @click="emit('load-suggestions', finding.id)">刷新历史建议</el-button>
        </div>

        <div class="fdp-suggestions">
          <div class="fdp-suggestions-head">
            <span class="fdp-suggestions-title">修复建议{{ suggestionTotal ? `（${suggestionTotal}）` : '' }}</span>
            <button class="fdp-suggestions-toggle" type="button" @click="toggleSuggestions">
              {{ suggestionsExpanded ? '收起建议' : '展开建议' }}
            </button>
          </div>

          <p v-if="!suggestionsExpanded" class="fdp-collapsed-summary">
            {{ collapsedSummary }}
          </p>

          <template v-else>
            <el-alert v-if="errorMessage" type="error" :title="errorMessage" :closable="false" show-icon class="fdp-suggestion-error" />
            <p v-else-if="loading && !suggestionsLoaded" class="fdp-empty-suggestions">正在加载修复建议…</p>
            <p v-else-if="suggestionsLoaded && suggestions.length === 0" class="fdp-empty-suggestions">暂未生成修复建议。</p>

            <div v-if="suggestions.length" class="fdp-suggestion-list">
              <RemediationSuggestionCard
                v-for="suggestion in suggestions"
                :key="suggestion.id"
                :suggestion="suggestion"
                :deleting="deletingSuggestionId === suggestion.id"
                @copy-patch="emit('copy-patch', $event)"
                @review="emit('review', $event)"
                @remove="emit('remove', $event)"
              />
              <button
                v-if="suggestionsHasMore"
                class="fdp-load-more"
                type="button"
                :disabled="suggestionsLoadingMore"
                @click="emit('load-more-suggestions', finding.id)"
              >
                {{ suggestionsLoadingMore ? '加载中…' : '加载更多建议' }}
              </button>
            </div>
          </template>
        </div>
      </div>
    </template>
    <el-empty v-else description="从左侧选择一条风险发现查看详情。" />
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import FindingSeverityTag from '@/components/security/FindingSeverityTag.vue'
import RemediationSuggestionCard from './RemediationSuggestionCard.vue'
import RiskFactorPanel from './RiskFactorPanel.vue'
import { riskFactorLabel } from '@/features/security/presentation'

const props = defineProps({
  finding: { type: Object, default: null },
  suggestions: { type: Array, default: () => [] },
  suggestionsLoaded: { type: Boolean, default: false },
  suggestionTotal: { type: Number, default: 0 },
  suggestionsHasMore: { type: Boolean, default: false },
  suggestionsLoadingMore: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  deletingSuggestionId: { type: [Number, String], default: null }
})

const emit = defineEmits(['generate', 'load-suggestions', 'load-more-suggestions', 'copy-patch', 'review', 'remove'])
const factorsVisible = ref(false)
const suggestionsExpanded = ref(false)
const factorLabel = riskFactorLabel
const confidenceLabel = computed(() => typeof props.finding?.confidence === 'number'
  ? `${Math.round(props.finding.confidence * 100)}%`
  : '服务端未提供')
const riskScoreText = computed(() => {
  const score = props.finding?.risk?.score
  return typeof score === 'number' ? score.toFixed(0) : '-'
})
const collapsedSummary = computed(() => {
  if (props.suggestionsLoaded && props.suggestions.length) {
    return `已加载 ${props.suggestions.length} 条建议${props.suggestionTotal > props.suggestions.length ? `，共 ${props.suggestionTotal} 条` : ''}，点击展开查看。`
  }
  if (props.suggestionTotal > 0) return `共 ${props.suggestionTotal} 条建议可审阅，点击展开查看。`
  return '暂无建议，可点击“生成修复建议”。'
})

const toggleSuggestions = () => {
  suggestionsExpanded.value = !suggestionsExpanded.value
  if (suggestionsExpanded.value && !props.suggestionsLoaded && props.finding) {
    emit('load-suggestions', props.finding.id)
  }
}

watch(() => props.finding?.id, () => {
  factorsVisible.value = false
  suggestionsExpanded.value = false
})
</script>

<style scoped lang="scss">
.finding-detail-panel { display: flex; flex-direction: column; min-height: 200px; }
.finding-detail-panel--empty { align-items: center; justify-content: center; padding: 24px; }
.fdp-head {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 10px 14px; border-bottom: 1px solid #eef1f5;
}
.fdp-head h3 { margin: 0; font-size: 14px; font-weight: 600; color: #1f2d3d; overflow-wrap: anywhere; }
.fdp-risk { color: #d43b3b; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; font-weight: 600; white-space: nowrap; }
.panel-body { padding: 14px; }
.fdp-topline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fdp-topline code { color: #52627a; background: #f1f4f8; padding: 2px 6px; border-radius: 4px; font-size: 11.5px; overflow-wrap: anywhere; }
.fdp-topline span { color: #6a7890; font-size: 12px; }
.fdp-status { text-transform: capitalize; }
.fdp-message { margin: 10px 0 0; color: #1f2d3d; line-height: 1.6; }
.fdp-meta { display: flex; gap: 10px; flex-wrap: wrap; color: #8494a8; font-size: 12px; margin-top: 6px; }
.facts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.fact { background: #f1f4f8; border: 1px solid #e2e7ee; border-radius: 4px; padding: 2px 8px; font-size: 12px; color: #52627a; }
.code-block { margin-top: 10px; border: 1px solid #dce3ec; border-radius: 6px; overflow: hidden; background: #f8fafc; }
.cb-head {
  display: flex; justify-content: space-between; gap: 8px;
  padding: 5px 10px; background: #f1f4f8; border-bottom: 1px solid #e2e7ee;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px; color: #6a7890;
}
.code-block pre {
  margin: 0; padding: 8px 10px; overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px;
  line-height: 1.7; color: #2b3a4e; white-space: pre-wrap; word-break: break-word;
}
.fdp-factor-toggle { margin: 10px 0 0; padding: 0; }
.fdp-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.fdp-suggestions { margin-top: 14px; border: 1px solid #e2e7ee; border-radius: 6px; overflow: hidden; }
.fdp-suggestions-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 7px 10px; background: #fafbfd;
}
.fdp-suggestions-title { font-size: 12.5px; font-weight: 600; color: #37465c; }
.fdp-suggestions-toggle { border: 0; background: none; color: #0b7fd1; font-size: 12.5px; cursor: pointer; padding: 0; }
.fdp-collapsed-summary { margin: 0; padding: 8px 10px; color: #6a7890; font-size: 12.5px; line-height: 1.6; }
.fdp-suggestion-error { margin: 10px; }
.fdp-empty-suggestions { margin: 0; padding: 10px; color: #6a7890; font-size: 13px; }
.fdp-suggestion-list { display: grid; gap: 10px; padding: 10px; max-height: 52vh; overflow-y: auto; }
.fdp-suggestion-list::-webkit-scrollbar { width: 8px; }
.fdp-suggestion-list::-webkit-scrollbar-thumb { background: #c2ccd9; border-radius: 4px; }
.fdp-suggestion-list::-webkit-scrollbar-track { background: transparent; }
.fdp-load-more {
  display: block; width: 100%;
  border: 1px dashed #c2ccd9; border-radius: 6px;
  background: #fafbfd; color: #52627a; font-size: 12.5px;
  padding: 7px 0; cursor: pointer;
}
.fdp-load-more:hover:not(:disabled) { border-color: #0b7fd1; color: #0b7fd1; }
.fdp-load-more:disabled { cursor: default; opacity: .6; }
</style>
