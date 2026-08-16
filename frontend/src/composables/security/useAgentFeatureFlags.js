import { ref, watch } from 'vue'
import { agentAPI } from '@/api'
import {
  buildV3FeatureFlagOverrides,
  normalizeV3FeatureFlags
} from '@/features/security/agent/featureFlagPresentation'

const EMPTY_FLAGS = Object.freeze({
  harness_v3: false,
  provider_raw_reasoning_stream: false
})

export function useAgentFeatureFlags(getWorkspaceId) {
  const loading = ref(false)
  const saving = ref(false)
  const accessDenied = ref(false)
  const errorMessage = ref('')
  const resolved = ref({ ...EMPTY_FLAGS })
  const overrides = ref({})
  let requestVersion = 0

  async function load() {
    const workspaceId = normalizeWorkspaceId()
    const version = ++requestVersion

    if (!workspaceId) {
      resetState()
      return false
    }

    loading.value = true
    saving.value = false
    accessDenied.value = false
    errorMessage.value = ''

    try {
      const response = await agentAPI.getFeatureFlags(workspaceId)
      if (version !== requestVersion) return false
      applyResponse(response)
      return true
    } catch (error) {
      if (version !== requestVersion) return false
      resetState()
      accessDenied.value = error?.response?.status === 403
      errorMessage.value = accessDenied.value
        ? '当前账号没有查看或管理该工作区 Agent 开关的权限。'
        : error?.response?.data?.error || '加载 Agent 能力开关失败。'
      return false
    } finally {
      if (version === requestVersion) loading.value = false
    }
  }

  async function saveV3Flags(flags) {
    return update(buildV3FeatureFlagOverrides(flags), '保存 Harness V3 开关失败。')
  }

  async function resetV3Overrides() {
    return update(
      {
        overrides: {
          harness_v3: null,
          provider_raw_reasoning_stream: null
        }
      },
      '恢复 Harness V3 工作区默认值失败。'
    )
  }

  async function update(payload, fallbackError) {
    const workspaceId = normalizeWorkspaceId()
    const version = ++requestVersion
    if (!workspaceId) {
      resetState()
      return false
    }

    saving.value = true
    accessDenied.value = false
    errorMessage.value = ''

    try {
      const response = await agentAPI.updateFeatureFlags(workspaceId, payload)
      if (version !== requestVersion) return false
      applyResponse(response)
      return true
    } catch (error) {
      if (version !== requestVersion) return false
      accessDenied.value = error?.response?.status === 403
      errorMessage.value = accessDenied.value
        ? '当前账号没有管理该工作区 Agent 开关的权限。'
        : error?.response?.data?.error || fallbackError
      return false
    } finally {
      if (version === requestVersion) saving.value = false
    }
  }

  function applyResponse(response) {
    const normalized = normalizeV3FeatureFlags(
      response?.resolved,
      response?.overrides
    )
    resolved.value = normalized.flags
    overrides.value = normalized.overrides
  }

  function resetState() {
    loading.value = false
    saving.value = false
    accessDenied.value = false
    errorMessage.value = ''
    resolved.value = { ...EMPTY_FLAGS }
    overrides.value = {}
  }

  function normalizeWorkspaceId() {
    const value = Number(getWorkspaceId?.())
    return Number.isInteger(value) && value > 0 ? value : null
  }

  watch(getWorkspaceId, load, { immediate: true })

  return {
    loading,
    saving,
    accessDenied,
    errorMessage,
    resolved,
    overrides,
    load,
    saveV3Flags,
    resetV3Overrides
  }
}
