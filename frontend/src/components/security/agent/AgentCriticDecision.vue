<template>
  <section class="critic-decision">
    <div
      v-if="loading"
      class="critic-decision__loading"
    >
      正在读取受控判定…
    </div>
    <p
      v-else-if="errorMessage"
      class="critic-decision__error"
      role="alert"
    >
      {{ errorMessage }}
    </p>
    <template v-else-if="latestVerdict">
      <div class="critic-decision__header">
        <span>Critic 判定</span>
        <BaseBadge :type="verdictMeta.type">
          {{ verdictMeta.label }}
        </BaseBadge>
      </div>
      <p class="critic-decision__reason">
        {{ latestVerdict.reasonSummary || '未提供可展示的判定理由。' }}
      </p>
      <p
        v-if="latestVerdict.nextAction"
        class="critic-decision__next"
      >
        下一步：{{ latestVerdict.nextAction }}
      </p>
    </template>
    <p
      v-else
      class="critic-decision__muted"
    >
      当前尚未形成 Critic 判定；页面不会根据模型输出伪造结论。
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseBadge } from '@/components/ui'

const props = defineProps({
  detail: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  errorMessage: {
    type: String,
    default: '',
  },
})

const latestVerdict = computed(() => {
  const verdicts = props.detail?.verdicts
  return Array.isArray(verdicts) && verdicts.length
    ? verdicts[verdicts.length - 1]
    : null
})
const verdictMeta = computed(() => verdictPresentation(latestVerdict.value?.verdict))

function verdictPresentation(verdict) {
  return {
    confirm_candidate: { type: 'green', label: '确认候选' },
    request_evidence: { type: 'yellow', label: '请求补证' },
    reject_hypothesis: { type: 'gray', label: '排除假设' },
    needs_more_evidence: { type: 'yellow', label: '证据不足' },
    stop_for_budget: { type: 'orange', label: '预算停止' },
  }[verdict] || { type: 'gray', label: '尚无结论' }
}
</script>

<style scoped lang="scss">
.critic-decision {
  margin-top: 10px;
  padding: 10px;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  background: #ffffff;
}

.critic-decision__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #1e3a8a;
  font-size: 12px;
  font-weight: 600;
}

.critic-decision__loading {
  color: #64748b;
  font-size: 12px;
}

.critic-decision__error {
  margin: 0;
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.55;
}

.critic-decision__reason {
  margin: 8px 0 0;
  color: #334155;
  font-size: 12px;
  line-height: 1.6;
}

.critic-decision__next {
  margin: 8px 0 0;
  color: #475569;
  font-size: 11px;
  line-height: 1.5;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

.critic-decision__muted {
  margin: 0;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.55;
}
</style>
