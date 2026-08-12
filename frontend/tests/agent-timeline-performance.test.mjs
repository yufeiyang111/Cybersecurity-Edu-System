// T13 Reducer 性能测试（M-19）：5000 事件无明显 O(n²) 卡顿。
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  applyTimelineBatch,
  createTimelineState
} from '../../frontend/src/features/security/agent/timelineReducer.js'

const EVENT_COUNT = 5000

function makeEvents(count) {
  const events = []
  for (let i = 1; i <= count; i++) {
    const type = i % 5 === 0 ? 'item.assistant_message.delta' : 'item.observation.created'
    events.push({
      sequence: i,
      event_type: type,
      item_id: `obs-${i % 50}`,
      payload: { delta: `第 ${i} 条内容片段。`, summary: `观察 ${i % 50}` }
    })
  }
  return events
}

test('5000 events reducer 无明显 O(n²) 卡顿', () => {
  const events = makeEvents(EVENT_COUNT)
  const started = performance.now()
  const state = applyTimelineBatch(createTimelineState(), events)
  const elapsed = performance.now() - started
  assert.equal(state.lastSequence, EVENT_COUNT)
  assert.equal(state.itemOrder.length, 50, '50 个 item 的 delta 不应改变位置')
  console.log(`timelineReducer: ${EVENT_COUNT} events in ${elapsed.toFixed(1)}ms`)
  assert.ok(elapsed < 3000, `耗时 ${elapsed.toFixed(0)}ms 超过 3s 阈值，疑似 O(n²)`)
})
