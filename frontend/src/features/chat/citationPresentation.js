import {
  hasNavigableDocument,
  normalizeCitationDetail,
  normalizeCitationManifest
} from './citationManifest.js'

const ANSWER_STATUSES = new Set([
  'supported',
  'insufficient_evidence',
  'conflicting_evidence',
  'degraded'
])

const STATUS_PRESENTATIONS = {
  supported: {
    label: '证据充分',
    description: '已找到可追溯资料支撑回答。',
    tone: 'success'
  },
  insufficient_evidence: {
    label: '证据不足',
    description: '当前知识库无法充分支撑该结论。',
    tone: 'warning'
  },
  conflicting_evidence: {
    label: '资料冲突',
    description: '已检索到适用条件或版本不同的资料。',
    tone: 'warning'
  },
  degraded: {
    label: '链路降级',
    description: '回答或引用未完成完整校验，请谨慎核验。',
    tone: 'danger'
  },
  legacy: {
    label: '历史记录',
    description: '该记录未保存可核验引用清单。',
    tone: 'muted'
  },
  pending: {
    label: '证据处理中',
    description: '正在等待本次回答的证据清单。',
    tone: 'muted'
  }
}

const RETRIEVAL_SIGNAL_PRESENTATIONS = {
  high: {
    label: '高',
    description: '检索辅助信号，不代表回答正确率。'
  },
  medium: {
    label: '中',
    description: '检索辅助信号，不代表回答正确率。'
  },
  low: {
    label: '低',
    description: '检索辅助信号，不代表回答正确率。'
  },
  unavailable: {
    label: '暂不可用',
    description: '当前记录没有可展示的检索辅助信号。'
  }
}

export function normalizeAssistantEvidence({
  answerStatus,
  citations,
  sources,
  pipelineVersion,
  isStreaming = false
} = {}) {
  const manifest = normalizeCitationManifest(citations)
  const normalizedStatus = ANSWER_STATUSES.has(answerStatus) ? answerStatus : null
  const legacySources = normalizeLegacySources(sources)

  if (isStreaming) {
    return {
      answerStatus: normalizedStatus,
      citationManifest: manifest,
      citationState: 'pending',
      legacySources
    }
  }
  if (!isNonEmptyString(pipelineVersion)) {
    return {
      answerStatus: normalizedStatus,
      citationManifest: manifest,
      citationState: 'legacy',
      legacySources
    }
  }
  if (!normalizedStatus || !manifest.isValid) {
    return {
      answerStatus: 'degraded',
      citationManifest: manifest,
      citationState: 'degraded',
      legacySources
    }
  }
  return {
    answerStatus: normalizedStatus,
    citationManifest: manifest,
    citationState: 'ready',
    legacySources
  }
}

export function normalizeLegacySources(value) {
  if (!Array.isArray(value)) {
    return []
  }

  const normalized = []
  const seen = new Set()
  for (const item of value) {
    if (!isPlainObject(item)) {
      continue
    }

    const source = shortText(item.source || item.source_type)
    const title = shortText(item.title || item.name) || source
    if (!title) {
      continue
    }

    const startLine = positiveInteger(item.start_line ?? item.startLine)
    const candidateEndLine = positiveInteger(item.end_line ?? item.endLine)
    const endLine = candidateEndLine && startLine && candidateEndLine < startLine
      ? null
      : candidateEndLine
    const fingerprint = `${title}\u0000${source || ''}\u0000${startLine || ''}\u0000${endLine || ''}`
    if (seen.has(fingerprint)) {
      continue
    }

    seen.add(fingerprint)
    normalized.push({
      title,
      source,
      startLine,
      endLine
    })
    if (normalized.length >= 8) {
      break
    }
  }
  return normalized
}

export function normalizeEvidenceResponse(value) {
  const evidence = isPlainObject(value?.evidence) ? value.evidence : value
  if (!isPlainObject(evidence)) {
    return null
  }

  const manifest = normalizeCitationManifest(evidence.citations)
  const citationDetails = Array.isArray(evidence.citation_details)
    ? evidence.citation_details
      .map((detail) => normalizeCitationDetail(detail, manifest.citations))
      .filter(Boolean)
    : []

  return {
    recordId: positiveInteger(evidence.record_id),
    answerStatus: ANSWER_STATUSES.has(evidence.answer_status)
      ? evidence.answer_status
      : null,
    citationManifest: manifest,
    citationDetails,
    citationDetailsTruncated: evidence.citation_details_truncated === true,
    retrievalSignal: normalizeRetrievalSignal(evidence.retrieval_signal)
  }
}

export function citationUsagePresentation(status, citationCount = 0) {
  const count = Number.isInteger(citationCount) && citationCount > 0
    ? citationCount
    : 0

  if (status === 'supported') {
    return {
      ariaLabel: '可核验证据',
      title: '引用证据',
      description: '原文预览由服务端按当前问答记录授权返回，可支撑本回答结论。',
      countLabel: `${count} 条可核验引用`,
      actionLabel: '查看证据',
      itemLabel: '已验证引用',
      showClaimCount: true
    }
  }

  if (status === 'insufficient_evidence') {
    return {
      ariaLabel: '相关参考资料',
      title: '相关参考资料',
      description: '以下资料仅供继续阅读，未作为本回答结论的支撑依据。',
      countLabel: `检索到 ${count} 条相关参考资料，未作为本回答的结论依据。`,
      actionLabel: '查看相关资料',
      itemLabel: '相关资料',
      showClaimCount: false
    }
  }

  if (status === 'conflicting_evidence') {
    return {
      ariaLabel: '存在冲突的参考资料',
      title: '冲突参考资料',
      description: '以下资料可能适用于不同条件或版本，不能作为单一结论的支撑依据。',
      countLabel: `检索到 ${count} 条存在冲突的参考资料。`,
      actionLabel: '查看冲突资料',
      itemLabel: '冲突资料',
      showClaimCount: false
    }
  }

  return {
    ariaLabel: '待核验资料',
    title: '待核验资料',
    description: '以下资料尚未完成完整证据校验，请结合原文谨慎判断。',
    countLabel: `检索到 ${count} 条待核验资料。`,
    actionLabel: '查看资料',
    itemLabel: '待核验资料',
    showClaimCount: false
  }
}
export function answerStatusPresentation(status, citationState = 'ready') {
  if (citationState === 'pending') {
    return STATUS_PRESENTATIONS.pending
  }
  if (citationState === 'legacy') {
    return STATUS_PRESENTATIONS.legacy
  }
  if (citationState === 'degraded') {
    return STATUS_PRESENTATIONS.degraded
  }
  return STATUS_PRESENTATIONS[status] || STATUS_PRESENTATIONS.degraded
}

export function retrievalSignalPresentation(signal) {
  const normalized = normalizeRetrievalSignal(signal)
  return {
    ...RETRIEVAL_SIGNAL_PRESENTATIONS[normalized.level],
    isCalibrated: false
  }
}

export {
  hasNavigableDocument,
  normalizeCitationManifest
}

function normalizeRetrievalSignal(value) {
  const level = isPlainObject(value) ? value.level : null
  return {
    level: Object.hasOwn(RETRIEVAL_SIGNAL_PRESENTATIONS, level)
      ? level
      : 'unavailable',
    isCalibrated: false
  }
}

function shortText(value) {
  if (!isNonEmptyString(value)) {
    return null
  }
  return value.trim().slice(0, 300)
}

function positiveInteger(value) {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) {
    return value
  }
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) {
    const normalized = Number(value)
    return Number.isSafeInteger(normalized) && normalized > 0 ? normalized : null
  }
  return null
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0
}
