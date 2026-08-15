const MAX_STAGE_COUNT = 999

export function normalizeRagProcessSummary(value) {
  const stageSummary = isPlainObject(value?.stage_summary)
    ? value.stage_summary
    : null
  if (!stageSummary) {
    return null
  }

  const candidate = isPlainObject(stageSummary.candidate)
    ? stageSummary.candidate
    : null
  const rerank = isPlainObject(stageSummary.rerank)
    ? stageSummary.rerank
    : null
  const evidence = isPlainObject(stageSummary.evidence)
    ? stageSummary.evidence
    : null
  const generation = isPlainObject(stageSummary.generation)
    ? stageSummary.generation
    : null

  const steps = [
    candidate && stageStep('候选召回', positiveCount(candidate.candidate_count)),
    rerank && stageStep('重排筛选', positiveCount(rerank.output_count)),
    evidence && stageStep('可用证据', positiveCount(evidence.reference_count)),
    generation && generation.status === 'completed'
      ? { label: '回答生成', detail: '已完成' }
      : null
  ].filter(Boolean)

  return steps.length ? { steps } : null
}

function stageStep(label, count) {
  if (count === null) {
    return null
  }
  return { label, detail: `${count} 项` }
}

function positiveCount(value) {
  if (!Number.isInteger(value) || value < 0) {
    return null
  }
  return Math.min(value, MAX_STAGE_COUNT)
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}