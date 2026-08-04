<template>
  <section class="file-table-card">
    <div class="card-head">
      <h2>文件覆盖明细</h2>
      <span class="note">{{ total }} 条收据</span>
    </div>
    <el-empty v-if="!loading && files.length === 0" description="暂无文件收据" :image-size="56" />
    <template v-else>
      <div class="file-table">
        <div class="file-row file-row--head">
          <span>文件</span>
          <span>大小</span>
          <span>覆盖</span>
        </div>
        <div v-for="file in files" :key="file.id" class="file-row">
          <span class="file-row__path" :title="file.file_path">{{ file.file_path }}</span>
          <span class="file-row__size">{{ formatBytes(file.file_size) }}</span>
          <el-tag :type="kindTag(file.coverage_kind)" size="small">{{ kindLabel(file.coverage_kind) }}</el-tag>
        </div>
      </div>
      <button
        v-if="hasMore()"
        class="load-more"
        :disabled="loading"
        @click="$emit('load-more')"
      >
        {{ loading ? '加载中…' : `加载更多（已显示 ${files.length} / ${total}）` }}
      </button>
    </template>
  </section>
</template>

<script setup>
defineProps({
  files: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  hasMore: { type: Function, required: true }
})
defineEmits(['load-more'])

const kindMeta = {
  baseline_scanned: { label: '基线覆盖', tagType: 'info' },
  specialized_sast: { label: '专用 SAST', tagType: 'primary' },
  generic_only: { label: '通用扫描', tagType: 'warning' },
  scanned_no_finding: { label: '无发现', tagType: 'success' },
  scanned_with_findings: { label: '有发现', tagType: 'danger' },
  excluded: { label: '排除', tagType: 'info' },
  skipped: { label: '跳过', tagType: 'info' },
  failed: { label: '失败', tagType: 'danger' },
  accounted: { label: '已清点', tagType: 'info' }
}

function kindLabel(kind) {
  return kindMeta[kind]?.label || kind || '-'
}
function kindTag(kind) {
  return kindMeta[kind]?.tagType || 'info'
}
function formatBytes(value) {
  if (value == null) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped lang="scss">
.file-table-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head .note { color: #6a7890; font-size: 12.5px; }
.file-table { max-height: 300px; overflow-y: auto; }
.file-row {
  display: grid; grid-template-columns: minmax(0, 1fr) 70px 90px; gap: 8px;
  align-items: center; padding: 6px 8px; font-size: 12.5px;
  border-bottom: 1px solid #f4f6f9; color: #334155;
}
.file-row--head { color: #8494a8; font-size: 12px; position: sticky; top: 0; background: #fff; }
.file-row__path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.file-row__size { color: #6a7890; font-variant-numeric: tabular-nums; }
.load-more {
  display: block; width: 100%; margin-top: 8px;
  border: 1px dashed #c2ccd9; border-radius: 6px; background: #fafbfd;
  color: #52627a; font-size: 12.5px; padding: 8px 0; cursor: pointer;
}
.load-more:hover:not(:disabled) { border-color: #0b7fd1; color: #0b7fd1; }
.load-more:disabled { cursor: default; opacity: .6; }
</style>
