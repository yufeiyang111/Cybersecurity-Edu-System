<template>
  <div class="knowledge-admin-page">
    <h2 class="page-title">知识管理</h2>

    <!-- 上传文档区域 -->
    <el-card class="upload-card">
      <template #header>
        <div class="card-header">
          <span>文档上传</span>
        </div>
      </template>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :on-change="handleChange"
        :before-remove="beforeRemove"
        multiple
        accept=".pdf,.docx,.doc,.html,.htm,.md,.txt"
      >
        <template #trigger>
          <el-button type="primary">
            <el-icon><Upload /></el-icon> 选择文件
          </el-button>
        </template>
        <el-button type="success" @click="submitUpload" :loading="uploading">
          <el-icon><UploadFilled /></el-icon> 开始上传
        </el-button>
        <template #tip>
          <div class="el-upload__tip">
            支持 PDF、Word(.docx/.doc)、HTML、Markdown、TXT 格式，单文件不超过 10MB
          </div>
        </template>
      </el-upload>

      <div class="upload-options">
        <el-select v-model="uploadCategoryId" placeholder="选择分类（可选）" clearable size="small" style="width: 200px;">
          <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
        </el-select>
        <el-select v-model="uploadDifficulty" placeholder="难度" size="small" style="width: 120px;">
          <el-option label="入门" value="easy" />
          <el-option label="进阶" value="medium" />
          <el-option label="高级" value="hard" />
        </el-select>
      </div>
    </el-card>

    <el-card>
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索标题..."
          prefix-icon="Search"
          clearable
          @keyup.enter="handleSearch"
          style="width: 300px;"
        />
        <el-select v-model="filterStatus" placeholder="筛选状态" clearable @change="handleSearch">
          <el-option label="已发布" value="published" />
          <el-option label="草稿" value="draft" />
          <el-option label="已归档" value="archived" />
        </el-select>
      </div>

      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="difficulty" label="难度" width="80">
          <template #default="{ row }">
            <el-tag :type="getDifficultyType(row.difficulty)" size="small">
              {{ getDifficultyText(row.difficulty) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="view_count" label="浏览" width="80" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button size="small" @click="handleAudit(row, 'approve')" v-if="row.status === 'draft'">
              通过
            </el-button>
            <el-button size="small" type="warning" @click="handleAudit(row, 'reject')" v-if="row.status === 'draft'">
              拒绝
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="知识详情" width="800px">
      <div v-if="currentItem" class="item-detail">
        <h3>{{ currentItem.title }}</h3>
        <div class="detail-meta">
          <el-tag>{{ currentItem.category_name }}</el-tag>
          <el-tag :type="getDifficultyType(currentItem.difficulty)">
            {{ getDifficultyText(currentItem.difficulty) }}
          </el-tag>
          <el-tag :type="getStatusType(currentItem.status)">
            {{ getStatusText(currentItem.status) }}
          </el-tag>
        </div>
        <el-divider />
        <div class="detail-content markdown-content" v-html="renderContent"></div>
      </div>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑知识" width="900px">
      <el-form v-if="editForm" label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editForm.category_id" placeholder="选择分类" clearable style="width: 100%;">
            <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-select v-model="editForm.difficulty" style="width: 100%;">
            <el-option label="入门" value="easy" />
            <el-option label="进阶" value="medium" />
            <el-option label="高级" value="hard" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%;">
            <el-option label="已发布" value="published" />
            <el-option label="草稿" value="draft" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="editForm.source" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="editForm.content" type="textarea" :rows="15" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit" :loading="editLoading">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { adminAPI, knowledgeAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, UploadFilled } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/features/markdown/renderMarkdown'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const filterStatus = ref('')
const detailVisible = ref(false)
const currentItem = ref(null)
const categories = ref([])
const uploading = ref(false)
const uploadRef = ref(null)
const uploadCategoryId = ref(null)
const uploadDifficulty = ref('medium')
const selectedFiles = ref([])

// 编辑相关
const editVisible = ref(false)
const editLoading = ref(false)
const editForm = ref(null)

const renderContent = computed(() => {
  return renderMarkdown(currentItem.value?.content)
})

const getDifficultyType = (difficulty) => {
  const types = { easy: 'success', medium: 'warning', hard: 'danger' }
  return types[difficulty] || 'info'
}

const getDifficultyText = (difficulty) => {
  const texts = { easy: '入门', medium: '进阶', hard: '高级' }
  return texts[difficulty] || '普通'
}

const getStatusType = (status) => {
  const types = { published: 'success', draft: 'warning', archived: 'info' }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = { published: '已发布', draft: '草稿', archived: '已归档' }
  return texts[status] || status
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchItems = async () => {
  loading.value = true
  try {
    const res = await adminAPI.getAllKnowledge({
      page: currentPage.value,
      per_page: pageSize.value,
      status: filterStatus.value || undefined
    })
    items.value = res.items || []
    total.value = res.total || 0
  } catch (error) {
    console.error('获取知识列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchItems()
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchItems()
}

const handleAudit = async (row, action) => {
  try {
    await adminAPI.auditKnowledge(row.id, { action })
    ElMessage.success(action === 'approve' ? '审核通过' : '审核拒绝')
    fetchItems()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleView = (row) => {
  currentItem.value = row
  detailVisible.value = true
}

const fetchCategories = async () => {
  try {
    const res = await knowledgeAPI.getCategories()
    categories.value = res.categories || []
  } catch (error) {
    console.error('获取分类失败')
  }
}

const submitUpload = async () => {
  const files = selectedFiles.value
  if (files.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }

  uploading.value = true

  for (const fileItem of files) {
    const rawFile = fileItem.raw
    if (!rawFile) continue

    const formData = new FormData()
    formData.append('file', rawFile)
    if (uploadCategoryId.value) {
      formData.append('category_id', uploadCategoryId.value)
    }
    formData.append('difficulty', uploadDifficulty.value)

    try {
      await knowledgeAPI.uploadDocument(formData)
      ElMessage.success(`上传成功: ${fileItem.name}`)
    } catch (error) {
      ElMessage.error(`上传失败: ${fileItem.name}`)
    }
  }

  uploading.value = false
  selectedFiles.value = []
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  fetchItems()
}

const beforeRemove = (file, fileList) => {
  return true
}

const handleChange = (file, uploadFiles) => {
  selectedFiles.value = [...uploadFiles]
}

const handleEdit = (row) => {
  editForm.value = {
    id: row.id,
    title: row.title,
    content: row.content,
    category_id: row.category_id,
    difficulty: row.difficulty,
    status: row.status,
    source: row.source
  }
  editVisible.value = true
}

const submitEdit = async () => {
  if (!editForm.value) return

  editLoading.value = true
  try {
    await adminAPI.updateKnowledge(editForm.value.id, editForm.value)
    ElMessage.success('更新成功')
    editVisible.value = false
    fetchItems()
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    editLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除知识 "${row.title}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await adminAPI.deleteKnowledge(row.id)
    ElMessage.success('删除成功')
    fetchItems()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchItems()
  fetchCategories()
})
</script>

<style lang="scss" scoped>
.knowledge-admin-page {
  .page-title {
    margin: 0 0 24px;
    font-size: 24px;
    color: #303133;
  }

  .upload-card {
    margin-bottom: 20px;

    .card-header {
      font-weight: 600;
      color: #303133;
    }

    :deep(.el-upload) {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      width: 100%;
    }

    :deep(.el-upload__tip) {
      width: 100%;
      margin-top: 8px;
      color: #909399;
      font-size: 12px;
    }

    .upload-options {
      margin-top: 16px;
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }
  }

  .toolbar {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
  }

  .pagination-wrapper {
    display: flex;
    justify-content: center;
    margin-top: 20px;
  }

  .item-detail {
    h3 {
      margin: 0 0 16px;
      color: #303133;
    }

    .detail-meta {
      display: flex;
      gap: 8px;
    }

    .detail-content {
      max-height: 500px;
      overflow-y: auto;
      line-height: 1.8;
      color: #606266;
      font-size: 14px;

      h1, h2, h3, h4, h5, h6 {
        margin-top: 1.5em;
        margin-bottom: 0.5em;
        font-weight: 600;
        color: #303133;
      }

      h1 { font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
      h2 { font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
      h3 { font-size: 1.3em; }
      h4 { font-size: 1.1em; }

      p {
        margin: 1em 0;
      }

      code {
        background: #f0f0f0;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 0.9em;
        color: #e83e8c;
      }

      pre {
        background: #1e1e1e;
        color: #d4d4d4;
        padding: 16px;
        border-radius: 8px;
        overflow-x: auto;
        margin: 1em 0;

        code {
          background: transparent;
          padding: 0;
          color: inherit;
        }
      }

      blockquote {
        margin: 1em 0;
        padding: 0.5em 1em;
        border-left: 4px solid #409eff;
        background: #f5f7fa;
        color: #606266;

        p {
          margin: 0.5em 0;
        }
      }

      ul, ol {
        padding-left: 2em;
        margin: 1em 0;

        li {
          margin: 0.5em 0;
        }
      }

      table {
        width: 100%;
        border-collapse: collapse;
        margin: 1em 0;

        th, td {
          border: 1px solid #dcdfe6;
          padding: 8px 12px;
          text-align: left;
        }

        th {
          background: #f5f7fa;
          font-weight: 600;
        }

        tr:nth-child(even) {
          background: #fafafa;
        }
      }

      a {
        color: #409eff;
        text-decoration: none;

        &:hover {
          text-decoration: underline;
        }
      }

      img {
        max-width: 100%;
        border-radius: 8px;
      }

      hr {
        border: none;
        border-top: 1px solid #eee;
        margin: 2em 0;
      }
    }
  }
}
</style>
