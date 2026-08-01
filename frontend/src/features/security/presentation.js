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
