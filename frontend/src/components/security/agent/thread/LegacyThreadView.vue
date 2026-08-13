<template>
  <div class="legacy-thread">
    <template v-for="message in visibleMessages" :key="`msg-${message.id}`">
      <div v-if="message.role === 'user'" class="lt-row lt-row--user">
        <div class="lt-bubble lt-bubble--user">{{ message.content }}</div>
      </div>
      <div v-else-if="message.role === 'agent' && message.message_type === 'llm_analysis'" class="lt-row">
        <div class="lt-bubble">
          <ChatMarkdown :content="message.content" />
        </div>
      </div>
    </template>

    <div v-if="steps.length" class="lt-section">
      <p class="lt-section__title">执行步骤</p>
      <div v-for="step in steps" :key="`step-${step.id}`" class="lt-step">
        <span class="lt-step__dot" :class="`lt-step__dot--${step.status}`" />
        <span class="lt-step__name">{{ step.node_key || step.tool_name || step.id }}</span>
        <span v-if="step.summary" class="lt-step__summary">{{ step.summary }}</span>
        <span v-else-if="step.error_code" class="lt-step__error">{{ step.error_code }}</span>
      </div>
    </div>

    <div v-if="run && run.warning_codes && run.warning_codes.length" class="lt-section">
      <div v-for="code in run.warning_codes" :key="`warn-${code}`" class="lt-warning">
        {{ code }}
      </div>
    </div>

    <div v-if="!llmAnalysis && running" class="lt-running">
      <span class="lt-running__dot" />
      Agent 正在执行…
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ChatMarkdown from '@/components/chat/ChatMarkdown.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  steps: { type: Array, default: () => [] },
  llmAnalysis: { type: String, default: '' },
  run: { type: Object, default: null },
  running: { type: Boolean, default: false }
})

const visibleMessages = computed(() => {
  return props.messages.filter((message) => {
    if (message.role === 'user') return true
    if (message.role === 'agent' && message.message_type === 'llm_analysis') return true
    return false
  })
})
</script>

<style scoped lang="scss">
.legacy-thread {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.lt-row {
  display: flex;
  justify-content: flex-start;

  &--user {
    justify-content: flex-end;
  }
}

.lt-bubble {
  max-width: 86%;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--chat-hairline, #e5e7eb);
  background: var(--chat-surface, #ffffff);
  color: var(--chat-ink, #1f2937);
  font-size: 14px;

  &--user {
    background: #eff6ff;
    border-color: #bfdbfe;
    color: #1e3a5f;
  }
}

.lt-section {
  display: flex;
  flex-direction: column;
  gap: 8px;

  &__title {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--chat-muted, #6b7280);
  }
}

.lt-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--chat-ink, #1f2937);

  &__dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--chat-hollow, #9ca3af);

    &--running {
      background: #2563eb;
    }

    &--completed {
      background: #16a34a;
    }

    &--failed {
      background: #dc2626;
    }
  }

  &__summary {
    color: var(--chat-muted, #6b7280);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__error {
    color: #dc2626;
  }
}

.lt-warning {
  padding: 8px 12px;
  border-radius: 6px;
  background: #fef9c3;
  border: 1px solid #fde047;
  color: #854d0e;
  font-size: 12px;
}

.lt-running {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--chat-muted, #6b7280);

  &__dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #2563eb;
    animation: lt-blink 1.2s infinite ease-in-out;
  }
}

@keyframes lt-blink {
  0%,
  80%,
  100% {
    opacity: 0.25;
  }
  40% {
    opacity: 1;
  }
}
</style>
