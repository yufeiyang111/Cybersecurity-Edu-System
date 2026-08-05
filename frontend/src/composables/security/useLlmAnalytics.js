import { reactive, ref } from 'vue'
import { llmAPI } from '@/api'

export function useLlmAnalytics() {
  const analytics = ref({
    summary: { total_calls: 0, total_cost: 0, total_tokens: 0, rpm: 0, tpm: 0 },
    models: [],
    providers: [],
    trend: []
  })
  const filters = reactive({ start: '', end: '', model: '' })
  const loading = ref(false)
  const errorMessage = ref('')

  const load = async () => {
    loading.value = true
    errorMessage.value = ''
    try {
      analytics.value = await llmAPI.getAnalytics(filters)
    } catch (error) {
      errorMessage.value = error?.response?.data?.error || '加载模型调用分析失败'
    } finally {
      loading.value = false
    }
  }

  return { analytics, filters, loading, errorMessage, load }
}
