<template>
  <section class="dependency-inventory">
    <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon class="section-alert" />
    <el-skeleton v-else-if="loading" :rows="4" animated />
    <el-empty v-else-if="dependencies.length === 0" description="当前快照未解析到支持的依赖清单；这不等同于不存在依赖风险。" />
    <div v-else class="table-wrap">
      <el-table :data="dependencies" class="dependency-table">
        <el-table-column label="包名" min-width="160">
          <template #default="{ row }"><code>{{ row.package_name }}</code></template>
        </el-table-column>
        <el-table-column prop="version" label="版本" min-width="110" />
        <el-table-column prop="ecosystem" label="生态" min-width="90" />
        <el-table-column label="来源" min-width="100">
          <template #default="{ row }"><el-tag size="small" :type="row.is_direct ? 'success' : 'info'">{{ row.is_direct ? '直接依赖' : '传递依赖' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="清单位置" min-width="220">
          <template #default="{ row }"><code>{{ row.manifest_path }}{{ row.source_line ? `:${row.source_line}` : '' }}</code></template>
        </el-table-column>
      </el-table>
      <button
        v-if="hasMore"
        class="dep-load-more"
        type="button"
        :disabled="loadingMore"
        @click="emit('load-more')"
      >
        {{ loadingMore ? '加载中…' : `加载更多依赖（已显示 ${dependencies.length} / ${total}）` }}
      </button>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  dependencies: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  error: { type: String, default: '' },
  hasMore: { type: Boolean, default: false },
  total: { type: Number, default: 0 }
})

const emit = defineEmits(['load-more'])
</script>

<style scoped lang="scss">
.section-alert { margin-bottom: 10px; }
.table-wrap { overflow-x: auto; }
.dependency-table { min-width: 700px; }
.dependency-table :deep(th.el-table__cell) { background: #fafbfd; color: #6a7890; font-size: 12.5px; font-weight: 600; }
.dependency-table :deep(td.el-table__cell) { padding: 8px 0; }
code { color: #37465c; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; overflow-wrap: anywhere; }
.dep-load-more {
  display: block; width: 100%; margin-top: 10px;
  border: 1px dashed #c2ccd9; border-radius: 6px;
  background: #fafbfd; color: #52627a; font-size: 12.5px;
  padding: 7px 0; cursor: pointer;
}
.dep-load-more:hover:not(:disabled) { border-color: #0b7fd1; color: #0b7fd1; }
.dep-load-more:disabled { cursor: default; opacity: .6; }
</style>
