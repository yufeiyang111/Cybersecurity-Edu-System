<template>
  <section class="coverage-card">
    <div class="card-head">
      <h2>扫描覆盖</h2>
      <span v-if="summary" class="note">共 {{ summary.total_files }} 个文件 · {{ summary.findings_count }} 个发现</span>
    </div>
    <div v-if="loading && !summary" class="coverage-skeleton">
      <el-skeleton :rows="3" animated />
    </div>
    <el-empty v-else-if="!summary" description="扫描完成后显示覆盖报告" :image-size="64" />
    <div v-else class="coverage-grid">
      <button
        v-for="item in items"
        :key="item.kind"
        class="coverage-item"
        :class="{ 'coverage-item--active': activeKind === item.kind }"
        @click="$emit('select-kind', item.kind)"
      >
        <span class="coverage-item__num">{{ summary[item.kind] ?? 0 }}</span>
        <span class="coverage-item__label">{{ item.label }}</span>
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  summary: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  activeKind: { type: String, default: '' }
})
defineEmits(['select-kind'])

const items = computed(() => [
  { kind: 'baseline_scanned', label: '基线覆盖' },
  { kind: 'specialized_sast', label: '专用 SAST' },
  { kind: 'generic_only', label: '通用扫描' },
  { kind: 'scanned_no_finding', label: '无发现文件' },
  { kind: 'scanned_with_findings', label: '有发现文件' },
  { kind: 'excluded', label: '排除' }
])
</script>

<style scoped lang="scss">
.coverage-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head .note { color: #6a7890; font-size: 12.5px; }
.coverage-skeleton { padding: 4px 0; }
.coverage-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.coverage-item {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
  border: 1px solid #e2e7ee; border-radius: 6px; background: #fafbfd;
  padding: 8px 10px; cursor: pointer; text-align: left;
  transition: border-color .15s ease, background .15s ease;
}
.coverage-item:hover { border-color: #0b7fd1; }
.coverage-item--active { background: #eff6ff; border-color: #2563eb; }
.coverage-item__num { font-size: 18px; font-weight: 700; color: #1f2d3d; font-variant-numeric: tabular-nums; }
.coverage-item__label { font-size: 12px; color: #6a7890; }
</style>
