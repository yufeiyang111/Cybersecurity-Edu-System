import { test } from 'node:test'
import assert from 'node:assert/strict'

import { presentAgentWarnings } from '../../frontend/src/features/security/agent/warningPresentation.js'

test('预算耗尽展示可理解的原因与受控停止说明，不暴露内部 code', () => {
  const [warning] = presentAgentWarnings(['AGENT_BUDGET_EXHAUSTED'])

  assert.equal(warning.title, '预算已用尽')
  assert.match(warning.detail, /停止继续扩展/)
  assert.equal(warning.title.includes("AGENT_BUDGET_EXHAUSTED"), false)
  assert.equal(warning.detail.includes("AGENT_BUDGET_EXHAUSTED"), false)
})

test('警告展示去重、忽略非字符串，并为未知警告提供安全泛化文案', () => {
  const warnings = presentAgentWarnings(['UNKNOWN_WARNING', 'UNKNOWN_WARNING', null])

  assert.equal(warnings.length, 1)
  assert.equal(warnings[0].title, '运行提示')
  assert.match(warnings[0].detail, /受控降级/)
})
