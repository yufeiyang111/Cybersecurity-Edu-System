import { ref } from 'vue'
import { helpAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

/**
 * 帮助中心数据加载组合式函数
 *
 * 职责：
 * - 公开侧：分类树 + 单篇文档（带请求序号防竞态）
 * - 管理侧：分类树（含未激活）+ 文档详情
 * - 统一的加载/错误状态
 */
export function useHelpCenter() {
  const loading = ref(false)
  const documentLoading = ref(false)
  const errorMessage = ref('')
  const tree = ref([])
  const currentDocument = ref(null)
  let treeRequestSequence = 0
  let documentRequestSequence = 0

  const loadTree = async () => {
    const requestSequence = ++treeRequestSequence
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await helpAPI.getTree()
      if (requestSequence !== treeRequestSequence) return
      tree.value = response.tree || []
    } catch (error) {
      if (requestSequence === treeRequestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载帮助文档目录失败。')
      }
    } finally {
      if (requestSequence === treeRequestSequence) loading.value = false
    }
  }

  const loadDocument = async (slug) => {
    if (!slug) {
      currentDocument.value = null
      return
    }
    const requestSequence = ++documentRequestSequence
    documentLoading.value = true
    errorMessage.value = ''
    try {
      const response = await helpAPI.getDocument(slug)
      if (requestSequence !== documentRequestSequence) return
      currentDocument.value = response.document || null
    } catch (error) {
      if (requestSequence === documentRequestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载帮助文档失败。')
        currentDocument.value = null
      }
    } finally {
      if (requestSequence === documentRequestSequence) documentLoading.value = false
    }
  }

  const loadAdminTree = async () => {
    const requestSequence = ++treeRequestSequence
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await helpAPI.getAdminTree()
      if (requestSequence !== treeRequestSequence) return
      tree.value = response.tree || []
    } catch (error) {
      if (requestSequence === treeRequestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载帮助文档目录失败。')
      }
    } finally {
      if (requestSequence === treeRequestSequence) loading.value = false
    }
  }

  const loadAdminDocument = async (documentId) => {
    if (!documentId) {
      currentDocument.value = null
      return
    }
    const requestSequence = ++documentRequestSequence
    documentLoading.value = true
    errorMessage.value = ''
    try {
      const response = await helpAPI.getAdminDocument(documentId)
      if (requestSequence !== documentRequestSequence) return
      currentDocument.value = response.document || null
    } catch (error) {
      if (requestSequence === documentRequestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载帮助文档失败。')
        currentDocument.value = null
      }
    } finally {
      if (requestSequence === documentRequestSequence) documentLoading.value = false
    }
  }

  const reset = () => {
    currentDocument.value = null
    errorMessage.value = ''
  }

  return {
    loading,
    documentLoading,
    errorMessage,
    tree,
    currentDocument,
    loadTree,
    loadDocument,
    loadAdminTree,
    loadAdminDocument,
    reset
  }
}