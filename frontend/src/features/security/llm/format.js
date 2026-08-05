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
  if (!value) return '未记录'
  const date = new Date(value)
  const diff = Math.max(0, Date.now() - date.getTime())
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes || 1} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  return `${Math.floor(hours / 24)} 天前`
}

export function formatLogDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

export function providerStatus(provider) {
  if (!provider?.is_enabled) return { label: '已禁用', tone: 'gray' }
  if (provider.last_check_status === 'healthy') return { label: '已连接', tone: 'green' }
  if (provider.last_check_status) return { label: '连接异常', tone: 'red' }
  return { label: '未验证', tone: 'gray' }
}
