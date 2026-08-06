<template>
  <section class="planner-card">
    <div class="card-head">
      <h2>计划</h2>
      <el-tag
        v-if="plannerMeta"
        :type="plannerMeta.tagType"
        size="small"
      >
        {{ plannerMeta.label }}
      </el-tag>
      <el-tag v-else type="info" size="small">未生成</el-tag>
    </div>
    <div v-if="loading && !plan" class="planner-card__empty">计划生成中…</div>
    <template v-else-if="plan">
      <p v-if="plan.objective" class="planner-card__objective">{{ plan.objective }}</p>
      <p v-if="plan.decision_summary" class="planner-card__summary">
        {{ plan.decision_summary }}
      </p>
      <div v-if="plan.hypotheses?.length" class="planner-card__block">
        <span class="planner-card__label">假设</span>
        <ul class="planner-card__list">
          <li v-for="(item, index) in plan.hypotheses" :key="index">{{ item }}</li>
        </ul>
      </div>
      <div v-if="plan.completion_criteria?.length" class="planner-card__block">
        <span class="planner-card__label">完成条件</span>
        <ul class="planner-card__list">
          <li v-for="(item, index) in plan.completion_criteria" :key="index">{{ item }}</li>
        </ul>
      </div>
      <div v-if="fallbackReason" class="planner-card__fallback">
        {{ fallbackReason }}
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { plannerSourceLabel } from '@/features/security/agent/statusMeta'

const props = defineProps({
  plan: { type: Object, default: null },
  fallbackReason: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

const plannerMeta = computed(() => {
  if (!props.plan?.planner_source) return null
  const label = plannerSourceLabel(props.plan.planner_source)
  return label || null
})
</script>

<style scoped lang="scss">
.planner-card {
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
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.planner-card__empty { color: #8494a8; font-size: 12.5px; }
.planner-card__objective { margin: 0 0 6px; font-size: 13px; font-weight: 600; color: #1f2d3d; }
.planner-card__summary { margin: 0 0 8px; font-size: 12.5px; line-height: 1.6; color: #52627a; }
.planner-card__block { margin-bottom: 8px; }
.planner-card__label { font-size: 12px; font-weight: 600; color: #6a7890; }
.planner-card__list { margin: 4px 0 0; padding-left: 16px; font-size: 12.5px; color: #52627a; line-height: 1.6; }
.planner-card__fallback {
  margin-top: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #fef9c3;
  color: #854d0e;
  font-size: 12px;
  line-height: 1.5;
}
</style>
