<template>
  <BasePanel
    title="评测摘要"
    subtitle="只展示已持久化的统计指标和失败阶段聚合。"
  >
    <div v-if="state === 'loading'" class="detail-loading">
      <span v-for="index in 6" :key="index" />
    </div>

    <div v-else-if="state === 'error'" class="detail-state detail-state--error" role="alert">
      <BaseIcon name="warning" :size="17" />
      <span>{{ errorMessage }}</span>
    </div>

    <div v-else-if="!detail" class="detail-state">
      <BaseIcon name="chart" :size="18" />
      <span>从左侧选择一条评测运行查看指标摘要。</span>
    </div>

    <template v-else>
      <div class="detail-meta">
        <div>
          <span>运行</span>
          <strong>#{{ detail.run.id }}</strong>
        </div>
        <div>
          <span>状态</span>
          <BaseBadge :type="badgeType(detail.run.status)">
            {{ runStatusPresentation(detail.run.status).label }}
          </BaseBadge>
        </div>
        <div>
          <span>结果数</span>
          <strong>{{ detail.resultTotal }}</strong>
        </div>
      </div>

      <div class="metric-groups">
        <section
          v-for="group in detail.run.metricGroups"
          :key="group.title"
          class="metric-group"
        >
          <h3>{{ group.title }}</h3>
          <dl>
            <div v-for="item in group.items" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section class="failure-summary">
        <h3>失败阶段聚合</h3>
        <div v-if="detail.failureStages.length" class="failure-tags">
          <BaseBadge
            v-for="item in detail.failureStages"
            :key="item.key"
            type="orange"
          >
            {{ item.key }} · {{ item.count }}
          </BaseBadge>
        </div>
        <p v-else>当前页没有记录失败阶段。</p>
      </section>
    </template>
  </BasePanel>
</template>

<script setup>
import { BaseBadge, BaseIcon, BasePanel } from '@/components/ui'
import { runStatusPresentation } from '@/features/admin/ragDiagnosticsPresentation'

defineProps({
  detail: { type: Object, default: null },
  state: { type: String, default: 'idle' },
  errorMessage: { type: String, default: '' }
})

function badgeType(status) {
  const tone = runStatusPresentation(status).tone
  if (tone === 'success') {
    return 'green'
  }
  if (tone === 'warning') {
    return 'orange'
  }
  if (tone === 'danger') {
    return 'red'
  }
  return 'blue'
}
</script>

<style scoped lang="scss">
.detail-loading {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;

  span {
    min-height: 62px;
    border-radius: 8px;
    background: #f1f5f9;
  }
}

.detail-state {
  display: flex;
  min-height: 164px;
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

.detail-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;

  > div {
    min-width: 0;
    padding: 9px;
    border-radius: 8px;
    background: #f8fafc;
  }

  span,
  strong {
    display: block;
  }

  span {
    margin-bottom: 4px;
    color: #64748b;
    font-size: 11px;
  }

  strong {
    color: #0f172a;
    font-size: 14px;
  }
}

.metric-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.metric-group,
.failure-summary {
  padding: 11px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;

  h3,
  p {
    margin: 0;
  }

  h3 {
    color: #334155;
    font-size: 13px;
  }
}

.metric-group {
  dl {
    display: grid;
    gap: 7px;
    margin: 9px 0 0;
  }

  dl div {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  dt,
  dd {
    margin: 0;
    font-size: 12px;
  }

  dt {
    color: #64748b;
  }

  dd {
    color: #0f172a;
    font-weight: 700;
  }
}

.failure-summary {
  margin-top: 10px;

  p {
    margin-top: 8px;
    color: #64748b;
    font-size: 12px;
  }
}

.failure-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
}

@media (min-width: 768px) and (max-width: 1200px) {
  .metric-groups {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .detail-loading,
  .detail-meta,
  .metric-groups {
    grid-template-columns: 1fr;
  }
}
</style>
