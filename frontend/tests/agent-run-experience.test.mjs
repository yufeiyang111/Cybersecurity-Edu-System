import { test } from 'node:test'
import assert from 'node:assert/strict'

import { resolveAgentRunExperience } from '../../frontend/src/features/security/agent/runExperience.js'

test('baseline 始终呈现为确定性工作流，不承诺运行中自主调度或追问', () => {
  const experience = resolveAgentRunExperience(
    { mode: 'baseline' },
    { loop_v2: true }
  )

  assert.equal(experience.kind, 'workflow')
  assert.equal(experience.supportsDynamicControl, false)
  assert.equal(experience.supportsAutonomousTools, false)
  assert.match(experience.description, /确定性/)
})

test('未开启 V2 的混合或深度模式必须降级说明，不能伪装成 Agent Loop', () => {
  const experience = resolveAgentRunExperience(
    { mode: 'deep_audit' },
    { loop_v2: false }
  )

  assert.equal(experience.kind, 'workflow_limited')
  assert.equal(experience.supportsDynamicControl, false)
  assert.match(experience.description, /未启用/)
})

test('仅开启 V2 Loop 的混合或深度模式展示模型在环能力', () => {
  const experience = resolveAgentRunExperience(
    { mode: 'hybrid' },
    { loop_v2: true }
  )

  assert.equal(experience.kind, 'agentic')
  assert.equal(experience.supportsDynamicControl, true)
  assert.equal(experience.supportsAutonomousTools, true)
})
test('创建时快照必须优先于当前工作区开关，避免把已完成的 Loop 任务渲染成受限工作流', () => {
  const experience = resolveAgentRunExperience(
    { mode: 'deep_audit', execution_feature_flag_source: 'run_snapshot' },
    { loop_v2: true, event_schema_v2: true, timeline_v2: true },
    { loop_v2: false, event_schema_v2: false, timeline_v2: false }
  )

  assert.equal(experience.kind, 'agentic')
  assert.match(experience.label, /Agent Loop/)
  assert.match(experience.configurationNote, /创建时/)
})

test('没有快照的历史 V2 任务必须明确说明执行方式来自已记录事件', () => {
  const experience = resolveAgentRunExperience(
    { mode: 'hybrid', execution_feature_flag_source: 'legacy_observed' },
    { loop_v2: true, event_schema_v2: true, timeline_v2: true },
    { loop_v2: false, event_schema_v2: false, timeline_v2: false }
  )

  assert.equal(experience.kind, 'agentic')
  assert.match(experience.configurationNote, /历史任务/)
  assert.match(experience.configurationNote, /已记录/)
})
