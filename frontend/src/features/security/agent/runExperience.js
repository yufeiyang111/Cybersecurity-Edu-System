const MODE_LABELS = {
  baseline: '基础审计工作流',
  hybrid: '混合审计',
  deep_audit: '深度审计'
}

export function resolveAgentRunExperience(run, featureFlags = {}) {
  const mode = String(run?.mode || 'baseline')
  const loopV2Enabled = featureFlags?.loop_v2 === true

  if (mode === 'baseline') {
    return {
      kind: 'workflow',
      label: MODE_LABELS.baseline,
      description: '按固定审计步骤执行确定性扫描与覆盖评估，不支持运行中追加方向。',
      supportsDynamicControl: false,
      supportsAutonomousTools: false
    }
  }

  if (!loopV2Enabled) {
    return {
      kind: 'workflow_limited',
      label: `${MODE_LABELS[mode] || '审计工作流'}（Loop 未启用）`,
      description: '当前工作区未启用模型在环 Loop；本轮按受限工作流执行，不支持运行中追加方向。',
      supportsDynamicControl: false,
      supportsAutonomousTools: false
    }
  }

  return {
    kind: 'agentic',
    label: `${MODE_LABELS[mode] || '审计'} Agent Loop`,
    description: '模型会基于已授权的工具结果决定后续步骤；运行中方向会作为有序控制输入进入 Loop。',
    supportsDynamicControl: true,
    supportsAutonomousTools: true
  }
}