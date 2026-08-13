// AgentThread 块合成纯函数测试（Node 内置 test runner）。
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { buildThreadBlocks } from '../../frontend/src/features/security/agent/threadBlocks.js'

function evt(sequence, eventType, payload = {}, itemId = null) {
  return { sequence, event_type: eventType, payload, item_id: itemId }
}

test('思考与工具调用按 sequence 严格交错', () => {
  const blocks = buildThreadBlocks({
    events: [
      evt(1, 'item.reasoning_summary.started', { sensitive_level: 'internal' }, 'rs1'),
      evt(2, 'item.reasoning_summary.delta', { delta: '先分析认证链路', sensitive_level: 'internal' }, 'rs1'),
      evt(3, 'tool.started', { tool_call_id: 101, tool_name: 'run_baseline_scan' }),
      evt(4, 'tool.started', { tool_call_id: 102, tool_name: 'get_findings' }),
      evt(5, 'item.reasoning_summary.started', { sensitive_level: 'internal' }, 'rs2'),
      evt(6, 'item.reasoning_summary.delta', { delta: '再看修复建议', sensitive_level: 'internal' }, 'rs2'),
      evt(7, 'tool.started', { tool_call_id: 103, tool_name: 'search_code' }),
      evt(8, 'item.assistant_message.completed', { content: '审查完成' })
    ],
    toolCalls: [
      { id: 101, tool_name: 'run_baseline_scan' },
      { id: 102, tool_name: 'get_findings' },
      { id: 103, tool_name: 'search_code' }
    ]
  })
  const kinds = blocks.map((b) => b.kind)
  assert.deepEqual(kinds, [
    'thinking',
    'tool',
    'tool',
    'thinking',
    'tool',
    'assistant'
  ], `交错顺序错误：${JSON.stringify(kinds)}`)
})

test('非 live 且无文本的 thinking 块可被过滤（started 后无 delta）', () => {
  const blocks = buildThreadBlocks({
    events: [
      evt(1, 'item.reasoning_summary.started', { sensitive_level: 'internal' }, 'rs-empty'),
      evt(2, 'tool.started', { tool_call_id: 201, tool_name: 'run_baseline_scan' }),
      evt(3, 'item.assistant_message.completed', { content: '完成' })
    ],
    toolCalls: [{ id: 201, tool_name: 'run_baseline_scan' }],
    run: { status: 'completed' }
  })
  // 组件层过滤：非 live 且空文本的 thinking 块应被丢弃
  const visible = blocks.filter((b) => {
    if (b.kind === 'thinking' && !b.live && !(b.text || '').trim()) return false
    return true
  })
  assert.equal(visible.filter((b) => b.kind === 'thinking').length, 0, '空思考块不应渲染')
  assert.equal(visible.length, 2, '工具块与助手块保留')
})

test('live 空文本 thinking 块保留（思考中动画）', () => {
  const blocks = buildThreadBlocks({
    events: [
      evt(1, 'item.reasoning_summary.started', { sensitive_level: 'internal' }, 'rs-live')
    ],
    reasoningLive: true,
    running: true
  })
  const thinking = blocks.filter((b) => b.kind === 'thinking')
  assert.equal(thinking.length, 1, 'live 思考块应保留')
  assert.equal(thinking[0].live, true)
})

test('工具快照兜底：无事件时按 toolCalls 顺序追加', () => {
  const blocks = buildThreadBlocks({
    events: [],
    toolCalls: [{ id: 1, tool_name: 'a' }, { id: 2, tool_name: 'b' }]
  })
  const tools = blocks.filter((b) => b.kind === 'tool')
  assert.equal(tools.length, 2)
  assert.deepEqual(tools.map((t) => t.tool.id), ['1', '2'])
})
