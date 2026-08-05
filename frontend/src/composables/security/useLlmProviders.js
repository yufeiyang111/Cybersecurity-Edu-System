import { ref } from 'vue'
import { llmAPI } from '@/api'

export function useLlmProviders() {
  const providers = ref([])
  const loading = ref(false)
  const errorMessage = ref('')

  const load = async () => {
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await llmAPI.listProviders()
      providers.value = response.providers || []
    } catch (error) {
      errorMessage.value = error?.response?.data?.error || '加载 LLM 配置失败'
      throw error
    } finally {
      loading.value = false
    }
  }

  const create = async (payload) => {
    const response = await llmAPI.createProvider(payload)
    await load()
    return response.provider
  }

  const update = async (id, payload) => {
    const response = await llmAPI.updateProvider(id, payload)
    await load()
    return response.provider
  }

  const remove = async (id) => {
    await llmAPI.deleteProvider(id)
    await load()
  }

  const testing = ref(null)

  const test = async (id) => {
    testing.value = id
    try {
      const response = await llmAPI.testProvider(id)
      await load()
      return response
    } finally {
      testing.value = null
    }
  }

  const setDefault = async (id) => {
    await llmAPI.setDefaultProvider(id)
    await load()
  }

  const toggle = async (id, enabled) => {
    await llmAPI.toggleProvider(id, enabled)
    await load()
  }

  return { providers, loading, errorMessage, load, create, update, remove, test, setDefault, toggle, testing }
}
