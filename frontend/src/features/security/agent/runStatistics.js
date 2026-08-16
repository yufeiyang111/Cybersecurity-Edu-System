const RUN_STATISTIC_KEYS = [
  'plan_node_total',
  'plan_node_completed',
  'plan_node_failed',
  'turn_total',
  'tool_call_total',
  'tool_call_succeeded',
  'tool_call_failed',
  'observation_total',
  'observation_with_code_evidence',
  'observation_unverified',
  'replan_total',
  'approval_pending',
  'warning_total'
]

function isNonNegativeInteger(value) {
  return Number.isSafeInteger(value) && value >= 0
}

function numberOrFallback(value, fallback = 0) {
  return isNonNegativeInteger(value) ? value : fallback
}

function statusValue(value) {
  return typeof value === 'string' ? value : ''
}

function planNodeFallback(plan) {
  const nodes = Array.isArray(plan?.nodes) ? plan.nodes : []
  return {
    total: nodes.length,
    completed: nodes.filter((node) => {
      return ['succeeded', 'completed'].includes(statusValue(node?.status))
    }).length,
    failed: nodes.filter((node) => {
      return statusValue(node?.status) === 'failed'
    }).length
  }
}

/**
 * 只接受后端显式返回的非负整数统计，避免接口异常值污染进度展示。
 */
export function normalizeRunStatistics(stats) {
  const source = stats && typeof stats === 'object' ? stats : {}
  return RUN_STATISTIC_KEYS.reduce((normalized, key) => {
    normalized[key] = numberOrFallback(source[key])
    return normalized
  }, {})
}

/**
 * 生成页面展示所需的统计值。
 *
 * 新接口的 ``stats`` 是权威总量，不能用当前 50 条分页步骤或工具调用数组替代。
 * 旧快照未提供 ``stats`` 时，只有 Run 本身和完整计划可安全作为有限降级来源；
 * 成功/失败工具数、Observation 和审批数不从当前页数组推断，避免伪造总量。
 */
export function resolveRunStatistics({ stats, run, plan } = {}) {
  const normalized = normalizeRunStatistics(stats)
  const nodeFallback = planNodeFallback(plan)
  const warningFallback = Array.isArray(run?.warning_codes)
    ? run.warning_codes.length
    : 0

  return {
    plan_node_total: numberOrFallback(stats?.plan_node_total, nodeFallback.total),
    plan_node_completed: numberOrFallback(
      stats?.plan_node_completed,
      nodeFallback.completed
    ),
    plan_node_failed: numberOrFallback(stats?.plan_node_failed, nodeFallback.failed),
    turn_total: numberOrFallback(stats?.turn_total, numberOrFallback(run?.iteration_count)),
    tool_call_total: numberOrFallback(
      stats?.tool_call_total,
      numberOrFallback(run?.tool_call_count)
    ),
    tool_call_succeeded: normalized.tool_call_succeeded,
    tool_call_failed: normalized.tool_call_failed,
    observation_total: normalized.observation_total,
    observation_with_code_evidence: normalized.observation_with_code_evidence,
    observation_unverified: normalized.observation_unverified,
    replan_total: numberOrFallback(
      stats?.replan_total,
      numberOrFallback(run?.replan_count)
    ),
    approval_pending: normalized.approval_pending,
    warning_total: numberOrFallback(stats?.warning_total, warningFallback)
  }
}