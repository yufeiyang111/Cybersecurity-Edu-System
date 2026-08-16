const V3_FLAG_KEYS = Object.freeze([
  'harness_v3',
  'provider_raw_reasoning_stream'
])

const EMPTY_V3_FLAGS = Object.freeze({
  harness_v3: false,
  provider_raw_reasoning_stream: false
})

export function normalizeV3FeatureFlags(resolved, overrides) {
  const flags = { ...EMPTY_V3_FLAGS }
  const normalizedOverrides = {}

  for (const key of V3_FLAG_KEYS) {
    if (typeof resolved?.[key] === 'boolean') {
      flags[key] = resolved[key]
    }
    if (typeof overrides?.[key] === 'boolean') {
      normalizedOverrides[key] = overrides[key]
    }
  }

  return {
    flags,
    overrides: normalizedOverrides
  }
}

export function buildV3FeatureFlagOverrides(flags) {
  const harnessV3 = flags?.harness_v3 === true

  return {
    overrides: {
      harness_v3: harnessV3,
      provider_raw_reasoning_stream:
        harnessV3 && flags?.provider_raw_reasoning_stream === true
    }
  }
}

export function hasV3WorkspaceOverride(overrides) {
  return V3_FLAG_KEYS.some((key) => typeof overrides?.[key] === 'boolean')
}
