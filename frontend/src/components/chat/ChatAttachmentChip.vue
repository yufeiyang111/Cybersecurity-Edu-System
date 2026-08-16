<template>
  <div
    class="chat-att-chip"
    role="button"
    tabindex="0"
    :title="attachment.name"
    @click="emit('preview', attachment)"
    @keydown.enter="emit('preview', attachment)"
    @keydown.space.prevent="emit('preview', attachment)"
  >
    <img
      v-if="attachment.type === 'image' && (attachment.preview || attachment.url)"
      :src="attachment.preview || attachment.url"
      alt=""
      class="chat-att-thumb"
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
    <div class="chat-att-info">
      <span class="chat-att-name" :title="attachment.name">{{ attachment.name }}</span>
      <span v-if="attachment.size" class="chat-att-size">{{ formatFileSize(attachment.size) }}</span>
    </div>
    <button
      v-if="removable"
      class="chat-att-x"
      :title="removeTitle"
      @click.stop="emit('remove', attachment)"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { formatFileSize } from '@/composables/chat/useAttachmentFiles'

defineProps({
  attachment: { type: Object, required: true },
  removable: { type: Boolean, default: false },
  removeTitle: { type: String, default: '移除' }
})

const emit = defineEmits(['preview', 'remove'])
</script>

<style scoped lang="scss">
.chat-att-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 220px;
  padding: 5px 8px;
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  background: var(--chat-bubble);
  cursor: pointer;
  user-select: none;
  transition: all 0.2s ease;

  &:hover,
  &:focus-visible {
    border-color: var(--chat-accent);
    outline: none;
  }

  > svg {
    width: 18px;
    height: 18px;
    stroke: var(--chat-accent);
    flex-shrink: 0;
  }

  .chat-att-thumb {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    object-fit: cover;
    flex-shrink: 0;
    border: 1px solid var(--chat-hairline);
  }

  .chat-att-info {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .chat-att-name {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--chat-ink);
    font-size: calc(12px * var(--chat-font-scale));
    font-weight: 500;
  }

  .chat-att-size {
    color: var(--chat-hollow);
    font-size: 10px;
  }

  .chat-att-x {
    margin-left: 2px;
    padding: 3px;
    border: none;
    background: transparent;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;

    &:hover {
      background: var(--chat-hover);
    }

    svg {
      width: 12px;
      height: 12px;
      stroke: var(--chat-hollow);
    }
  }
}
</style>
