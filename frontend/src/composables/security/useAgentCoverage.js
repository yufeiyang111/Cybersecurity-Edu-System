import { ref } from 'vue'
import { agentAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

export function useAgentCoverage(runIdGetter) {
  const loading = ref(false)
  const errorMessage = ref('')
  const summary = ref(null)
  const files = ref([])
  const total = ref(0)
  const activeKind = ref('')
  const PAGE_SIZE = 20
  let requestSequence = 0

  const resolveRunId = () => (typeof runIdGetter === 'function' ? runIdGetter() : runIdGetter)

  async function loadCoverage(kind = '') {
    const runId = resolveRunId()
    if (!runId) return
    const sequence = ++requestSequence
    loading.value = true
    errorMessage.value = ''
    activeKind.value = kind
    try {
      const response = await agentAPI.getCoverage(runId, { kind: kind || undefined, limit: PAGE_SIZE, offset: 0 })
      if (sequence !== requestSequence) return
      summary.value = response.coverage
      files.value = response.files || []
      total.value = response.pagination?.total || 0
    } catch (error) {
      if (sequence === requestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载扫描覆盖失败。')
      }
    } finally {
      if (sequence === requestSequence) loading.value = false
    }
  }

  async function loadMore() {
    const runId = resolveRunId()
    if (!runId || loading.value || files.value.length >= total.value) return
    const sequence = ++requestSequence
    loading.value = true
    try {
      const response = await agentAPI.getCoverage(runId, {
        kind: activeKind.value || undefined,
        limit: PAGE_SIZE,
        offset: files.value.length
      })
      if (sequence !== requestSequence) return
      const known = new Set(files.value.map((file) => file.id))
      files.value = [...files.value, ...(response.files || []).filter((file) => !known.has(file.id))]
      total.value = response.pagination?.total || total.value
    } catch (error) {
      if (sequence === requestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载更多覆盖文件失败。')
      }
    } finally {
      if (sequence === requestSequence) loading.value = false
    }
  }

  const hasMore = () => files.value.length < total.value

  return {
    loading,
    errorMessage,
    summary,
    files,
    total,
    activeKind,
    loadCoverage,
    loadMore,
    hasMore
  }
}
