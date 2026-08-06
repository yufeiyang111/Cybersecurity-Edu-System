const TITLE_LIMIT = 28

export function titleFromQuestion(question) {
  const normalized = String(question || '')
    .replace(/\s+/g, ' ')
    .replace(/^[\s\d.)、-]+/, '')
    .replace(/[?？。！!]+$/, '')
    .trim()

  if (!normalized) return '新会话'
  return normalized.length > TITLE_LIMIT
    ? `${normalized.slice(0, TITLE_LIMIT)}…`
    : normalized
}
