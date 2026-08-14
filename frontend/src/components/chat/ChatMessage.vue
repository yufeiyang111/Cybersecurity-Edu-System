<template>
  <div class="chat-msg" :class="message.role">
    <ChatUserMessage
      v-if="message.role === 'user'"
      :message="message"
    />

    <template v-else>
      <div class="cm-logo" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="1.8">
          <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" />
          <path d="M9.5 12l2 2 3.5-4" />
        </svg>
      </div>
      <div class="cm-body cm-assistant-body">
        <ChatThinking
          :seconds="message.response_time"
          :citation-count="citationCount"
          :model-name="message.model_name"
          :reasoning="message.reasoning"
        />
        <div
          v-if="message.streaming && !message.content"
          class="cm-stream-dots"
          aria-label="正在生成回答"
        >
          <span />
          <span />
          <span />
        </div>
        <ChatMarkdown v-if="message.content" :content="message.content" />
        <AnswerEvidenceSummary
          v-if="showCitations"
          :answer-status="message.answerStatus"
          :citation-count="citationCount"
          :citation-state="message.citationState"
          :detail-state="message.evidenceLoadState"
          :error-message="message.evidenceError"
          :record-id="message.recordId"
          @load-evidence="handleLoadEvidence"
        />
        <AnswerCitationList
          v-if="showCitations && message.evidenceLoadState === 'success'"
          :citations="citationDetails"
          :retrieval-signal="message.retrievalSignal"
          :details-truncated="message.citationDetailsTruncated"
          @open-detail="handleOpenCitationDetail"
          @open-original="handleOpenCitationOriginal"
        />
        <AnswerUncertaintyPanel
          :answer-status="message.answerStatus"
          :citation-state="message.citationState"
        />
        <ChatRagWarnings v-if="showWarnings" :warnings="message.ragWarnings" />
        <ChatMessageActions
          :feedback="message.feedback"
          @copy="emit('copy', message)"
          @favorite="emit('favorite', message)"
          @feedback="handleFeedback"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AnswerCitationList from './AnswerCitationList.vue'
import AnswerEvidenceSummary from './AnswerEvidenceSummary.vue'
import AnswerUncertaintyPanel from './AnswerUncertaintyPanel.vue'
import ChatMarkdown from './ChatMarkdown.vue'
import ChatMessageActions from './ChatMessageActions.vue'
import ChatRagWarnings from './ChatRagWarnings.vue'
import ChatThinking from './ChatThinking.vue'
import ChatUserMessage from './ChatUserMessage.vue'
import { useChatPreferences } from '@/composables/chat/useChatPreferences'

const props = defineProps({
  message: { type: Object, required: true }
})

const emit = defineEmits([
  'copy',
  'favorite',
  'feedback',
  'view-evidence',
  'citation-detail',
  'citation-original'
])

const { preferences } = useChatPreferences()

const showCitations = computed(() => preferences.show_citations !== false)
const showWarnings = computed(() => preferences.show_security_warnings !== false)
const citationCount = computed(() => {
  const citations = props.message.citationManifest?.citations
  return Array.isArray(citations) ? citations.length : 0
})
const citationDetails = computed(() => {
  return Array.isArray(props.message.citationDetails)
    ? props.message.citationDetails
    : []
})

function handleLoadEvidence(origin) {
  emit('view-evidence', props.message, origin)
}

function handleOpenCitationDetail({ citation, trigger }) {
  emit('citation-detail', props.message, citation, trigger)
}

function handleOpenCitationOriginal({ citation }) {
  emit('citation-original', props.message, citation)
}

function handleFeedback(value) {
  emit('feedback', props.message, value)
}
</script>

<style scoped lang="scss">
.chat-msg {
  display: flex;
  gap: 14px;
  padding: calc(20px * var(--chat-space-scale)) 0;
}

.cm-logo {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  margin-top: 1px;
  border-radius: 50%;
  background: var(--chat-accent-gradient);

  svg {
    width: 16px;
    height: 16px;
  }
}

.cm-body {
  min-width: 0;
}

.cm-assistant-body {
  flex: 1;
}

.chat-msg.user {
  justify-content: flex-end;
}

.cm-stream-dots {
  display: flex;
  gap: 4px;
  padding: 10px 0;

  span {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--chat-hollow);
    animation: stream-dot 1.2s ease-in-out infinite;

    &:nth-child(2) {
      animation-delay: 0.15s;
    }

    &:nth-child(3) {
      animation-delay: 0.3s;
    }
  }
}

@keyframes stream-dot {
  0%,
  60%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@media (min-width: 768px) and (max-width: 1200px) {
  .chat-msg {
    gap: 12px;
  }
}

@media (max-width: 767px) {
  .chat-msg {
    gap: 9px;
    padding: calc(16px * var(--chat-space-scale)) 0;
  }

  .cm-logo {
    width: 24px;
    height: 24px;
  }
}
</style>
