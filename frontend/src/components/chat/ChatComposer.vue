<template>
  <div class="chat-composer">
    <div class="cc-inner">
      <div v-if="attachments.length" class="cc-attachments">
        <ChatAttachmentChip
          v-for="att in attachments"
          :key="att.uid"
          :attachment="att"
          removable
          :remove-title="t('composer.remove')"
          @preview="openPreview"
          @remove="removeAttachment"
        />
      </div>

      <div class="cc-box">
        <button class="cc-plus" :title="t('composer.addFiles')" @click="pickFiles">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M12 5v14M5 12h14" /></svg>
        </button>
        <textarea
          ref="textareaRef"
          id="chat-composer-input"
          name="message"
          :aria-label="placeholder"
          v-model="text"
          rows="1"
          :placeholder="placeholder"
          @keydown.enter.exact.prevent="handleEnter"
          @keydown.enter.shift="onShiftEnter"
          @paste="handlePaste"
        ></textarea>
        <button
          class="cc-send"
          :class="{ active: canSend }"
          :disabled="!canSend"
          :title="t('composer.send')"
          @click="handleSend"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
        </button>
      </div>

      <div class="cc-hint">
        <span>{{ hintText }}</span>
        <span class="cc-kbd"><kbd>Enter</kbd> {{ t('composer.send') }}</span>
      </div>
    </div>

    <input
      ref="fileInputRef"
      id="chat-composer-files"
      name="attachments"
      :aria-label="t('composer.addFiles')"
      type="file"
      multiple
      class="cc-file-input"
      @change="onFilesSelected"
    >

    <div v-if="dragging" class="cc-drag-overlay">
      <div class="cc-drag-box">{{ t('composer.drop') }}</div>
    </div>

    <ChatAttachmentPreview ref="previewRef" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from '@/features/chat/i18n'
import { ElMessage } from 'element-plus'
import ChatAttachmentChip from '@/components/chat/ChatAttachmentChip.vue'
import ChatAttachmentPreview from '@/components/chat/ChatAttachmentPreview.vue'
import {
  buildAttachmentEntries,
  filesFromDrop,
  filesFromPaste
} from '@/composables/chat/useAttachmentFiles'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: '' }
})

const emit = defineEmits(['send'])
const { t } = useI18n()

const text = ref('')
const attachments = ref([])
const dragging = ref(false)
const textareaRef = ref(null)
const fileInputRef = ref(null)
const previewRef = ref(null)

let uidSeed = 0

const placeholder = computed(() => props.placeholder || t('composer.placeholder'))
const canSend = computed(() => text.value.trim().length > 0 || attachments.value.length > 0)
const hintText = computed(() =>
  attachments.value.length
    ? t('composer.attachments', { count: attachments.value.length })
    : t('composer.hint')
)

const resize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}
watch(text, resize)

const addFiles = async (files) => {
  if (!files || !files.length) return
  const entries = await buildAttachmentEntries(files, attachments.value.length)
  for (const entry of entries) {
    entry.uid = ++uidSeed
    attachments.value.push(entry)
  }
}

const onFilesSelected = (e) => {
  addFiles(Array.from(e.target.files || []))
  e.target.value = ''
}

const pickFiles = () => fileInputRef.value?.click()

const removeAttachment = (att) => {
  const idx = attachments.value.findIndex((a) => a.uid === att.uid)
  if (idx !== -1) attachments.value.splice(idx, 1)
}

const openPreview = (att) => {
  previewRef.value?.openAttachment(att)
}

const handlePaste = async (e) => {
  const pastedFiles = filesFromPaste(e)
  if (pastedFiles.length > 0) {
    e.preventDefault()
    await addFiles(pastedFiles)
  }
}

const onShiftEnter = (e) => {
  e.preventDefault()
  const el = textareaRef.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  text.value = text.value.slice(0, start) + '\n' + text.value.slice(end)
  resize()
  requestAnimationFrame(() => {
    el.selectionStart = el.selectionEnd = start + 1
  })
}

const handleEnter = () => handleSend()

const handleSend = () => {
  if (props.disabled) return
  const value = text.value.trim()
  if (!value && !attachments.value.length) return
  emit('send', {
    text: value,
    files: attachments.value.map(a => a.file),
    attachmentMeta: attachments.value.map(a => ({
      name: a.name,
      type: a.type,
      size: a.size,
      preview: a.preview
    }))
  })
  text.value = ''
  attachments.value = []
  resize()
}

const onDragEnter = (e) => {
  e.preventDefault()
  if (e.dataTransfer?.types?.includes('Files')) dragging.value = true
}
const onDragOver = (e) => e.preventDefault()
const onDragLeave = (e) => {
  e.preventDefault()
  if (e.target === document.documentElement) dragging.value = false
}
const onDrop = (e) => {
  e.preventDefault()
  dragging.value = false
  addFiles(filesFromDrop(e))
}

onMounted(() => {
  document.addEventListener('dragenter', onDragEnter)
  document.addEventListener('dragover', onDragOver)
  document.addEventListener('dragleave', onDragLeave)
  document.addEventListener('drop', onDrop)
})
onBeforeUnmount(() => {
  document.removeEventListener('dragenter', onDragEnter)
  document.removeEventListener('dragover', onDragOver)
  document.removeEventListener('dragleave', onDragLeave)
  document.removeEventListener('drop', onDrop)
})
</script>

<style lang="scss" scoped>
.chat-composer {
  padding: calc(12px * var(--chat-space-scale)) 20px 8px;
  position: relative;
}
.cc-inner {
  max-width: var(--chat-content-width);
  margin: 0 auto;
}

.cc-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.cc-box {
  background: var(--chat-canvas);
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  display: flex;
  align-items: flex-end;
  gap: 4px;
  padding: 8px 8px 8px 10px;
  &:focus-within {
    border-color: var(--chat-accent);
  }
}
.cc-plus {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  &:hover {
    background: var(--chat-hover);
  }
  svg {
    width: 17px;
    height: 17px;
    stroke: var(--chat-ink);
  }
}
textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-family: inherit;
  font-size: calc(15px * var(--chat-font-scale));
  line-height: 1.5;
  padding: 6px 4px;
  max-height: 160px;
  color: var(--chat-ink);
  background: transparent;
  &::placeholder {
    color: var(--chat-hollow);
  }
}
.cc-send {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  background: var(--chat-bubble);
  display: flex;
  align-items: center;
  justify-content: center;
  &:disabled {
    cursor: default;
  }
  &.active {
    background: var(--chat-accent-gradient, var(--chat-accent));
  }
  svg {
    width: 16px;
    height: 16px;
    stroke: var(--chat-hollow);
  }
  &.active svg {
    stroke: var(--chat-canvas);
  }
}

.cc-hint {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
  color: var(--chat-hollow);
  .cc-kbd {
    display: inline-flex;
    gap: 4px;
    align-items: center;
  }
  kbd {
    font-family: inherit;
    font-size: 11px;
    color: var(--chat-hollow);
    border: 1px solid var(--chat-hairline);
    border-bottom-width: 2px;
    border-radius: 4px;
    padding: 0 5px;
    background: var(--chat-canvas);
  }
}

.cc-file-input {
  display: none;
}

.cc-drag-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: color-mix(in srgb, var(--chat-canvas) 85%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.cc-drag-box {
  border: 1.5px dashed var(--chat-accent-border);
  border-radius: var(--chat-radius);
  padding: 20px 32px;
  background: var(--chat-canvas);
  font-size: 14px;
  color: var(--chat-ink);
}
</style>
