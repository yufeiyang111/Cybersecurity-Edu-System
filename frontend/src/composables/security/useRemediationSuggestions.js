import { ref } from 'vue'
import { securityAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

export function useRemediationSuggestions() {
  const suggestionsByFinding = ref({})
  const suggestionsLoaded = ref({})
  const suggestionLoading = ref({})
  const suggestionErrors = ref({})
  const suggestionsTotal = ref({})
  const suggestionsLoadingMore = ref({})

  const SUGGESTIONS_PAGE_SIZE = 5

  const suggestionsFor = (findingId) => suggestionsByFinding.value[findingId] || []

  const setSuggestionState = (target, findingId, value) => {
    target.value = { ...target.value, [findingId]: value }
  }

  const loadSuggestions = async (findingId, { silent = false, shouldApply = () => true } = {}) => {
    if (suggestionLoading.value[findingId]) return []
    if (shouldApply()) {
      setSuggestionState(suggestionLoading, findingId, true)
      setSuggestionState(suggestionErrors, findingId, '')
    }
    try {
      const response = await securityAPI.listRemediationSuggestions(findingId, { limit: SUGGESTIONS_PAGE_SIZE })
      if (!shouldApply()) return []
      const items = response.items || []
      setSuggestionState(suggestionsByFinding, findingId, items)
      setSuggestionState(suggestionsLoaded, findingId, true)
      setSuggestionState(suggestionsTotal, findingId, response.pagination?.total ?? items.length)
      return items
    } catch (error) {
      if (shouldApply() && !silent) {
        setSuggestionState(suggestionErrors, findingId, securityApiErrorMessage(error, '加载修复建议失败。'))
      }
      return []
    } finally {
      if (shouldApply()) setSuggestionState(suggestionLoading, findingId, false)
    }
  }

  const loadMoreSuggestions = async (findingId, { shouldApply = () => true } = {}) => {
    const current = suggestionsFor(findingId)
    if (suggestionLoading.value[findingId] || suggestionsLoadingMore.value[findingId]) return []
    if (!shouldApply()) return []
    setSuggestionState(suggestionsLoadingMore, findingId, true)
    try {
      const response = await securityAPI.listRemediationSuggestions(findingId, {
        limit: SUGGESTIONS_PAGE_SIZE,
        offset: current.length
      })
      if (!shouldApply()) return []
      const incoming = response.items || []
      const knownIds = new Set(current.map((item) => item.id))
      setSuggestionState(
        suggestionsByFinding,
        findingId,
        [...current, ...incoming.filter((item) => !knownIds.has(item.id))]
      )
      setSuggestionState(suggestionsTotal, findingId, response.pagination?.total ?? current.length + incoming.length)
      setSuggestionState(suggestionsLoaded, findingId, true)
      return incoming
    } catch (error) {
      setSuggestionState(suggestionErrors, findingId, securityApiErrorMessage(error, '加载更多修复建议失败。'))
      return []
    } finally {
      if (shouldApply()) setSuggestionState(suggestionsLoadingMore, findingId, false)
    }
  }

  const generateSuggestion = async (finding) => {
    if (suggestionLoading.value[finding.id]) return null
    setSuggestionState(suggestionLoading, finding.id, true)
    setSuggestionState(suggestionErrors, finding.id, '')
    try {
    const response = await securityAPI.generateRemediationSuggestion(finding.id)
    const current = suggestionsFor(finding.id)
    setSuggestionState(
      suggestionsByFinding,
      finding.id,
      [response.suggestion, ...current.filter((item) => item.id !== response.suggestion.id)]
    )
    setSuggestionState(suggestionsLoaded, finding.id, true)
    setSuggestionState(suggestionsTotal, finding.id, (suggestionsTotal.value[finding.id] ?? current.length) + 1)
    return response.suggestion
    } catch (error) {
      setSuggestionState(suggestionErrors, finding.id, securityApiErrorMessage(error, '生成修复建议失败。'))
      return null
    } finally {
      setSuggestionState(suggestionLoading, finding.id, false)
    }
  }

  const reviewSuggestion = async (suggestionId, review) => {
    const response = await securityAPI.reviewRemediationSuggestion(suggestionId, review)
    const updated = response.suggestion
    const current = suggestionsFor(updated.finding_id)
    if (current.length) {
      setSuggestionState(
        suggestionsByFinding,
        updated.finding_id,
        current.map((item) => item.id === updated.id ? updated : item)
      )
    }
    return updated
  }

  const removeSuggestion = async (suggestion) => {
    await securityAPI.deleteRemediationSuggestion(suggestion.id)
    const current = suggestionsFor(suggestion.finding_id)
    setSuggestionState(
      suggestionsByFinding,
      suggestion.finding_id,
      current.filter((item) => item.id !== suggestion.id)
    )
    const total = suggestionsTotal.value[suggestion.finding_id]
    if (typeof total === 'number') {
      setSuggestionState(suggestionsTotal, suggestion.finding_id, Math.max(0, total - 1))
    }
  }

  return {
    suggestionsLoaded,
    suggestionLoading,
    suggestionErrors,
    suggestionsTotal,
    suggestionsLoadingMore,
    suggestionsFor,
    loadSuggestions,
    loadMoreSuggestions,
    generateSuggestion,
    reviewSuggestion,
    removeSuggestion
  }
}
