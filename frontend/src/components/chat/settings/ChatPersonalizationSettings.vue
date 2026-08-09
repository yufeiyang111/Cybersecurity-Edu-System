<template>
  <div class="settings-section">
    <h2>{{ t('personal.title') }}</h2>
    <p class="section-help">{{ t('personal.help') }}</p>

    <label for="about-user">{{ t('personal.aboutUser') }}</label>
    <textarea
      id="about-user"
      v-model="modelValue.about_user"
      maxlength="1000"
      :placeholder="t('personal.aboutUserPlaceholder')"
    ></textarea>

    <label for="response-preferences">{{ t('personal.responsePrefs') }}</label>
    <textarea
      id="response-preferences"
      v-model="modelValue.response_preferences"
      maxlength="2000"
      :placeholder="t('personal.responsePrefsPlaceholder')"
    ></textarea>

    <label for="custom-prompt">{{ t('personal.customPrompt') }}</label>
    <textarea
      id="custom-prompt"
      v-model="modelValue.custom_prompt"
      maxlength="4000"
      :placeholder="t('personal.customPromptPlaceholder')"
    ></textarea>

    <label for="response-style">{{ t('personal.responseStyle') }}</label>
    <select id="response-style" v-model="modelValue.response_style" class="wide-select">
      <option value="professional">{{ t('personal.styleProfessional') }}</option>
      <option value="concise">{{ t('personal.styleConcise') }}</option>
      <option value="teaching">{{ t('personal.styleTeaching') }}</option>
      <option value="analytical">{{ t('personal.styleAnalytical') }}</option>
    </select>

    <label class="switch-row"><input v-model="modelValue.show_citations" type="checkbox"><span>{{ t('personal.showCitations') }}</span></label>
    <label class="switch-row"><input v-model="modelValue.show_security_warnings" type="checkbox"><span>{{ t('personal.showWarnings') }}</span></label>
  </div>
</template>

<script setup>
import { useI18n } from '@/features/chat/i18n'

defineProps({ modelValue: { type: Object, required: true } })
const { t } = useI18n()
</script>

<style scoped>
.settings-section h2 { margin: 0; font-size: 21px; color: var(--chat-ink); }
.section-help { margin: 6px 0 22px; color: var(--chat-hollow); font-size: 13px; }
.settings-section label:not(.switch-row) {
  display: block;
  margin: 16px 0 6px;
  color: var(--chat-muted);
  font-size: 13px;
  font-weight: 600;
}
.settings-section textarea {
  display: block;
  width: 100%;
  min-height: 78px;
  box-sizing: border-box;
  resize: vertical;
  padding: 10px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 7px;
  font: inherit;
  background: var(--chat-field);
  color: var(--chat-ink);
}
.wide-select {
  min-width: 150px;
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
