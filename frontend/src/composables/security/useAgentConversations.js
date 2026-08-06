import { ref, watch } from 'vue'
import { agentAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

export function useAgentConversations(projectIdGetter) {
  const conversations = ref([])
  const loading = ref(false)
  const errorMessage = ref('')
  let requestId = 0

  async function load(projectId) {
    const currentRequest = ++requestId
    conversations.value = []
    errorMessage.value = ''
    if (!projectId) {
      loading.value = false
      return
    }

    loading.value = true
    try {
      const response = await agentAPI.listProjectConversations(projectId, { page: 1, page_size: 20 })
      if (currentRequest !== requestId) return
      conversations.value = response.items || []
    } catch (error) {
      if (currentRequest === requestId) {
        errorMessage.value = securityApiErrorMessage(error, '加载历史会话失败。')
      }
    } finally {
      if (currentRequest === requestId) loading.value = false
    }
  }

  watch(projectIdGetter, load, { immediate: true })

  return { conversations, loading, errorMessage, load }
}
