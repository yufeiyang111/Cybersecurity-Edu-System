<template>
  <div class="assistant-block">
    <div class="ab-head">
      <span class="ab-logo" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="1.8">
          <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" />
          <path d="M9.5 12l2 2 3.5-4" />
        </svg>
      </span>
      <span class="ab-label">Agent</span>
      <span v-if="live" class="ab-live">回答中…</span>
      <span v-if="statusLabel" class="ab-status">{{ statusLabel }}</span>
      <span v-if="time" class="ab-time">{{ time }}</span>
    </div>
    <div v-if="text" class="ab-body">
      <ChatMarkdown :content="text" />
    </div>
    <div v-else-if="live" class="ab-stream">
      <span class="ab-stream__dot" />
      <span class="ab-stream__dot" />
      <span class="ab-stream__dot" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ChatMarkdown from '@/components/chat/ChatMarkdown.vue'
import { agentStatusMeta } from '@/features/security/agent/statusMeta'

const props = defineProps({
  text: { type: String, default: '' },
  status: { type: String, default: '' },
  live: { type: Boolean, default: false },
  time: { type: String, default: '' }
})

const statusLabel = computed(() => {
  if (!props.status) return ''
  return agentStatusMeta(props.status).label
})
</script>

<style scoped lang="scss">
.assistant-block {
  display: flex;
  gap: 12px;
  padding: 4px 0;
}

.ab-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.ab-logo {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--chat-accent-gradient, var(--chat-accent));
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    width: 14px;
    height: 14px;
  }
}

.ab-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--chat-muted);
}

.ab-live {
  font-size: 12px;
  color: var(--chat-accent);
  animation: ab-pulse 1.4s infinite ease-in-out;
}

.ab-status {
  font-size: 12px;
  color: var(--chat-hollow);
}

.ab-time {
  font-size: 12px;
  color: var(--chat-hollow);
  margin-left: auto;
}

.ab-body {
  flex: 1;
  min-width: 0;

  :deep(.chat-markdown) {
    font-size: calc(15px * var(--chat-font-scale));
    color: var(--chat-ink);
  }
}

.ab-stream {
  display: flex;
  gap: 4px;
  align-items: center;
  height: 24px;

  .ab-stream__dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--chat-hollow);
    animation: ab-blink 1.2s infinite ease-in-out;

    &:nth-child(2) {
      animation-delay: 0.2s;
    }

    &:nth-child(3) {
      animation-delay: 0.4s;
    }
  }
}

@keyframes ab-blink {
  0%,
  80%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@keyframes ab-pulse {
  0%,
  100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}
</style>
