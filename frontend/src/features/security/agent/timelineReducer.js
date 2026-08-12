// T11 事件源时间线 Reducer（纯函数，无 Vue/Pinia/API alias 依赖，Node 可直接测试）。
//
// 事实源：itemsById + itemOrder + lastSequence + snapshotWatermark。
// itemOrder 只由 Item 首个事件的 sequence 决定；同一 Item 的 delta 不改变位置；
// 重复事件/重复 delta 幂等；任何事件（含 legacy reasoning）先做 Gap 检测。

export const CONNECTION_CONNECTING = 'connecting'
export const CONNECTION_CONNECTED = 'connected'
export const CONNECTION_RECONNECTING = 'reconnecting'
export const CONNECTION_RESYNCING = 'resyncing'
export const CONNECTION_ERROR = 'error'

export function createTimelineState() {
  return {
    itemsById: {},
    itemOrder: [],
    lastSequence: 0,
    snapshotWatermark: 0,
    stateVersion: 0,
    connectionState: CONNECTION_CONNECTING,
    gapDetected: false,
    terminal: false,
    approvals: [],
    costs: null
  }
}

// ---------------------------------------------------------------- hydration

export function hydrateTimelineState(snapshot) {
  const state = createTimelineState()
  const items = Array.isArray(snapshot.items) ? snapshot.items : []
  state.snapshotWatermark = snapshot.snapshot_watermark ?? snapshot.last_sequence ?? 0
  state.lastSequence = snapshot.last_sequence ?? state.snapshotWatermark
  state.stateVersion = snapshot.state_version ?? 0
  state.connectionState = CONNECTION_CONNECTED
  const seen = new Set()
  for (const raw of items) {
    if (!raw || !raw.public_id || seen.has(raw.public_id)) continue
    seen.add(raw.public_id)
    const item = normalizeItem(raw, state.lastSequence)
    state.itemsById[item.publicId] = item
    state.itemOrder.push(item.publicId)
  }
  return state
}

function normalizeItem(raw, fallbackSequence) {
  return {
    publicId: raw.public_id,
    itemType: raw.item_type || 'unknown',
    status: raw.status || 'started',
    content: raw.content || '',
    summary: raw.summary || {},
    parentId: raw.parent_item_id || null,
    sensitiveLevel: raw.sensitive_level || 'internal',
    errorCode: raw.summary?.error_code || null,
    sequence: fallbackSequence
  }
}

// ---------------------------------------------------------------- events

export function applyTimelineEvent(state, event) {
  if (!event) return state
  const sequence = event.sequence != null ? event.sequence : event.id
  if (sequence == null) {
    // heartbeat 等无 sequence 帧：刷新连接健康但不进时间线
    return state
  }
  const numeric = Number(sequence)
  if (!Number.isInteger(numeric) || numeric < 0) return state
  if (numeric <= state.lastSequence) return state

  if (numeric > state.lastSequence + 1) {
    return {
      ...state,
      gapDetected: true,
      connectionState: CONNECTION_RESYNCING
    }
  }

  const eventType = event.event_type || event.event
  if (eventType === 'run.completed' || eventType === 'run.failed' || eventType === 'run.canceled') {
    return {
      ...finishItemByEvent(state, event, numeric),
      lastSequence: numeric,
      terminal: true
    }
  }

  let next = state
  if (eventType && eventType.startsWith('item.')) {
    next = applyItemEvent(state, event, numeric)
  }

  return {
    ...next,
    lastSequence: numeric,
    gapDetected: false
  }
}

function applyItemEvent(state, event, sequence) {
  const eventType = event.event_type || event.event
  const payload = event.payload || {}
  const publicId = event.item_id || payload.item_public_id || payload.item_id
  if (!publicId) return state

  if (eventType.endsWith('.started') || eventType.endsWith('.created')) {
    return upsertItem(state, {
      publicId,
      itemType: itemTypeOf(eventType),
      status: 'started',
      content: payload.delta || '',
      summary: payload,
      parentId: payload.parent_item_id || null,
      sensitiveLevel: payload.sensitive_level || 'internal',
      errorCode: null,
      sequence
    })
  }

  if (eventType.endsWith('.delta')) {
    const existing = state.itemsById[publicId]
    if (!existing) {
      return upsertItem(state, {
        publicId,
        itemType: itemTypeOf(eventType),
        status: 'streaming',
        content: payload.delta || '',
        summary: payload,
        parentId: null,
        sensitiveLevel: payload.sensitive_level || 'internal',
        errorCode: null,
        sequence
      })
    }
    return {
      ...state,
      itemsById: {
        ...state.itemsById,
        [publicId]: {
          ...existing,
          status: 'streaming',
          content: existing.content + (payload.delta || ''),
          summary: { ...existing.summary, ...payload }
        }
      }
    }
  }

  if (eventType.endsWith('.completed') || eventType.endsWith('.failed')) {
    const existing = state.itemsById[publicId]
    const frozen = {
      ...(existing || {
        publicId,
        itemType: itemTypeOf(eventType),
        status: 'started',
        content: '',
        summary: {},
        parentId: null,
        sensitiveLevel: 'internal',
        errorCode: null,
        sequence
      }),
      status: eventType.endsWith('.failed') ? 'failed' : 'completed',
      content: payload.content ?? payload.analysis ?? existing?.content ?? '',
      errorCode: payload.error_code || null
    }
    return {
      ...state,
      itemsById: { ...state.itemsById, [publicId]: frozen }
    }
  }

  return state
}

function upsertItem(state, item) {
  const existing = state.itemsById[item.publicId]
  if (existing) {
    return {
      ...state,
      itemsById: { ...state.itemsById, [item.publicId]: { ...existing, ...item } }
    }
  }
  return {
    ...state,
    itemsById: { ...state.itemsById, [item.publicId]: item },
    itemOrder: [...state.itemOrder, item.publicId]
  }
}

function finishItemByEvent(state, event, sequence) {
  const eventType = event.event_type || event.event
  const itemTypes = ['assistant_message', 'tool_call', 'reasoning_summary', 'plan', 'decision_summary']
  const next = { ...state }
  for (const type of itemTypes) {
    const candidates = Object.values(next.itemsById).filter((item) => item.itemType === type)
    for (const item of candidates) {
      if (item.status === 'completed' || item.status === 'failed') continue
      next.itemsById = {
        ...next.itemsById,
        [item.publicId]: { ...item, status: 'completed' }
      }
    }
  }
  return next
}

function itemTypeOf(eventType) {
  const body = eventType.replace(/^item\./, '')
  const parts = body.split('.')
  return parts[0] || 'unknown'
}

// ---------------------------------------------------------------- batch

export function applyTimelineBatch(state, events) {
  const ordered = events
    .filter((event) => event && (event.sequence != null || event.id != null))
    .slice()
    .sort((a, b) => {
      const seqA = Number(a.sequence != null ? a.sequence : a.id)
      const seqB = Number(b.sequence != null ? b.sequence : b.id)
      return seqA - seqB
    })
  let next = state
  for (const event of ordered) {
    next = applyTimelineEvent(next, event)
  }
  return next
}

export function timelineItems(state) {
  return state.itemOrder
    .map((publicId) => state.itemsById[publicId])
    .filter(Boolean)
}
