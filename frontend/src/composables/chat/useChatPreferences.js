import { reactive, ref, watch } from 'vue'
import { authAPI } from '@/api'
import { useUserStore } from '@/stores/user'
import { setLanguage } from '@/features/chat/i18n'

export const DEFAULT_CHAT_PREFERENCES = {
  theme: 'system',
  color_preset: 'default',
  font_family: 'auto',
  font_size: 'medium',
  border_radius: 'auto',
  content_density: 'standard',
  content_width: 'standard',
  language: 'zh-CN',
  about_user: '',
  response_preferences: '',
  custom_prompt: '',
  response_style: 'professional',
  show_citations: true,
  show_security_warnings: true
}

const STORAGE_KEY = 'cyberguard-chat-preferences'

const readLocalPreferences = () => {
  try {
    return { ...DEFAULT_CHAT_PREFERENCES, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') }
  } catch {
    return { ...DEFAULT_CHAT_PREFERENCES }
  }
}

const applyPreferences = (preferences) => {
  const root = document.documentElement
  root.dataset.chatTheme = preferences.theme
  root.dataset.chatPreset = preferences.color_preset
  root.dataset.chatFont = preferences.font_family
  root.dataset.chatFontScale = preferences.font_size
  root.dataset.chatRadius = preferences.border_radius
  root.dataset.chatDensity = preferences.content_density
  root.dataset.chatWidth = preferences.content_width
  root.lang = preferences.language
  setLanguage(preferences.language)
}

const preferences = reactive(readLocalPreferences())
let loadPromise = null
let loadedUserKey = null
let preferenceRevision = 0

export function useChatPreferences() {
  const userStore = useUserStore()
  const loading = ref(false)
  const saving = ref(false)

  const replacePreferences = (value) => {
    Object.assign(preferences, DEFAULT_CHAT_PREFERENCES, value || {})
    applyPreferences(preferences)
  }

  const load = async () => {
    const userKey = userStore.isLoggedIn ? String(userStore.user?.id || 'authenticated') : 'guest'
    if (loadedUserKey === userKey && !loadPromise) {
      applyPreferences(preferences)
      return true
    }
    if (loadPromise) return loadPromise

    const revisionAtStart = preferenceRevision
    loading.value = true
    loadPromise = (async () => {
      try {
        if (userStore.isLoggedIn) {
          const response = await authAPI.getPreferences()
          if (revisionAtStart === preferenceRevision) replacePreferences(response.preferences)
        } else {
          applyPreferences(preferences)
        }
        if (revisionAtStart === preferenceRevision) loadedUserKey = userKey
        return true
      } catch {
        applyPreferences(preferences)
        return false
      } finally {
        loading.value = false
        loadPromise = null
      }
    })()
    return loadPromise
  }

  const save = async () => {
    preferenceRevision += 1
    saving.value = true
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
      if (userStore.isLoggedIn) {
        const response = await authAPI.updatePreferences({ ...preferences })
        replacePreferences(response.preferences)
        loadedUserKey = String(userStore.user?.id || 'authenticated')
      } else {
        applyPreferences(preferences)
      }
      return true
    } catch {
      return false
    } finally {
      saving.value = false
    }
  }

  const reset = async () => {
    preferenceRevision += 1
    try {
      if (userStore.isLoggedIn) {
        const response = await authAPI.resetPreferences()
        replacePreferences(response.preferences)
      } else {
        replacePreferences(DEFAULT_CHAT_PREFERENCES)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
      }
      loadedUserKey = userStore.isLoggedIn ? String(userStore.user?.id || 'authenticated') : 'guest'
      return true
    } catch {
      return false
    }
  }

  watch(preferences, applyPreferences, { deep: true })
  applyPreferences(preferences)

  return { preferences, loading, saving, load, save, reset }
}
