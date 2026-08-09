<template>
  <div class="chat-composer">
    <div class="cc-inner">
      <div v-if="attachments.length" class="cc-attachments">
        <div v-for="(att, idx) in attachments" :key="att.uid" class="cc-chip">
          <img v-if="att.preview" :src="att.preview" alt="">
          <svg v-else viewBox="0 0 24 24" fill="none" stroke-width="1.6">
            <path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6z" />
            <path d="M14 3v6h6" />
          </svg>
          <span class="cc-chip-name">{{ att.name }}</span>
          <button class="cc-chip-x" :title="t('composer.remove')" @click="removeAttachment(idx)">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>
      </div>

      <div class="cc-box">
        <button class="cc-plus" :title="t('composer.addFiles')" @click="pickFiles">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M12 5v14M5 12h14" /></svg>
        </button>
        <textarea
          ref="textareaRef"
          v-model="text"
          rows="1"
          :placeholder="placeholder"
          @keydown.enter.exact.prevent="handleEnter"
          @keydown.enter.shift="onShiftEnter"
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
      type="file"
      multiple
      class="cc-file-input"
      @change="onFilesSelected"
    >

    <div v-if="dragging" class="cc-drag-overlay">
      <div class="cc-drag-box">{{ t('composer.drop') }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from '@/features/chat/i18n'

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

const previewImage = (file) => {
  if (!file.type.startsWith('image/')) return null
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => resolve(null)
    reader.readAsDataURL(file)
  })
}

const addFiles = async (files) => {
  for (const file of files) {
    if (attachments.value.length >= 5) break
    attachments.value.push({
      uid: ++uidSeed,
      name: file.name,
      type: file.type.startsWith('image/') ? 'image' : 'file',
      size: file.size,
      file,
      preview: await previewImage(file)
    })
  }
}

const onFilesSelected = (e) => {
  addFiles(Array.from(e.target.files || []))
  e.target.value = ''
}

const pickFiles = () => fileInputRef.value?.click()

const removeAttachment = (idx) => {
  attachments.value.splice(idx, 1)
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
  emit('send', { text: value, files: attachments.value.map(a => a.file) })
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
  if (e.dataTransfer?.files?.length) addFiles(Array.from(e.dataTransfer.files))
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
.chat-composer { padding: calc(12px * var(--chat-space-scale)) 20px 8px; position: relative; }
.cc-inner { max-width: var(--chat-content-width); margin: 0 auto; }

.cc-attachments { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.cc-chip {
  display: flex; align-items: center; gap: 8px;
  background: var(--chat-bubble);
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  padding: 6px 8px;
  font-size: 12.5px;
  img {
    width: 28px; height: 28px; border-radius: 6px; object-fit: cover;
    flex-shrink: 0;
  }
  > svg { width: 18px; height: 18px; stroke: var(--chat-hollow); flex-shrink: 0; }
  .cc-chip-name {
    max-width: 140px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    color: var(--chat-ink);
  }
  .cc-chip-x {
    border: none; background: transparent; cursor: pointer; padding: 2px;
    display: flex; align-items: center; border-radius: 4px;
    &:hover { background: var(--chat-hover); }
    svg { width: 12px; height: 12px; stroke: var(--chat-hollow); }
  }
}

.cc-box {
  background: var(--chat-canvas);
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  display: flex; align-items: flex-end; gap: 4px;
  padding: 8px 8px 8px 10px;
  &:focus-within { border-color: var(--chat-accent); }
}
.cc-plus {
  width: 34px; height: 34px; border-radius: 50%;
  border: none; cursor: pointer; flex-shrink: 0;
  background: transparent;
  display: flex; align-items: center; justify-content: center;
  &:hover { background: var(--chat-hover); }
  svg { width: 17px; height: 17px; stroke: var(--chat-ink); }
}
textarea {
  flex: 1; border: none; outline: none; resize: none;
  font-family: inherit; font-size: calc(15px * var(--chat-font-scale)); line-height: 1.5;
  padding: 6px 4px; max-height: 160px; color: var(--chat-ink);
  background: transparent;
  &::placeholder { color: var(--chat-hollow); }
}
.cc-send {
  width: 34px; height: 34px; border-radius: 50%;
  border: none; cursor: pointer; flex-shrink: 0;
  background: var(--chat-bubble);
  display: flex; align-items: center; justify-content: center;
  &:disabled { cursor: default; }
   &.active { background: var(--chat-accent-gradient, var(--chat-accent)); }
  svg { width: 16px; height: 16px; stroke: var(--chat-hollow); }
  &.active svg { stroke: var(--chat-canvas); }
}

.cc-hint {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 8px; font-size: 12px; color: var(--chat-hollow);
  .cc-kbd { display: inline-flex; gap: 4px; align-items: center; }
  kbd {
    font-family: inherit; font-size: 11px; color: var(--chat-hollow);
    border: 1px solid var(--chat-hairline); border-bottom-width: 2px;
    border-radius: 4px; padding: 0 5px; background: var(--chat-canvas);
  }
}

.cc-file-input { display: none; }

.cc-drag-overlay {
  position: fixed; inset: 0; z-index: 50;
  background: rgba(255, 255, 255, 0.6);
  display: flex; align-items: center; justify-content: center;
  pointer-events: none;
}
.cc-drag-box {
  border: 1.5px dashed rgba(0, 0, 0, 0.35);
   border-radius: var(--chat-radius); padding: 20px 32px;
  background: var(--chat-canvas);
  font-size: 14px;
  color: var(--chat-ink);
}
</style>
