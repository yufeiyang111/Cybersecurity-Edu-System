const RUN_STATISTIC_KEYS = [
  'plan_node_total',
  'plan_node_completed',
  'plan_node_failed',
  'turn_total',
  'llm_call_total',
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
    llm_call_total: numberOrFallback(
      stats?.llm_call_total,
      numberOrFallback(run?.llm_call_count)
    ),
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

function isHarnessV3Run(run) {
  const mode = typeof run?.mode === 'string' ? run.mode : ''
  if (!['hybrid', 'deep_audit'].includes(mode)) {
    return false
  }

  const featureFlags = run?.execution_feature_flags ?? run?.feature_flags_snapshot
  return featureFlags?.harness_v3 === true
}

/**
 * 将不同 Harness 的模型活动转化为不误导用户的展示指标。
 *
 * V3 的 ``iteration_count`` 仅代表旧 Loop 决策轮次，不能用它覆盖
 * Provider 规划和 Deep Review 的真实调用；旧执行模式继续保留原有轮次口径。
 */
export function resolveModelActivityMetric({ run, statistics } = {}) {
  const source = statistics && typeof statistics === 'object' ? statistics : {}

  if (isHarnessV3Run(run)) {
    return {
      label: 'Provider 调用',
      value: numberOrFallback(source.llm_call_total, numberOrFallback(run?.llm_call_count)),
      hint: '受限规划与 Deep Review 的真实 Provider 调用'
    }
  }

  return {
    label: '模型轮次',
    value: numberOrFallback(source.turn_total, numberOrFallback(run?.iteration_count)),
    hint: '每次模型决策算 1 轮'
  }
}
