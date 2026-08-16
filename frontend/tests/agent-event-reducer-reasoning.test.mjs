// eventReducer 的 v2 reasoning summary 事件测试（Node 内置 test runner）。
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  createAgentRunState,
  reduceAgentEvent
} from '../../frontend/src/features/security/agent/eventReducer.js'

function evt(sequence, eventType, payload = {}) {
  return { sequence, event_type: eventType, payload }
}

test('v2 reasoning_summary.started 重置推理流并标记 live', () => {
  let state = createAgentRunState()
  state = reduceAgentEvent(state, evt(1, 'item.reasoning_summary.started', {
    sensitive_level: 'internal'
  }))
  assert.equal(state.reasoningStream, '')
  assert.equal(state.reasoningLive, true)
  assert.equal(state.reasoningSensitiveLevel, 'internal')
  assert.equal(state.lastSequence, 1)
})

test('v2 reasoning_summary.delta 累积脱敏摘要', () => {
  let state = createAgentRunState()
  state = reduceAgentEvent(state, evt(1, 'item.reasoning_summary.started', {
    sensitive_level: 'internal'
  }))
  state = reduceAgentEvent(state, evt(2, 'item.reasoning_summary.delta', {
    delta: '先核对扫描证据',
    sensitive_level: 'internal'
  }))
  state = reduceAgentEvent(state, evt(3, 'item.reasoning_summary.delta', {
    delta: '，再定位入口。',
    sensitive_level: 'internal'
  }))
  assert.equal(state.reasoningStream, '先核对扫描证据，再定位入口。')
  assert.equal(state.reasoningLive, true)
})

test('v2 reasoning_summary.completed 结束 live 状态', () => {
  let state = createAgentRunState()
  state = reduceAgentEvent(state, evt(1, 'item.reasoning_summary.delta', {
    delta: '分析完成',
    sensitive_level: 'internal'
  }))
  state = reduceAgentEvent(state, evt(2, 'item.reasoning_summary.completed', {}))
  assert.equal(state.reasoningLive, false)
  assert.equal(state.reasoningStream, '分析完成')
})

test('v2 reasoning 事件保持顺序推进 lastSequence', () => {
  let state = createAgentRunState()
  state = reduceAgentEvent(state, evt(1, 'item.reasoning_summary.started', {}))
  state = reduceAgentEvent(state, evt(2, 'item.tool_call.started', {
    tool_call_id: 1,
    name: 'run_baseline_scan'
  }))
  state = reduceAgentEvent(state, evt(3, 'item.reasoning_summary.delta', {
    delta: '工具执行后继续分析',
    sensitive_level: 'internal'
  }))
  assert.equal(state.lastSequence, 3)
  assert.equal(state.reasoningStream, '工具执行后继续分析')
})

test('Provider 原始 reasoning 是瞬时帧：不推进 sequence、不进入历史事件尾部', () => {
  let state = createAgentRunState()
  state = reduceAgentEvent(state, evt(5, 'item.tool_call.started', {
    tool_call_id: 1,
    name: 'run_deep_review'
  }))
  const eventCount = state.events.length
  state = reduceAgentEvent(state, {
    event_type: 'provider_reasoning_raw_delta',
    sequence: null,
    transient: true,
    payload: {
      transient: true,
      source: 'provider',
      delta: 'Provider 实际返回的 reasoning delta'
    }
  })

  assert.equal(state.providerRawReasoning, 'Provider 实际返回的 reasoning delta')
  assert.equal(state.providerRawReasoningLive, true)
  assert.equal(state.lastSequence, 5)
  assert.equal(state.events.length, eventCount)
})

test('伪造或非瞬时 Provider reasoning 帧必须被忽略', () => {
  const state = createAgentRunState()
  const next = reduceAgentEvent(state, {
    event_type: 'provider_reasoning_raw_delta',
    sequence: null,
    transient: false,
    payload: {
      transient: false,
      delta: '不应展示'
    }
  })

  assert.equal(next.providerRawReasoning, '')
  assert.equal(next.lastSequence, 0)
})
