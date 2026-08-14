import { ref } from 'vue'
import { adminAPI } from '@/api'
import {
  normalizeEvaluationRunDetailResponse,
  normalizeEvaluationRunsResponse
} from '@/features/admin/ragEvaluationPresentation'
import { normalizeRagTraceResponse } from '@/features/admin/ragTracePresentation'

/**
 * 管理端 RAG 诊断数据编排：组件只接收脱敏后的展示模型。
 */
export function useRagDiagnostics() {
  const runs = ref([])
  const runsPagination = ref({ total: 0, page: 1, perPage: 20, pages: 0 })
  const runsState = ref('idle')
  const runsError = ref('')
  const selectedRun = ref(null)
  const selectedRunState = ref('idle')
  const selectedRunError = ref('')
  const trace = ref(null)
  const traceState = ref('idle')
  const traceError = ref('')

  const loadRuns = async (page = runsPagination.value.page) => {
    runsState.value = 'loading'
    runsError.value = ''
    try {
      const response = await adminAPI.getRagEvaluationRuns({ page, per_page: 12 })
      const data = normalizeEvaluationRunsResponse(response)
      runs.value = data.runs
      runsPagination.value = {
        total: data.total,
        page: data.page,
        perPage: data.perPage,
        pages: data.pages
      }
      runsState.value = data.runs.length ? 'success' : 'empty'
      return data
    } catch (error) {
      runsState.value = 'error'
      runsError.value = safeErrorMessage(error, '评测运行摘要暂时无法加载。')
      throw error
    }
  }

  const loadRunDetail = async (runId) => {
    const normalizedId = positiveInteger(runId)
    if (!normalizedId) {
      throw new Error('评测运行标识无效。')
    }
    selectedRunState.value = 'loading'
    selectedRunError.value = ''
    try {
      const response = await adminAPI.getRagEvaluationRun(normalizedId, { page: 1, per_page: 100 })
      const data = normalizeEvaluationRunDetailResponse(response)
      if (!data || data.run.id !== normalizedId) {
        throw new Error('评测运行详情响应无效。')
      }
      selectedRun.value = data
      selectedRunState.value = 'success'
      return data
    } catch (error) {
      selectedRunState.value = 'error'
      selectedRunError.value = safeErrorMessage(error, '评测运行详情暂时无法加载。')
      throw error
    }
  }

  const loadTrace = async (traceId) => {
    const normalizedId = positiveInteger(traceId)
    if (!normalizedId) {
      throw new Error('请输入正整数 Trace ID。')
    }
    traceState.value = 'loading'
    traceError.value = ''
    try {
      const response = await adminAPI.getRagTrace(normalizedId)
      const data = normalizeRagTraceResponse(response)
      if (!data || data.id !== normalizedId) {
        throw new Error('检索追踪响应无效。')
      }
      trace.value = data
      traceState.value = 'success'
      return data
    } catch (error) {
      traceState.value = 'error'
      traceError.value = safeErrorMessage(error, '检索追踪暂时无法加载。')
      throw error
    }
  }

  return {
    runs,
    runsPagination,
    runsState,
    runsError,
    selectedRun,
    selectedRunState,
    selectedRunError,
    trace,
    traceState,
    traceError,
    loadRuns,
    loadRunDetail,
    loadTrace
  }
}

function positiveInteger(value) {
  const number = Number(value)
  return Number.isInteger(number) && number > 0 ? number : null
}

function safeErrorMessage(error, fallback) {
  const status = Number(error?.response?.status)
  if (status === 403) {
    return '当前账号没有管理员诊断权限。'
  }
  if (status === 404) {
    return '未找到该诊断记录。'
  }
  return fallback
}
