<template>
  <section class="diagnostics-header">
    <div>
      <p class="diagnostics-header__eyebrow">RAG OBSERVABILITY</p>
      <h1>RAG 研发诊断</h1>
      <p>
        仅展示脱敏后的检索阶段摘要与离线评测指标，不展示用户问题、正文、Prompt 或 CoT。
      </p>
    </div>
    <BaseButton
      variant="default"
      type="button"
      :disabled="loading"
      @click="$emit('refresh')"
    >
      <BaseIcon name="history" :size="15" />
      <span>{{ loading ? '刷新中' : '刷新评测运行' }}</span>
    </BaseButton>
  </section>
</template>

<script setup>
import { BaseButton, BaseIcon } from '@/components/ui'

defineProps({
  loading: { type: Boolean, default: false }
})

defineEmits(['refresh'])
</script>

<style scoped lang="scss">
.diagnostics-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 4px 0;

  h1,
  p {
    margin: 0;
  }

  h1 {
    color: #111827;
    font-size: 24px;
    line-height: 1.3;
  }

  p:last-child {
    max-width: 720px;
    margin-top: 8px;
    color: #6b7280;
    font-size: 13px;
    line-height: 1.6;
  }
}

.diagnostics-header__eyebrow {
  color: #4b5563;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

@media (min-width: 768px) and (max-width: 1200px) {
  .diagnostics-header {
    gap: 16px;
  }
}

@media (max-width: 767px) {
  .diagnostics-header {
    flex-direction: column;
    gap: 14px;

    .ui-btn {
      width: 100%;
    }
  }
}
</style>
