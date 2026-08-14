<template>
  <div class="cm-body cm-user-bubble">
    <div v-if="message.attachments?.length" class="cm-attachments">
      <div
        v-for="(attachment, index) in message.attachments"
        :key="index"
        class="cm-att"
      >
        <img
          v-if="attachment.type === 'image' && attachment.preview"
          :src="attachment.preview"
          alt=""
        >
        <svg
          v-else
          viewBox="0 0 24 24"
          fill="none"
          stroke-width="1.6"
          aria-hidden="true"
        >
          <path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6z" />
          <path d="M14 3v6h6" />
        </svg>
        <span class="cm-att-name">{{ attachment.name }}</span>
      </div>
    </div>
    <div class="cm-text">{{ message.content }}</div>
  </div>
</template>

<script setup>
defineProps({
  message: { type: Object, required: true }
})
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

.cm-att {
  display: inline-flex;
  max-width: 180px;
  align-items: center;
  gap: 5px;
  padding: 4px 7px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 6px;
  color: var(--chat-hollow);
  font-size: calc(12px * var(--chat-font-scale));

  svg {
    width: 14px;
    height: 14px;
    stroke: var(--chat-hollow);
  }

  img {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    object-fit: cover;
  }
}

.cm-att-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
