import { onBeforeUnmount, ref, watch } from 'vue'
import { agentAPI } from '@/api'
import { useAgentRunStore } from '@/stores/agentRunStore'
import { securityApiErrorMessage } from '@/features/security/presentation'
import { useAgentEventStream } from '@/composables/security/useAgentEventStream'

export function useAgentRun() {
  const store = useAgentRunStore()
  const { connect, disconnect } = useAgentEventStream()
  const loading = ref(false)
  const errorMessage = ref('')
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
    try {
      const snapshot = await agentAPI.getRun(runId)
      if (requestGeneration !== generation) return
      store.hydrate(snapshot)
      attachStream(runId, (frame) => {
        store.applyEvent({
          id: frame.id,
          sequence: frame.id,
          event_type: frame.event,
          payload: frame.data?.payload || {},
          state_version: frame.data?.state_version ?? null,
          occurred_at: frame.data?.occurred_at || null
        })
      })
    } catch (error) {
      if (requestGeneration === generation) {
        errorMessage.value = securityApiErrorMessage(error, '加载 Agent 任务失败。')
      }
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
      if (gap && activeRunId) {
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
    actionLoading,
    loadRun,
    createRun,
    pauseRun: (runId) => runAction('pause', runId),
    resumeRun: (runId) => runAction('resume', runId),
    cancelRun: (runId) => runAction('cancel', runId)
  }
}
