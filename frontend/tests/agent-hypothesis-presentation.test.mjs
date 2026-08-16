import assert from 'node:assert/strict'
import test from 'node:test'
import {
  attackPathEmptyStateMessage,
  isAttackPathMode,
  isV3AttackPathRun,
  normalizeHypothesisDetailResponse,
  normalizeHypothesisListResponse
} from '../src/features/security/agent/hypothesisPresentation.js'

test('攻击路径视图只对 Hybrid/Deep 的 V3 运行开启', () => {
  assert.equal(isAttackPathMode({ mode: 'hybrid' }), true)
  assert.equal(isAttackPathMode({ mode: 'deep_audit' }), true)
  assert.equal(isAttackPathMode({ mode: 'baseline' }), false)
  assert.equal(
    isV3AttackPathRun({ mode: 'deep_audit' }, { harness_v3: true }),
    true
  )
  assert.equal(
    isV3AttackPathRun({ mode: 'deep_audit' }, { harness_v3: false }),
    false
  )
})

test('假设列表仅保留白名单字段并拒绝伪造原始推理字段', () => {
  const normalized = normalizeHypothesisListResponse({
    items: [
      {
        id: 8,
        hypothesis_key: 'unsafe-flow',
        skill_key: 'unsafe_execution_deserialization',
        title: '危险执行路径',
        target_summary: '验证攻击路径',
        priority: 90,
        status: 'confirmed',
        required_evidence: ['untrusted_input', 'dangerous_sink'],
        authorized_scopes: [
          { file_path: 'app.py', start_line: 10, end_line: 20 },
          { file_path: '../secret.py', start_line: 1, end_line: 2 }
        ],
        satisfied_evidence: ['untrusted_input'],
        evidence_gaps: [],
        provider_raw_reasoning: '不得进入界面状态',
        unexpected_html: '<script>alert(1)</script>'
      }
    ],
    total: 1,
    page: 1,
    page_size: 20,
    metrics: {
      hypothesis_count: 1,
      code_evidence_coverage: 0.5,
      evidence_insufficient_rate: 2,
      budget_exhaustion_rate: -1,
      skill_counts: [{ skill_key: 'unsafe_execution_deserialization', candidate_count: 1 }]
    }
  })

  assert.equal(normalized.items.length, 1)
  assert.deepEqual(normalized.items[0], {
    id: 8,
    hypothesisKey: 'unsafe-flow',
    skillKey: 'unsafe_execution_deserialization',
    title: '危险执行路径',
    targetSummary: '验证攻击路径',
    priority: 90,
    status: 'confirmed',
    plannerSource: '',
    requiredEvidence: ['untrusted_input', 'dangerous_sink'],
    authorizedScopes: [{ filePath: 'app.py', startLine: 10, endLine: 20 }],
    satisfiedEvidence: ['untrusted_input'],
    evidenceGaps: [],
    reflectionCount: 0,
    executionAttemptCount: 0,
    createdAt: '',
    updatedAt: ''
  })
  assert.equal(JSON.stringify(normalized.items[0]).includes('reasoning'), false)
  assert.equal(normalized.metrics.codeEvidenceCoverage, 0.5)
  assert.equal(normalized.metrics.evidenceInsufficientRate, null)
  assert.equal(normalized.metrics.budgetExhaustionRate, null)
})

test('详情仅渲染受控 Critic Verdict，不透传额外 Provider 字段', () => {
  const detail = normalizeHypothesisDetailResponse({
    hypothesis: {
      id: 9,
      hypothesis_key: 'auth-flow',
      skill_key: 'authorization_boundary',
      title: '授权边界',
      target_summary: '验证对象归属',
      priority: 80,
      status: 'needs_evidence',
      verdicts: [
        {
          id: 3,
          verdict_version: 1,
          verdict: 'needs_more_evidence',
          reason_summary: '缺少授权代码位置。',
          evidence_gaps: ['缺少 guard'],
          next_action: { action: 'collect_guard', raw_reasoning: 'hidden' },
          critic_version: 'evidence_critic_v1',
          provider_response: 'must-not-pass'
        }
      ]
    }
  })

  assert.deepEqual(detail.verdicts, [
    {
      id: 3,
      verdictVersion: 1,
      verdict: 'needs_more_evidence',
      reasonSummary: '缺少授权代码位置。',
      evidenceGaps: ['缺少 guard'],
      nextAction: 'collect_guard',
      criticVersion: 'evidence_critic_v1',
      createdAt: ''
    }
  ])
  assert.equal(JSON.stringify(detail).includes('provider_response'), false)
  assert.equal(JSON.stringify(detail).includes('raw_reasoning'), false)
})

test('畸形 API 结果安全降级为空结构', () => {
  assert.deepEqual(normalizeHypothesisListResponse(null), {
    items: [],
    total: 0,
    page: 1,
    pageSize: 20,
    metrics: {
      hypothesisCount: 0,
      statusCounts: {},
      skillCounts: [],
      codeEvidenceCoverage: null,
      evidenceInsufficientRate: null,
      budgetExhaustionRate: null,
      deepReviewCost: {
        callCount: 0,
        costKnown: false,
        totalCost: null,
        averagePerHypothesis: null
      }
    }
  })
  assert.equal(normalizeHypothesisDetailResponse({ hypothesis: { id: 0 } }), null)
})

test('攻击路径空态准确区分阻断、预算收口、历史终态和执行中', () => {
  assert.equal(
    attackPathEmptyStateMessage({ runStatus: 'blocked', terminal: true }),
    '该审计因证据或安全策略被阻断，未形成可验证的漏洞假设。'
  )
  assert.equal(
    attackPathEmptyStateMessage({ runStatus: 'completed_with_warnings', terminal: true }),
    '本次审计已带警告收口；未形成可验证的漏洞假设。'
  )
  assert.equal(
    attackPathEmptyStateMessage({
      terminal: true,
      budgetExhausted: true,
    }),
    '本次审计因预算上限收口，未形成可验证的漏洞假设。'
  )
  assert.equal(
    attackPathEmptyStateMessage({ terminal: true }),
    '本次审计未形成可验证的漏洞假设。'
  )
  assert.equal(
    attackPathEmptyStateMessage({ terminal: false }),
    '正在等待确定性基线形成可验证假设。'
  )
})
