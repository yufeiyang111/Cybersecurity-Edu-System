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
  blocked: { label: '证据不足，待补充', tagType: 'warning' },
  cancel_requested: { label: '取消收尾中', tagType: 'warning' },
  partial: { label: '历史部分结果', tagType: 'warning' },
  failed: { label: '失败', tagType: 'danger' },
  canceled: { label: '已取消', tagType: 'info' }
}

const terminalRunStatuses = new Set([
  'completed',
  'completed_with_warnings',
  'blocked',
  'partial',
  'failed',
  'canceled'
])

export const agentRunModeMeta = {
  baseline: {
    label: '基础审计工作流',
    description: '确定性扫描与覆盖评估；运行中不支持追加方向'
  },
  hybrid: {
    label: '混合审计',
    description: '启用 Agent Loop 时才提供模型在环能力'
  },
  deep_audit: {
    label: '深度审计',
    description: '启用 Agent Loop 时才允许模型基于工具结果继续审查'
  }
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
  closed: { label: '已结束', tagType: 'info' }
}

export function isTerminalAgentRunStatus(status) {
  return terminalRunStatuses.has(status)
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

const TOOL_NAME_LABELS = {
  inventory_snapshot: '清点快照',
  run_baseline_scan: '基线扫描',
  get_dependency_inventory: '依赖库存',
  get_scan_coverage: '扫描覆盖',
  rank_findings: '风险排序',
  get_findings: '查询发现',
  finalize_agent_report: '生成摘要',
  map_repository: '映射仓库',
  search_code: '代码搜索',
  read_code_slice: '代码切片',
  run_deep_review: '执行深度证据审查'
}

export function toolNameLabel(toolName) {
  return TOOL_NAME_LABELS[toolName] || toolName || '未知工具'
}
