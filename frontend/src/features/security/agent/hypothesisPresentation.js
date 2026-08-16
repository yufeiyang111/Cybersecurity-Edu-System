const ATTACK_PATH_MODES = new Set(['hybrid', 'deep_audit'])
const HYPOTHESIS_STATUSES = new Set([
  'queued',
  'active',
  'needs_evidence',
  'confirmed',
  'rejected',
  'stopped_for_budget'
])
const VERDICTS = new Set([
  'confirm_candidate',
  'request_evidence',
  'reject_hypothesis',
  'needs_more_evidence',
  'stop_for_budget'
])

export function isAttackPathMode(run) {
  return ATTACK_PATH_MODES.has(String(run?.mode || '').trim())
}

export function isV3AttackPathRun(run, featureFlags) {
  return isAttackPathMode(run) && featureFlags?.harness_v3 === true
}

export function attackPathEmptyStateMessage({
  runStatus = '',
  terminal = false,
  budgetExhausted = false,
} = {}) {
  if (runStatus === 'blocked') {
    return '该审计因证据或安全策略被阻断，未形成可验证的漏洞假设。'
  }
  if (budgetExhausted) {
    return '本次审计因预算上限收口，未形成可验证的漏洞假设。'
  }
  if (runStatus === 'completed_with_warnings') {
    return '本次审计已带警告收口；未形成可验证的漏洞假设。'
  }
  if (terminal) {
    return '本次审计未形成可验证的漏洞假设。'
  }
  return '正在等待确定性基线形成可验证假设。'
}

export function normalizeHypothesisListResponse(payload) {
  const source = isRecord(payload) ? payload : {}
  const items = Array.isArray(source.items)
    ? source.items.map(normalizeHypothesis).filter(Boolean)
    : []
  return {
    items,
    total: nonNegativeInteger(source.total, items.length),
    page: positiveInteger(source.page, 1),
    pageSize: positiveInteger(source.page_size, 20),
    metrics: normalizeHypothesisMetrics(source.metrics)
  }
}

export function normalizeHypothesisDetailResponse(payload) {
  const hypothesis = normalizeHypothesis(payload?.hypothesis)
  if (!hypothesis) return null
  const verdicts = Array.isArray(payload?.hypothesis?.verdicts)
    ? payload.hypothesis.verdicts.map(normalizeVerdict).filter(Boolean)
    : []
  return { ...hypothesis, verdicts }
}

export function normalizeHypothesisMetrics(value) {
  const source = isRecord(value) ? value : {}
  const total = nonNegativeInteger(source.hypothesis_count, 0)
  return {
    hypothesisCount: total,
    statusCounts: normalizeStatusCounts(source.status_counts),
    skillCounts: normalizeSkillCounts(source.skill_counts),
    codeEvidenceCoverage: rate(source.code_evidence_coverage),
    evidenceInsufficientRate: rate(source.evidence_insufficient_rate),
    budgetExhaustionRate: rate(source.budget_exhaustion_rate),
    deepReviewCost: normalizeDeepReviewCost(source.deep_review_cost)
  }
}

export function normalizeHypothesis(value) {
  if (!isRecord(value) || !positiveInteger(value.id, 0)) return null
  return {
    id: value.id,
    hypothesisKey: text(value.hypothesis_key, 64),
    skillKey: text(value.skill_key, 64),
    title: text(value.title, 200),
    targetSummary: text(value.target_summary, 1000),
    priority: nonNegativeInteger(value.priority, 0),
    status: HYPOTHESIS_STATUSES.has(value.status) ? value.status : 'unknown',
    plannerSource: text(value.planner_source, 64),
    requiredEvidence: textList(value.required_evidence, 12, 120),
    authorizedScopes: normalizeScopes(value.authorized_scopes),
    satisfiedEvidence: textList(value.satisfied_evidence, 12, 160),
    evidenceGaps: textList(value.evidence_gaps, 12, 240),
    reflectionCount: nonNegativeInteger(value.reflection_count, 0),
    executionAttemptCount: nonNegativeInteger(value.execution_attempt_count, 0),
    createdAt: text(value.created_at, 64),
    updatedAt: text(value.updated_at, 64)
  }
}

function normalizeVerdict(value) {
  if (!isRecord(value) || !positiveInteger(value.id, 0)) return null
  return {
    id: value.id,
    verdictVersion: positiveInteger(value.verdict_version, 1),
    verdict: VERDICTS.has(value.verdict) ? value.verdict : 'unknown',
    reasonSummary: text(value.reason_summary, 2000),
    evidenceGaps: textList(value.evidence_gaps, 12, 240),
    nextAction: text(value.next_action?.action, 120),
    criticVersion: text(value.critic_version, 64),
    createdAt: text(value.created_at, 64)
  }
}

function normalizeScopes(value) {
  if (!Array.isArray(value)) return []
  return value.slice(0, 12).flatMap((scope) => {
    const filePath = text(scope?.file_path, 500)
    const startLine = positiveInteger(scope?.start_line, 0)
    const endLine = positiveInteger(scope?.end_line, 0)
    if (!isSafeRelativePath(filePath) || !startLine || endLine < startLine) return []
    return [{ filePath, startLine, endLine }]
  })
}

function normalizeStatusCounts(value) {
  if (!isRecord(value)) return {}
  return Object.fromEntries(
    Object.entries(value)
      .filter(([status]) => HYPOTHESIS_STATUSES.has(status))
      .map(([status, count]) => [status, nonNegativeInteger(count, 0)])
  )
}

function normalizeSkillCounts(value) {
  if (!Array.isArray(value)) return []
  return value.slice(0, 12).flatMap((item) => {
    const skillKey = text(item?.skill_key, 64)
    if (!skillKey) return []
    return [{
      skillKey,
      candidateCount: nonNegativeInteger(item.candidate_count, 0)
    }]
  })
}

function normalizeDeepReviewCost(value) {
  const source = isRecord(value) ? value : {}
  const costKnown = source.cost_known === true
  return {
    callCount: nonNegativeInteger(source.call_count, 0),
    costKnown,
    totalCost: costKnown ? finiteNumber(source.total_cost) : null,
    averagePerHypothesis: costKnown
      ? finiteNumber(source.average_per_hypothesis)
      : null
  }
}

function rate(value) {
  const number = finiteNumber(value)
  return number == null || number < 0 || number > 1 ? null : number
}

function nonNegativeInteger(value, fallback) {
  return Number.isInteger(value) && value >= 0 ? value : fallback
}

function positiveInteger(value, fallback) {
  return Number.isInteger(value) && value > 0 ? value : fallback
}

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function text(value, maximum) {
  return typeof value === 'string' ? value.trim().slice(0, maximum) : ''
}

function isSafeRelativePath(value) {
  if (!value || value.includes('\\') || value.startsWith('/') || /^[A-Za-z]:/.test(value)) {
    return false
  }
  return !value.split('/').some((part) => part === '' || part === '.' || part === '..')
}

function textList(value, limit, maximum) {
  if (!Array.isArray(value)) return []
  return [...new Set(value.map((item) => text(item, maximum)).filter(Boolean))].slice(0, limit)
}

function isRecord(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}
