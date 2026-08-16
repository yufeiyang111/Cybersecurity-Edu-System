<template>
  <div class="cm-body cm-user-bubble">
    <div v-if="message.attachments?.length" class="cm-attachments">
      <ChatAttachmentChip
        v-for="(att, index) in message.attachments"
        :key="index"
        :attachment="att"
        @preview="openPreview"
      />
    </div>
    <div class="cm-text">{{ message.content }}</div>

    <ChatAttachmentPreview ref="previewRef" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ChatAttachmentChip from './ChatAttachmentChip.vue'
import ChatAttachmentPreview from './ChatAttachmentPreview.vue'

defineProps({
  message: { type: Object, required: true }
})

const previewRef = ref(null)

const openPreview = (att) => {
  previewRef.value?.openAttachment(att)
}
</script>

<style scoped lang="scss">
.cm-user-bubble {
  max-width: min(75%, 560px);
  padding: 11px 14px;
  border-radius: 16px 16px 3px 16px;
  color: var(--chat-ink);
  background: var(--chat-bubble);
}

.cm-text {
  font-size: calc(15px * var(--chat-font-scale));
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.cm-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

@media (min-width: 768px) and (max-width: 1200px) {
  .cm-user-bubble {
    max-width: 82%;
  }
}

@media (max-width: 767px) {
  .cm-user-bubble {
    max-width: 88%;
    padding: 10px 12px;
  }
}
</style>
