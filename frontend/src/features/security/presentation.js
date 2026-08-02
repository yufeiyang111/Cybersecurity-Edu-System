const reviewStateDefinitions = {
  pending: { label: '待审核', tagType: 'info' },
  accepted: { label: '已接受', tagType: 'success' },
  rejected: { label: '已拒绝', tagType: 'danger' },
  needs_revision: { label: '需修改', tagType: 'warning' }
}

export function formatSecurityDate(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}

export function reviewStateLabel(state) {
  return reviewStateDefinitions[state]?.label || state || '-'
}

export function reviewStateTagType(state) {
  return reviewStateDefinitions[state]?.tagType || 'info'
}

export function securityApiErrorMessage(error, fallback) {
  return error?.response?.data?.error || fallback
}

const riskPriorityDefinitions = {
  critical: { label: '严重', tagType: 'danger' },
  high: { label: '高危', tagType: 'danger' },
  medium: { label: '中危', tagType: 'warning' },
  low: { label: '低危', tagType: 'success' }
}

const riskFactorLabels = {
  severity: '严重度',
  confidence: '置信度',
  exploitability: '可利用性',
  internet_exposure: '互联网暴露面',
  asset_criticality: '资产关键度',
  data_sensitivity: '数据敏感度',
  dependency_reachability: '依赖可达性',
  exploit_maturity: '利用成熟度',
  fix_availability: '修复可用性',
  age: '存续时长'
}

export function riskPriorityMeta(priority) {
  return riskPriorityDefinitions[priority] || { label: priority || '-', tagType: 'info' }
}

export function riskFactorLabel(name) {
  return riskFactorLabels[name] || name || '-'
}

export function riskScoreColor(score) {
  if (score >= 80) return '#b42318'
  if (score >= 60) return '#c2410c'
  if (score >= 35) return '#b54708'
  return '#0e9384'
}
