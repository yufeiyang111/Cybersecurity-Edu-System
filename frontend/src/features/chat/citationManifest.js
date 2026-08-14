const MAX_CITATION_TEXT_LENGTH = 128

export function normalizeCitationManifest(value) {
  const manifest = Array.isArray(value)
    ? { citations: value, claim_citations: {} }
    : value

  if (!isPlainObject(manifest) || !Array.isArray(manifest.citations)) {
    return {
      isValid: false,
      citations: [],
      claimCitations: {}
    }
  }

  const citations = []
  const seenCitationIds = new Set()
  let isValid = true

  for (const item of manifest.citations) {
    const citation = normalizeCitation(item)
    if (!citation || seenCitationIds.has(citation.citationId)) {
      isValid = false
      continue
    }
    seenCitationIds.add(citation.citationId)
    citations.push(citation)
  }

  const normalizedClaims = normalizeClaimCitations(manifest.claim_citations)
  return {
    isValid: isValid && normalizedClaims.isValid,
    citations,
    claimCitations: normalizedClaims.value
  }
}

export function normalizeCitationDetail(value, manifestCitations) {
  if (!isPlainObject(value)) {
    return null
  }
  const citationId = shortText(value.citation_id || value.citationId)
  if (!citationId) {
    return null
  }

  const manifestCitation = manifestCitations.find((citation) => citation.citationId === citationId)
  if (!manifestCitation) {
    return null
  }

  return {
    ...manifestCitation,
    title: shortText(value.title) || manifestCitation.title,
    titlePath: shortText(value.title_path || value.titlePath) || manifestCitation.titlePath,
    source: shortText(value.source) || manifestCitation.source,
    startLine: positiveInteger(value.start_line || value.startLine) || manifestCitation.startLine,
    endLine: positiveInteger(value.end_line || value.endLine) || manifestCitation.endLine,
    corpusVersion: shortText(value.corpus_version || value.corpusVersion) || manifestCitation.corpusVersion,
    claimCount: nonNegativeInteger(value.claim_count || value.claimCount) || 0,
    document: normalizeDocument(value.document),
    preview: normalizePreview(value.preview)
  }
}

export function hasNavigableDocument(citation) {
  return positiveInteger(citation?.document?.knowledgeId) !== null
}

function normalizeCitation(item) {
  if (!isPlainObject(item)) {
    return null
  }
  const citationId = shortText(item.citation_id || item.citationId)
  if (!citationId) {
    return null
  }
  return {
    citationId,
    documentId: shortText(item.document_id || item.documentId),
    title: shortText(item.title) || '未命名资料',
    titlePath: shortText(item.title_path || item.titlePath),
    source: shortText(item.source),
    startLine: positiveInteger(item.start_line || item.startLine),
    endLine: positiveInteger(item.end_line || item.endLine),
    corpusVersion: shortText(item.corpus_version || item.corpusVersion)
  }
}

function normalizeClaimCitations(value) {
  if (value === undefined || value === null) {
    return { isValid: true, value: {} }
  }
  if (!isPlainObject(value)) {
    return { isValid: false, value: {} }
  }

  let isValid = true
  const entries = Object.entries(value).flatMap(([claim, citationIds]) => {
    if (!isNonEmptyString(claim) || !Array.isArray(citationIds)) {
      isValid = false
      return []
    }
    const normalizedIds = citationIds.filter((citationId) => isNonEmptyString(citationId))
    if (normalizedIds.length !== citationIds.length) {
      isValid = false
    }
    return [[claim.trim(), normalizedIds.map((citationId) => citationId.trim())]]
  })
  return {
    isValid,
    value: Object.fromEntries(entries)
  }
}

function normalizeDocument(value) {
  if (!isPlainObject(value) || value.type !== 'public_knowledge') {
    return null
  }
  const knowledgeId = positiveInteger(value.knowledge_id || value.knowledgeId)
  if (!knowledgeId) {
    return null
  }
  return { type: 'public_knowledge', knowledgeId }
}

function normalizePreview(value) {
  if (!isPlainObject(value) || !isNonEmptyString(value.text)) {
    return null
  }
  return {
    text: value.text.trim(),
    startLine: positiveInteger(value.start_line || value.startLine),
    endLine: positiveInteger(value.end_line || value.endLine),
    isTruncated: value.is_truncated === true || value.isTruncated === true
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

function nonNegativeInteger(value) {
  if (typeof value === 'number' && Number.isInteger(value) && value >= 0) {
    return value
  }
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) {
    const normalized = Number(value)
    return Number.isSafeInteger(normalized) && normalized >= 0 ? normalized : null
  }
  return null
}

function shortText(value, maxLength = MAX_CITATION_TEXT_LENGTH) {
  return isNonEmptyString(value) ? value.trim().slice(0, maxLength) : null
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0
}
