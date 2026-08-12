// T11 timelineReducer 纯函数测试（Node 内置 test runner）。
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  applyTimelineBatch,
  applyTimelineEvent,
  createTimelineState,
  hydrateTimelineState,
  timelineItems
} from '../../frontend/src/features/security/agent/timelineReducer.js'

function evt(sequence, eventType, payload = {}, itemId = null) {
  return { sequence, event_type: eventType, payload, item_id: itemId }
}

test('乱序批次按 sequence 应用', () => {
  const state = applyTimelineBatch(createTimelineState(), [
    evt(2, 'item.tool_call.started', {}, 't2'),
    evt(1, 'item.tool_call.started', {}, 't1')
  ])
  const items = timelineItems(state)
  assert.deepEqual(items.map((item) => item.publicId), ['t1', 't2'])
  assert.equal(state.lastSequence, 2)
})

test('同一 item 的 delta 不改变位置', () => {
  let state = createTimelineState()
  state = applyTimelineEvent(state, evt(1, 'item.assistant_message.started', {}, 'asst'))
  state = applyTimelineEvent(state, evt(2, 'item.reasoning_summary.delta', { delta: '推理' }, 'rs'))
  state = applyTimelineEvent(state, evt(3, 'item.assistant_message.delta', { delta: '第一段' }, 'asst'))
  state = applyTimelineEvent(state, evt(4, 'item.assistant_message.delta', { delta: '第二段' }, 'asst'))
  const order = state.itemOrder
  assert.deepEqual(order, ['asst', 'rs'], 'delta 不得改变 item 位置')
  assert.equal(state.itemsById.asst.content, '第一段第二段')
})

test('重复 event / delta 幂等', () => {
  let state = createTimelineState()
  state = applyTimelineEvent(state, evt(1, 'item.assistant_message.delta', { delta: 'A' }, 'asst'))
  state = applyTimelineEvent(state, evt(1, 'item.assistant_message.delta', { delta: 'A' }, 'asst'))
  assert.equal(state.itemsById.asst.content, 'A')
  assert.equal(state.lastSequence, 1)
})

test('gap 检测：缺号事件触发 resync 且停止应用', () => {
  let state = createTimelineState()
  state = applyTimelineEvent(state, evt(1, 'item.user_message.created', {}, 'msg'))
  state = applyTimelineEvent(state, evt(5, 'item.tool_call.started', {}, 'tool'))
  assert.equal(state.gapDetected, true)
  assert.equal(state.connectionState, 'resyncing')
  assert.equal(state.itemsById.tool, undefined, '缺口后的增量不得应用')
})

test('legacy reasoning 事件同样先做 gap 检测', () => {
  let state = createTimelineState()
  state = applyTimelineEvent(state, evt(1, 'item.reasoning_summary.delta', { delta: 'x' }, 'rs'))
  state = applyTimelineEvent(state, evt(3, 'llm.reasoning_delta', { delta: 'legacy' }, 'rs'))
  assert.equal(state.gapDetected, true)
})

test('hydration 与服务端水位一致', () => {
  const snapshot = {
    items: [
      { public_id: 'msg-1', item_type: 'user_message', status: 'completed', content: '检查越权' },
      { public_id: 'asst-1', item_type: 'assistant_message', status: 'completed', content: '审查完成' }
    ],
    snapshot_watermark: 12,
    last_sequence: 12,
    state_version: 5
  }
  const state = hydrateTimelineState(snapshot)
  assert.equal(state.snapshotWatermark, 12)
  assert.equal(state.lastSequence, 12)
  assert.equal(state.stateVersion, 5)
  assert.deepEqual(timelineItems(state).map((item) => item.publicId), ['msg-1', 'asst-1'])
})

test('assistant delta 累计与刷新 Snapshot 文本逐字一致', () => {
  let state = createTimelineState()
  state = applyTimelineEvent(state, evt(1, 'item.assistant_message.started', {}, 'asst'))
  state = applyTimelineEvent(state, evt(2, 'item.assistant_message.delta', { delta: '审查完成：' }, 'asst'))
  state = applyTimelineEvent(state, evt(3, 'item.assistant_message.delta', { delta: '发现 3 个高风险项。' }, 'asst'))
  const streamed = state.itemsById.asst.content
  const hydrated = hydrateTimelineState({
    items: [{ public_id: 'asst', item_type: 'assistant_message', status: 'completed', content: streamed }],
    snapshot_watermark: 3,
    last_sequence: 3,
    state_version: 1
  })
  assert.equal(hydrated.itemsById.asst.content, streamed)
})

test('heartbeat 无 sequence 不进时间线', () => {
  let state = createTimelineState()
  const before = timelineItems(state).length
  state = applyTimelineEvent(state, { event: 'heartbeat', data: { sequence: 3 } })
  assert.equal(timelineItems(state).length, before)
  assert.equal(state.lastSequence, 0)
})

test('tool_result 作为子 item 挂到父 item 之后', () => {
  let state = createTimelineState()
  state = applyTimelineEvent(state, evt(1, 'item.tool_call.started', {}, 'call-1'))
  state = applyTimelineEvent(state, evt(2, 'item.tool_call.completed', { content: 'ok' }, 'call-1'))
  state = applyTimelineEvent(state, evt(3, 'item.tool_result.created', { parent_item_id: 'call-1', summary: '结果' }, 'res-1'))
  const order = state.itemOrder
  assert.deepEqual(order, ['call-1', 'res-1'])
  assert.equal(state.itemsById['res-1'].parentId, 'call-1')
})

test('run.completed 置 terminal 并冻结未完成 item', () => {
  let state = createTimelineState()
  state = applyTimelineEvent(state, evt(1, 'item.assistant_message.started', {}, 'asst'))
  state = applyTimelineEvent(state, evt(2, 'run.completed', { status: 'completed' }))
  assert.equal(state.terminal, true)
  assert.equal(state.itemsById.asst.status, 'completed')
})

test('batch 应用保持顺序', () => {
  const state = applyTimelineBatch(createTimelineState(), [
    evt(1, 'item.user_message.created', {}, 'msg'),
    evt(2, 'item.reasoning_summary.delta', { delta: '先核对证据' }, 'rs'),
    evt(3, 'item.reasoning_summary.completed', {}, 'rs')
  ])
  assert.equal(state.lastSequence, 3)
  assert.equal(state.itemsById.rs.status, 'completed')
})
