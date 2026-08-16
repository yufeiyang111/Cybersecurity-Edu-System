import { defineStore } from 'pinia'
import { isTerminalAgentRunStatus } from '@/features/security/agent/statusMeta'
import {
  createAgentRunState,
  hydrateAgentRunState,
  reduceAgentEvent,
  applyEventBatch
} from '@/features/security/agent/eventReducer'
import {
  applyTimelineBatch,
  applyTimelineEvent,
  createTimelineState,
  hydrateTimelineState
} from '@/features/security/agent/timelineReducer'

export const useAgentRunStore = defineStore('agentRun', {
  state: () => ({
    ...createAgentRunState(),
    timeline: createTimelineState()
  }),

  getters: {
    statusLabel: (state) => state.run?.status || null,
    isTerminal: (state) => {
      const status = state.run?.status
      return isTerminalAgentRunStatus(status)
    },
    canPause: (state) => Boolean(state.run?.can_pause),
    canResume: (state) => Boolean(state.run?.can_resume),
    canCancel: (state) => Boolean(state.run?.can_cancel),
    timelineItems: (state) => {
      return state.timeline.itemOrder
        .map((publicId) => state.timeline.itemsById[publicId])
        .filter(Boolean)
    }
  },

  actions: {
    hydrate(snapshot) {
      Object.assign(this, hydrateAgentRunState(snapshot))
      this.timeline = hydrateTimelineState(snapshot)
    },

    applyEvent(event) {
      const next = reduceAgentEvent(this.$state, event)
      Object.assign(this, next)
      if (event && event.sequence != null) {
        this.timeline = applyTimelineEvent(this.timeline, event)
      }
    },

    applyEvents(events) {
      const next = applyEventBatch(this.$state, events)
      Object.assign(this, next)
      this.timeline = applyTimelineBatch(this.timeline, events)
    },

    setConnectionState(connectionState) {
      this.connectionState = connectionState
      if (this.timeline) {
        this.timeline = { ...this.timeline, connectionState }
      }
    },

    markResynced() {
      this.gapDetected = false
      this.connectionState = 'connected'
      if (this.timeline) {
        this.timeline = {
          ...this.timeline,
          gapDetected: false,
          connectionState: 'connected'
        }
      }
    },

    reset() {
      Object.assign(this, createAgentRunState())
      this.timeline = createTimelineState()
    }
  }
})
