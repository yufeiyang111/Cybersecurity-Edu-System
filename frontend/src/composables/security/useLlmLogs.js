import { reactive, ref } from 'vue'
import { llmAPI } from '@/api'

export function useLlmLogs() {
  const logs = ref([])
  const summary = ref({ total_calls: 0, total_cost: 0, rpm: 0, tpm: 0 })
  const pagination = reactive({ page: 1, perPage: 10, total: 0, pages: 0 })
  const loading = ref(false)
  const errorMessage = ref('')
  const filters = reactive({ start: '', end: '', model: '', operation: '', status: '' })

  const load = async () => {
    loading.value = true
    errorMessage.value = ''
    const params = {
      ...filters,
      page: pagination.page,
      per_page: pagination.perPage
    }
    try {
      const [logsResponse, summaryResponse] = await Promise.all([
        llmAPI.listLogs(params),
        llmAPI.getLogSummary(filters)
      ])
      logs.value = logsResponse.items || []
      pagination.total = logsResponse.total || 0
      pagination.pages = logsResponse.pages || 0
      summary.value = summaryResponse.summary || summary.value
    } catch (error) {
      errorMessage.value = error?.response?.data?.error || '加载调用日志失败'
    } finally {
      loading.value = false
    }
  }

  const search = () => {
    pagination.page = 1
    return load()
  }

  const reset = () => {
    Object.assign(filters, { start: '', end: '', model: '', operation: '', status: '' })
    pagination.page = 1
    return load()
  }

  const changePage = (page) => {
    pagination.page = page
    return load()
  }

  const changePerPage = (value) => {
    pagination.perPage = Number(value)
    pagination.page = 1
    return load()
  }

  return {
    logs,
    summary,
    pagination,
    filters,
    loading,
    errorMessage,
    load,
    search,
    reset,
    changePage,
    changePerPage
  }
}
