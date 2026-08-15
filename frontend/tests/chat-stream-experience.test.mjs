import { test } from 'node:test'
import assert from 'node:assert/strict'

import { normalizeRagProcessSummary } from '../../frontend/src/features/chat/ragProcessPresentation.js'
import { isNearStreamBottom } from '../../frontend/src/features/chat/streamFollowState.js'

test('只归一化允许展示的 RAG 阶段计数，不携带 query 或证据正文', () => {
  const summary = normalizeRagProcessSummary({
    stage_summary: {
      candidate: { candidate_count: 40, query: '不能显示' },
      rerank: { output_count: 15, candidates: [{ content: '不能显示' }] },
      evidence: { reference_count: 6, token_count: 1200 },
      generation: { status: 'completed', provider_error: '不能显示' }
    }
  })

  assert.deepEqual(summary, {
    steps: [
      { label: '候选召回', detail: '40 项' },
      { label: '重排筛选', detail: '15 项' },
      { label: '可用证据', detail: '6 项' },
      { label: '回答生成', detail: '已完成' }
    ]
  })
  assert.equal(JSON.stringify(summary).includes('不能显示'), false)
})

test('无受控阶段摘要时不渲染伪造的检索过程', () => {
  assert.equal(normalizeRagProcessSummary(null), null)
  assert.equal(normalizeRagProcessSummary({ stage_summary: { candidate: { candidate_count: -1 } } }), null)
})

test('用户向上滚动离开底部后停止流式跟随，回到底部阈值内恢复', () => {
  const nearBottom = { scrollHeight: 1200, clientHeight: 600, scrollTop: 550 }
  const readingHistory = { scrollHeight: 1200, clientHeight: 600, scrollTop: 430 }

  assert.equal(isNearStreamBottom(nearBottom), true)
  assert.equal(isNearStreamBottom(readingHistory), false)
})

test('不完整的滚动容器按可继续跟随处理，避免阻断首屏定位', () => {
  assert.equal(isNearStreamBottom(null), true)
  assert.equal(isNearStreamBottom({ scrollHeight: 100 }), true)
})