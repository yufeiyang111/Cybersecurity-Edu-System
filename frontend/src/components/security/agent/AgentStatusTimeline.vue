<template>
  <section class="timeline-card">
    <div class="card-head">
      <h2>执行时间线</h2>
      <span class="note">{{ steps.length }} 个步骤</span>
    </div>
    <el-empty v-if="!loading && steps.length === 0" description="暂无执行步骤" :image-size="72" />
    <div v-else class="timeline">
      <div v-for="step in steps" :key="step.id" class="timeline__item">
        <span class="timeline__dot" :class="`timeline__dot--${step.status}`" aria-hidden="true" />
        <div class="timeline__body">
          <div class="timeline__row">
            <span class="timeline__title">{{ stepTitle(step) }}</span>
            <el-tag :type="metaOf(step.status).tagType" size="small">{{ metaOf(step.status).label }}</el-tag>
          </div>
          <div class="timeline__meta">
            <template v-if="step.tool_name">工具：{{ step.tool_name }}</template>
            <template v-else>内部步骤</template>
            <template v-if="step.summary"> · {{ step.summary }}</template>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { stepStatusMetaOf } from '@/features/security/agent/statusMeta'

defineProps({
  steps: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const metaOf = (status) => stepStatusMetaOf(status)

function stepTitle(step) {
  if (step.node_key === 'inventory') return '清点快照文件'
  if (step.node_key === 'report') return '生成运行摘要'
  return step.node_key || `步骤 #${step.id}`
}
</script>

<style scoped lang="scss">
.timeline-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head .note { color: #6a7890; font-size: 12.5px; }
.timeline { display: flex; flex-direction: column; gap: 0; }
.timeline__item { position: relative; display: flex; gap: 10px; padding: 0 0 16px 4px; }
.timeline__item::before {
  content: ''; position: absolute; left: 9px; top: 18px; bottom: -2px;
  width: 1px; background: #e2e7ee;
}
.timeline__item:last-child::before { display: none; }
.timeline__dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 5px; flex: none; }
.timeline__dot--running { background: #1d4ed8; }
.timeline__dot--completed { background: #1c8a4d; }
.timeline__dot--failed { background: #d43b3b; }
.timeline__dot--canceled, .timeline__dot--pending, .timeline__dot--ready { background: #c2ccd9; }
.timeline__body { min-width: 0; flex: 1; }
.timeline__row { display: flex; align-items: center; gap: 8px; }
.timeline__title { font-size: 13.5px; font-weight: 600; color: #1f2d3d; }
.timeline__meta { color: #6a7890; font-size: 12.5px; margin-top: 2px; line-height: 1.5; }
</style>
