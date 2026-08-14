import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { qaAPI } from '@/api'
import {
  hasNavigableDocument,
  normalizeEvidenceResponse
} from '@/features/chat/citationPresentation'

/**
 * 问答引用证据的唯一数据加载入口。
 * 组件只通过 props / emit 展示，不自行请求或拼接知识文档 ID。
 */
export function useCitationEvidence() {
  const router = useRouter()
  const records = ref({})
  const drawerVisible = ref(false)
  const selectedCitation = ref(null)
  const selectedSignal = ref(null)
  const selectedRecordId = ref(null)
  const requests = new Map()
  let focusOrigin = null

  const loadEvidence = async (recordId) => {
    const normalizedRecordId = positiveInteger(recordId)
    if (!normalizedRecordId) {
      throw new Error('该回答尚未保存，暂时无法读取证据详情。')
    }

    const cacheKey = String(normalizedRecordId)
    const cached = records.value[cacheKey]
    if (cached?.state === 'success') {
      return cached.data
    }
    if (requests.has(cacheKey)) {
      return requests.get(cacheKey)
    }

    records.value = {
      ...records.value,
      [cacheKey]: { state: 'loading', data: cached?.data || null }
    }

    const request = qaAPI.getEvidence(normalizedRecordId)
      .then((response) => {
        const data = normalizeEvidenceResponse(response)
        if (!data || data.recordId !== normalizedRecordId) {
          throw new Error('证据详情响应无效。')
        }
        records.value = {
          ...records.value,
          [cacheKey]: { state: 'success', data }
        }
        return data
      })
      .catch((error) => {
        records.value = {
          ...records.value,
          [cacheKey]: {
            state: 'error',
            data: cached?.data || null,
            errorMessage: safeErrorMessage(error)
          }
        }
        throw error
      })
      .finally(() => {
        requests.delete(cacheKey)
      })

    requests.set(cacheKey, request)
    return request
  }

  const stateFor = (recordId) => {
    const normalizedRecordId = positiveInteger(recordId)
    if (!normalizedRecordId) {
      return { state: 'unavailable', data: null, errorMessage: '' }
    }
    return records.value[String(normalizedRecordId)] || {
      state: 'idle',
      data: null,
      errorMessage: ''
    }
  }

  const openCitation = async (recordId, citationId, origin) => {
    const data = await loadEvidence(recordId)
    const citation = data.citationDetails.find((item) => item.citationId === citationId)
    if (!citation) {
      throw new Error('该引用当前不可用。')
    }
    focusOrigin = origin instanceof HTMLElement ? origin : null
    selectedCitation.value = citation
    selectedSignal.value = data.retrievalSignal
    selectedRecordId.value = positiveInteger(recordId)
    drawerVisible.value = true
  }

  const openOriginalDocument = async (recordId, citationId) => {
    const data = await loadEvidence(recordId)
    const citation = data.citationDetails.find((item) => item.citationId === citationId)
    if (!citation || !hasNavigableDocument(citation)) {
      throw new Error('该引用的知识库原文当前不可用。')
    }
    await router.push({
      name: 'KnowledgeDetail',
      params: { id: citation.document.knowledgeId }
    })
  }

  const closeDrawer = async () => {
    drawerVisible.value = false
    selectedCitation.value = null
    selectedSignal.value = null
    selectedRecordId.value = null
    const origin = focusOrigin
    focusOrigin = null
    await nextTick()
    if (origin?.isConnected) {
      origin.focus()
    }
  }

  return {
    drawerVisible,
    selectedCitation,
    selectedSignal,
    selectedRecordId,
    loadEvidence,
    stateFor,
    openCitation,
    openOriginalDocument,
    closeDrawer
  }
}

function positiveInteger(value) {
  const normalized = Number(value)
  return Number.isInteger(normalized) && normalized > 0 ? normalized : null
}

function safeErrorMessage(error) {
  const message = typeof error?.message === 'string' ? error.message.trim() : ''
  return message && message.length <= 120
    ? message
    : '证据详情暂时无法加载，请稍后重试。'
}
