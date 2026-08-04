import { securityApiErrorMessage } from '@/features/security/presentation'
import { agentStatusMeta, agentModeMeta } from '@/features/security/agent/statusMeta'

const STEP_CAP = 50
const TOOL_CALL_CAP = 50
const EVENT_TAIL_CAP = 100

export function createAgentRunState() {
  return {
    run: null,
    plan: null,
    steps: [],
    toolCalls: [],
    events: [],
    lastSequence: 0,
    stateVersion: 0,
    reasoningStream: '',
    reasoningLive: false,
    connectionState: 'connecting',
    gapDetected: false
  }
}

export function hydrateAgentRunState(snapshot) {
  return {
    run: snapshot.run || null,
    plan: snapshot.plan || null,
    steps: snapshot.steps || [],
    toolCalls: snapshot.tool_calls || [],
    events: snapshot.events || [],
    lastSequence: snapshot.last_sequence || 0,
    stateVersion: snapshot.state_version || 0,
    reasoningStream: '',
    reasoningLive: false,
    connectionState: 'connected',
    gapDetected: false
  }
}

function upsertById(list, item, cap) {
  const index = list.findIndex((entry) => entry.id === item.id)
  const next = index >= 0 ? [...list] : [...list, item]
  if (index >= 0) next[index] = item
  return next.slice(-cap)
}

function applyRunStateChange(state, event) {
  const payload = event.payload || {}
  const run = { ...(state.run || {}) }
  run.status = payload.status || run.status
  run.state_version = event.state_version ?? run.state_version
  run.last_event_sequence = event.sequence ?? run.last_event_sequence
  if (event.state_version != null) state.stateVersion = event.state_version
  state.run = run
}

export function reduceAgentEvent(state, event) {
  if (!event || event.sequence == null) return state
  if (event.sequence <= state.lastSequence) return state

  if (event.event_type === 'llm.reasoning_delta') {
    // 直通事件：只实时累积，不写入历史列表；刷新后由 snapshot 清空。
    return {
      ...state,
      reasoningStream: state.reasoningStream + (event.payload?.delta || ''),
      reasoningLive: true,
      lastSequence: event.sequence
    }
  }

  const next = { ...state }
  if (event.sequence > state.lastSequence + 1) next.gapDetected = true

  switch (event.event_type) {
    case 'run.state_changed':
      applyRunStateChange(next, event)
      break
    case 'run.paused':
    case 'run.resumed':
      applyRunStateChange(next, { ...event, payload: { ...(event.payload || {}), status: event.event_type === 'run.paused' ? 'paused' : 'executing_tools' } })
      break
    case 'run.completed':
      applyRunStateChange(next, { ...event, payload: { ...(event.payload || {}), status: 'completed' } })
      break
    case 'plan.created': {
      const payload = event.payload || {}
      next.plan = {
        ...(next.plan || {}),
        plan_id: payload.plan_id ?? next.plan?.plan_id,
        plan_version: payload.plan_version ?? next.plan?.plan_version,
        planner_source: payload.planner_source ?? next.plan?.planner_source
      }
      break
    }
    case 'step.started':
    case 'step.completed':
    case 'step.failed': {
      const payload = event.payload || {}
      const status = event.event_type === 'step.started' ? 'running' : event.event_type === 'step.completed' ? 'completed' : 'failed'
      next.steps = upsertById(next.steps, {
        id: payload.step_execution_id,
        node_key: payload.node_key,
        status,
        summary: payload.summary || '',
        error_code: payload.error_code || null,
        attempt_number: payload.attempt_number || 1,
        tool_name: payload.tool_name || null
      }, STEP_CAP)
      break
    }
    case 'tool.started':
    case 'tool.completed':
    case 'tool.failed': {
      const payload = event.payload || {}
      const status = event.event_type === 'tool.started' ? 'running' : event.event_type === 'tool.completed' ? 'succeeded' : 'failed'
      next.toolCalls = upsertById(next.toolCalls, {
        id: payload.tool_call_id,
        tool_name: payload.tool_name,
        node_key: payload.node_key,
        status,
        summary: payload.summary || '',
        error_code: payload.error_code || null,
        latency_ms: payload.latency_ms ?? null,
        artifact_refs: payload.artifact_refs || [],
        metrics: payload.metrics || null
      }, TOOL_CALL_CAP)
      if (event.event_type === 'tool.started' && next.run) {
        next.run = { ...next.run, tool_call_count: (next.run.tool_call_count || 0) + 1 }
      }
      break
    }
    case 'warning.raised': {
      const payload = event.payload || {}
      if (Array.isArray(payload.warning_codes)) {
        const run = { ...(next.run || {}) }
        run.warning_codes = [...new Set([...(run.warning_codes || []), ...payload.warning_codes])]
        next.run = run
      }
      break
    }
    default:
      break
  }

  const tail = [...next.events, {
    id: event.id ?? event.sequence,
    sequence: event.sequence,
    event_type: event.event_type,
    occurred_at: event.occurred_at || null,
    payload: event.payload || {}
  }]
  next.events = tail.slice(-EVENT_TAIL_CAP)
  next.lastSequence = event.sequence
  return next
}

export function applyEventBatch(state, events) {
  let next = state
  for (const event of events) next = reduceAgentEvent(next, event)
  return next
}

export { securityApiErrorMessage, agentStatusMeta, agentModeMeta }
