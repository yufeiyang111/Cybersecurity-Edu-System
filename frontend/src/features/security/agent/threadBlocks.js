// AgentThread 块合成纯函数（无 Vue 依赖，Node 可直接测试）。
//
// 事实源：thinking / tool / assistant 全部按事件 sequence 严格交错排序，
// 与 Codex 时间线一致——思考在前、工具紧随、再思考、再工具……

export function buildThreadBlocks({
  events = [],
  toolCalls = [],
  reasoningStream = '',
  reasoningLive = false,
  reasoningSensitiveLevel = 'internal',
  llmAnalysis = '',
  run = null,
  running = false,
  fallbackText = '',
  fallbackDetail = []
}) {
  const items = []
  const toolById = {}
  for (const tool of toolCalls) {
    toolById[String(tool.id)] = tool
  }

  const upsertThinking = (itemId, delta, live, sensitiveLevel, seq) => {
    const existing = items.find(
      (item) => item.kind === 'thinking' && item.key === `reasoning-${itemId}`
    )
    if (existing) {
      existing.text += delta || ''
      existing.live = live
      if (sensitiveLevel) existing.sensitiveLevel = sensitiveLevel
    } else {
      items.push({
        kind: 'thinking',
        key: `reasoning-${itemId}`,
        title: '推理摘要',
        text: delta || '',
        live,
        sensitiveLevel: sensitiveLevel || 'internal',
        seq
      })
    }
  }

  for (const event of events) {
    const type = event.event_type || ''
    const payload = event.payload || {}
    const seq = Number(event.sequence) || 0
    const itemId = event.item_id || payload.item_id || payload.item_public_id || String(seq)

    if (type === 'item.reasoning_summary.started') {
      // started 不置 live：等待 delta 到来才视为"思考中"。
      // 若 started 后无任何 delta（内容被脱敏丢弃），块保持空且非 live，
      // 组件层会过滤掉，避免显示空"THINKING 思考中…"。
      upsertThinking(itemId, '', false, payload.sensitive_level || 'internal', seq)
    } else if (type === 'item.reasoning_summary.delta') {
      upsertThinking(itemId, payload.delta || '', true, payload.sensitive_level, seq)
    } else if (type === 'tool.started') {
      const callId = String(payload.tool_call_id ?? '')
      if (callId) {
        const tool = toolById[callId]
        items.push({
          kind: 'tool',
          key: `tool-${callId}`,
          tool: tool ? { ...tool, id: callId } : { id: callId, tool_name: payload.tool_name },
          seq
        })
      }
    } else if (type === 'item.assistant_message.completed') {
      const content = payload.content ?? payload.analysis ?? ''
      items.push({
        kind: 'assistant',
        key: `assistant-${seq}`,
        text: content,
        status: run?.status || 'completed',
        live: false,
        time: event.occurred_at || '',
        seq
      })
    }
  }

  const coveredToolIds = new Set(
    items.filter((item) => item.kind === 'tool').map((item) => item.tool.id)
  )
  for (const tool of toolCalls) {
    const id = String(tool.id)
    if (!coveredToolIds.has(id)) {
      items.push({
        kind: 'tool',
        key: `tool-snapshot-${id}`,
        tool: { ...tool, id },
        seq: Number.MAX_SAFE_INTEGER
      })
    }
  }

  if (reasoningLive || reasoningStream) {
    const liveIdx = items.findIndex((item) => item.kind === 'thinking')
    if (liveIdx >= 0) {
      items[liveIdx].text = reasoningStream || items[liveIdx].text
      items[liveIdx].live = reasoningLive
      items[liveIdx].sensitiveLevel = reasoningSensitiveLevel
    } else if (reasoningStream) {
      items.push({
        kind: 'thinking',
        key: 'reasoning-live',
        title: '推理摘要',
        text: reasoningStream,
        live: reasoningLive,
        sensitiveLevel: reasoningSensitiveLevel,
        seq: Number.MAX_SAFE_INTEGER - 1
      })
    }
  }

  if (llmAnalysis) {
    const hasAssistant = items.some((item) => item.kind === 'assistant')
    if (!hasAssistant) {
      items.push({
        kind: 'assistant',
        key: 'assistant-final',
        text: llmAnalysis,
        status: run?.status || 'completed',
        live: false,
        time: run?.finished_at || '',
        seq: Number.MAX_SAFE_INTEGER
      })
    }
  } else if (fallbackText && !running) {
    items.push({
      kind: 'assistant',
      key: 'assistant-fallback',
      text: fallbackText,
      status: run?.status || 'completed',
      live: false,
      time: run?.finished_at || '',
      seq: Number.MAX_SAFE_INTEGER
    })
  }

  const warningCodes = run?.warning_codes || []
  if (warningCodes.length) {
    const warned = items.find((item) => item.kind === 'warning')
    if (!warned) {
      items.push({
        kind: 'warning',
        key: 'warning-final',
        codes: warningCodes,
        seq: Number.MAX_SAFE_INTEGER
      })
    }
  }

  return items
    .slice()
    .sort((a, b) => (a.seq || 0) - (b.seq || 0))
}
