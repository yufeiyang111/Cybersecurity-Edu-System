import { ref } from 'vue'
import { securityAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

export function useSecurityKnowledge() {
  const loading = ref(false)
  const documentsLoading = ref(false)
  const errorMessage = ref('')
  const sources = ref([])
  const documents = ref([])
  const selectedSource = ref(null)
  let sourcesRequestSequence = 0
  let documentsRequestSequence = 0

  const loadDocuments = async (sourceId) => {
    if (!sourceId) return
    const requestSequence = ++documentsRequestSequence
    documentsLoading.value = true
    try {
      const response = await securityAPI.listKnowledgeDocuments(sourceId, { limit: 100 })
      if (requestSequence === documentsRequestSequence && selectedSource.value?.id === sourceId) {
        documents.value = response.items || []
      }
    } catch (error) {
      if (requestSequence === documentsRequestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载知识文档失败。')
      }
    } finally {
      if (requestSequence === documentsRequestSequence) documentsLoading.value = false
    }
  }

  const loadSources = async () => {
    const requestSequence = ++sourcesRequestSequence
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await securityAPI.listKnowledgeSources({ limit: 100 })
      if (requestSequence !== sourcesRequestSequence) return
      sources.value = response.items || []
      const retainedSource = sources.value.find((source) => source.id === selectedSource.value?.id)
      selectedSource.value = retainedSource || sources.value[0] || null
      documents.value = []
      if (selectedSource.value) await loadDocuments(selectedSource.value.id)
    } catch (error) {
      if (requestSequence === sourcesRequestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载安全知识来源失败。')
      }
    } finally {
      if (requestSequence === sourcesRequestSequence) loading.value = false
    }
  }

  const selectSource = async (source) => {
    if (selectedSource.value?.id === source.id) return
    selectedSource.value = source
    documents.value = []
    errorMessage.value = ''
    await loadDocuments(source.id)
  }

  const createSource = async (payload) => {
    const response = await securityAPI.createKnowledgeSource(payload)
    sources.value = [response.source, ...sources.value]
    selectedSource.value = response.source
    documents.value = []
    return response.source
  }

  const createDocument = async (payload) => {
    if (!selectedSource.value) throw new Error('请先选择安全知识来源。')
    const response = await securityAPI.createKnowledgeDocument(selectedSource.value.id, payload)
    documents.value = [response.document, ...documents.value]
    return response.document
  }

  return {
    loading,
    documentsLoading,
    errorMessage,
    sources,
    documents,
    selectedSource,
    loadSources,
    selectSource,
    createSource,
    createDocument
  }
}
