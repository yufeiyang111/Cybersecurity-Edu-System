<template>
  <article
    class="attack-path-item"
    :class="{ 'attack-path-item--selected': selected }"
  >
    <div class="attack-path-item__header">
      <div class="attack-path-item__heading">
        <p class="attack-path-item__eyebrow">
          {{ hypothesis.skillKey || '未标记技能' }} · 优先级 {{ hypothesis.priority }}
        </p>
        <h4>{{ hypothesis.title || '未命名漏洞假设' }}</h4>
      </div>
      <BaseBadge :type="statusMeta.type">
        {{ statusMeta.label }}
      </BaseBadge>
    </div>

    <p class="attack-path-item__summary">
      {{ hypothesis.targetSummary || '该候选未提供可展示的目标摘要。' }}
    </p>

    <dl class="attack-path-item__facts">
      <div>
        <dt>审查次数</dt>
        <dd>{{ hypothesis.executionAttemptCount }} 次</dd>
      </div>
      <div>
        <dt>反思次数</dt>
        <dd>{{ hypothesis.reflectionCount }} 次</dd>
      </div>
    </dl>

    <AgentAttackPathEvidence
      :satisfied-evidence="hypothesis.satisfiedEvidence"
      :evidence-gaps="hypothesis.evidenceGaps"
      :authorized-scopes="hypothesis.authorizedScopes"
    />

    <BaseButton
      class="attack-path-item__detail-button"
      variant="ghost"
      type="button"
      :aria-expanded="selected"
      @click="$emit('select', hypothesis.id)"
    >
      <BaseIcon
        :name="selected ? 'chevron-down' : 'eye'"
        :size="15"
      />
      {{ selected ? '收起 Critic 判定' : '查看 Critic 判定' }}
    </BaseButton>

    <AgentCriticDecision
      v-if="selected"
      :detail="detail"
      :loading="detailLoading"
      :error-message="detailErrorMessage"
    />
  </article>
</template>

<script setup>
import { computed } from 'vue'
import AgentAttackPathEvidence from '@/components/security/agent/AgentAttackPathEvidence.vue'
import AgentCriticDecision from '@/components/security/agent/AgentCriticDecision.vue'
import {
  BaseBadge,
  BaseButton,
  BaseIcon,
} from '@/components/ui'

const props = defineProps({
  hypothesis: {
    type: Object,
    required: true,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  detail: {
    type: Object,
    default: null,
  },
  detailLoading: {
    type: Boolean,
    default: false,
  },
  detailErrorMessage: {
    type: String,
    default: '',
  },
})

defineEmits(['select'])

const statusMeta = computed(() => statusPresentation(props.hypothesis.status))

function statusPresentation(status) {
  return {
    queued: { type: 'gray', label: '等待核验' },
    active: { type: 'blue', label: '正在核验' },
    needs_evidence: { type: 'yellow', label: '证据不足' },
    confirmed: { type: 'green', label: '已确认候选' },
    rejected: { type: 'gray', label: '已排除' },
    stopped_for_budget: { type: 'orange', label: '预算停止' },
  }[status] || { type: 'gray', label: '状态未知' }
}
</script>

<style scoped lang="scss">
.attack-path-item {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.attack-path-item--selected {
  border-color: #2563eb;
  background: #eff6ff;
}

.attack-path-item__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.attack-path-item__heading {
  min-width: 0;
}

.attack-path-item__eyebrow {
  margin: 0 0 3px;
  color: #64748b;
  font-size: 11px;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

.attack-path-item h4 {
  margin: 0;
  color: #1e293b;
  font-size: 14px;
  line-height: 1.5;
}

.attack-path-item__summary {
  margin: 8px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.65;
}

.attack-path-item__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}

.attack-path-item__facts div {
  padding: 8px;
  border-radius: 6px;
  background: #f8fafc;
}

.attack-path-item__facts dt {
  color: #64748b;
  font-size: 11px;
}

.attack-path-item__facts dd {
  margin: 3px 0 0;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

.attack-path-item__detail-button {
  margin-top: 12px;
}

@media (max-width: 768px) {
  .attack-path-item {
    padding: 12px;
  }
}
</style>
