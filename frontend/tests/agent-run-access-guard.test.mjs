import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  isAgentRunAccessDenied,
  shouldLoadAgentRunSupplementalData
} from '../../frontend/src/features/security/agent/runAccessGuard.js'

test('仅 HTTP 403 被识别为 Agent Run 工作区访问拒绝', () => {
  assert.equal(isAgentRunAccessDenied({ response: { status: 403 } }), true)
  assert.equal(isAgentRunAccessDenied({ response: { status: '403' } }), true)
})

test('会话失效、资源不存在、限流、服务端错误和网络错误不能误判为访问拒绝', () => {
  for (const error of [
    { response: { status: 401 } },
    { response: { status: 404 } },
    { response: { status: 429 } },
    { response: { status: 500 } },
    new Error('network failed'),
    null,
    undefined
  ]) {
    assert.equal(isAgentRunAccessDenied(error), false)
  }
})

test('只有主 Run 已成功加载且未被拒绝访问时，才允许继续加载附属数据', () => {
  assert.equal(
    shouldLoadAgentRunSupplementalData({ runLoaded: true, accessDenied: false }),
    true
  )
  assert.equal(
    shouldLoadAgentRunSupplementalData({ runLoaded: false, accessDenied: true }),
    false
  )
  assert.equal(
    shouldLoadAgentRunSupplementalData({ runLoaded: false, accessDenied: false }),
    false
  )
  assert.equal(
    shouldLoadAgentRunSupplementalData({ runLoaded: true, accessDenied: true }),
    false
  )
})
