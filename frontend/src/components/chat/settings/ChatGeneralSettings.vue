<template>
  <div class="settings-section">
    <h2>{{ t('general.title') }}</h2>
    <p class="section-help">{{ t('general.help') }}</p>

    <label for="language">{{ t('general.language') }}</label>
    <select
      id="language"
      v-model="modelValue.language"
      class="wide-select"
    >
      <option
        v-for="item in languages"
        :key="item.value"
        :value="item.value"
      >
        {{ item.label }}
      </option>
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
    <p class="section-note">
      控制每次回答的最大输出长度；值越大回答越详尽，成本与耗时也越高。上限 384000，留空使用引擎默认 16384，保存后下次打开仍会保留。
    </p>

    <label
      class="switch-row"
      for="allow-ungrounded-answers"
    >
      <input
        id="allow-ungrounded-answers"
        v-model="modelValue.allow_ungrounded_answers"
        type="checkbox"
      >
      <span>知识库无证据时仍允许 AI 回答</span>
    </label>
    <p class="section-note switch-note">
      仅在启用 RAG v2 时生效：系统仍会先检索知识库；仅在未找到可验证内容时，才允许 AI 基于通用知识回答。该类回答会明确标注为“未检索内容”，不提供知识库引用。
    </p>

    <label class="switch-row">
      <input
        type="checkbox"
        checked
        disabled
      >
      <span>{{ t('general.saveHistory') }}</span>
    </label>
    <label class="switch-row">
      <input
        type="checkbox"
        checked
        disabled
      >
      <span>{{ t('general.enterSend') }}</span>
    </label>

    <p class="section-note">{{ t('general.note') }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from '@/features/chat/i18n'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  }
})

const { t } = useI18n()

const maxTokensInput = computed({
  get: () => props.modelValue.qa_max_tokens ?? '',
  set: (value) => {
    props.modelValue.qa_max_tokens = value === '' || value === null
      ? null
      : Number(value)
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

<style scoped lang="scss">
.settings-section {
  h2 {
    margin: 0;
    color: var(--chat-ink);
    font-size: 21px;
  }

  label:not(.switch-row) {
    display: block;
    margin: 16px 0 6px;
    color: var(--chat-muted);
    font-size: 13px;
    font-weight: 600;
  }
}

.section-help,
.section-note {
  margin: 6px 0 22px;
  color: var(--chat-hollow);
  font-size: 13px;
  line-height: 1.6;
}

.switch-note {
  margin-top: 6px;
}

.wide-select,
.wide-input {
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 6px;
  background: var(--chat-field);
  color: var(--chat-ink);
  padding: 8px;
}

.wide-select {
  min-width: 180px;
}

.wide-input {
  width: 180px;
}

.switch-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 16px;
  color: var(--chat-muted);
  font-size: 13px;
  line-height: 1.5;

  input {
    flex: 0 0 auto;
    margin-top: 3px;
  }
}
</style>
