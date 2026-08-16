import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  normalizeRunStatistics,
  resolveRunStatistics
} from '../../frontend/src/features/security/agent/runStatistics.js'
import {
  hydrateAgentRunState,
  reduceAgentEvent
} from '../../frontend/src/features/security/agent/eventReducer.js'
import {
  agentStatusMeta,
  isTerminalAgentRunStatus
} from '../../frontend/src/features/security/agent/statusMeta.js'

test('服务端统计优先于当前分页步骤和工具列表', () => {
  const stats = resolveRunStatistics({
    stats: {
      plan_node_total: 72,
      plan_node_completed: 72,
      plan_node_failed: 0,
      turn_total: 6,
      tool_call_total: 50,
      tool_call_succeeded: 49,
      tool_call_failed: 1,
      observation_total: 3,
      observation_with_code_evidence: 2,
      observation_unverified: 1,
      replan_total: 2,
      approval_pending: 1,
      warning_total: 1
    },
    run: {
      iteration_count: 0,
      tool_call_count: 0,
      replan_count: 0,
      warning_codes: []
    },
    plan: {
      nodes: [{ status: 'succeeded' }]
    }
  })

  assert.equal(stats.plan_node_total, 72)
  assert.equal(stats.turn_total, 6)
  assert.equal(stats.tool_call_total, 50)
  assert.equal(stats.tool_call_succeeded, 49)
  assert.equal(stats.observation_with_code_evidence, 2)
})

test('旧快照缺少 stats 时使用安全降级，不把数组页长度伪装成总量', () => {
  const stats = resolveRunStatistics({
    stats: null,
    run: {
      iteration_count: 4,
      tool_call_count: 18,
      replan_count: 1,
      warning_codes: ['AGENT_PROVIDER_TIMEOUT']
    },
    plan: {
      nodes: [
        { status: 'succeeded' },
        { status: 'failed' },
        { status: 'running' }
      ]
    }
  })

  assert.equal(stats.plan_node_total, 3)
  assert.equal(stats.plan_node_completed, 1)
  assert.equal(stats.plan_node_failed, 1)
  assert.equal(stats.turn_total, 4)
  assert.equal(stats.tool_call_total, 18)
  assert.equal(stats.tool_call_succeeded, 0)
  assert.equal(stats.tool_call_failed, 0)
  assert.equal(stats.warning_total, 1)
})

test('统计归一化拒绝负数、浮点数和非数字输入', () => {
  const stats = normalizeRunStatistics({
    turn_total: -1,
    tool_call_total: 3.5,
    warning_total: '4',
    approval_pending: Number.NaN
  })

  assert.equal(stats.turn_total, 0)
  assert.equal(stats.tool_call_total, 0)
  assert.equal(stats.warning_total, 0)
  assert.equal(stats.approval_pending, 0)
})

test('新增终态与取消收尾状态具有清晰、可区分的呈现语义', () => {
  assert.equal(agentStatusMeta('cancel_requested').label, '取消收尾中')
  assert.equal(agentStatusMeta('blocked').label, '证据不足，待补充')
  assert.equal(isTerminalAgentRunStatus('cancel_requested'), false)
  assert.equal(isTerminalAgentRunStatus('blocked'), true)
})

test('SSE 增量只在新 sequence 上更新统计，重复帧不会重复计数', () => {
  let state = hydrateAgentRunState({
    run: {
      status: 'executing_tools',
      iteration_count: 2,
      tool_call_count: 5,
      warning_codes: []
    },
    stats: {
      plan_node_total: 5,
      plan_node_completed: 2,
      plan_node_failed: 0,
      turn_total: 2,
      tool_call_total: 5,
      tool_call_succeeded: 4,
      tool_call_failed: 1,
      observation_total: 0,
      observation_with_code_evidence: 0,
      observation_unverified: 0,
      replan_total: 0,
      approval_pending: 0,
      warning_total: 0
    },
    last_sequence: 10
  })

  const started = {
    sequence: 11,
    iteration: 3,
    event_type: 'tool.started',
    payload: { tool_call_id: 99, tool_name: 'read_code_slice' }
  }
  state = reduceAgentEvent(state, started)
  state = reduceAgentEvent(state, started)
  state = reduceAgentEvent(state, {
    sequence: 12,
    iteration: 3,
    event_type: 'tool.completed',
    payload: { tool_call_id: 99, tool_name: 'read_code_slice' }
  })

  assert.equal(state.stats.turn_total, 3)
  assert.equal(state.stats.tool_call_total, 6)
  assert.equal(state.stats.tool_call_succeeded, 5)
  assert.equal(state.run.tool_call_count, 6)
  assert.equal(state.lastSequence, 12)
})