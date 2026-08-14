import {
  isPlainObject,
  nonNegativeInteger,
  positiveInteger,
  shortText
} from './ragDiagnosticsPresentation.js'

const RETRIEVAL_PATHS = {
  dense_only: 'Dense',
  bm25_only: 'BM25',
  both: 'RRF 融合',
  lexical_only_degraded: '词法降级',
  legacy: '兼容链路',
  unknown: '未知路径'
}

const MAX_WARNING_COUNT = 8
const MAX_COUNT_ITEMS = 6
const ANSWER_STATUSES = new Set([
  'supported',
  'insufficient_evidence',
  'conflicting_evidence',
  'degraded'
])

export function normalizeRagTraceResponse(value) {
  const trace = isPlainObject(value?.trace) ? value.trace : value
  if (!isPlainObject(trace) || !positiveInteger(trace.id)) {
    return null
  }

  const stages = isPlainObject(trace.stage_summary) ? trace.stage_summary : {}
  return {
    id: positiveInteger(trace.id),
    pipelineVersionId: positiveInteger(trace.pipeline_version_id),
    retrievalMs: nonNegativeInteger(trace.retrieval_ms),
    createdAt: shortText(trace.created_at, 64),
    warnings: normalizeWarningCodes(trace.warnings),
    candidate: normalizeCandidateStage(stages.candidate),
    rerank: normalizeRerankStage(stages.rerank),
    evidence: normalizeEvidenceStage(stages.evidence),
    answer: normalizeAnswerStage(stages.answer)
  }
}

function normalizeCandidateStage(value) {
  const source = isPlainObject(value) ? value : {}
  const rawPaths = isPlainObject(source.retrieval_paths)
    ? source.retrieval_paths
    : {}
  const retrievalPaths = Object.entries(RETRIEVAL_PATHS)
    .map(([key, label]) => ({
      label,
      count: nonNegativeInteger(rawPaths[key])
    }))
    .filter((item) => item.count !== null)

  return {
    candidateCount: nonNegativeInteger(source.candidate_count),
    degraded: source.degraded === true,
    retrievalPaths
  }
}

function normalizeRerankStage(value) {
  const source = isPlainObject(value) ? value : {}
  const status = ['completed', 'failed', 'skipped'].includes(source.status)
    ? source.status
    : 'unavailable'
  return {
    status,
    inputCount: nonNegativeInteger(source.input_count),
    outputCount: nonNegativeInteger(source.output_count),
    elapsedMs: nonNegativeInteger(source.elapsed_ms)
  }
}

function normalizeEvidenceStage(value) {
  const source = isPlainObject(value) ? value : {}
  return {
    answerStatus: safeAnswerStatus(source.answer_status),
    referenceCount: nonNegativeInteger(source.reference_count),
    tokenCount: nonNegativeInteger(source.token_count),
    tokenBudget: positiveInteger(source.token_budget),
    rejectionCounts: normalizeCountEntries(source.rejection_counts)
  }
}

function normalizeAnswerStage(value) {
  const source = isPlainObject(value) ? value : {}
  return {
    answerStatus: safeAnswerStatus(source.answer_status),
    citationCount: nonNegativeInteger(source.citation_count),
    claimCount: nonNegativeInteger(source.claim_count),
    warningCount: nonNegativeInteger(source.warning_count)
  }
}

function normalizeCountEntries(value) {
  if (!isPlainObject(value)) {
    return []
  }
  return Object.entries(value)
    .filter(([key]) => /^[a-z_]{1,48}$/i.test(key))
    .map(([key, count]) => ({
      key,
      count: nonNegativeInteger(count)
    }))
    .filter((item) => item.count !== null)
    .sort((left, right) => right.count - left.count || left.key.localeCompare(right.key))
    .slice(0, MAX_COUNT_ITEMS)
}

function normalizeWarningCodes(value) {
  if (!Array.isArray(value)) {
    return []
  }
  const validCodes = value
    .map((item) => shortText(item, 64))
    .filter((item) => item && /^[A-Z0-9_-]+$/.test(item))
  return [...new Set(validCodes)].slice(0, MAX_WARNING_COUNT)
}

function safeAnswerStatus(value) {
  return ANSWER_STATUSES.has(value) ? value : null
}
