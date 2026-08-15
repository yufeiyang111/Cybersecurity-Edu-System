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