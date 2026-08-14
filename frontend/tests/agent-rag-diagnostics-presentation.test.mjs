import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  normalizeEvaluationRunDetailResponse,
  normalizeEvaluationRunsResponse
} from '../../frontend/src/features/admin/ragEvaluationPresentation.js'
import { normalizeRagTraceResponse } from '../../frontend/src/features/admin/ragTracePresentation.js'

test('诊断 trace 只归一化白名单阶段字段，不携带候选文档、query 或正文', () => {
  const trace = normalizeRagTraceResponse({
    trace: {
      id: 18,
      pipeline_version_id: 6,
      retrieval_ms: 42,
      created_at: '2026-08-14T10:00:00Z',
      request_id: 'request-secret',
      record_id: 99,
      query_fingerprint: 'fingerprint',
      warnings: ['QDRANT_UNAVAILABLE', 'bad warning text'],
      stage_summary: {
        query: '不能出现在页面中',
        candidate: {
          candidate_count: 12,
          retrieval_paths: { dense_only: 3, bm25_only: 2, both: 7 },
          candidates: [{ document_id: '99', content: '不能出现在页面中' }]
        },
        rerank: { status: 'completed', input_count: 12, output_count: 6, elapsed_ms: 18 },
        evidence: {
          answer_status: 'supported',
          reference_count: 4,
          token_count: 800,
          token_budget: 1200,
          rejection_counts: { prompt_injection: 1, unsafe_key: 2 }
        },
        answer: { answer_status: 'supported', citation_count: 4, claim_count: 3, warning_count: 1 }
      }
    }
  })

  assert.equal(trace.id, 18)
  assert.equal(trace.candidate.candidateCount, 12)
  assert.deepEqual(trace.candidate.retrievalPaths, [
    { label: 'Dense', count: 3 },
    { label: 'BM25', count: 2 },
    { label: 'RRF 融合', count: 7 }
  ])
  assert.deepEqual(trace.warnings, ['QDRANT_UNAVAILABLE'])
  assert.equal('requestId' in trace, false)
  assert.equal('recordId' in trace, false)
  assert.equal('queryFingerprint' in trace, false)
  assert.equal('candidates' in trace.candidate, false)
  assert.equal(JSON.stringify(trace).includes('不能出现在页面中'), false)
  assert.equal(JSON.stringify(trace).includes('document_id'), false)
})

test('评测运行只展示指标白名单，忽略报告路径和未声明字段', () => {
  const response = normalizeEvaluationRunsResponse({
    runs: [{
      id: 9,
      pipeline_version_id: 2,
      corpus_version: 'public-v1',
      status: 'completed',
      report_path: 'rag_report_private.json',
      metrics: {
        retrieval: { recall_at_20: 0.8, internal_query: '不应显示' },
        evidence: { context_precision: 0.5, source_diversity: 0.75 },
        citation: { is_deterministic: true, unsafe_supported_negative_count: 0 },
        runtime: { retrieval_p95_ms: 88, raw_prompt_tokens: 9999 }
      }
    }],
    total: 1,
    page: 1,
    per_page: 12,
    pages: 1
  })

  assert.equal(response.runs.length, 1)
  const normalized = response.runs[0]
  assert.equal('reportPath' in normalized, false)
  assert.deepEqual(normalized.metricGroups.flatMap((group) => group.items), [
    { label: 'Recall@20', value: '80.0%' },
    { label: '上下文精度', value: '50.0%' },
    { label: '来源多样性', value: '75.0%' },
    { label: '引用确定性', value: '通过' },
    { label: '危险负例', value: '0' },
    { label: '检索 P95', value: '88 ms' }
  ])
  assert.equal(JSON.stringify(normalized).includes('不应显示'), false)
  assert.equal(JSON.stringify(normalized).includes('9999'), false)
})

test('评测详情只聚合失败阶段，不泄露 case ID 或各 case 指标原文', () => {
  const detail = normalizeEvaluationRunDetailResponse({
    run: {
      id: 10,
      corpus_version: 'public-v1',
      status: 'completed_with_failures',
      metrics: {}
    },
    results: [
      { case_id: 11, failure_stage: 'execution', answer_metrics: { notes: '敏感上下文' } },
      { case_id: 12, failure_stage: 'execution', retrieval_metrics: { document_id: '9' } },
      { case_id: 13, failure_stage: 'version' },
      { case_id: 14, failure_stage: '非法 文本' }
    ],
    result_page: { total: 4, page: 1, pages: 1 }
  })

  assert.equal(detail.resultTotal, 4)
  assert.deepEqual(detail.failureStages, [
    { key: 'execution', count: 2 },
    { key: 'version', count: 1 }
  ])
  assert.equal(JSON.stringify(detail).includes('case_id'), false)
  assert.equal(JSON.stringify(detail).includes('敏感上下文'), false)
  assert.equal(JSON.stringify(detail).includes('document_id'), false)
})

test('非法诊断响应拒绝归一化，避免把不可信对象交给页面渲染', () => {
  assert.equal(normalizeRagTraceResponse({ trace: { id: 0 } }), null)
  assert.equal(normalizeEvaluationRunDetailResponse({ run: { id: 'bad' } }), null)
})
