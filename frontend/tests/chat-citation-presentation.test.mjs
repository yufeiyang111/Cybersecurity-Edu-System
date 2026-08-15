import { test } from 'node:test'
import assert from 'node:assert/strict'

import { citationUsagePresentation } from '../../frontend/src/features/chat/citationPresentation.js'

test('证据充分时只将已验证引用标记为回答依据', () => {
  const presentation = citationUsagePresentation('supported', 6)

  assert.equal(presentation.ariaLabel, '可核验证据')
  assert.equal(presentation.title, '引用证据')
  assert.equal(presentation.countLabel, '6 条可核验引用')
  assert.equal(presentation.actionLabel, '查看证据')
  assert.equal(presentation.itemLabel, '已验证引用')
  assert.equal(presentation.showClaimCount, true)
})

test('证据不足时不把检索结果伪装成支撑回答的引用', () => {
  const presentation = citationUsagePresentation('insufficient_evidence', 6)

  assert.equal(presentation.ariaLabel, '相关参考资料')
  assert.equal(presentation.title, '相关参考资料')
  assert.equal(presentation.countLabel, '检索到 6 条相关参考资料，未作为本回答的结论依据。')
  assert.equal(presentation.actionLabel, '查看相关资料')
  assert.equal(presentation.itemLabel, '相关资料')
  assert.equal(presentation.showClaimCount, false)
})

test('资料冲突或未知状态不会错误展示主张覆盖信息', () => {
  const conflicting = citationUsagePresentation('conflicting_evidence', 2)
  const unknown = citationUsagePresentation('unexpected_status', -1)

  assert.equal(conflicting.title, '冲突参考资料')
  assert.equal(conflicting.showClaimCount, false)
  assert.equal(unknown.title, '待核验资料')
  assert.equal(unknown.countLabel, '检索到 0 条待核验资料。')
  assert.equal(unknown.showClaimCount, false)
})