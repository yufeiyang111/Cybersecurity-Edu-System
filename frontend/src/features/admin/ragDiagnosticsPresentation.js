const ANSWER_STATUS_LABELS = {
  supported: '证据充分',
  insufficient_evidence: '证据不足',
  conflicting_evidence: '资料冲突',
  degraded: '链路降级'
}

const RUN_STATUS_LABELS = {
  completed: '已完成',
  completed_with_failures: '完成但有失败',
  running: '运行中',
  failed: '执行失败'
}

export function runStatusPresentation(status) {
  const label = RUN_STATUS_LABELS[status] || '未知状态'
  if (status === 'completed') {
    return { label, tone: 'success' }
  }
  if (status === 'running') {
    return { label, tone: 'info' }
  }
  if (status === 'completed_with_failures') {
    return { label, tone: 'warning' }
  }
  return { label, tone: 'danger' }
}

export function answerStatusPresentation(status) {
  const label = ANSWER_STATUS_LABELS[status] || '未提供'
  if (status === 'supported') {
    return { label, tone: 'success' }
  }
  if (status === 'insufficient_evidence' || status === 'conflicting_evidence') {
    return { label, tone: 'warning' }
  }
  if (status === 'degraded') {
    return { label, tone: 'danger' }
  }
  return { label, tone: 'muted' }
}

export function formatDuration(value) {
  const duration = nonNegativeInteger(value)
  if (duration === null) {
    return '未提供'
  }
  return `${duration} ms`
}

export function formatDateTime(value) {
  const normalized = shortText(value, 64)
  if (!normalized) {
    return '未提供'
  }
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) {
    return '未提供'
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

export function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function positiveInteger(value) {
  const number = finiteNumber(value)
  if (number === null || !Number.isInteger(number) || number <= 0) {
    return null
  }
  return number
}

export function nonNegativeInteger(value) {
  const number = finiteNumber(value)
  if (number === null || !Number.isInteger(number) || number < 0) {
    return null
  }
  return number
}

export function shortText(value, maxLength) {
  if (typeof value !== 'string') {
    return ''
  }
  return value.trim().slice(0, maxLength)
}

function finiteNumber(value) {
  if (typeof value === 'boolean' || value === null || value === '') {
    return null
  }
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}
