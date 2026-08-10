<template>
  <div class="help-admin">
    <div class="help-admin__header">
      <div>
        <h2 class="page-title">帮助文档管理</h2>
        <p class="page-desc">管理公开帮助中心的分类与文档。文档内容为 Markdown，支持多级标题、表格、代码块等结构。</p>
      </div>
      <BaseButton variant="primary" @click="openCreateCategory">新建分类</BaseButton>
    </div>

    <div class="help-admin__layout">
      <HelpDocumentList
        :tree="adminTree"
        :loading="loading"
        :active-document-id="activeDocumentId"
        @select-document="selectDocument"
        @edit-category="openEditCategory"
        @delete-category="confirmDeleteCategory"
      />

      <div class="help-admin__editor">
        <HelpDocumentEditor
          :document="editingDocument"
          :tree="adminTree"
          :saving="saving"
          @save="saveDocument"
        />
      </div>
    </div>

    <HelpCategoryDialog
      v-model="categoryDialogVisible"
      :tree="adminTree"
      :editing-category="editingCategory"
      @submit="submitCategory"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { BaseButton } from '@/components/ui'
import { helpAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'
import HelpDocumentList from '@/components/admin/help/HelpDocumentList.vue'
import HelpDocumentEditor from '@/components/admin/help/HelpDocumentEditor.vue'
import HelpCategoryDialog from '@/components/admin/help/HelpCategoryDialog.vue'

const loading = ref(false)
const saving = ref(false)
const adminTree = ref([])
const editingDocument = ref(null)
const activeDocumentId = ref(null)
const categoryDialogVisible = ref(false)
const editingCategory = ref(null)

const loadTree = async () => {
  loading.value = true
  try {
    const response = await helpAPI.getAdminTree()
    adminTree.value = response.tree || []
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '加载帮助文档目录失败。'))
  } finally {
    loading.value = false
  }
}

const selectDocument = async (document) => {
  if (!document.id) {
    // 新建：仅携带默认分类
    editingDocument.value = { category_id: document.category_id, is_active: true }
    activeDocumentId.value = null
    return
  }
  activeDocumentId.value = document.id
  try {
    const response = await helpAPI.getAdminDocument(document.id)
    editingDocument.value = response.document
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '加载文档详情失败。'))
  }
}

const saveDocument = async (payload) => {
  saving.value = true
  try {
    if (editingDocument.value) {
      const response = await helpAPI.updateDocument(editingDocument.value.id, payload)
      ElMessage.success('文档已更新')
      editingDocument.value = response.document
    } else {
      const response = await helpAPI.createDocument(payload)
      ElMessage.success('文档已创建')
      editingDocument.value = response.document
    }
    await loadTree()
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '保存文档失败。'))
  } finally {
    saving.value = false
  }
}

const confirmDeleteDocument = async (document) => {
  try {
    await ElMessageBox.confirm(
      `确定删除文档「${document.title}」吗？删除后无法恢复。`,
      '删除帮助文档',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await helpAPI.deleteDocument(document.id)
    ElMessage.success('文档已删除')
    if (activeDocumentId.value === document.id) {
      editingDocument.value = null
      activeDocumentId.value = null
    }
    await loadTree()
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '删除文档失败。'))
  }
}

const openCreateCategory = () => {
  editingCategory.value = null
  categoryDialogVisible.value = true
}

const openEditCategory = (category) => {
  editingCategory.value = category
  categoryDialogVisible.value = true
}

const confirmDeleteCategory = async (category) => {
  try {
    await ElMessageBox.confirm(
      `确定删除分类「${category.name}」吗？分类下存在文档或子分类时无法删除。`,
      '删除分类',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await helpAPI.deleteCategory(category.id)
    ElMessage.success('分类已删除')
    await loadTree()
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '删除分类失败。'))
  }
}

const submitCategory = async (payload) => {
  try {
    if (editingCategory.value) {
      await helpAPI.updateCategory(editingCategory.value.id, payload)
      ElMessage.success('分类已更新')
    } else {
      await helpAPI.createCategory(payload)
      ElMessage.success('分类已创建')
    }
    categoryDialogVisible.value = false
    await loadTree()
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '保存分类失败。'))
  }
}

onMounted(loadTree)
</script>

<style scoped lang="scss">
.help-admin {
  padding: 24px 0 48px;

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 20px;
  }

  &__layout {
    display: grid;
    grid-template-columns: 300px minmax(0, 1fr);
    gap: 16px;
    align-items: start;
  }
}

.page-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.page-desc {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  max-width: 640px;
  line-height: 1.6;
}

@media (max-width: 1000px) {
  .help-admin__layout {
    grid-template-columns: 1fr;
  }
}
</style>