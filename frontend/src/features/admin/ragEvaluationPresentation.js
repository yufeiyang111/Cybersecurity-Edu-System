import {
  isPlainObject,
  nonNegativeInteger,
  positiveInteger,
  shortText
} from './ragDiagnosticsPresentation.js'

const RETRIEVAL_METRICS = [
  ['recall_at_20', 'Recall@20'],
  ['recall_at_40', 'Recall@40'],
  ['mrr_at_20', 'MRR@20'],
  ['ndcg_at_10', 'nDCG@10']
]

const EVIDENCE_METRICS = [
  ['expected_evidence_coverage', '证据覆盖'],
  ['context_precision', '上下文精度'],
  ['source_diversity', '来源多样性'],
  ['token_utilization', '预算利用率']
]

const CITATION_METRICS = [
  ['status_matches_expected', '状态匹配'],
  ['citations_belong_to_pack', '引用归属'],
  ['is_deterministic', '引用确定性'],
  ['unsafe_supported_negative_count', '危险负例', 'count']
]

const RUNTIME_METRICS = [
  ['retrieval_p50_ms', '检索 P50', 'duration'],
  ['retrieval_p95_ms', '检索 P95', 'duration'],
  ['rerank_p50_ms', '重排 P50', 'duration'],
  ['rerank_p95_ms', '重排 P95', 'duration']
]

const RUN_STATUSES = new Set([
  'completed',
  'completed_with_failures',
  'running',
  'failed'
])
const MAX_FAILURE_STAGE_COUNT = 6

export function normalizeEvaluationRunsResponse(value) {
  const source = isPlainObject(value) ? value : {}
  const runs = Array.isArray(source.runs)
    ? source.runs.map(normalizeEvaluationRun).filter(Boolean)
    : []

  return {
    runs,
    total: nonNegativeInteger(source.total) ?? 0,
    page: positiveInteger(source.page) ?? 1,
    perPage: positiveInteger(source.per_page) ?? 20,
    pages: nonNegativeInteger(source.pages) ?? 0
  }
}

export function normalizeEvaluationRunDetailResponse(value) {
  const source = isPlainObject(value) ? value : {}
  const run = normalizeEvaluationRun(source.run)
  if (!run) {
    return null
  }

  const results = Array.isArray(source.results) ? source.results : []
  return {
    run,
    resultTotal: nonNegativeInteger(source.result_page?.total) ?? results.length,
    failureStages: countFailureStages(results),
    page: positiveInteger(source.result_page?.page) ?? 1,
    pages: nonNegativeInteger(source.result_page?.pages) ?? 0
  }
}

function normalizeEvaluationRun(value) {
  if (!isPlainObject(value) || !positiveInteger(value.id)) {
    return null
  }
  return {
    id: positiveInteger(value.id),
    pipelineVersionId: positiveInteger(value.pipeline_version_id),
    corpusVersion: shortText(value.corpus_version, 128) || '未提供',
    status: RUN_STATUSES.has(value.status) ? value.status : 'unknown',
    startedAt: shortText(value.started_at, 64),
    finishedAt: shortText(value.finished_at, 64),
    metricGroups: normalizeMetricGroups(value.metrics)
  }
}

function normalizeMetricGroups(value) {
  const source = isPlainObject(value) ? value : {}
  return [
    metricGroup('检索质量', source.retrieval, RETRIEVAL_METRICS),
    metricGroup('证据质量', source.evidence, EVIDENCE_METRICS),
    metricGroup('引用治理', source.citation, CITATION_METRICS),
    metricGroup('运行耗时', source.runtime, RUNTIME_METRICS)
  ].filter((group) => group.items.length > 0)
}

function metricGroup(title, source, definitions) {
  const metrics = isPlainObject(source) ? source : {}
  return {
    title,
    items: definitions
      .map(([key, label, kind]) => normalizeMetricItem(label, metrics[key], kind))
      .filter(Boolean)
  }
}

function normalizeMetricItem(label, value, kind) {
  if (typeof value === 'boolean') {
    return { label, value: value ? '通过' : '未通过' }
  }
  if (kind === 'count') {
    const count = nonNegativeInteger(value)
    if (count === null) {
      return null
    }
    return { label, value: String(count) }
  }

  const number = finiteNumber(value)
  if (number === null) {
    return null
  }
  if (kind === 'duration') {
    return { label, value: `${Math.round(number)} ms` }
  }
  return { label, value: `${(number * 100).toFixed(1)}%` }
}

function countFailureStages(results) {
  const counts = new Map()
  results.forEach((result) => {
    const stage = shortText(result?.failure_stage, 64)
    if (!stage || !/^[a-z0-9_-]+$/i.test(stage)) {
      return
    }
    counts.set(stage, (counts.get(stage) || 0) + 1)
  })
  return [...counts.entries()]
    .map(([key, count]) => ({ key, count }))
    .sort((left, right) => right.count - left.count || left.key.localeCompare(right.key))
    .slice(0, MAX_FAILURE_STAGE_COUNT)
}

function finiteNumber(value) {
  if (typeof value === 'boolean' || value === null || value === '') {
    return null
  }
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}
