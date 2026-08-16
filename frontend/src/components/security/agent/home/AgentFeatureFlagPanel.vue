<template>
  <BasePanel
    v-if="workspaceId"
    class="feature-flag-panel"
  >
    <template #header>
      <div class="feature-flag-panel__heading">
        <h2>Harness V3 能力</h2>
        <p>仅影响后续创建的混合审计和深度审计任务。</p>
      </div>
      <BaseBadge :type="draft.harness_v3 ? 'green' : 'gray'">
        {{ draft.harness_v3 ? '已启用' : '未启用' }}
      </BaseBadge>
    </template>

    <div
      v-if="loading"
      class="feature-flag-panel__loading"
      aria-busy="true"
      aria-live="polite"
    >
      <el-skeleton :rows="3" animated />
    </div>

    <div
      v-else-if="accessDenied"
      class="feature-flag-panel__notice feature-flag-panel__notice--warning"
      role="alert"
    >
      {{ errorMessage || '当前账号没有管理该工作区 Agent 开关的权限。' }}
    </div>

    <template v-else>
      <div
        v-if="errorMessage"
        class="feature-flag-panel__notice feature-flag-panel__notice--error"
        role="alert"
      >
        {{ errorMessage }}
      </div>

      <label class="feature-flag-panel__item">
        <span class="feature-flag-panel__copy">
          <strong>启用 Harness V3</strong>
          <small>启用受限的假设、证据、Critic 与攻击路径验证闭环。</small>
        </span>
        <el-switch
          v-model="draft.harness_v3"
          aria-label="启用 Harness V3"
        />
      </label>

      <label
        class="feature-flag-panel__item"
        :class="{ 'feature-flag-panel__item--disabled': !draft.harness_v3 }"
      >
        <span class="feature-flag-panel__copy">
          <strong>实时展示 Provider 原始推理</strong>
          <small>仅当前创建者在线连接可见；刷新、历史回放和数据库均不保留原文。</small>
        </span>
        <el-switch
          v-model="draft.provider_raw_reasoning_stream"
          :disabled="!draft.harness_v3"
          aria-label="实时展示 Provider 原始推理"
        />
      </label>

      <p class="feature-flag-panel__hint">
        本页面保存的是工作区覆盖值。历史任务继续使用创建时的功能开关快照，不会被改写。
      </p>

      <div class="feature-flag-panel__actions">
        <BaseButton
          type="button"
          variant="ghost"
          :disabled="saving || !hasWorkspaceOverride"
          @click="emit('reset')"
        >
          恢复默认
        </BaseButton>
        <BaseButton
          type="button"
          variant="primary"
          :disabled="saving"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存开关' }}
        </BaseButton>
      </div>
    </template>
  </BasePanel>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { BaseBadge, BaseButton, BasePanel } from '@/components/ui'
import { hasV3WorkspaceOverride } from '@/features/security/agent/featureFlagPresentation'

const props = defineProps({
  workspaceId: {
    type: Number,
    default: null
  },
  resolved: {
    type: Object,
    default: () => ({})
  },
  overrides: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  },
  saving: {
    type: Boolean,
    default: false
  },
  accessDenied: {
    type: Boolean,
    default: false
  },
  errorMessage: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['save', 'reset'])
const draft = reactive({
  harness_v3: false,
  provider_raw_reasoning_stream: false
})

const hasWorkspaceOverride = computed(() => {
  return hasV3WorkspaceOverride(props.overrides)
})

watch(
  () => props.resolved,
  (next) => {
    draft.harness_v3 = next?.harness_v3 === true
    draft.provider_raw_reasoning_stream =
      draft.harness_v3 && next?.provider_raw_reasoning_stream === true
  },
  {
    deep: true,
    immediate: true
  }
)

watch(
  () => draft.harness_v3,
  (enabled) => {
    if (!enabled) {
      draft.provider_raw_reasoning_stream = false
    }
  }
)

function save() {
  emit('save', {
    harness_v3: draft.harness_v3,
    provider_raw_reasoning_stream: draft.provider_raw_reasoning_stream
  })
}
</script>

<style scoped lang="scss">
.feature-flag-panel {
  min-height: 0;
}

.feature-flag-panel__heading {
  min-width: 0;
}

.feature-flag-panel__heading h2 {
  margin: 0;
  color: #172033;
  font-size: 14px;
  font-weight: 650;
}

.feature-flag-panel__heading p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 11.5px;
  line-height: 1.45;
}

.feature-flag-panel__loading {
  min-height: 100px;
}

.feature-flag-panel__notice {
  margin-bottom: 10px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}

.feature-flag-panel__notice--warning {
  border-color: #fde68a;
  color: #854d0e;
  background: #fefce8;
}

.feature-flag-panel__notice--error {
  border-color: #fecaca;
  color: #b91c1c;
  background: #fef2f2;
}

.feature-flag-panel__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
}

.feature-flag-panel__item--disabled {
  cursor: not-allowed;
}

.feature-flag-panel__copy {
  min-width: 0;
}

.feature-flag-panel__copy strong {
  display: block;
  color: #334155;
  font-size: 12.5px;
  font-weight: 650;
}

.feature-flag-panel__copy small {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 11.5px;
  line-height: 1.45;
}

.feature-flag-panel__item--disabled .feature-flag-panel__copy strong,
.feature-flag-panel__item--disabled .feature-flag-panel__copy small {
  color: #94a3b8;
}

.feature-flag-panel__hint {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 11.5px;
  line-height: 1.5;
}

.feature-flag-panel__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.feature-flag-panel__actions :deep(.ui-btn:disabled) {
  cursor: not-allowed;
  opacity: 0.55;
}

@media (max-width: 768px) {
  .feature-flag-panel__item {
    align-items: flex-start;
  }

  .feature-flag-panel__actions {
    justify-content: stretch;
  }

  .feature-flag-panel__actions :deep(.ui-btn) {
    flex: 1;
  }
}
</style>
