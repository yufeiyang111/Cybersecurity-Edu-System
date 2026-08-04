import { defineStore } from 'pinia'
import {
  createAgentRunState,
  hydrateAgentRunState,
  reduceAgentEvent,
  applyEventBatch
} from '@/features/security/agent/eventReducer'

export const useAgentRunStore = defineStore('agentRun', {
  state: () => createAgentRunState(),

  getters: {
    statusLabel: (state) => state.run?.status || null,
    isTerminal: (state) => {
      const status = state.run?.status
      return ['completed', 'completed_with_warnings', 'partial', 'failed', 'canceled'].includes(status)
    },
    canPause: (state) => Boolean(state.run?.can_pause),
    canResume: (state) => Boolean(state.run?.can_resume),
    canCancel: (state) => Boolean(state.run?.can_cancel)
  },

  actions: {
    hydrate(snapshot) {
      Object.assign(this, hydrateAgentRunState(snapshot))
    },

    applyEvent(event) {
      const next = reduceAgentEvent(this.$state, event)
      Object.assign(this, next)
    },

    applyEvents(events) {
      const next = applyEventBatch(this.$state, events)
      Object.assign(this, next)
    },

    setConnectionState(connectionState) {
      this.connectionState = connectionState
    },

    markResynced() {
      this.gapDetected = false
      this.connectionState = 'connected'
    },

    reset() {
      Object.assign(this, createAgentRunState())
    }
  }
})
