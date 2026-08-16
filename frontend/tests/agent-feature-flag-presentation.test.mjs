import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildV3FeatureFlagOverrides,
  hasV3WorkspaceOverride,
  normalizeV3FeatureFlags
} from '../src/features/security/agent/featureFlagPresentation.js'

test('规范化仅接受布尔值，并保留工作区覆盖来源', () => {
  const result = normalizeV3FeatureFlags(
    {
      harness_v3: true,
      provider_raw_reasoning_stream: 'true'
    },
    {
      harness_v3: false,
      provider_raw_reasoning_stream: null,
      unexpected: true
    }
  )

  assert.deepEqual(result.flags, {
    harness_v3: true,
    provider_raw_reasoning_stream: false
  })
  assert.deepEqual(result.overrides, {
    harness_v3: false
  })
  assert.equal(hasV3WorkspaceOverride(result.overrides), true)
})

test('关闭 Harness V3 时不能单独保存原始推理实时通道', () => {
  assert.deepEqual(
    buildV3FeatureFlagOverrides({
      harness_v3: false,
      provider_raw_reasoning_stream: true
    }),
    {
      overrides: {
        harness_v3: false,
        provider_raw_reasoning_stream: false
      }
    }
  )
})

test('启用 Harness V3 后可以显式保存原始推理实时通道', () => {
  assert.deepEqual(
    buildV3FeatureFlagOverrides({
      harness_v3: true,
      provider_raw_reasoning_stream: true
    }),
    {
      overrides: {
        harness_v3: true,
        provider_raw_reasoning_stream: true
      }
    }
  )
})
