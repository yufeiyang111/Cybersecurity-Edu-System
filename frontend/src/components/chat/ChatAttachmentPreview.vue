<template>
  <el-image-viewer
    v-if="imageViewerVisible"
    :url-list="[imageViewerUrl]"
    @close="closeImageViewer"
  />

  <DocPreviewDialog
    v-model:visible="docDialogVisible"
    :file="selectedDocFile"
  />
</template>

<script setup>
import { ref } from 'vue'
import { ElImageViewer } from 'element-plus'
import DocPreviewDialog from '@/components/chat/DocPreviewDialog.vue'

const imageViewerVisible = ref(false)
const imageViewerUrl = ref('')
const docDialogVisible = ref(false)
const selectedDocFile = ref(null)

const closeImageViewer = () => {
  imageViewerVisible.value = false
  imageViewerUrl.value = ''
}

/**
 * 打开附件预览：图片走大图查看器，其他走文档文本弹窗
 */
const openAttachment = (att) => {
  if (!att) return
  const src = att.preview || att.url
  if (att.type === 'image' && src) {
    imageViewerUrl.value = src
    imageViewerVisible.value = true
  } else {
    selectedDocFile.value = att
    docDialogVisible.value = true
  }
}

defineExpose({ openAttachment })
</script>
