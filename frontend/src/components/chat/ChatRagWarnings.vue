<template>
  <div v-if="items.length" class="chat-rag-warnings" role="alert">
    <div class="crw-title">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8">
        <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" />
        <path d="M12 8v4M12 15.5h.01" />
      </svg>
      <span>{{ t('warnings.title', { count: items.length }) }}</span>
    </div>
    <ul class="crw-list">
      <li v-for="item in items" :key="item.id + item.flagsText" class="crw-item">
        <code>{{ item.id }}</code>
        <span>{{ item.flagsText || warningCodeLabel(item.id) }}</span>
      </li>
    </ul>
    <p class="crw-note">{{ t('warnings.note') }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { parseRagWarning, warningCodeLabel } from '@/features/security/warningCodes'
import { useI18n } from '@/features/chat/i18n'

const props = defineProps({
  warnings: { type: Array, default: () => [] }
})

const items = computed(() => (props.warnings || []).map(parseRagWarning))
const { t } = useI18n()
</script>

<style lang="scss" scoped>
.chat-rag-warnings {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--chat-warning-border);
  border-radius: var(--chat-radius);
  background: var(--chat-warning-bg);
}
.crw-title {
  display: flex; align-items: center; gap: 8px;
  color: var(--chat-warning-ink); font-size: calc(13px * var(--chat-font-scale)); font-weight: 600;
  svg { width: 16px; height: 16px; stroke: var(--chat-warning-icon); flex-shrink: 0; }
}
.crw-list {
  margin: 8px 0 0; padding: 0; list-style: none;
}
.crw-item {
  display: flex; gap: 8px; flex-wrap: wrap; align-items: baseline;
  font-size: calc(12.5px * var(--chat-font-scale)); color: var(--chat-warning-ink); line-height: 1.6;
  opacity: 0.9;
  code { color: var(--chat-warning-ink); font-weight: 600; }
}
.crw-note {
  margin: 8px 0 0; font-size: calc(12px * var(--chat-font-scale)); color: var(--chat-warning-ink);
  opacity: 0.75;
}
</style>
