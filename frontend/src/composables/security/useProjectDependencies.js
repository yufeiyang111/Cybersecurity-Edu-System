import { computed, ref } from 'vue'
import { securityAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

const scaFindingCategory = 'sca'

function normalizedScaWarnings(taskSummary) {
  const warnings = Array.isArray(taskSummary?.warnings) ? taskSummary.warnings : []
  return warnings
    .filter((warning) => warning && typeof warning === 'object' && warning.scanner === scaFindingCategory)
    .map((warning) => typeof warning.error === 'string' ? warning.error : '')
    .filter(Boolean)
}

function deriveScaStatus(taskSummary, findings) {
  const summary = taskSummary || {}
  const warnings = normalizedScaWarnings(summary)
  const enabled = summary.sca_enabled
  const reportedFindingCount = Number(summary.sca_findings_count)

  if (enabled === false) {
    return {
      kind: 'not-enabled',
      title: 'SCA 未启用',
      description: '此扫描任务未启用软件成分分析，无法据此判断依赖风险。',
      warnings,
      findingCount: 0
    }
  }

  if (warnings.length) {
    return {
      kind: 'warning',
      title: 'SCA 结果存在告警',
      description: '扫描任务返回了依赖分析告警；请结合告警和已持久化 Finding 判断结果完整性。',
      warnings,
      findingCount: findings.length
    }
  }

  if (findings.length || reportedFindingCount > 0) {
    return {
      kind: 'risk',
      title: '发现依赖风险',
      description: '以下风险来自当前扫描任务持久化的 SCA Finding。',
      warnings,
      findingCount: findings.length
    }
  }

  if (enabled === true) {
    return {
      kind: 'clear',
      title: '未发现已持久化的 SCA 风险',
      description: '当前任务已启用 SCA，且未返回 SCA Finding；这不是对全部依赖的长期安全保证。',
      warnings,
      findingCount: 0
    }
  }

  return {
    kind: 'unknown',
    title: '等待 SCA 扫描状态',
    description: '当前任务尚未提供可判断的 SCA 状态，请等待扫描完成或刷新任务。',
    warnings,
    findingCount: findings.length
  }
}

export function useProjectDependencies(projectId) {
  const dependencies = ref([])
  const dependenciesLoading = ref(false)
  const dependenciesLoadingMore = ref(false)
  const dependenciesError = ref('')
  const dependenciesTotal = ref(0)
  const loadedSnapshotId = ref(null)
  const scaFindings = ref([])
  const scaStatus = ref(deriveScaStatus(null, []))
  let requestSequence = 0

  const DEPENDENCIES_PAGE_SIZE = 50

  const dependencyCount = computed(() => dependencies.value.length)
  const dependenciesHasMore = computed(() => dependencies.value.length < dependenciesTotal.value)
  const resolveProjectId = () => typeof projectId === 'function' ? projectId() : projectId

  const clearDependencies = () => {
    requestSequence += 1
    dependencies.value = []
    dependenciesError.value = ''
    dependenciesTotal.value = 0
    loadedSnapshotId.value = null
    scaFindings.value = []
    scaStatus.value = deriveScaStatus(null, [])
    dependenciesLoading.value = false
    dependenciesLoadingMore.value = false
  }

  const loadDependencies = async (snapshotId, findings, taskSummary) => {
    const requestId = ++requestSequence
    const currentScaFindings = (findings || []).filter((finding) => finding.category === scaFindingCategory)
    scaFindings.value = currentScaFindings
    scaStatus.value = deriveScaStatus(taskSummary, currentScaFindings)

    if (!snapshotId) {
      dependencies.value = []
      dependenciesError.value = ''
      dependenciesTotal.value = 0
      loadedSnapshotId.value = null
      dependenciesLoading.value = false
      dependenciesLoadingMore.value = false
      return
    }

    if (snapshotId === loadedSnapshotId.value && !dependenciesError.value) return

    dependencies.value = []
    dependenciesError.value = ''
    dependenciesTotal.value = 0
    dependenciesLoading.value = true
    try {
      const response = await securityAPI.getDependencies(resolveProjectId(), {
        snapshot_id: snapshotId,
        limit: DEPENDENCIES_PAGE_SIZE
      })
      if (requestId !== requestSequence) return
      dependencies.value = response.items || []
      dependenciesTotal.value = response.pagination?.total ?? dependencies.value.length
      loadedSnapshotId.value = snapshotId
    } catch (error) {
      if (requestId === requestSequence) {
        dependenciesError.value = securityApiErrorMessage(error, '依赖库存加载失败。')
      }
    } finally {
      if (requestId === requestSequence) {
        dependenciesLoading.value = false
      }
    }
  }

  const loadMoreDependencies = async () => {
    const snapshotId = loadedSnapshotId.value
    if (!snapshotId || dependenciesLoadingMore.value || dependenciesLoading.value) return
    const requestId = ++requestSequence
    dependenciesLoadingMore.value = true
    try {
      const response = await securityAPI.getDependencies(resolveProjectId(), {
        snapshot_id: snapshotId,
        limit: DEPENDENCIES_PAGE_SIZE,
        offset: dependencies.value.length
      })
      if (requestId !== requestSequence) return
      const incoming = response.items || []
      const knownKeys = new Set(dependencies.value.map((item) => item.id))
      dependencies.value = [...dependencies.value, ...incoming.filter((item) => !knownKeys.has(item.id))]
      dependenciesTotal.value = response.pagination?.total ?? dependencies.value.length
    } catch (error) {
      if (requestId === requestSequence) {
        dependenciesError.value = securityApiErrorMessage(error, '加载更多依赖失败。')
      }
    } finally {
      if (requestId === requestSequence) {
        dependenciesLoadingMore.value = false
      }
    }
  }

  return {
    dependencies,
    dependenciesLoading,
    dependenciesLoadingMore,
    dependenciesError,
    dependenciesTotal,
    dependenciesHasMore,
    scaFindings,
    scaStatus,
    dependencyCount,
    loadDependencies,
    loadMoreDependencies,
    clearDependencies
  }
}
