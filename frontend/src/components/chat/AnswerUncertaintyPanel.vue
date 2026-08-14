<template>
  <section
    v-if="presentation"
    class="answer-uncertainty-panel"
    :data-tone="presentation.tone"
  >
    <BaseIcon :name="presentation.icon" :size="16" />
    <div>
      <h3>{{ presentation.title }}</h3>
      <p>{{ presentation.description }}</p>
      <p class="uncertainty-action">{{ presentation.action }}</p>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'

const props = defineProps({
  answerStatus: { type: String, default: null },
  citationState: { type: String, default: 'ready' }
})

const presentation = computed(() => {
  if (props.citationState === 'degraded' || props.answerStatus === 'degraded') {
    return {
      title: '回答未完成完整证据校验',
      description: '请将回答视为辅助信息，并优先核验可用引用。',
      action: '建议：补充问题上下文，或稍后重试。',
      tone: 'danger',
      icon: 'warning'
    }
  }
  if (props.answerStatus === 'insufficient_evidence') {
    return {
      title: '当前知识库证据不足',
      description: '系统未找到足以支撑结论的资料，不会编造答案。',
      action: '建议：补充产品版本、场景或关键日志信息后重试。',
      tone: 'warning',
      icon: 'warning'
    }
  }
  if (props.answerStatus === 'conflicting_evidence') {
    return {
      title: '资料存在适用条件差异',
      description: '不同资料可能对应不同版本、环境或处置条件。',
      action: '建议：查看引用原文，并明确你所处的版本和环境。',
      tone: 'warning',
      icon: 'warning'
    }
  }
  return null
})
</script>

<style scoped lang="scss">
.answer-uncertainty-panel {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-top: 12px;
  padding: 11px 12px;
  border: 1px solid var(--chat-warning-border);
  border-radius: var(--chat-radius);
  color: var(--chat-warning-ink);
  background: var(--chat-warning-bg);

  &[data-tone='danger'] {
    border-color: var(--chat-danger-border);
    color: var(--chat-danger-ink);
    background: var(--chat-danger-bg);
  }

  h3 {
    margin: 0;
    font-size: calc(13px * var(--chat-font-scale));
  }

  p {
    margin: 3px 0 0;
    font-size: calc(12px * var(--chat-font-scale));
    line-height: 1.55;
  }
}

.uncertainty-action {
  font-weight: 600;
}

@media (max-width: 767px) {
  .answer-uncertainty-panel {
    margin-top: 10px;
    padding: 10px;
  }
}
</style>
