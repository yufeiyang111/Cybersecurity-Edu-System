<template>
  <div class="workbench-header">
    <div>
      <div class="breadcrumb"><BaseIcon name="activity" :size="14" />安全运营 / Agent 工作台</div>
      <h1>Agent 工作台</h1>
    </div>
    <div class="header-actions">
      <BaseButton :disabled="loading" @click="$emit('refresh')">
        <BaseIcon name="refresh" :size="15" />刷新列表
      </BaseButton>
      <BaseButton variant="primary" @click="$emit('create')">
        <BaseIcon name="plus" :size="15" />新建审计
      </BaseButton>
    </div>
  </div>

  <div class="summary-grid" aria-label="工作台摘要">
    <div class="stat-card">
      <span class="stat-card__icon stat-card__icon--default">
        <BaseIcon name="layers" :size="16" />
      </span>
      <div class="stat-card__body">
        <strong class="stat-card__value">{{ totalProjects }}</strong>
        <span class="stat-card__label">个项目</span>
      </div>
    </div>
    <div class="stat-card">
      <span class="stat-card__icon stat-card__icon--blue">
        <BaseIcon name="activity" :size="16" />
      </span>
      <div class="stat-card__body">
        <strong class="stat-card__value stat-card__value--blue">{{ runningCount }}</strong>
        <span class="stat-card__label">个 Agent 执行中</span>
      </div>
    </div>
    <div class="stat-card">
      <span class="stat-card__icon stat-card__icon--red">
        <BaseIcon name="alert-triangle" :size="16" />
      </span>
      <div class="stat-card__body">
        <strong class="stat-card__value stat-card__value--red">{{ attentionCount }}</strong>
        <span class="stat-card__label">个项目需要关注</span>
      </div>
    </div>
    <div class="source-note">
      <BaseIcon name="file" :size="14" />
      <span>未读取项目源码</span>
    </div>
  </div>
</template>

<script setup>
import { BaseButton, BaseIcon } from '@/components/ui'

defineProps({
  totalProjects: { type: Number, default: 0 },
  runningCount: { type: Number, default: 0 },
  attentionCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false }
})

defineEmits(['refresh', 'create'])
</script>

<style scoped lang="scss">
.workbench-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 18px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: #94a3b8;
  font-size: 12px;
  transition: color .2s ease;
}

.breadcrumb:hover { color: #2563eb; }
.breadcrumb :deep(.ui-icon) { color: #64748b; transition: transform .3s ease, color .2s ease; }
.breadcrumb:hover :deep(.ui-icon) { color: #2563eb; transform: rotate(-12deg) scale(1.1); }

h1 {
  margin: 0;
  color: #172033;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  transition: color .2s ease, transform .2s ease;
}

h1:hover { color: #1d4ed8; transform: translateY(-1px); }

.header-actions { display: flex; gap: 8px; flex-shrink: 0; }

.header-actions :deep(.ui-btn) {
  transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease, background .2s ease;
}

.header-actions :deep(.ui-btn:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.16);
}

.header-actions :deep(.ui-btn:active) { transform: translateY(0); }

.summary-grid {
  display: flex;
  align-items: stretch;
  gap: 12px;
  min-height: 40px;
  padding-bottom: 16px;
  flex-wrap: wrap;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 130px;
  padding: 10px 14px;
  background: #ffffff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
}

.stat-card:hover {
  border-color: #bfdbfe;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  transform: translateY(-1px);
}

.stat-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  flex: none;
}

.stat-card__icon--default { background: #f1f5f9; color: #475569; }
.stat-card__icon--blue { background: #eff6ff; color: #2563eb; }
.stat-card__icon--red { background: #fee2e2; color: #dc2626; }

.stat-card__body {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.stat-card__value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
  color: #172033;
  font-variant-numeric: tabular-nums;
}

.stat-card__value--blue { color: #2563eb; }
.stat-card__value--red { color: #dc2626; }

.stat-card__label {
  color: #64748b;
  font-size: 12.5px;
  white-space: nowrap;
}

.source-note {
  display: flex;
  align-items: center;
  gap: 6px;
  align-self: center;
  margin-left: auto;
  padding: 5px 12px;
  background: #f8fafc;
  border: 1px solid #e2e7ee;
  border-radius: 999px;
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

.source-note :deep(.ui-icon) { color: #94a3b8; }

@media (prefers-reduced-motion: reduce) {
  .breadcrumb, .breadcrumb :deep(.ui-icon), h1,
  .header-actions :deep(.ui-btn), .summary-line strong {
    transition: none;
  }
}

@media (max-width: 720px) {
  .workbench-header { align-items: flex-start; flex-direction: column; gap: 14px; }
  .header-actions { width: 100%; }
  .header-actions :deep(.ui-btn) { flex: 1; }
  .summary-grid { gap: 10px; }
  .stat-card { min-width: calc(50% - 5px); flex: 1; }
  .source-note { margin-left: 0; width: 100%; justify-content: center; }
}
</style>
