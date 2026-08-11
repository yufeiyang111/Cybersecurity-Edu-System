<template>
  <section class="version-card">
    <div class="card-head">
      <h2>计划版本</h2>
      <el-tag v-if="currentVersion" type="primary" size="small">
        v{{ currentVersion }}
      </el-tag>
    </div>
    <div v-if="loading && !plans.length" class="version-card__empty">
      计划加载中…
    </div>
    <div v-else-if="!plans.length" class="version-card__empty">
      暂无计划
    </div>
    <ul v-else class="version-list">
      <li
        v-for="plan in plans"
        :key="plan.plan_version"
        class="version-item"
        :class="{ 'version-item--current': plan.plan_version === currentVersion }"
        @click="$emit('select', plan.plan_version)"
      >
        <span class="version-item__badge">v{{ plan.plan_version }}</span>
        <div class="version-item__body">
          <span class="version-item__source">{{ sourceLabel(plan.planner_source) }}</span>
          <span class="version-item__nodes">{{ plan.nodes.length }} 节点</span>
          <span v-if="plan.decision_summary" class="version-item__summary">
            {{ plan.decision_summary }}
          </span>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { plannerSourceLabel } from '@/features/security/agent/statusMeta'

const props = defineProps({
  plans: { type: Array, default: () => [] },
  currentVersion: { type: Number, default: 0 },
  loading: { type: Boolean, default: false }
})

defineEmits(['select'])

function sourceLabel(source) {
  const meta = plannerSourceLabel(source)
  return meta?.label || source || '未知'
}
</script>

<style scoped lang="scss">
.version-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.card-head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.version-card__empty {
  color: #8494a8;
  font-size: 12.5px;
}

.version-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.version-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border: 1px solid #eef1f6;
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  background: #fbfcfe;
}

.version-item:hover {
  border-color: #2563eb;
}

.version-item--current {
  background: #eff6ff;
  border-color: #2563eb;
}

.version-item__badge {
  font-size: 12px;
  font-weight: 700;
  color: #2563eb;
  background: #eff6ff;
  border-radius: 6px;
  padding: 2px 6px;
  flex: 0 0 auto;
}

.version-item--current .version-item__badge {
  color: #fff;
  background: #2563eb;
}

.version-item__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.version-item__source {
  font-size: 12.5px;
  font-weight: 600;
  color: #1f2d3d;
}

.version-item__nodes {
  font-size: 12px;
  color: #6a7890;
}

.version-item__summary {
  font-size: 12px;
  line-height: 1.5;
  color: #52627a;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
