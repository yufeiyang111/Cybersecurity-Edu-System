<template>
  <el-dialog
    class="doc-preview-dialog"
    :model-value="visible"
    width="min(680px, calc(100vw - 32px))"
    destroy-on-close
    @update:model-value="handleUpdate"
  >
    <template #header>
      <div class="doc-preview-title-box">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" class="doc-preview-icon">
          <path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6z" />
          <path d="M14 3v6h6" />
        </svg>
        <div class="doc-preview-meta">
          <span class="doc-preview-filename" :title="file?.name">{{ file?.name || '文档预览' }}</span>
          <span v-if="file?.size" class="doc-preview-size">{{ formatFileSize(file.size) }}</span>
        </div>
      </div>
    </template>

    <div class="doc-preview-body">
      <div v-if="loading" class="doc-preview-loading">
        <span class="doc-preview-spinner"></span>
        <span>正在加载内容…</span>
      </div>
      <div v-else-if="errorMsg" class="doc-preview-error">
        {{ errorMsg }}
      </div>
      <pre v-else class="doc-preview-content">{{ previewText || '（文档内容为空或未能提取到纯文本）' }}</pre>
    </div>

    <template #footer>
      <span class="doc-preview-hint">共 {{ (previewText || '').length }} 字符</span>
      <el-button @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  file: { type: Object, default: () => null }
})

const emit = defineEmits(['update:visible', 'close'])

const previewText = ref('')
const loading = ref(false)
const errorMsg = ref('')

const formatFileSize = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const loadFileContent = async (fileObj) => {
  if (!fileObj) {
    previewText.value = ''
    return
  }
  if (fileObj.text) {
    previewText.value = fileObj.text
    return
  }
  if (fileObj.file instanceof File) {
    const raw = fileObj.file
    const name = raw.name.toLowerCase()
    const isPlainText = /\.(txt|md|markdown|json|xml|yaml|yml|log|csv|html|htm|js|py|sql|sh|css)$/i.test(name)
    if (isPlainText) {
      loading.value = true
      errorMsg.value = ''
      try {
        const text = await raw.text()
        previewText.value = text.slice(0, 30000)
      } catch (err) {
        errorMsg.value = '读取本地文件内容失败'
      } finally {
        loading.value = false
      }
      return
    }
    previewText.value = `[${raw.name}] 为二进制或结构化文档格式（如 Word、PDF 等），发送后将由服务端解析并提取正文内容。`
    return
  }
  previewText.value = fileObj.text || '（暂无纯文本提取内容）'
}

watch(
  () => [props.visible, props.file],
  ([visible, file]) => {
    if (visible && file) {
      loadFileContent(file)
    } else {
      previewText.value = ''
      errorMsg.value = ''
    }
  },
  { immediate: true }
)

const handleUpdate = (value) => {
  emit('update:visible', value)
  if (!value) emit('close')
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}
</script>

<style scoped lang="scss">
.doc-preview-dialog {
  .doc-preview-title-box {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .doc-preview-icon {
    width: 22px;
    height: 22px;
    stroke: var(--chat-accent);
    flex-shrink: 0;
  }

  .doc-preview-meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .doc-preview-filename {
    font-size: 14px;
    font-weight: 600;
    color: var(--chat-ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 420px;
  }

  .doc-preview-size {
    font-size: 12px;
    color: var(--chat-hollow);
  }
}

.doc-preview-body {
  padding: 4px 2px;
  max-height: 60vh;
  overflow-y: auto;
}

.doc-preview-loading,
.doc-preview-error {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  font-size: 13px;
  color: var(--chat-hollow);
  gap: 8px;
}

.doc-preview-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--chat-hairline);
  border-top-color: var(--chat-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.doc-preview-content {
  margin: 0;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--chat-ink);
  background: var(--chat-bubble);
  border-radius: var(--chat-radius);
  padding: 14px 16px;
}

.doc-preview-hint {
  font-size: 12px;
  color: var(--chat-hollow);
  margin-right: auto;
}
</style>
