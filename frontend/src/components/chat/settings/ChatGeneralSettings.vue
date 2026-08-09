<template>
  <div class="settings-section">
    <h2>{{ t('general.title') }}</h2>
    <p class="section-help">{{ t('general.help') }}</p>

    <label for="language">{{ t('general.language') }}</label>
    <select id="language" v-model="modelValue.language" class="wide-select">
      <option v-for="item in languages" :key="item.value" :value="item.value">{{ item.label }}</option>
    </select>

    <label for="qa-max-tokens">回答最大 Tokens</label>
    <input
      id="qa-max-tokens"
      v-model.number="maxTokensInput"
      type="number"
      min="1"
      max="384000"
      class="wide-input"
      placeholder="留空使用默认（16384）"
    >
    <p class="section-note">控制每次回答的最大输出长度；值越大回答越详尽，成本与耗时也越高。上限 384000，留空使用引擎默认 16384，保存后下次打开仍会保留。</p>

    <label class="switch-row"><input type="checkbox" checked disabled><span>{{ t('general.saveHistory') }}</span></label>
    <label class="switch-row"><input type="checkbox" checked disabled><span>{{ t('general.enterSend') }}</span></label>

    <p class="section-note">{{ t('general.note') }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from '@/features/chat/i18n'

const props = defineProps({ modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const maxTokensInput = computed({
  get: () => props.modelValue.qa_max_tokens ?? '',
  set: (value) => {
    const num = value === '' || value === null ? null : Number(value)
    emit('update:modelValue', { ...props.modelValue, qa_max_tokens: num })
  }
})

const languages = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'Français' },
  { value: 'ru', label: 'Русский' },
  { value: 'ja', label: '日本語' },
  { value: 'vi', label: 'Tiếng Việt' },
  { value: 'zh-TW', label: '繁體中文' }
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
.wide-input {
  width: 180px;
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
