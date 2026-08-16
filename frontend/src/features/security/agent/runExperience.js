const MODE_LABELS = {
  baseline: '基础审计工作流',
  hybrid: '混合审计',
  deep_audit: '深度审计'
}

const FLAG_KEYS = ['loop_v2', 'event_schema_v2', 'timeline_v2']

function hasResolvedFlags(flags) {
  return FLAG_KEYS.some((key) => typeof flags?.[key] === 'boolean')
}

function hasSameFlags(left, right) {
  return FLAG_KEYS.every((key) => left?.[key] === right?.[key])
}

function resolveExecutionSource(run) {
  const source = String(run?.execution_feature_flag_source || '')
  return ['run_snapshot', 'legacy_observed', 'workspace_fallback'].includes(source)
    ? source
    : 'workspace_fallback'
}

function configurationNote(source, executionFlags, workspaceFlags) {
  if (source === 'legacy_observed') {
    return '历史任务未保存功能开关快照，系统已依据已记录的 v2 事件和模型轮次还原实际执行方式。'
  }

  if (source === 'run_snapshot') {
    if (hasResolvedFlags(workspaceFlags) && !hasSameFlags(executionFlags, workspaceFlags)) {
      return '本任务创建时的功能开关快照与当前工作区不同；任务已按创建时快照执行，后续配置不会改写历史执行方式。'
    }
    return '本任务按创建时的功能开关快照执行。'
  }

  return ''
}

export function resolveAgentRunExperience(run, featureFlags = {}, workspaceFeatureFlags = {}) {
  const mode = String(run?.mode || 'baseline')
  const source = resolveExecutionSource(run)
  const loopV2Enabled = featureFlags?.loop_v2 === true
  const note = configurationNote(source, featureFlags, workspaceFeatureFlags)

  if (mode === 'baseline') {
    return {
      kind: 'workflow',
      label: MODE_LABELS.baseline,
      description: '按固定审计步骤执行确定性扫描与覆盖评估，不支持运行中追加方向。',
      configurationNote: note,
      supportsDynamicControl: false,
      supportsAutonomousTools: false
    }
  }

  if (!loopV2Enabled) {
    return {
      kind: 'workflow_limited',
      label: (MODE_LABELS[mode] || '审计工作流') + '（Loop 未启用）',
      description: '本轮未启用模型在环 Loop；按受限工作流执行，不支持运行中追加方向。',
      configurationNote: note,
      supportsDynamicControl: false,
      supportsAutonomousTools: false
    }
  }

  return {
    kind: 'agentic',
    label: (MODE_LABELS[mode] || '审计') + ' Agent Loop',
    description: '模型基于已授权的工具结果决定后续步骤；运行中方向会作为有序控制输入进入 Loop。',
    configurationNote: note,
    supportsDynamicControl: true,
    supportsAutonomousTools: true
  }
}
