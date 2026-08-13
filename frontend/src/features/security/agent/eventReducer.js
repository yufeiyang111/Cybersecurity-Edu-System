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
    messages: [],
    scanSummary: null,
    decisions: [],
    lastSequence: 0,
    stateVersion: 0,
    reasoningStream: '',
    reasoningLive: false,
    reasoningSensitiveLevel: 'internal',
    llmAnalysis: null,
    lastProvider: null,
    connectionState: 'connecting',
    gapDetected: false
  }
}

export function hydrateAgentRunState(snapshot) {
  const agentAnalysis = (snapshot.messages || []).find(
    (message) => message.role === 'agent' && message.message_type === 'llm_analysis'
  )
  const agentReasoning = (snapshot.messages || []).find(
    (message) => message.role === 'agent' && message.message_type === 'llm_reasoning'
  )
  const startedEvent = [...(snapshot.events || [])]
    .reverse()
    .find((event) => event.event_type === 'llm.started')
  return {
    run: snapshot.run || null,
    plan: snapshot.plan || null,
    steps: snapshot.steps || [],
    toolCalls: snapshot.tool_calls || [],
    events: snapshot.events || [],
    messages: snapshot.messages || [],
    scanSummary: snapshot.scan_summary || null,
    decisions: snapshot.decisions || [],
    lastSequence: snapshot.last_sequence || 0,
    stateVersion: snapshot.state_version || 0,
    reasoningStream: agentReasoning?.content || '',
    reasoningLive: false,
    reasoningSensitiveLevel: 'internal',
    llmAnalysis: agentAnalysis?.content || null,
    lastProvider: startedEvent?.payload
      ? { provider: startedEvent.payload.provider, model: startedEvent.payload.model }
      : null,
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

  if (event.event_type === 'item.reasoning_summary.started') {
    // v2 推理摘要开始：重置累积（每次模型轮独立）。
    return {
      ...state,
      reasoningStream: '',
      reasoningLive: true,
      reasoningSensitiveLevel: event.payload?.sensitive_level || 'internal',
      lastSequence: event.sequence
    }
  }

  if (event.event_type === 'item.reasoning_summary.delta') {
    // v2 推理摘要增量：累积受限摘要（已脱敏限长）。
    return {
      ...state,
      reasoningStream: state.reasoningStream + (event.payload?.delta || ''),
      reasoningLive: true,
      reasoningSensitiveLevel: event.payload?.sensitive_level || state.reasoningSensitiveLevel,
      lastSequence: event.sequence
    }
  }

  if (event.event_type === 'item.reasoning_summary.completed' ||
      event.event_type === 'item.reasoning_summary.failed') {
    return {
      ...state,
      reasoningLive: false,
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
    case 'plan.replanned': {
      const payload = event.payload || {}
      next.plan = {
        ...(next.plan || {}),
        plan_id: payload.plan_id ?? next.plan?.plan_id,
        plan_version: payload.plan_version ?? next.plan?.plan_version,
        supersedes_version: payload.supersedes_version ?? null,
        reason_code: payload.reason_code || null,
        new_nodes: payload.new_nodes || []
      }
      if (next.run) {
        next.run = { ...next.run, plan_version: payload.plan_version ?? next.run.plan_version, replan_count: (next.run.replan_count || 0) + 1 }
      }
      break
    }
    case 'decision.recorded': {
      const payload = event.payload || {}
      next.decisions = [
        ...(next.decisions || []),
        {
          id: payload.decision_id,
          plan_version: payload.plan_version,
          supersedes_version: payload.supersedes_version ?? null,
          reason_code: payload.reason_code,
          decision_type: payload.decision_type,
          detail: payload.detail || {},
          occurred_at: event.occurred_at || null
        }
      ].slice(-20)
      break
    }
    case 'strategy.switched': {
      const payload = event.payload || {}
      next.decisions = [
        ...(next.decisions || []),
        {
          id: `strategy-${event.sequence}`,
          plan_version: payload.to_plan_version ?? null,
          supersedes_version: payload.from_plan_version ?? null,
          reason_code: payload.reason_code,
          decision_type: 'strategy_switch',
          detail: { decision_summary: payload.decision_summary || '' },
          occurred_at: event.occurred_at || null
        }
      ].slice(-20)
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
        input_summary: payload.input_summary || '',
        summary: payload.summary || '',
        output_summary: payload.output_summary || '',
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
    case 'llm.completed': {
      const payload = event.payload || {}
      if (payload.analysis) next.llmAnalysis = payload.analysis
      if (payload.reasoning) next.reasoningStream = payload.reasoning
      next.reasoningLive = false
      break
    }
    case 'llm.failed': {
      next.reasoningLive = false
      break
    }
    case 'llm.started': {
      const payload = event.payload || {}
      next.lastProvider = payload.provider ? { provider: payload.provider, model: payload.model } : null
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
