<template>
  <section
    v-if="shouldRender"
    class="answer-evidence-summary"
    :data-tone="presentation.tone"
  >
    <div class="summary-icon" aria-hidden="true">
      <BaseIcon :name="iconName" :size="15" />
    </div>
    <div class="summary-copy">
      <div class="summary-title">{{ presentation.label }}</div>
      <p class="summary-description">{{ presentation.description }}</p>
      <p
        v-if="citationCount > 0"
        class="summary-meta"
      >
        {{ citationCount }} 条可核验引用
      </p>
      <p
        v-else-if="citationState === 'legacy'"
        class="summary-meta"
      >
        历史来源信息不具备稳定 citation 标识。
      </p>
      <p
        v-if="detailState === 'error'"
        class="summary-error"
      >
        {{ errorMessage || '证据预览加载失败，可再次尝试。' }}
      </p>
    </div>
    <button
      v-if="canLoadEvidence"
      class="summary-action"
      type="button"
      @click="$emit('load-evidence', $event.currentTarget)"
    >
      <BaseIcon
        :name="detailState === 'loading' ? 'clock' : 'file-text'"
        :size="14"
      />
      <span>{{ actionLabel }}</span>
    </button>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'
import { answerStatusPresentation } from '@/features/chat/citationPresentation'

const props = defineProps({
  answerStatus: { type: String, default: null },
  citationCount: { type: Number, default: 0 },
  citationState: { type: String, default: 'legacy' },
  detailState: { type: String, default: 'idle' },
  errorMessage: { type: String, default: '' },
  recordId: { type: Number, default: null }
})

defineEmits(['load-evidence'])

const presentation = computed(() => {
  return answerStatusPresentation(props.answerStatus, props.citationState)
})

const shouldRender = computed(() => {
  return Boolean(props.citationState)
})

const canLoadEvidence = computed(() => {
  return props.citationCount > 0 && Number.isInteger(props.recordId) && props.recordId > 0
})

const actionLabel = computed(() => {
  if (props.detailState === 'loading') {
    return '加载证据中'
  }
  if (props.detailState === 'success') {
    return '刷新证据'
  }
  if (props.detailState === 'error') {
    return '重新加载'
  }
  return '查看证据'
})

const iconName = computed(() => {
  if (presentation.value.tone === 'success') {
    return 'shield'
  }
  if (presentation.value.tone === 'warning' || presentation.value.tone === 'danger') {
    return 'warning'
  }
  return 'file-text'
})
</script>

<style scoped lang="scss">
.answer-evidence-summary {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 16px;
  padding: 11px 12px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: var(--chat-radius);
  background: var(--chat-bubble);
  color: var(--chat-ink);

  &[data-tone='success'] {
    border-color: var(--chat-success-border);
    background: var(--chat-success-bg);

    .summary-icon,
    .summary-title {
      color: var(--chat-success-ink);
    }
  }

  &[data-tone='warning'] {
    border-color: var(--chat-warning-border);
    background: var(--chat-warning-bg);

    .summary-icon,
    .summary-title {
      color: var(--chat-warning-ink);
    }
  }

  &[data-tone='danger'] {
    border-color: var(--chat-danger-border);
    background: var(--chat-danger-bg);

    .summary-icon,
    .summary-title,
    .summary-error {
      color: var(--chat-danger-ink);
    }
  }
}

.summary-icon {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 7px;
  color: var(--chat-ink);
  background: var(--chat-field);
}

.summary-copy {
  min-width: 0;
  flex: 1;
}

.summary-title {
  font-size: calc(13px * var(--chat-font-scale));
  font-weight: 650;
}

.summary-description,
.summary-meta,
.summary-error {
  margin: 3px 0 0;
  font-size: calc(12px * var(--chat-font-scale));
  line-height: 1.5;
}

.summary-description,
.summary-meta {
  color: var(--chat-muted);
}

.summary-error {
  color: var(--chat-danger-ink);
}

.summary-action {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 5px;
  min-height: 28px;
  padding: 5px 8px;
  border: 1px solid var(--chat-accent-border);
  border-radius: 7px;
  color: var(--chat-ink);
  background: var(--chat-field);
  font: inherit;
  font-size: calc(12px * var(--chat-font-scale));
  cursor: pointer;

  &:hover {
    background: var(--chat-hover);
  }

  &:focus-visible {
    outline: 2px solid var(--chat-link);
    outline-offset: 2px;
  }
}

@media (min-width: 768px) and (max-width: 1200px) {
  .answer-evidence-summary {
    padding: 10px;
  }
}

@media (max-width: 767px) {
  .answer-evidence-summary {
    align-items: center;
    margin-top: 14px;
    padding: 10px;
  }

  .summary-description {
    display: none;
  }

  .summary-action {
    padding: 5px 7px;
  }
}
</style>
