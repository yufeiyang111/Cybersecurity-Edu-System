import { ref } from 'vue'
import { securityAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

export function useRemediationSuggestions() {
  const suggestionsByFinding = ref({})
  const suggestionsLoaded = ref({})
  const suggestionLoading = ref({})
  const suggestionErrors = ref({})
  let findingsGeneration = 0

  const suggestionsFor = (findingId) => suggestionsByFinding.value[findingId] || []

  const setSuggestionState = (target, findingId, value) => {
    target.value = { ...target.value, [findingId]: value }
  }

  const resetForFindings = () => {
    suggestionsByFinding.value = {}
    suggestionsLoaded.value = {}
    suggestionLoading.value = {}
    suggestionErrors.value = {}
  }

  const loadSuggestions = async (findingId, { silent = false, shouldApply = () => true } = {}) => {
    if (suggestionLoading.value[findingId]) return []
    if (shouldApply()) {
      setSuggestionState(suggestionLoading, findingId, true)
      setSuggestionState(suggestionErrors, findingId, '')
    }
    try {
      const response = await securityAPI.listRemediationSuggestions(findingId, { limit: 20 })
      if (!shouldApply()) return []
      const items = response.items || []
      setSuggestionState(suggestionsByFinding, findingId, items)
      setSuggestionState(suggestionsLoaded, findingId, true)
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

  const preloadForFindings = async (findings) => {
    const generation = ++findingsGeneration
    resetForFindings()
    await Promise.all(
      findings.slice(0, 20).map((finding) => loadSuggestions(finding.id, {
        silent: true,
        shouldApply: () => generation === findingsGeneration
      }))
    )
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

  return {
    suggestionsLoaded,
    suggestionLoading,
    suggestionErrors,
    suggestionsFor,
    loadSuggestions,
    preloadForFindings,
    generateSuggestion,
    reviewSuggestion
  }
}
