import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  answerStatusPresentation,
  hasNavigableDocument,
  normalizeAssistantEvidence,
  normalizeCitationManifest,
  normalizeEvidenceResponse,
  normalizeLegacySources,
  retrievalSignalPresentation
} from '../../frontend/src/features/chat/citationPresentation.js'

const validManifest = {
  citations: [
    {
      citation_id: 'C-1',
      document_id: '12',
      title: 'SQL 注入防护',
      title_path: 'Web 安全 / SQL 注入',
      start_line: 4,
      end_line: 9
    }
  ],
  claim_citations: {
    主张: ['C-1']
  }
}

test('v2 supported 回答保留稳定 citation manifest，不显示相似度百分比', () => {
  const evidence = normalizeAssistantEvidence({
    answerStatus: 'supported',
    citations: validManifest,
    pipelineVersion: 'rag-v2'
  })

  assert.equal(evidence.answerStatus, 'supported')
  assert.equal(evidence.citationState, 'ready')
  assert.equal(evidence.citationManifest.citations[0].citationId, 'C-1')
  assert.equal(evidence.citationManifest.citations[0].titlePath, 'Web 安全 / SQL 注入')
  assert.equal('similarity' in evidence.citationManifest.citations[0], false)
})

test('v2 缺失或重复 citation manifest 必须降级，而不是继续声称 supported', () => {
  const missing = normalizeAssistantEvidence({
    answerStatus: 'supported',
    citations: null,
    pipelineVersion: 'rag-v2'
  })
  const duplicate = normalizeAssistantEvidence({
    answerStatus: 'supported',
    citations: {
      citations: [
        { citation_id: 'C-1', title: 'a' },
        { citation_id: 'C-1', title: 'b' }
      ]
    },
    pipelineVersion: 'rag-v2'
  })

  assert.equal(missing.answerStatus, 'degraded')
  assert.equal(missing.citationState, 'degraded')
  assert.equal(duplicate.answerStatus, 'degraded')
  assert.equal(duplicate.citationManifest.isValid, false)
})

test('流式过程和无 pipeline 的历史记录有明确状态，不伪造证据', () => {
  const pending = normalizeAssistantEvidence({
    answerStatus: 'supported',
    citations: validManifest,
    pipelineVersion: 'rag-v2',
    isStreaming: true
  })
  const legacy = normalizeAssistantEvidence({
    citations: validManifest
  })

  assert.equal(pending.citationState, 'pending')
  assert.equal(answerStatusPresentation(pending.answerStatus, pending.citationState).label, '证据处理中')
  assert.equal(legacy.citationState, 'legacy')
  assert.equal(answerStatusPresentation(legacy.answerStatus, legacy.citationState).label, '历史记录')
})

test('历史记录的 legacy sources 必须保留为只读来源，不能因缺 manifest 而被隐藏', () => {
  const evidence = normalizeAssistantEvidence({
    sources: [
      {
        title: '旧版 SQL 注入资料',
        source: 'HackTricks',
        start_line: 3,
        end_line: 8
      }
    ]
  })

  assert.equal(evidence.citationState, 'legacy')
  assert.deepEqual(evidence.legacySources, [
    {
      title: '旧版 SQL 注入资料',
      source: 'HackTricks',
      startLine: 3,
      endLine: 8
    }
  ])
})

test('legacy sources 丢弃无效字段、去重并且不透传旧 payload 的敏感内容', () => {
  const sources = normalizeLegacySources([
    null,
    { title: '', source: '' },
    {
      title: '旧资料',
      source: 'HackTricks',
      start_line: '7',
      end_line: '3',
      document_id: 44,
      content: '不应进入前端历史来源卡片的正文'
    },
    {
      title: '旧资料',
      source: 'HackTricks',
      start_line: 7,
      end_line: 3
    }
  ])

  assert.deepEqual(sources, [
    {
      title: '旧资料',
      source: 'HackTricks',
      startLine: 7,
      endLine: null
    }
  ])
  assert.equal(JSON.stringify(sources).includes('document_id'), false)
  assert.equal(JSON.stringify(sources).includes('不应进入前端历史来源卡片的正文'), false)
})

test('evidence 详情只接受 manifest 内 citation 和后端授权的知识库跳转目标', () => {
  const payload = normalizeEvidenceResponse({
    evidence: {
      record_id: 7,
      answer_status: 'supported',
      citations: validManifest,
      retrieval_signal: { level: 'high', is_calibrated: false },
      citation_details: [
        {
          citation_id: 'C-1',
          title: '后端确认标题',
          claim_count: 2,
          document: { type: 'public_knowledge', knowledge_id: 12 },
          preview: {
            text: '受控预览',
            start_line: 4,
            end_line: 9,
            is_truncated: false
          }
        },
        {
          citation_id: 'C-forged',
          title: '伪造引用',
          document: { type: 'public_knowledge', knowledge_id: 99 }
        }
      ]
    }
  })

  assert.equal(payload.recordId, 7)
  assert.equal(payload.citationDetails.length, 1)
  assert.equal(payload.citationDetails[0].claimCount, 2)
  assert.equal(payload.citationDetails[0].preview.text, '受控预览')
  assert.equal(hasNavigableDocument(payload.citationDetails[0]), true)
  assert.equal(hasNavigableDocument({ document: { type: 'public_knowledge', knowledgeId: 'not-an-id' } }), false)
})

test('未校准检索辅助信号只展示等级和非正确率说明', () => {
  const high = retrievalSignalPresentation({ level: 'high', is_calibrated: true })
  const unknown = retrievalSignalPresentation({ level: '99%' })

  assert.equal(high.label, '高')
  assert.equal(high.isCalibrated, false)
  assert.match(high.description, /不代表回答正确率/)
  assert.equal(unknown.label, '暂不可用')
})

test('非法 citation manifest 保持安全空结构并使 v2 回答降级', () => {
  const manifest = normalizeCitationManifest({
    citations: [{ citation_id: 'C-1', title: '存在引用' }],
    claim_citations: 'not-an-object'
  })
  const evidence = normalizeAssistantEvidence({
    answerStatus: 'supported',
    citations: {
      citations: [{ citation_id: 'C-1', title: '存在引用' }],
      claim_citations: 'not-an-object'
    },
    pipelineVersion: 'rag-v2'
  })

  assert.equal(manifest.isValid, false)
  assert.deepEqual(manifest.claimCitations, {})
  assert.equal(evidence.answerStatus, 'degraded')
})
