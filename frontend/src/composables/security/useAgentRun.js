import { onBeforeUnmount, ref, watch } from 'vue'
import { agentAPI } from '@/api'
import { isAgentRunAccessDenied } from '@/features/security/agent/runAccessGuard'
import { useAgentRunStore } from '@/stores/agentRunStore'
import { securityApiErrorMessage } from '@/features/security/presentation'
import { useAgentEventStream } from '@/composables/security/useAgentEventStream'

export function useAgentRun() {
  const store = useAgentRunStore()
  const { connect, disconnect } = useAgentEventStream()
  const loading = ref(false)
  const errorMessage = ref('')
  const accessDenied = ref(false)
  const actionLoading = ref({ pause: false, resume: false, cancel: false })
  let activeRunId = null
  let generation = 0

  function attachStream(runId, onEvent) {
    connect({
      runId,
      getLastEventId: () => store.lastSequence,
      onEvent,
      onStateChange: (connectionState) => store.setConnectionState(connectionState)
    })
  }

  async function loadRun(runId) {
    const requestGeneration = ++generation
    activeRunId = runId
    disconnect()
    loading.value = true
    errorMessage.value = ''
    accessDenied.value = false
    try {
      const snapshot = await agentAPI.getRun(runId)
      if (requestGeneration !== generation) return false
      store.hydrate(snapshot)
      attachStream(runId, (frame) => {
        const isProviderRawReasoning = frame.event === 'provider_reasoning_raw_delta'
        store.applyEvent({
          id: frame.id,
          sequence: frame.id,
          event_type: frame.event,
          payload: isProviderRawReasoning ? (frame.data || {}) : (frame.data?.payload || {}),
          transient: isProviderRawReasoning && frame.data?.transient === true,
          state_version: frame.data?.state_version ?? null,
          occurred_at: frame.data?.occurred_at || null,
          iteration: frame.data?.iteration ?? 0
        })
      })
      return true
    } catch (error) {
      if (requestGeneration !== generation) return false
      if (isAgentRunAccessDenied(error)) {
        // 403 是稳定终态：断开流并清除旧任务，避免伪造“连接中”状态。
        activeRunId = null
        disconnect()
        store.reset()
        accessDenied.value = true
        return false
      }
      errorMessage.value = securityApiErrorMessage(error, '加载 Agent 任务失败。')
      return false
    } finally {
      if (requestGeneration === generation) loading.value = false
    }
  }

  async function createRun(projectId, goal, mode) {
    errorMessage.value = ''
    try {
      const response = await agentAPI.createRun(projectId, { goal_text: goal, mode })
      return response.run
    } catch (error) {
      errorMessage.value = securityApiErrorMessage(error, '创建 Agent 任务失败。')
      return null
    }
  }

  async function runAction(action, runId) {
    if (actionLoading.value[action]) return
    actionLoading.value[action] = true
    errorMessage.value = ''
    try {
      await agentAPI[`${action}Run`](runId)
      await loadRun(runId)
      return true
    } catch (error) {
      errorMessage.value = securityApiErrorMessage(error, '操作 Agent 任务失败。')
      return false
    } finally {
      actionLoading.value[action] = false
    }
  }

  // 事件序列出现断层时以快照为准重新同步（SSE 断线/重连的权威状态源）。
  watch(
    () => store.gapDetected,
    (gap) => {
      if (gap && activeRunId && !accessDenied.value) {
        store.setConnectionState('resyncing')
        loadRun(activeRunId).then(() => store.markResynced())
      }
    }
  )

  onBeforeUnmount(() => {
    generation += 1
    disconnect()
  })

  return {
    store,
    loading,
    errorMessage,
    accessDenied,
    actionLoading,
    loadRun,
    createRun,
    pauseRun: (runId) => runAction('pause', runId),
    resumeRun: (runId) => runAction('resume', runId),
    cancelRun: (runId) => runAction('cancel', runId)
  }
}
