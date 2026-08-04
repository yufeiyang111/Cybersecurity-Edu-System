import { computed, ref } from 'vue'
import { securityAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

const terminalTaskStatuses = new Set(['completed', 'completed_with_warnings', 'failed', 'canceled'])
const completedTaskStatuses = new Set(['completed', 'completed_with_warnings'])

export function useProjectScanTasks(projectId, { onFindingsChanged = async () => {} } = {}) {
  const loading = ref(false)
  const findingsLoading = ref(false)
  const findingsLoadingMore = ref(false)
  const errorMessage = ref('')
  const tasks = ref([])
  const findings = ref([])
  const findingsStats = ref(null)
  const findingsSort = ref('default')
  const selectedTaskId = ref(null)
  const taskActionLoading = ref({})
  let pollTimer = null
  let findingsRequestSequence = 0

  const FINDINGS_PAGE_SIZE = 50

  const completedTaskCount = computed(() => tasks.value.filter((task) => completedTaskStatuses.has(task.status)).length)
  const highRiskCount = computed(() => {
    if (findingsStats.value?.high_count !== undefined) return findingsStats.value.high_count
    return findings.value.filter((finding) => ['critical', 'high'].includes(finding.severity)).length
  })
  const avgRiskScore = computed(() => {
    if (findingsStats.value?.avg_score !== undefined) return findingsStats.value.avg_score
    const scores = findings.value
      .map((finding) => finding.risk?.score)
      .filter((score) => typeof score === 'number')
    if (!scores.length) return null
    return scores.reduce((sum, score) => sum + score, 0) / scores.length
  })
  const findingsTotal = computed(() => findingsStats.value?.total ?? findings.value.length)
  const findingsHasMore = computed(() => findings.value.length < findingsTotal.value)
  const hasRunningTasks = computed(() => tasks.value.some((task) => !terminalTaskStatuses.has(task.status)))
  const selectedTask = computed(() => tasks.value.find((task) => task.id === selectedTaskId.value) || null)

  const resolveProjectId = () => typeof projectId === 'function' ? projectId() : projectId

  const syncPolling = () => {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = hasRunningTasks.value ? setInterval(load, 4000) : null
  }

  const stopPolling = () => {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = null
  }

  const loadFindings = async (taskId, params = {}) => {
    selectedTaskId.value = taskId
    findings.value = []
    findingsStats.value = null
    findingsLoading.value = true
    const requestSequence = ++findingsRequestSequence
    try {
      const response = await securityAPI.getFindings(taskId, { limit: FINDINGS_PAGE_SIZE, ...params })
      if (requestSequence !== findingsRequestSequence) return
      findings.value = response.items || []
      findingsStats.value = response.stats || null
      await onFindingsChanged(findings.value)
    } catch (error) {
      if (requestSequence === findingsRequestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载风险发现项失败。')
      }
    } finally {
      if (requestSequence === findingsRequestSequence) findingsLoading.value = false
    }
  }

  const loadMoreFindings = async () => {
    if (!selectedTaskId.value || findingsLoadingMore.value) return
    const requestSequence = ++findingsRequestSequence
    findingsLoadingMore.value = true
    try {
      const response = await securityAPI.getFindings(selectedTaskId.value, {
        limit: FINDINGS_PAGE_SIZE,
        offset: findings.value.length,
        sort: findingsSort.value === 'risk' ? 'risk' : undefined
      })
      if (requestSequence !== findingsRequestSequence) return
      const incoming = response.items || []
      const knownIds = new Set(findings.value.map((finding) => finding.id))
      findings.value = [...findings.value, ...incoming.filter((finding) => !knownIds.has(finding.id))]
      findingsStats.value = response.stats || findingsStats.value
    } catch (error) {
      if (requestSequence === findingsRequestSequence) {
        errorMessage.value = securityApiErrorMessage(error, '加载更多风险发现项失败。')
      }
    } finally {
      if (requestSequence === findingsRequestSequence) findingsLoadingMore.value = false
    }
  }

  const setFindingsSort = async (sort) => {
    findingsSort.value = sort
    if (!selectedTaskId.value) return
    await loadFindings(selectedTaskId.value, sort === 'risk' ? { sort: 'risk' } : undefined)
  }

  async function load() {
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await securityAPI.getTasks(resolveProjectId())
      tasks.value = response.items || []
      const activeTask = tasks.value.find((task) => task.id === selectedTaskId.value) || tasks.value[0]
      if (activeTask) {
        await loadFindings(activeTask.id, findingsSort.value === 'risk' ? { sort: 'risk' } : undefined)
      } else {
        selectedTaskId.value = null
        findings.value = []
        await onFindingsChanged([])
      }
    } catch (error) {
      errorMessage.value = securityApiErrorMessage(error, '加载扫描任务失败。')
    } finally {
      loading.value = false
      syncPolling()
    }
  }

  async function runTaskAction(taskId, action) {
    const key = `${action}:${taskId}`
    if (taskActionLoading.value[key]) return false
    taskActionLoading.value = { ...taskActionLoading.value, [key]: true }
    try {
      if (action === 'cancel') {
        await securityAPI.cancelTask(taskId)
      } else {
        await securityAPI.retryTask(taskId)
      }
      await load()
      return true
    } catch (error) {
      errorMessage.value = securityApiErrorMessage(
        error,
        action === 'cancel' ? '取消扫描任务失败。' : '重新派发扫描任务失败。'
      )
      return false
    } finally {
      const next = { ...taskActionLoading.value }
      delete next[key]
      taskActionLoading.value = next
    }
  }

  const rescanLoading = ref(false)
  async function rescan() {
    if (rescanLoading.value) return false
    rescanLoading.value = true
    try {
      await securityAPI.rescanProject(resolveProjectId())
      await load()
      return true
    } catch (error) {
      errorMessage.value = securityApiErrorMessage(error, '重新扫描失败。')
      return false
    } finally {
      rescanLoading.value = false
    }
  }

  return {
    loading,
    findingsLoading,
    findingsLoadingMore,
    errorMessage,
    tasks,
    findings,
    findingsStats,
    findingsTotal,
    findingsHasMore,
    selectedTaskId,
    selectedTask,
    taskActionLoading,
    completedTaskCount,
    highRiskCount,
    avgRiskScore,
    hasRunningTasks,
    findingsSort,
    load,
    loadFindings,
    loadMoreFindings,
    setFindingsSort,
    cancelTask: (taskId) => runTaskAction(taskId, 'cancel'),
    retryTask: (taskId) => runTaskAction(taskId, 'retry'),
    rescan,
    rescanLoading,
    stopPolling
  }
}