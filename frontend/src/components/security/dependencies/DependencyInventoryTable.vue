<template>
  <section class="dependency-inventory">
    <div class="section-heading">
      <div>
        <p class="section-eyebrow">SNAPSHOT INVENTORY</p>
        <h3>依赖库存</h3>
        <p>仅展示当前快照解析出的规范化依赖坐标，不展示依赖文件原文。</p>
      </div>
      <el-tag effect="plain">{{ dependencies.length }} 项</el-tag>
    </div>

    <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon class="section-alert" />
    <el-skeleton v-else-if="loading" :rows="4" animated />
    <el-empty v-else-if="dependencies.length === 0" description="当前快照未解析到支持的依赖清单；这不等同于不存在依赖风险。" />
    <div v-else class="table-wrap">
      <el-table :data="dependencies" class="dependency-table">
        <el-table-column label="包名" min-width="170">
          <template #default="{ row }"><code>{{ row.package_name }}</code></template>
        </el-table-column>
        <el-table-column prop="version" label="版本" min-width="130" />
        <el-table-column prop="ecosystem" label="生态" min-width="110" />
        <el-table-column label="来源" min-width="120">
          <template #default="{ row }"><el-tag size="small" :type="row.is_direct ? 'success' : 'info'">{{ row.is_direct ? '直接依赖' : '传递依赖' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="清单位置" min-width="260">
          <template #default="{ row }"><code>{{ row.manifest_path }}{{ row.source_line ? `:${row.source_line}` : '' }}</code></template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>

<script setup>
defineProps({
  dependencies: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})
</script>

<style scoped lang="scss">
.dependency-inventory { padding: 20px; border: 1px solid #d9e2ec; border-radius: 14px; background: #fff; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.section-eyebrow { margin: 0 0 6px; color: #0e9384; font-size: 11px; font-weight: 700; letter-spacing: .09em; }
h3 { margin: 0; color: #102a43; font-size: 17px; }
.section-heading > div > p:last-child { margin: 8px 0 0; color: #627d98; font-size: 13px; line-height: 1.6; }
.section-alert { margin-top: 16px; }
.table-wrap { margin-top: 16px; overflow-x: auto; }
.dependency-table { min-width: 780px; }
code { color: #243b53; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; overflow-wrap: anywhere; }
</style>
