<template>
  <article
    :id="`finding-${finding.id}`"
    class="finding-list-item"
    :class="{ 'finding-list-item--selected': selected }"
    tabindex="0"
    role="button"
    :aria-pressed="selected"
    @click="emit('select', finding)"
    @keydown.enter="emit('select', finding)"
  >
    <div class="fli-topline">
      <FindingSeverityTag :severity="finding.severity" />
      <RiskScoreBadge :risk="finding.risk" />
      <span class="fli-score">{{ riskScoreText }}</span>
    </div>
    <p class="fli-message" :title="finding.message">{{ finding.message }}</p>
    <div class="fli-meta">
      <code>{{ finding.file_path }}:{{ finding.start_line }}</code>
      <span class="fli-status" :class="{ 'fli-status--ready': suggestionReady }">
        {{ suggestionReady ? '已生成建议' : '未生成' }}
      </span>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import FindingSeverityTag from '@/components/security/FindingSeverityTag.vue'
import RiskScoreBadge from './RiskScoreBadge.vue'

const props = defineProps({
  finding: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  suggestionReady: { type: Boolean, default: false }
})

const emit = defineEmits(['select'])

const riskScoreText = computed(() => {
  const score = props.finding.risk?.score
  return typeof score === 'number' ? score.toFixed(0) : '--'
})
</script>

<style scoped lang="scss">
.finding-list-item {
  padding: 9px 12px;
  border: 1px solid #dfe6ef;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color .2s ease, background .2s ease, box-shadow .2s ease, transform .2s ease;
  outline: none;
}
.finding-list-item:hover {
  border-color: #aac5ef;
  box-shadow: 0 7px 16px rgba(37, 99, 235, 0.08);
  transform: translateX(2px);
}
.finding-list-item:focus-visible { box-shadow: 0 0 0 3px rgba(11, 127, 209, .2); }
.finding-list-item--selected {
  border-color: #2563eb;
  background: #f5f9ff;
  box-shadow: inset 3px 0 #2563eb, 0 7px 16px rgba(37, 99, 235, 0.08);
}
.fli-topline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fli-score { color: #8494a8; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.fli-message {
  margin: 5px 0 0;
  color: #1f2d3d;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.fli-meta {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-top: 5px;
}
.fli-meta code {
  color: #6a7890; background: #f1f4f8; padding: 2px 6px; border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px;
  overflow-wrap: anywhere;
}
.fli-status { color: #8494a8; font-size: 11.5px; white-space: nowrap; }
.fli-status--ready { color: #1c8a4d; }
</style>
