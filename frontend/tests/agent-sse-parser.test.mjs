// T11 sseParser 纯函数测试（Node 内置 test runner）。
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { parseSseChunk, parseSseFrame } from '../../frontend/src/features/security/agent/sseParser.js'

test('解析 id/event/data 帧', () => {
  const frame = parseSseFrame(
    'id: 12\nevent: item.tool_call.started\ndata: {"tool_name": "read_code_slice"}\n'
  )
  assert.equal(frame.id, 12)
  assert.equal(frame.event, 'item.tool_call.started')
  assert.deepEqual(frame.data, { tool_name: 'read_code_slice' })
})

test('正式 heartbeat 帧被识别且不进时间线', () => {
  const frame = parseSseFrame('event: heartbeat\ndata: {"sequence": 5}\n')
  assert.equal(frame.event, 'heartbeat')
  assert.equal(frame.id, null)
  assert.equal(frame.data.sequence, 5)
})

test('多行 data 拼接为完整 JSON', () => {
  const frame = parseSseFrame(
    'event: item.assistant_message.delta\n' +
      'data: {\n' +
      'data:   "delta": "第一行，第二行"\n' +
      'data: }\n'
  )
  assert.equal(frame.event, 'item.assistant_message.delta')
  assert.equal(frame.data.delta, '第一行，第二行')
})

test('纯注释帧回调 ping（连接存活信号）', () => {
  const frame = parseSseFrame(': ping\n')
  assert.equal(frame.event, 'ping')
  assert.equal(frame.id, null)
})

test('错误帧解析', () => {
  const frame = parseSseFrame(
    'event: error\ndata: {"code": "AGENT_SSE_REPLAY_GAP", "message": "水位过旧"}\n'
  )
  assert.equal(frame.event, 'error')
  assert.equal(frame.data.code, 'AGENT_SSE_REPLAY_GAP')
})

test('尾帧（无 data 的完成帧）返回 event 占位', () => {
  const frame = parseSseFrame('event: done\n')
  assert.equal(frame.event, 'done')
  assert.equal(frame.data, null)
})

test('增量 buffer 解析并保留残帧', () => {
  const first = parseSseChunk('id: 1\nevent: run.created\ndata: {"run_id": 1}\n\nid: 2\nevent: ')
  assert.equal(first.frames.length, 1)
  assert.equal(first.frames[0].id, 1)
  assert.match(first.rest, /^id: 2/)

  const second = parseSseChunk(first.rest + 'item.tool_call.started\ndata: {}\n\n')
  assert.equal(second.frames.length, 1)
  assert.equal(second.frames[0].id, 2)
  assert.equal(second.frames[0].event, 'item.tool_call.started')
  assert.equal(second.rest, '')
})

test('非法 JSON data 保留原始串不崩溃', () => {
  const frame = parseSseFrame('event: item.x\ndata: not-json\n')
  assert.equal(frame.event, 'item.x')
  assert.ok(frame.data.__raw)
})

test('空输入返回 null', () => {
  assert.equal(parseSseFrame(''), null)
  assert.equal(parseSseFrame(null), null)
})
