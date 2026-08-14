<template>
  <BasePanel
    title="检索阶段摘要"
    subtitle="严格白名单渲染：不显示候选明细、文档标识、问题、Prompt 或 CoT。"
  >
    <div v-if="state === 'loading'" class="trace-loading" aria-label="正在加载检索追踪">
      <span v-for="index in 8" :key="index" />
    </div>

    <div v-else-if="state === 'error'" class="trace-state trace-state--error" role="alert">
      <BaseIcon name="warning" :size="17" />
      <span>{{ errorMessage }}</span>
    </div>

    <div v-else-if="!trace" class="trace-state">
      <BaseIcon name="layers" :size="18" />
      <span>输入 Trace ID 后可查看候选、重排、证据与回答阶段的摘要。</span>
    </div>

    <template v-else>
      <div class="trace-meta">
        <span>Trace #{{ trace.id }}</span>
        <span>Pipeline #{{ trace.pipelineVersionId || '未关联' }}</span>
        <span>总检索 {{ formatDuration(trace.retrievalMs) }}</span>
        <span>{{ formatDateTime(trace.createdAt) }}</span>
      </div>

      <div class="trace-stages">
        <RagTraceStageCard type="candidate" :stage="trace.candidate" />
        <RagTraceStageCard type="rerank" :stage="trace.rerank" />
        <RagTraceStageCard type="evidence" :stage="trace.evidence" />
        <RagTraceStageCard type="answer" :stage="trace.answer" />
      </div>

      <section v-if="trace.warnings.length" class="trace-warnings">
        <h3>Warning</h3>
        <div>
          <BaseBadge v-for="warning in trace.warnings" :key="warning" type="orange">
            {{ warning }}
          </BaseBadge>
        </div>
      </section>
    </template>
  </BasePanel>
</template>

<script setup>
import { BaseBadge, BaseIcon, BasePanel } from '@/components/ui'
import RagTraceStageCard from './RagTraceStageCard.vue'
import {
  formatDateTime,
  formatDuration
} from '@/features/admin/ragDiagnosticsPresentation'

defineProps({
  trace: { type: Object, default: null },
  state: { type: String, default: 'idle' },
  errorMessage: { type: String, default: '' }
})
</script>

<style scoped lang="scss">
.trace-loading {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;

  span {
    min-height: 106px;
    border-radius: 8px;
    background: #f1f5f9;
  }
}

.trace-state {
  display: flex;
  min-height: 218px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #64748b;
  font-size: 13px;
  text-align: center;

  &--error {
    color: #b91c1c;
  }
}

.trace-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;

  span {
    padding: 4px 7px;
    border-radius: 999px;
    color: #475569;
    background: #f1f5f9;
    font-size: 11px;
  }
}

.trace-stages {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.trace-warnings {
  margin-top: 10px;
  padding: 10px;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  background: #fffaf0;

  h3 {
    margin: 0;
    color: #9a3412;
    font-size: 12px;
  }

  > div {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 9px;
  }
}

@media (min-width: 768px) and (max-width: 1200px) {
  .trace-loading,
  .trace-stages {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .trace-loading,
  .trace-stages {
    grid-template-columns: 1fr;
  }

  .trace-meta {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
</style>
