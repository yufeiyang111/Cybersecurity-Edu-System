import { ref } from 'vue'
import { qaAPI, knowledgeAPI } from '@/api'

export function useProfileStats() {
  const loading = ref(false)
  const questions = ref(0)
  const favorites = ref(0)
  const answers = ref(0)

  async function load() {
    loading.value = true
    try {
      const [qaCount, qaFav, knowledgeFav, recent] = await Promise.all([
        qaAPI.getHistory({ page: 1, per_page: 1 }).catch(() => null),
        qaAPI.getFavorites({ page: 1, per_page: 1 }).catch(() => null),
        knowledgeAPI.getMyFavorites({ page: 1, per_page: 1 }).catch(() => null),
        qaAPI.getHistory({ page: 1, per_page: 100 }).catch(() => null)
      ])

      questions.value = qaCount?.total || 0
      favorites.value = (qaFav?.total || 0) + (knowledgeFav?.total || 0)
      answers.value = (recent?.records || []).filter((r) => r.answer).length
    } catch {
      questions.value = 0
      favorites.value = 0
      answers.value = 0
    } finally {
      loading.value = false
    }
  }

  return { loading, questions, favorites, answers, load }
}
