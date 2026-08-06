import { ref } from 'vue'
import { securityAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

export function useProjectSnapshots(projectId) {
  const loading = ref(false)
  const errorMessage = ref('')
  const snapshots = ref([])
  const actionLoading = ref({})
  let requestSequence = 0

  const resolveProjectId = () => typeof projectId === 'function' ? projectId() : projectId

  const load = async () => {
    const current = ++requestSequence
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await securityAPI.listSnapshots(resolveProjectId(), { limit: 100 })
      if (current !== requestSequence) return
      snapshots.value = response.items || []
    } catch (error) {
      if (current === requestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载项目快照失败。')
      }
    } finally {
      if (current === requestSequence) loading.value = false
    }
  }

  const remove = async (snapshot) => {
    if (actionLoading.value[snapshot.id]) return false
    actionLoading.value = { ...actionLoading.value, [snapshot.id]: true }
    try {
      await securityAPI.deleteSnapshot(resolveProjectId(), snapshot.id)
      snapshots.value = snapshots.value.filter((item) => item.id !== snapshot.id)
      return true
    } catch (error) {
      errorMessage.value = securityApiErrorMessage(error, '删除项目快照失败。')
      return false
    } finally {
      const next = { ...actionLoading.value }
      delete next[snapshot.id]
      actionLoading.value = next
    }
  }

  return {
    loading,
    errorMessage,
    snapshots,
    actionLoading,
    load,
    remove
  }
}
