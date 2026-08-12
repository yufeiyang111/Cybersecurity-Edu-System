import { reactive, ref } from 'vue'
import { llmAPI } from '@/api'

export function useLlmAnalytics() {
  const analytics = ref({
    summary: { total_calls: 0, total_tokens: 0, input_tokens: 0, cached_input_tokens: 0, cache_hit_rate: 0, rpm: 0, tpm: 0 },
    models: [],
    providers: [],
    trend: []
  })
  const filters = reactive({
    start: '',
    end: '',
    time_range: '1d',
    granularity: 'hour',
    model: ''
  })
  const loading = ref(false)
  const errorMessage = ref('')
  let requestSequence = 0

  const load = async () => {
    const sequence = ++requestSequence
    loading.value = true
    errorMessage.value = ''
    try {
      const params = { ...filters }
      if (params.time_range) {
        delete params.start
        delete params.end
      }
      const response = await llmAPI.getAnalytics(params)
      if (sequence !== requestSequence) return
      analytics.value = response
    } catch (error) {
      if (sequence !== requestSequence) return
      errorMessage.value = error?.response?.data?.error || '加载模型调用分析失败'
    } finally {
      if (sequence === requestSequence) {
        loading.value = false
      }
    }
  }

  return { analytics, filters, loading, errorMessage, load }
}
