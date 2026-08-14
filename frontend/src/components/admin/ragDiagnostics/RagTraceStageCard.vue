<template>
  <section class="stage-card">
    <template v-if="type === 'candidate'">
      <header>
        <BaseIcon name="layers" :size="16" />
        <h3>候选检索</h3>
      </header>
      <strong>{{ stage.candidateCount ?? '未提供' }}</strong>
      <span>候选数量</span>
      <div v-if="stage.retrievalPaths.length" class="count-tags">
        <BaseBadge
          v-for="item in stage.retrievalPaths"
          :key="item.label"
          type="gray"
        >
          {{ item.label }} · {{ item.count }}
        </BaseBadge>
      </div>
      <p v-if="stage.degraded">当前候选阶段已降级。</p>
    </template>

    <template v-else-if="type === 'rerank'">
      <header>
        <BaseIcon name="target" :size="16" />
        <h3>重排</h3>
      </header>
      <strong>{{ rerankLabel }}</strong>
      <span>执行状态</span>
      <dl>
        <div>
          <dt>输入 / 输出</dt>
          <dd>{{ stage.inputCount ?? '—' }} / {{ stage.outputCount ?? '—' }}</dd>
        </div>
        <div>
          <dt>耗时</dt>
          <dd>{{ formatDuration(stage.elapsedMs) }}</dd>
        </div>
      </dl>
    </template>

    <template v-else-if="type === 'evidence'">
      <header>
        <BaseIcon name="file-text" :size="16" />
        <h3>Evidence Pack</h3>
      </header>
      <strong>{{ stage.referenceCount ?? '未提供' }}</strong>
      <span>受控证据数量</span>
      <dl>
        <div>
          <dt>Token 预算</dt>
          <dd>{{ tokenBudgetLabel }}</dd>
        </div>
        <div>
          <dt>证据状态</dt>
          <dd>{{ answerStatusPresentation(stage.answerStatus).label }}</dd>
        </div>
      </dl>
      <div v-if="stage.rejectionCounts.length" class="count-tags">
        <BaseBadge
          v-for="item in stage.rejectionCounts"
          :key="item.key"
          type="orange"
        >
          {{ item.key }} · {{ item.count }}
        </BaseBadge>
      </div>
    </template>

    <template v-else>
      <header>
        <BaseIcon name="shield" :size="16" />
        <h3>回答治理</h3>
      </header>
      <strong>{{ answerStatusPresentation(stage.answerStatus).label }}</strong>
      <span>最终 Answer Status</span>
      <dl>
        <div>
          <dt>引用 / 主张</dt>
          <dd>{{ stage.citationCount ?? '—' }} / {{ stage.claimCount ?? '—' }}</dd>
        </div>
        <div>
          <dt>告警数</dt>
          <dd>{{ stage.warningCount ?? '—' }}</dd>
        </div>
      </dl>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseBadge, BaseIcon } from '@/components/ui'
import {
  answerStatusPresentation,
  formatDuration
} from '@/features/admin/ragDiagnosticsPresentation'

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (value) => ['candidate', 'rerank', 'evidence', 'answer'].includes(value)
  },
  stage: {
    type: Object,
    required: true
  }
})

const rerankLabel = computed(() => {
  const labels = {
    completed: '已执行',
    skipped: '已跳过',
    failed: '执行失败',
    unavailable: '未提供'
  }
  return labels[props.stage.status] || '未提供'
})

const tokenBudgetLabel = computed(() => {
  const count = props.stage.tokenCount
  const budget = props.stage.tokenBudget
  if (count === null || count === undefined || !budget) {
    return '未提供'
  }
  return `${count} / ${budget}`
})
</script>

<style scoped lang="scss">
.stage-card {
  min-width: 0;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;

  header {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #475569;
  }

  h3,
  p {
    margin: 0;
  }

  h3 {
    font-size: 12px;
  }

  > strong,
  > span {
    display: block;
  }

  > strong {
    margin-top: 10px;
    overflow: hidden;
    color: #0f172a;
    font-size: 17px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  > span {
    margin-top: 2px;
    color: #64748b;
    font-size: 11px;
  }

  p {
    margin-top: 7px;
    color: #b45309;
    font-size: 11px;
  }

  dl {
    display: grid;
    gap: 5px;
    margin: 10px 0 0;
  }

  dl div {
    display: flex;
    justify-content: space-between;
    gap: 6px;
  }

  dt,
  dd {
    margin: 0;
    font-size: 11px;
  }

  dt {
    color: #64748b;
  }

  dd {
    overflow: hidden;
    color: #334155;
    font-weight: 650;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.count-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 9px;
}
</style>
