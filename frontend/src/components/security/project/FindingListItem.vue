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
    </div>
    <p class="fli-message" :title="finding.message">{{ finding.message }}</p>
    <div class="fli-meta">
      <code>{{ finding.file_path }}:{{ finding.start_line }}</code>
      <span class="fli-status">{{ finding.status }}</span>
    </div>
  </article>
</template>

<script setup>
import FindingSeverityTag from '@/components/security/FindingSeverityTag.vue'
import RiskScoreBadge from './RiskScoreBadge.vue'

defineProps({
  finding: { type: Object, required: true },
  selected: { type: Boolean, default: false }
})

const emit = defineEmits(['select'])
</script>

<style scoped lang="scss">
.finding-list-item {
  padding: 12px 14px;
  border: 1px solid #d9e2ec;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: border-color .15s ease, background .15s ease, box-shadow .15s ease;
  outline: none;
}
.finding-list-item:hover { border-color: #9fb3c8; }
.finding-list-item:focus-visible { box-shadow: 0 0 0 3px rgba(14, 147, 132, .2); }
.finding-list-item--selected {
  border-color: #0e9384;
  background: #f0fdfa;
  box-shadow: 0 0 0 2px rgba(14, 147, 132, .14);
}
.fli-topline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fli-message {
  margin: 8px 0 0;
  color: #243b53;
  font-size: 13.5px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.fli-meta {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-top: 8px;
}
.fli-meta code { color: #486581; background: #eef3f8; padding: 2px 6px; border-radius: 4px; font-size: 11.5px; overflow-wrap: anywhere; }
.fli-status { color: #627d98; font-size: 11.5px; text-transform: capitalize; white-space: nowrap; }
</style>
