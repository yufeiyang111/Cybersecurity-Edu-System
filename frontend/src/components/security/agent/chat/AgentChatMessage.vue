<template>
  <div class="agent-msg" :class="message.role">
    <template v-if="message.role === 'user'">
      <div class="am-body am-user-bubble">
        <div class="am-text">{{ message.text }}</div>
      </div>
    </template>

    <template v-else>
      <div class="am-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="1.8">
          <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" />
          <path d="M9.5 12l2 2 3.5-4" />
        </svg>
      </div>
      <div class="am-body am-agent-body">
        <div v-if="message.turnSeq || message.status || message.time" class="am-meta">
          <span v-if="message.turnSeq" class="am-meta__turn">Turn {{ message.turnSeq }}</span>
          <span v-if="message.status" class="am-meta__status">{{ statusLabel }}</span>
          <span v-if="message.time" class="am-meta__time">{{ message.time }}</span>
        </div>

        <AgentChatThinking
          v-if="message.reasoning || message.reasoningLive"
          :text="message.reasoning"
          :live="message.reasoningLive"
        />

        <AgentChatToolCalls :tool-calls="message.toolCalls" />

        <div v-if="message.streaming && !message.llmAnalysis" class="am-stream-dots">
          <span></span><span></span><span></span>
        </div>

        <div v-if="message.llmAnalysis" class="am-analysis">
          <ChatMarkdown :content="message.llmAnalysis" />
        </div>
        <div v-else-if="message.text && !message.streaming" class="am-text">{{ message.text }}</div>

        <div v-if="message.detail && message.detail.length" class="am-detail">
          <div v-for="(line, index) in message.detail" :key="index" class="am-detail__line">
            <template v-if="line.kind === 'severity'">
              <span v-if="line.counts.critical" class="am-sev am-sev--critical">严重 {{ line.counts.critical }}</span>
              <span v-if="line.counts.high" class="am-sev am-sev--high">高危 {{ line.counts.high }}</span>
              <span v-if="line.counts.medium" class="am-sev am-sev--medium">中危 {{ line.counts.medium }}</span>
              <span v-if="line.counts.low" class="am-sev am-sev--low">低危 {{ line.counts.low }}</span>
              <span v-if="line.counts.info" class="am-sev am-sev--info">信息 {{ line.counts.info }}</span>
            </template>
            <template v-else>
              <span class="am-detail__label">{{ line.kind }}</span>
              <span class="am-detail__value">{{ line.text }}</span>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ChatMarkdown from '@/components/chat/ChatMarkdown.vue'
import AgentChatThinking from './AgentChatThinking.vue'
import AgentChatToolCalls from './AgentChatToolCalls.vue'
import { agentStatusMeta } from '@/features/security/agent/statusMeta'

const props = defineProps({
  message: { type: Object, required: true }
})

const statusLabel = computed(() => agentStatusMeta(props.message.status).label)
</script>

<style scoped lang="scss">
.agent-msg {
  display: flex;
  gap: 14px;
  padding: calc(20px * var(--chat-space-scale)) 0;
}

.am-logo {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--chat-accent-gradient, var(--chat-accent));
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;

  svg {
    width: 16px;
    height: 16px;
  }
}

.am-body {
  flex: 1;
  min-width: 0;
}

.agent-msg.user {
  justify-content: flex-end;
}

.am-user-bubble {
  max-width: 68%;
  background: var(--chat-bubble);
  border-radius: var(--chat-radius);
  padding: calc(12px * var(--chat-space-scale)) calc(16px * var(--chat-space-scale));
  font-size: calc(15px * var(--chat-font-scale));
  line-height: 1.6;
}

.am-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: calc(15px * var(--chat-font-scale));
  line-height: 1.6;
  color: var(--chat-ink);
}

/* 元信息：弱化展示，不抢正文注意力 */
.am-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 11.5px;
  color: var(--chat-hollow);
}

.am-meta__turn {
  font-weight: 600;
  color: var(--chat-muted);
}

.am-meta__status {
  color: var(--chat-accent);
}

.am-stream-dots {
  display: flex;
  gap: 4px;
  align-items: center;
  height: 24px;

  span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--chat-hollow);
    animation: am-blink 1.2s infinite ease-in-out;

    &:nth-child(2) {
      animation-delay: 0.2s;
    }

    &:nth-child(3) {
      animation-delay: 0.4s;
    }
  }
}

.am-analysis {
  :deep(.chat-markdown) {
    font-size: calc(15px * var(--chat-font-scale));
    color: var(--chat-ink);
  }
}

.am-detail {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.am-detail__line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.am-detail__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--chat-hollow);
}

.am-detail__value {
  font-size: 13px;
  color: var(--chat-muted);
}

.am-sev {
  font-size: 12px;
  font-weight: 600;
  border-radius: 999px;
  padding: 2px 10px;
}

.am-sev--critical {
  background: var(--chat-danger-bg);
  border: 1px solid var(--chat-danger-border);
  color: var(--chat-danger-ink);
}

.am-sev--high {
  background: var(--chat-warning-bg);
  border: 1px solid var(--chat-warning-border);
  color: var(--chat-warning-ink);
}

.am-sev--medium {
  background: var(--chat-warning-bg);
  border: 1px solid var(--chat-warning-border);
  color: var(--chat-warning-ink);
}

.am-sev--low {
  background: var(--chat-success-bg);
  border: 1px solid var(--chat-success-border);
  color: var(--chat-success-ink);
}

.am-sev--info {
  background: var(--chat-hover);
  border: 1px solid var(--chat-hairline);
  color: var(--chat-muted);
}

@keyframes am-blink {
  0%, 80%, 100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
</style>
