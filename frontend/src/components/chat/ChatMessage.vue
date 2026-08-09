<template>
  <div class="chat-msg" :class="message.role">
    <template v-if="message.role === 'user'">
      <div class="cm-body cm-user-bubble">
        <div v-if="message.attachments?.length" class="cm-attachments">
          <div v-for="(att, idx) in message.attachments" :key="idx" class="cm-att">
            <img v-if="att.type === 'image' && att.preview" :src="att.preview" alt="">
            <svg v-else viewBox="0 0 24 24" fill="none" stroke-width="1.6">
              <path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6z" />
              <path d="M14 3v6h6" />
            </svg>
            <span class="cm-att-name">{{ att.name }}</span>
          </div>
        </div>
        <div class="cm-text">{{ message.content }}</div>
      </div>
    </template>

    <template v-else>
      <div class="cm-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="1.8">
          <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" />
          <path d="M9.5 12l2 2 3.5-4" />
        </svg>
      </div>
      <div class="cm-body cm-assistant-body">
        <ChatThinking
          :seconds="message.response_time"
          :sources="message.sources"
          :confidence="message.confidence"
          :model-name="message.model_name"
          :reasoning="message.reasoning"
        />
        <div v-if="message.streaming && !message.content" class="cm-stream-dots">
          <span></span><span></span><span></span>
        </div>
        <ChatMarkdown v-if="message.content" :content="message.content" />
        <ChatRagWarnings v-if="showWarnings" :warnings="message.ragWarnings" />
        <ChatSources v-if="showCitations" :sources="message.sources" />
        <div class="cm-actions">
          <button :title="t('message.copy')" @click="$emit('copy', message)">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6">
              <rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 012-2h10" />
            </svg>
          </button>
          <button :title="t('message.favorite')" @click="$emit('favorite', message)">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6">
              <path d="M12 4l2.9 6 6.6.9-4.8 4.6 1.2 6.5-5.9-3.1-5.9 3.1 1.2-6.5L2.5 10.9 9.1 10 12 4z" />
            </svg>
          </button>
          <button
            :title="t('message.good')"
            :class="{ active: message.feedback === 'good' }"
            @click="$emit('feedback', message, 'good')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6">
              <path d="M7 11v10H4V11h3zm0 0l4-8h3a2 2 0 012 2v6h6a1 1 0 011 1l-2 7a2 2 0 01-2 1H7" />
            </svg>
          </button>
          <button
            :title="t('message.bad')"
            :class="{ active: message.feedback === 'bad' }"
            @click="$emit('feedback', message, 'bad')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6">
              <path d="M17 13V3h3v10h-3zm0 0l-4 8h-3a2 2 0 01-2-2v-6H2a1 1 0 01-1-1l2-7a2 2 0 012-1h12" />
            </svg>
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ChatMarkdown from './ChatMarkdown.vue'
import ChatRagWarnings from './ChatRagWarnings.vue'
import ChatSources from './ChatSources.vue'
import ChatThinking from './ChatThinking.vue'
import { useChatPreferences } from '@/composables/chat/useChatPreferences'
import { useI18n } from '@/features/chat/i18n'

defineProps({
  message: { type: Object, required: true }
})
defineEmits(['copy', 'favorite', 'feedback'])

const { t } = useI18n()
const { preferences } = useChatPreferences()
// 展示开关：默认展示，仅当用户在设置里显式关闭时才隐藏
const showCitations = computed(() => preferences.show_citations !== false)
const showWarnings = computed(() => preferences.show_security_warnings !== false)
</script>

<style lang="scss" scoped>
.chat-msg { display: flex; gap: 14px; padding: calc(20px * var(--chat-space-scale)) 0; }

.cm-logo {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
  background: var(--chat-accent-gradient, var(--chat-accent));
  display: flex; align-items: center; justify-content: center;
  margin-top: 2px;
  svg { width: 16px; height: 16px; }
}
.cm-body { flex: 1; min-width: 0; }

.chat-msg.user { justify-content: flex-end; }
.cm-user-bubble {
  max-width: 68%;
  background: var(--chat-bubble);
  border-radius: var(--chat-radius);
  padding: calc(12px * var(--chat-space-scale)) calc(16px * var(--chat-space-scale));
  font-size: calc(15px * var(--chat-font-scale));
  line-height: 1.6;
  .cm-text { white-space: pre-wrap; word-break: break-word; }
}

.cm-attachments { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.cm-stream-dots {
  display: flex; gap: 4px; align-items: center; height: 24px;
  span {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--chat-hollow);
    animation: cm-blink 1.2s infinite ease-in-out;
    &:nth-child(2) { animation-delay: .2s; }
    &:nth-child(3) { animation-delay: .4s; }
  }
}
@keyframes cm-blink {
  0%, 80%, 100% { opacity: .25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}
.cm-att {
  display: flex; align-items: center; gap: 6px;
  border: 1px solid var(--chat-hairline);
  background: var(--chat-canvas);
   border-radius: var(--chat-radius);
  padding: 4px 8px;
  max-width: 200px;
  img {
    width: 32px; height: 32px; border-radius: 6px; object-fit: cover;
    flex-shrink: 0;
  }
  svg { width: 18px; height: 18px; stroke: var(--chat-hollow); flex-shrink: 0; }
  .cm-att-name {
    font-size: 12px; color: var(--chat-ink);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
}

.cm-actions {
  display: flex; gap: 2px; margin-top: 8px;
  opacity: 0; transition: opacity .15s;
}
.chat-msg:hover .cm-actions { opacity: 1; }
.cm-actions button {
  border: none; background: transparent; cursor: pointer;
  width: 28px; height: 28px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  &:hover { background: var(--chat-hover); }
  &.active { background: var(--chat-accent-soft); }
  &.active svg { stroke: var(--chat-accent); }
  svg { width: 15px; height: 15px; stroke: var(--chat-hollow); }
}
</style>
