<template>
  <BasePanel class="attack-path-panel">
    <template #header>
      <div class="attack-path-panel__header">
        <div>
          <div class="attack-path-panel__title-row">
            <BaseIcon
              name="activity"
              :size="16"
            />
            <h3>攻击路径验证</h3>
          </div>
          <p>展示受限技能、代码证据条件和独立 Critic 判定；不是模型自由结论。</p>
        </div>
        <BaseBadge :type="enabled ? 'blue' : 'gray'">
          {{ enabled ? 'Harness V3' : 'V3 未开启' }}
        </BaseBadge>
      </div>
    </template>

    <p
      v-if="!enabled"
      class="attack-path-panel__notice"
    >
      当前任务未在创建时启用 Harness V3，因此没有可读取的攻击路径验证记录。
    </p>

    <template v-else>
      <AgentAttackPathMetrics :metrics="metrics" />

      <AgentAttackPathState
        v-if="loading || errorMessage || items.length === 0"
        :loading="loading"
        :error-message="errorMessage"
        :empty-message="emptyStateMessage"
        @retry="$emit('retry')"
      />

      <div
        v-else
        class="attack-path-panel__list"
      >
        <AgentAttackPathItem
          v-for="hypothesis in items"
          :key="hypothesis.id"
          :hypothesis="hypothesis"
          :selected="selectedId === hypothesis.id"
          :detail="selectedId === hypothesis.id ? selectedDetail : null"
          :detail-loading="selectedId === hypothesis.id && detailLoading"
          :detail-error-message="selectedId === hypothesis.id ? detailErrorMessage : ''"
          @select="$emit('select', $event)"
        />
      </div>
    </template>
  </BasePanel>
</template>

<script setup>
import { computed } from 'vue'
import AgentAttackPathItem from '@/components/security/agent/AgentAttackPathItem.vue'
import AgentAttackPathMetrics from '@/components/security/agent/AgentAttackPathMetrics.vue'
import AgentAttackPathState from '@/components/security/agent/AgentAttackPathState.vue'
import { attackPathEmptyStateMessage } from '@/features/security/agent/hypothesisPresentation'
import {
  BaseBadge,
  BaseIcon,
  BasePanel,
} from '@/components/ui'

const props = defineProps({
  enabled: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  detailLoading: {
    type: Boolean,
    default: false,
  },
  detailErrorMessage: {
    type: String,
    default: '',
  },
  terminal: {
    type: Boolean,
    default: false,
  },
  runStatus: {
    type: String,
    default: '',
  },
  errorMessage: {
    type: String,
    default: '',
  },
  items: {
    type: Array,
    default: () => [],
  },
  metrics: {
    type: Object,
    default: () => ({}),
  },
  selectedId: {
    type: Number,
    default: null,
  },
  selectedDetail: {
    type: Object,
    default: null,
  },
})

defineEmits(['retry', 'select'])

const emptyStateMessage = computed(() => {
  const budgetExhausted = Number(
    props.metrics?.statusCounts?.stopped_for_budget || 0
  ) > 0
  return attackPathEmptyStateMessage({
    runStatus: props.runStatus,
    terminal: props.terminal,
    budgetExhausted,
  })
})
</script>

<style scoped lang="scss">
.attack-path-panel {
  border-color: #dbe4ee;
}

.attack-path-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.attack-path-panel__title-row {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #334155;
}

.attack-path-panel__title-row h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.attack-path-panel__header p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.attack-path-panel__notice {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.attack-path-panel__list {
  display: grid;
  gap: 10px;
}

@media (max-width: 768px) {
  .attack-path-panel__header {
    gap: 8px;
  }
}
</style>
