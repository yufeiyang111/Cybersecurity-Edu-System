<template>
  <div class="cm-actions">
    <button
      :title="t('message.copy')"
      type="button"
      @click="$emit('copy')"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" aria-hidden="true">
        <rect x="9" y="9" width="11" height="11" rx="2" />
        <path d="M5 15V5a2 2 0 012-2h10" />
      </svg>
    </button>
    <button
      :title="t('message.favorite')"
      type="button"
      @click="$emit('favorite')"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" aria-hidden="true">
        <path d="M12 4l2.9 6 6.6.9-4.8 4.6 1.2 6.5-5.9-3.1-5.9 3.1 1.2-6.5L2.5 10.9 9.1 10 12 4z" />
      </svg>
    </button>
    <button
      :title="t('message.good')"
      :class="{ active: feedback === 'good' }"
      type="button"
      @click="$emit('feedback', 'good')"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" aria-hidden="true">
        <path d="M7 11v10H4V11h3zm0 0l4-8h3a2 2 0 012 2v6h6a1 1 0 011 1l-2 7a2 2 0 01-2 1H7" />
      </svg>
    </button>
    <button
      :title="t('message.bad')"
      :class="{ active: feedback === 'bad' }"
      type="button"
      @click="$emit('feedback', 'bad')"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" aria-hidden="true">
        <path d="M17 13V3h3v10h-3zm0 0l-4 8h-3a2 2 0 01-2-2v-6H2a1 1 0 01-1-1l2-7a2 2 0 012-1h12" />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { useI18n } from '@/features/chat/i18n'

defineProps({
  feedback: { type: String, default: '' }
})

defineEmits(['copy', 'favorite', 'feedback'])

const { t } = useI18n()
</script>

<style scoped lang="scss">
.cm-actions {
  display: flex;
  gap: 2px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.15s;

  button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    cursor: pointer;

    &:hover {
      background: var(--chat-hover);
    }

    &:focus-visible {
      outline: 2px solid var(--chat-link);
      outline-offset: 2px;
    }

    &.active {
      background: var(--chat-accent-soft);

      svg {
        stroke: var(--chat-accent);
      }
    }

    svg {
      width: 15px;
      height: 15px;
      stroke: var(--chat-hollow);
    }
  }
}

:global(.chat-msg:hover) .cm-actions,
.cm-actions:focus-within {
  opacity: 1;
}

@media (max-width: 767px) {
  .cm-actions {
    opacity: 1;
  }
}
</style>
