<template>
  <div class="knowledge-admin-page">
    <div class="page-heading animate-fadeIn">
      <h2>知识管理</h2>
      <el-button
        type="primary"
        @click="scrollToUpload"
      >
        <el-icon>
          <Upload />
        </el-icon>
        上传文档
      </el-button>
    </div>

    <el-card
      ref="uploadCardRef"
      class="panel-card upload-card animate-fadeIn"
      shadow="never"
      style="animation-delay: 0.08s"
    >
      <template #header>
        <div class="panel-card__header">
          <span>文档上传</span>
          <span class="panel-card__header-tip">支持 PDF、Word(.docx/.doc)、HTML、Markdown、TXT</span>
        </div>
      </template>

      <el-upload
        ref="uploadRef"
        class="upload-drop"
        drag
        :auto-upload="false"
        :on-change="handleChange"
        :before-remove="beforeRemove"
        multiple
        accept=".pdf,.docx,.doc,.html,.htm,.md,.txt"
      >
        <el-icon class="upload-drop__icon">
          <UploadFilled />
        </el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或 <em>点击选择文件</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            单文件不超过 10MB
          </div>
        </template>
      </el-upload>

      <div class="upload-options">
        <span class="upload-options__label">上传设置</span>
        <el-select
          v-model="uploadCategoryId"
          placeholder="选择分类（可选）"
          clearable
          size="default"
          style="width: 200px"
        >
          <el-option
            v-for="cat in categories"
            :key="cat.id"
            :label="cat.name"
            :value="cat.id"
          />
        </el-select>
        <el-select
          v-model="uploadDifficulty"
          placeholder="难度"
          size="default"
          style="width: 140px"
        >
          <el-option label="入门" value="easy" />
          <el-option label="进阶" value="medium" />
          <el-option label="高级" value="hard" />
        </el-select>
        <el-button
          type="success"
          :loading="uploading"
          @click="submitUpload"
        >
          <el-icon>
            <UploadFilled />
          </el-icon>
          开始上传（{{ selectedFiles.length }}）
        </el-button>
      </div>
    </el-card>

    <el-card
      class="panel-card list-card animate-fadeIn"
      shadow="never"
      style="animation-delay: 0.16s"
    >
      <template #header>
        <div class="panel-card__header">
          <span>知识列表</span>
          <span class="panel-card__header-count">共 {{ total }} 条</span>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索标题..."
          clearable
          class="toolbar__search"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon>
              <Search />
            </el-icon>
          </template>
        </el-input>

        <div class="toolbar__filters">
          <button
            v-for="option in statusOptions"
            :key="option.value"
            type="button"
            class="filter-chip"
            :class="{ 'filter-chip--active': filterStatus === option.value }"
            @click="handleFilterChange(option.value)"
          >
            <span
              class="filter-chip__dot"
              :style="{ background: option.color }"
            />
            {{ option.label }}
          </button>
        </div>
      </div>

      <el-table
        :data="items"
        v-loading="loading"
        stripe
        class="knowledge-table"
        @row-click="handleView"
      >
        <template #empty>
          <div class="table-empty">暂无知识文档</div>
        </template>
        <el-table-column label="标题" min-width="240">
          <template #default="{ row }">
            <div class="title-cell">
              <span class="title-cell__icon">
                <el-icon>
                  <Document />
                </el-icon>
              </span>
              <span class="title-cell__text">{{ row.title }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category_name" label="分类" width="120">
          <template #default="{ row }">
            <span v-if="row.category_name" class="category-tag">{{ row.category_name }}</span>
            <span v-else class="muted-text">未分类</span>
          </template>
        </el-table-column>
        <el-table-column label="难度" width="90">
          <template #default="{ row }">
            <span
              class="difficulty-dots"
              :class="`difficulty-dots--${row.difficulty || 'medium'}`"
              :title="getDifficultyText(row.difficulty)"
            >
              <i
                v-for="n in 3"
                :key="n"
                :class="{ 'is-active': n <= difficultyLevel(row.difficulty) }"
              />
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="status-text" :class="`status-text--${row.status}`">
              <i class="status-text__dot" />
              {{ getStatusText(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="浏览" width="80" align="center">
          <template #default="{ row }">
            <span class="view-count">
              <el-icon>
                <View />
              </el-icon>
              {{ row.view_count || 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-tooltip content="查看" placement="top">
                <el-button
                  size="small"
                  circle
                  class="action-btn"
                  @click.stop="handleView(row)"
                >
                  <el-icon>
                    <View />
                  </el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="编辑" placement="top">
                <el-button
                  size="small"
                  circle
                  class="action-btn"
                  @click.stop="handleEdit(row)"
                >
                  <el-icon>
                    <Edit />
                  </el-icon>
                </el-button>
              </el-tooltip>
              <template v-if="row.status === 'draft'">
                <el-tooltip content="审核通过" placement="top">
                  <el-button
                    size="small"
                    circle
                    type="success"
                    class="action-btn"
                    @click.stop="handleAudit(row, 'approve')"
                  >
                    <el-icon>
                      <CircleCheck />
                    </el-icon>
                  </el-button>
                </el-tooltip>
                <el-tooltip content="审核拒绝" placement="top">
                  <el-button
                    size="small"
                    circle
                    type="warning"
                    class="action-btn"
                    @click.stop="handleAudit(row, 'reject')"
                  >
                    <el-icon>
                      <Close />
                    </el-icon>
                  </el-button>
                </el-tooltip>
              </template>
              <el-tooltip content="删除" placement="top">
                <el-button
                  size="small"
                  circle
                  type="danger"
                  class="action-btn"
                  @click.stop="handleDelete(row)"
                >
                  <el-icon>
                    <Delete />
                  </el-icon>
                </el-button>
              </el-tooltip>
            </div>
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
          <span v-if="currentItem.category_name" class="category-tag">{{ currentItem.category_name }}</span>
          <span class="difficulty-dots" :class="`difficulty-dots--${currentItem.difficulty || 'medium'}`">
            <i v-for="n in 3" :key="n" :class="{ 'is-active': n <= difficultyLevel(currentItem.difficulty) }" />
          </span>
          <span class="status-text" :class="`status-text--${currentItem.status}`">
            <i class="status-text__dot" />
            {{ getStatusText(currentItem.status) }}
          </span>
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
          <el-input v-model="editForm.content" type="textarea" :rows="32" />
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
import {
  Upload,
  UploadFilled,
  Search,
  View,
  Edit,
  Delete,
  CircleCheck,
  Close,
  Document
} from '@element-plus/icons-vue'
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
const uploadCardRef = ref(null)
const uploadCategoryId = ref(null)
const uploadDifficulty = ref('medium')
const selectedFiles = ref([])

// 编辑相关
const editVisible = ref(false)
const editLoading = ref(false)
const editForm = ref(null)

const statusOptions = [
  { value: '', label: '全部', color: '#909399' },
  { value: 'published', label: '已发布', color: '#2ea44f' },
  { value: 'draft', label: '草稿', color: '#d29922' },
  { value: 'archived', label: '已归档', color: '#6e7781' }
]

const renderContent = computed(() => {
  return renderMarkdown(currentItem.value?.content)
})

const difficultyLevel = (difficulty) => {
  const levels = { easy: 1, medium: 2, hard: 3 }
  return levels[difficulty] || 2
}

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
  const date = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const fetchItems = async () => {
  loading.value = true
  try {
    const res = await adminAPI.getAllKnowledge({
      page: currentPage.value,
      per_page: pageSize.value,
      status: filterStatus.value || undefined,
      keyword: keyword.value.trim() || undefined
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

const handleFilterChange = (status) => {
  filterStatus.value = status
  handleSearch()
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

const scrollToUpload = () => {
  if (uploadCardRef.value) {
    uploadCardRef.value.$el.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
    content: row.content || '',
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
  // ==================== 页面标题行 ====================
  .page-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      color: #1f2937;
    }
  }

  // ==================== 内容卡片 ====================
  .panel-card {
    border-radius: 12px;
    border: 1px solid #e6e8eb;
    transition: transform 0.25s ease, box-shadow 0.25s ease;

    :deep(.el-card__header) {
      background: #fff;
      border-bottom-color: #e6e8eb;
    }

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
    }
  }

  .panel-card__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: 600;
    color: #303133;
  }

  .panel-card__header-tip {
    font-size: 12px;
    font-weight: 400;
    color: #909399;
  }

  .panel-card__header-count {
    font-size: 12px;
    font-weight: 400;
    color: #909399;
  }

  // ==================== 上传区 ====================
  .upload-card {
    margin-bottom: 20px;

    :deep(.el-upload) {
      width: 100%;
    }
  }

  .upload-drop {
    :deep(.el-upload-dragger) {
      border: 2px dashed #d0d7de;
      border-radius: 12px;
      padding: 28px 0;
      transition: border-color 0.25s ease, background 0.25s ease;

      &:hover {
        border-color: #2ea44f;
        background: rgba(46, 164, 79, 0.04);
      }
    }
  }

  .upload-drop__icon {
    font-size: 44px;
    color: #c8d2dd;
    margin-bottom: 10px;
    transition: color 0.25s ease, transform 0.25s ease;
  }

  .upload-drop:hover .upload-drop__icon {
    color: #2ea44f;
    transform: translateY(-3px);
  }

  .upload-options {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 16px;
    flex-wrap: wrap;
  }

  .upload-options__label {
    font-size: 13px;
    font-weight: 600;
    color: #606266;
  }

  // ==================== 列表区 ====================
  .list-card {
    :deep(.el-card__body) {
      padding: 0;
    }
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    padding: 16px 20px;
    border-bottom: 1px solid #e6e8eb;
  }

  .toolbar__search {
    width: 280px;
  }

  .toolbar__filters {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border: 1px solid #e6e8eb;
    border-radius: 999px;
    background: #fff;
    color: #606266;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      border-color: #2ea44f;
      color: #2ea44f;
    }

    &--active {
      background: rgba(46, 164, 79, 0.08);
      border-color: #2ea44f;
      color: #2ea44f;
      font-weight: 600;
    }
  }

  .filter-chip__dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  // ==================== 表格 ====================
  .knowledge-table {
    min-height: 620px;

    :deep(th.el-table__cell) {
      background: #fafbfc;
    }

    :deep(tbody tr) {
      cursor: pointer;
      transition: background 0.15s ease;
    }

    :deep(tbody tr:hover > td.el-table__cell) {
      background: #f6f8fa;
    }
  }

  .table-empty {
    padding: 80px 0;
    color: #909399;
    font-size: 13px;
  }

  .title-cell {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .title-cell__icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: #eef2ff;
    color: #4f46e5;
    flex-shrink: 0;
  }

  .title-cell__text {
    color: #303133;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: color 0.15s ease;

    &:hover {
      color: #2ea44f;
    }
  }

  .category-tag {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 999px;
    background: #f0f2f5;
    color: #57606a;
    font-size: 12px;
    font-weight: 500;
  }

  .muted-text {
    color: #c8d2dd;
    font-size: 12px;
  }

  // 难度点（●●●）
  .difficulty-dots {
    display: inline-flex;
    gap: 4px;

    i {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #e6e8eb;
      transition: background 0.2s ease;
    }

    &--easy i.is-active {
      background: #2ea44f;
    }

    &--medium i.is-active {
      background: #d29922;
    }

    &--hard i.is-active {
      background: #cf222e;
    }
  }

  // 状态点 + 文字
  .status-text {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;

    &__dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    &--published {
      color: #2ea44f;

      .status-text__dot {
        background: #2ea44f;
      }
    }

    &--draft {
      color: #d29922;

      .status-text__dot {
        background: #d29922;
      }
    }

    &--archived {
      color: #6e7781;

      .status-text__dot {
        background: #6e7781;
      }
    }
  }

  .view-count {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: #909399;
    font-size: 13px;
    font-variant-numeric: tabular-nums;
  }

  // 操作按钮
  .action-buttons {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .action-btn {
    border-color: #e6e8eb;
    color: #606266;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 10px rgba(15, 23, 42, 0.12);
      border-color: #2ea44f;
      color: #2ea44f;
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: center;
    padding: 16px 0;
  }

  // ==================== 详情 ====================
  .item-detail {
    h3 {
      margin: 0 0 16px;
      color: #303133;
    }

    .detail-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .detail-content {
      max-height: 500px;
      overflow-y: auto;
      line-height: 1.8;
      color: #606266;
      font-size: 14px;
    }
  }
}

@media (max-width: 768px) {
  .knowledge-admin-page {
    .page-heading {
      flex-wrap: wrap;

      .el-button {
        width: 100%;
      }
    }

    .toolbar__search {
      width: 100%;
    }

    .upload-options {
      .el-select {
        width: 100% !important;
      }

      .el-button {
        width: 100%;
      }
    }

    .panel-card__header-tip {
      display: none;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .knowledge-admin-page {
    .panel-card {
      transition: none;
    }

    .panel-card:hover {
      transform: none;
    }

    .upload-drop__icon {
      transition: none;
    }

    .filter-chip,
    .action-btn,
    .difficulty-dots i,
    .title-cell__text {
      transition: none;
    }
  }
}
</style>
