import { agentAPI } from '@/api'

const RECONNECT_BACKOFF_MS = [1000, 2000, 4000, 8000, 15000]
const RECONNECT_JITTER_MS = 300
const HEARTBEAT_TIMEOUT_MS = 45000

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function useAgentEventStream() {
  let generation = 0
  let activeController = null
  let heartbeatTimer = null

  function clearHeartbeat() {
    if (heartbeatTimer) clearTimeout(heartbeatTimer)
    heartbeatTimer = null
  }

  function armHeartbeat(onStateChange) {
    clearHeartbeat()
    heartbeatTimer = setTimeout(() => {
      // 45 秒无任何数据视为连接异常，强制重连。
      activeController?.abort()
      onStateChange?.('reconnecting')
    }, HEARTBEAT_TIMEOUT_MS)
  }

  async function connect({ runId, getLastEventId, onEvent, onStateChange }) {
    const generationId = ++generation
    let attempt = 0
    while (generationId === generation) {
      const controller = new AbortController()
      activeController = controller
      onStateChange?.('connecting')
      try {
        const result = await agentAPI.streamAgentEvents(runId, {
          lastEventId: getLastEventId(),
          signal: controller.signal,
          onEvent: (frame) => {
            attempt = 0
            armHeartbeat(onStateChange)
            onEvent?.(frame)
          }
        })
        clearHeartbeat()
        if (result === 'aborted') return
        if (generationId !== generation) return
        onStateChange?.('closed')
        return
      } catch (error) {
        clearHeartbeat()
        if (error?.name === 'AbortError' || generationId !== generation) return
      }
      if (generationId !== generation) return
      onStateChange?.('reconnecting')
      const delay = RECONNECT_BACKOFF_MS[Math.min(attempt, RECONNECT_BACKOFF_MS.length - 1)]
      attempt += 1
      await sleep(delay + Math.random() * RECONNECT_JITTER_MS)
    }
  }

  function disconnect() {
    generation += 1
    clearHeartbeat()
    activeController?.abort()
    activeController = null
  }

  return { connect, disconnect }
}
