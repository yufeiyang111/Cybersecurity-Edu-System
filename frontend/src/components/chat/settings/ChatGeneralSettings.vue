<template>
  <div class="settings-section">
    <h2>{{ t('general.title') }}</h2>
    <p class="section-help">{{ t('general.help') }}</p>

    <label for="language">{{ t('general.language') }}</label>
    <select id="language" v-model="modelValue.language" class="wide-select">
      <option v-for="item in languages" :key="item.value" :value="item.value">{{ item.label }}</option>
    </select>

    <label class="switch-row"><input type="checkbox" checked disabled><span>{{ t('general.saveHistory') }}</span></label>
    <label class="switch-row"><input type="checkbox" checked disabled><span>{{ t('general.enterSend') }}</span></label>

    <p class="section-note">{{ t('general.note') }}</p>
  </div>
</template>

<script setup>
import { useI18n } from '@/features/chat/i18n'

defineProps({ modelValue: { type: Object, required: true } })
const { t } = useI18n()

// 目前仅提供简体中文 / 英文两套完整翻译，其他语言暂不列出
const languages = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en', label: 'English' }
]
</script>

<style scoped>
.settings-section h2 { margin: 0; font-size: 21px; color: var(--chat-ink); }
.section-help,
.section-note { margin: 6px 0 22px; color: var(--chat-hollow); font-size: 13px; line-height: 1.6; }
.settings-section label:not(.switch-row) {
  display: block;
  margin: 16px 0 6px;
  color: var(--chat-muted);
  font-size: 13px;
  font-weight: 600;
}
.wide-select {
  min-width: 180px;
  padding: 8px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 6px;
  background: var(--chat-field);
  color: var(--chat-ink);
}
.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  color: var(--chat-muted);
  font-size: 13px;
}
</style>
