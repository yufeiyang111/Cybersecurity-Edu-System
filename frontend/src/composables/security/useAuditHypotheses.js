import { ref } from 'vue'
import { agentAPI } from '@/api'
import {
  normalizeHypothesisDetailResponse,
  normalizeHypothesisListResponse
} from '@/features/security/agent/hypothesisPresentation'

const EMPTY_METRICS = Object.freeze({
  hypothesisCount: 0,
  statusCounts: {},
  skillCounts: [],
  codeEvidenceCoverage: null,
  evidenceInsufficientRate: null,
  budgetExhaustionRate: null,
  deepReviewCost: {
    callCount: 0,
    costKnown: false,
    totalCost: null,
    averagePerHypothesis: null
  }
})

export function useAuditHypotheses() {
  const loading = ref(false)
  const detailLoading = ref(false)
  const errorMessage = ref('')
  const detailErrorMessage = ref('')
  const items = ref([])
  const total = ref(0)
  const metrics = ref(EMPTY_METRICS)
  const selectedId = ref(null)
  const selectedDetail = ref(null)

  async function load(runId) {
    if (!positiveId(runId)) {
      clear()
      return false
    }
    loading.value = true
    errorMessage.value = ''
    detailErrorMessage.value = ''
    try {
      const response = await agentAPI.getHypotheses(runId, {
        page: 1,
        page_size: 20
      })
      const normalized = normalizeHypothesisListResponse(response)
      items.value = normalized.items
      total.value = normalized.total
      metrics.value = normalized.metrics
      if (!items.value.some((item) => item.id === selectedId.value)) {
        clearSelection()
      }
      return true
    } catch (error) {
      items.value = []
      total.value = 0
      metrics.value = EMPTY_METRICS
      errorMessage.value = '暂时无法读取攻击路径验证结果，请稍后重试。'
      return false
    } finally {
      loading.value = false
    }
  }

  async function select(runId, hypothesisId) {
    if (!positiveId(runId) || !positiveId(hypothesisId)) return false
    selectedId.value = hypothesisId
    selectedDetail.value = null
    detailLoading.value = true
    detailErrorMessage.value = ''
    try {
      const response = await agentAPI.getHypothesis(runId, hypothesisId)
      selectedDetail.value = normalizeHypothesisDetailResponse(response)
      return Boolean(selectedDetail.value)
    } catch (error) {
      detailErrorMessage.value = '暂时无法读取该候选的 Critic 判定。'
      return false
    } finally {
      detailLoading.value = false
    }
  }

  function clearSelection() {
    selectedId.value = null
    selectedDetail.value = null
    detailErrorMessage.value = ''
    detailLoading.value = false
  }

  function clear() {
    loading.value = false
    errorMessage.value = ''
    items.value = []
    total.value = 0
    metrics.value = EMPTY_METRICS
    clearSelection()
  }

  return {
    loading,
    detailLoading,
    errorMessage,
    detailErrorMessage,
    items,
    total,
    metrics,
    selectedId,
    selectedDetail,
    load,
    select,
    clearSelection,
    clear
  }
}

function positiveId(value) {
  return Number.isInteger(Number(value)) && Number(value) > 0
}
