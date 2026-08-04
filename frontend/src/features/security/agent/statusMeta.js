export const agentRunStatusMeta = {
  created: { label: '已创建', tagType: 'info' },
  queued: { label: '排队中', tagType: 'info' },
  preparing: { label: '准备中', tagType: 'warning' },
  mapping_repository: { label: '映射仓库', tagType: 'warning' },
  planning: { label: '规划中', tagType: 'warning' },
  validating_plan: { label: '校验计划', tagType: 'warning' },
  executing_tools: { label: '执行工具', tagType: 'primary' },
  evaluating_evidence: { label: '评估证据', tagType: 'primary' },
  replanning: { label: '重新规划', tagType: 'warning' },
  deep_reviewing: { label: '深度审查', tagType: 'primary' },
  awaiting_approval: { label: '等待审批', tagType: 'warning' },
  paused: { label: '已暂停', tagType: 'info' },
  generating_report: { label: '生成报告', tagType: 'primary' },
  completed: { label: '已完成', tagType: 'success' },
  completed_with_warnings: { label: '完成（有警告）', tagType: 'warning' },
  partial: { label: '部分完成', tagType: 'warning' },
  failed: { label: '失败', tagType: 'danger' },
  canceled: { label: '已取消', tagType: 'info' }
}

export const agentRunModeMeta = {
  baseline: { label: '基线扫描', description: '确定性扫描 + 覆盖报告' },
  hybrid: { label: '混合审计', description: '基线扫描 + Agent 语义分析' },
  deep_audit: { label: '深度审计', description: '全链路 LLM 深度审查' }
}

export const stepStatusMeta = {
  running: { label: '执行中', tagType: 'primary' },
  completed: { label: '完成', tagType: 'success' },
  failed: { label: '失败', tagType: 'danger' },
  pending: { label: '等待', tagType: 'info' },
  ready: { label: '就绪', tagType: 'info' },
  canceled: { label: '已取消', tagType: 'info' }
}

export const toolStatusMeta = {
  running: { label: '执行中', tagType: 'primary' },
  succeeded: { label: '成功', tagType: 'success' },
  failed: { label: '失败', tagType: 'danger' }
}

export const connectionStateMeta = {
  connecting: { label: '连接中', tagType: 'info' },
  connected: { label: '已连接', tagType: 'success' },
  reconnecting: { label: '重连中', tagType: 'warning' },
  resyncing: { label: '状态同步', tagType: 'warning' },
  closed: { label: '已断开', tagType: 'info' }
}

export function agentStatusMeta(status) {
  return agentRunStatusMeta[status] || { label: status || '-', tagType: 'info' }
}

export function agentModeMeta(mode) {
  return agentRunModeMeta[mode] || { label: mode || '-', description: '' }
}

export function stepStatusMetaOf(status) {
  return stepStatusMeta[status] || { label: status || '-', tagType: 'info' }
}

export function toolStatusMetaOf(status) {
  return toolStatusMeta[status] || { label: status || '-', tagType: 'info' }
}

export function connectionStateMetaOf(state) {
  return connectionStateMeta[state] || { label: state || '-', tagType: 'info' }
}

export function plannerSourceLabel(source) {
  if (source === 'llm_live') return { label: '真实 LLM 计划', tagType: 'success' }
  if (source === 'rule_based_policy') return { label: '本地策略计划', tagType: 'warning' }
  return { label: source || '未生成', tagType: 'info' }
}
