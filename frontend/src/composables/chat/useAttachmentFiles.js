/**
 * 问答附件文件处理共享逻辑
 * 负责：文件读取为预览、大小格式化、剪贴板粘贴文件提取、拖拽文件提取
 * 供 ChatComposer / 其他附件入口复用
 */
import { ElMessage } from 'element-plus'

export const MAX_ATTACHMENTS = 5

export const formatFileSize = (bytes) => {
  if (!bytes || bytes === 0) return ''
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + sizes[i]
}

/**
 * 读取图片文件为 dataURL 预览；非图片返回 null
 */
export const readImagePreview = (file) => {
  if (!file || !file.type.startsWith('image/')) return Promise.resolve(null)
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => resolve(null)
    reader.readAsDataURL(file)
  })
}

/**
 * 把 File 列表转换为附件条目（含本地缩略图）
 * 超过 MAX_ATTACHMENTS 时提示并截断
 */
export const buildAttachmentEntries = async (files, currentCount = 0) => {
  if (!files || !files.length) return []
  const entries = []
  for (const file of files) {
    if (currentCount + entries.length >= MAX_ATTACHMENTS) {
      ElMessage.warning(`单次最多上传 ${MAX_ATTACHMENTS} 个附件`)
      break
    }
    const isImage = file.type.startsWith('image/')
    entries.push({
      name: file.name || (isImage ? `image_${Date.now()}.png` : 'unnamed_file'),
      type: isImage ? 'image' : 'file',
      size: file.size,
      file,
      preview: await readImagePreview(file)
    })
  }
  return entries
}

/**
 * 从剪贴板事件提取粘贴的图片/文件；截图自动命名为 screenshot_<时间戳>.<ext>
 */
export const filesFromPaste = (event) => {
  const clipboardData = event.clipboardData || window.clipboardData
  if (!clipboardData) return []
  const pastedFiles = []
  for (const item of Array.from(clipboardData.items || [])) {
    if (item.kind !== 'file') continue
    const file = item.getAsFile()
    if (!file) continue
    if (!file.name || file.name === 'image.png') {
      const ext = file.type.split('/')[1] || 'png'
      const renamed = new File([file], `screenshot_${Date.now()}.${ext}`, { type: file.type })
      pastedFiles.push(renamed)
    } else {
      pastedFiles.push(file)
    }
  }
  return pastedFiles
}

/**
 * 从拖拽事件提取文件列表
 */
export const filesFromDrop = (event) => {
  return Array.from(event.dataTransfer?.files || [])
}
