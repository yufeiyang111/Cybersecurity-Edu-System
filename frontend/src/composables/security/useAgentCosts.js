import { computed, ref, watch } from 'vue'
import { agentAPI } from '@/api'

export function useAgentCosts(getRunId) {
  const loading = ref(false)
  const errorMessage = ref('')
  const summary = ref(null)
  const invocations = ref([])

  const costKnown = computed(() => summary.value?.cost_known === true)

  async function loadCosts() {
    const runId = getRunId()
    if (!runId) {
      summary.value = null
      invocations.value = []
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      const payload = await agentAPI.getRunCosts(runId)
      summary.value = payload.summary || null
      invocations.value = payload.invocations || []
    } catch (error) {
      errorMessage.value = error?.response?.data?.error || '加载成本数据失败'
    } finally {
      loading.value = false
    }
  }

  watch(getRunId, loadCosts, { immediate: true })

  return { loading, errorMessage, summary, invocations, costKnown, loadCosts }
}
