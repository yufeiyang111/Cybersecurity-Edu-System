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
  pipelineVersion,
  isStreaming = false
} = {}) {
  const manifest = normalizeCitationManifest(citations)
  const normalizedStatus = ANSWER_STATUSES.has(answerStatus) ? answerStatus : null

  if (isStreaming) {
    return {
      answerStatus: normalizedStatus,
      citationManifest: manifest,
      citationState: 'pending'
    }
  }
  if (!isNonEmptyString(pipelineVersion)) {
    return {
      answerStatus: normalizedStatus,
      citationManifest: manifest,
      citationState: 'legacy'
    }
  }
  if (!normalizedStatus || !manifest.isValid) {
    return {
      answerStatus: 'degraded',
      citationManifest: manifest,
      citationState: 'degraded'
    }
  }
  return {
    answerStatus: normalizedStatus,
    citationManifest: manifest,
    citationState: 'ready'
  }
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
