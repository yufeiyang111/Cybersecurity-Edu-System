<template>
  <BasePanel
    title="离线评测运行"
    subtitle="分页读取的运行摘要；选择一条运行查看受控指标。"
  >
    <template #actions>
      <BaseBadge type="gray">{{ total }} 条</BaseBadge>
    </template>

    <div v-if="state === 'loading'" class="run-skeletons" aria-label="正在加载评测运行">
      <span v-for="index in 4" :key="index" />
    </div>

    <div v-else-if="state === 'error'" class="run-state run-state--error" role="alert">
      <BaseIcon name="warning" :size="17" />
      <span>{{ errorMessage }}</span>
      <BaseButton variant="ghost" type="button" @click="$emit('retry')">重试</BaseButton>
    </div>

    <div v-else-if="state === 'empty'" class="run-state">
      <BaseIcon name="file-text" :size="18" />
      <span>暂时没有可展示的离线评测运行。</span>
    </div>

    <div v-else class="run-list">
      <button
        v-for="run in runs"
        :key="run.id"
        class="run-row"
        :class="{ 'run-row--selected': selectedRunId === run.id }"
        type="button"
        @click="$emit('select-run', run.id)"
      >
        <span class="run-row__id">运行 #{{ run.id }}</span>
        <span class="run-row__corpus">{{ run.corpusVersion }}</span>
        <BaseBadge :type="badgeType(run.status)">{{ runStatusPresentation(run.status).label }}</BaseBadge>
        <span class="run-row__time">{{ formatDateTime(run.startedAt) }}</span>
        <BaseIcon name="arrow-right" :size="14" />
      </button>
    </div>

    <template v-if="pages > 1" #footer>
      <div class="run-pagination">
        <BaseButton
          variant="ghost"
          type="button"
          :disabled="page <= 1 || state === 'loading'"
          @click="$emit('change-page', page - 1)"
        >
          上一页
        </BaseButton>
        <span>第 {{ page }} / {{ pages }} 页</span>
        <BaseButton
          variant="ghost"
          type="button"
          :disabled="page >= pages || state === 'loading'"
          @click="$emit('change-page', page + 1)"
        >
          下一页
        </BaseButton>
      </div>
    </template>
  </BasePanel>
</template>

<script setup>
import { BaseBadge, BaseButton, BaseIcon, BasePanel } from '@/components/ui'
import {
  formatDateTime,
  runStatusPresentation
} from '@/features/admin/ragDiagnosticsPresentation'

defineProps({
  runs: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pages: { type: Number, default: 0 },
  state: { type: String, default: 'idle' },
  errorMessage: { type: String, default: '' },
  selectedRunId: { type: Number, default: null }
})

defineEmits(['retry', 'select-run', 'change-page'])

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
.run-skeletons {
  display: grid;
  gap: 8px;

  span {
    display: block;
    height: 48px;
    border-radius: 8px;
    background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 37%, #f1f5f9 63%);
    background-size: 400% 100%;
    animation: run-loading 1.25s ease infinite;
  }
}

.run-state {
  display: flex;
  min-height: 132px;
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

.run-list {
  display: grid;
  gap: 7px;
}

.run-row {
  display: grid;
  grid-template-columns: 82px minmax(120px, 1fr) auto minmax(132px, auto) 16px;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #334155;
  background: #ffffff;
  font: inherit;
  font-size: 12px;
  text-align: left;
  cursor: pointer;

  &:hover,
  &--selected {
    border-color: #2563eb;
    background: #eff6ff;
  }

  &:focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: 2px;
  }
}

.run-row__id {
  color: #0f172a;
  font-weight: 700;
}

.run-row__corpus,
.run-row__time {
  overflow: hidden;
  color: #64748b;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  color: #64748b;
  font-size: 12px;
}

@keyframes run-loading {
  0% {
    background-position: 100% 50%;
  }

  100% {
    background-position: 0 50%;
  }
}

@media (min-width: 768px) and (max-width: 1200px) {
  .run-row {
    grid-template-columns: 76px minmax(100px, 1fr) auto 16px;
  }

  .run-row__time {
    display: none;
  }
}

@media (max-width: 767px) {
  .run-row {
    grid-template-columns: 1fr auto 16px;
    gap: 8px;
  }

  .run-row__corpus,
  .run-row__time {
    display: none;
  }

  .run-pagination {
    justify-content: space-between;
  }
}
</style>
