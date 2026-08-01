<template>
  <article class="panel documents-panel">
    <div class="panel-heading">
      <div>
        <h2>{{ selectedSource ? `${selectedSource.name} 的文档` : '版本化文档' }}</h2>
        <p>{{ selectedSource ? '列表仅返回治理元数据，不回显文档正文。' : '选择一个知识来源后查看文档版本。' }}</p>
      </div>
      <el-button type="primary" plain :disabled="!selectedSource" :icon="Document" @click="emit('create-document')">新增文档</el-button>
    </div>

    <el-empty v-if="!selectedSource" description="请选择左侧知识来源" />
    <el-empty v-else-if="!loading && documents.length === 0" description="该来源还没有版本化文档。" />
    <el-table v-else :data="documents" class="document-table">
      <el-table-column prop="title" label="标题" min-width="190" />
      <el-table-column prop="document_version" label="版本" min-width="130" />
      <el-table-column label="标签" min-width="160">
        <template #default="{ row }"><el-tag v-for="tag in row.tags || []" :key="tag" size="small" class="tag">{{ tag }}</el-tag></template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }"><el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '生效' : '停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="170">
        <template #default="{ row }">{{ formatSecurityDate(row.updated_at) }}</template>
      </el-table-column>
    </el-table>
  </article>
</template>

<script setup>
import { Document } from '@element-plus/icons-vue'
import { formatSecurityDate } from '@/features/security/presentation'

defineProps({
  selectedSource: { type: Object, default: null },
  documents: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['create-document'])
</script>

<style scoped lang="scss">
.panel { background:#fff; border:1px solid #e6eaf0; border-radius:16px; padding:24px; box-shadow:0 10px 30px rgba(20,33,61,.06); }
.panel-heading { display:flex; gap:16px; align-items:flex-start; justify-content:space-between; margin-bottom:20px; }
.panel-heading h2 { margin:0; font-size:19px; }
.panel-heading p { margin:7px 0 0; color:#788496; line-height:1.55; }
.document-table { width:100%; }
.tag { margin:2px; }
@media(max-width:820px){ .panel{padding:18px} }
</style>
