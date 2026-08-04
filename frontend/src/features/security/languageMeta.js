const languageDefinitions = [
  {
    key: 'python',
    match: /python/,
    code: 'PY',
    label: 'Python',
    color: '#2563eb'
  },
  {
    key: 'java',
    match: /java/,
    code: 'JV',
    label: 'Java',
    color: '#ea580c'
  },
  {
    key: 'javascript',
    match: /javascript|typescript|node/,
    code: 'JS',
    label: 'JavaScript / TypeScript',
    color: '#ca8a04'
  },
  {
    key: 'go',
    match: /^(go|golang)$/,
    code: 'GO',
    label: 'Go',
    color: '#16a34a'
  }
]

const fallback = { key: 'unknown', code: '??', label: '未知', color: '#94a3b8' }

export function languageMeta(raw) {
  const value = String(raw || '').trim().toLowerCase()
  if (!value) return fallback
  for (const definition of languageDefinitions) {
    if (definition.match.test(value)) return definition
  }
  return fallback
}
