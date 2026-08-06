export function formatMoney(value, currency = '¥') {
  const amount = Number(value || 0)
  return `${currency}${amount.toFixed(4)}`
}

export function formatInteger(value) {
  return Number(value || 0).toLocaleString('zh-CN')
}

export function formatDuration(value) {
  const seconds = Number(value || 0) / 1000
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`
}

export function formatRelativeTime(value) {
  const date = parseUtcDate(value)
  if (!date) return '未记录'
  const diff = Math.max(0, Date.now() - date.getTime())
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes || 1} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  return `${Math.floor(hours / 24)} 天前`
}

export function formatLogDate(value) {
  const date = parseUtcDate(value)
  if (!date) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function parseUtcDate(value) {
  if (!value) return null
  const text = String(value).trim()
  if (!text) return null
  const hasTimezone = /[zZ]$/.test(text) || /[+-]\d{2}:\d{2}$/.test(text)
  const normalized = hasTimezone ? text : `${text}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function providerStatus(provider) {
  if (!provider?.is_enabled) return { label: '已禁用', tone: 'gray' }
  if (provider.last_check_status === 'healthy') return { label: '已连接', tone: 'green' }
  if (provider.last_check_status) return { label: '连接异常', tone: 'red' }
  return { label: '未验证', tone: 'gray' }
}
