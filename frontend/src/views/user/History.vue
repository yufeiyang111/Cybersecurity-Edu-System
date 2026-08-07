<template>
  <div class="history-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>问答历史</span>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索问题..."
          prefix-icon="Search"
          clearable
          @keyup.enter="handleSearch"
          style="width: 300px;"
        />
      </div>

      <el-table :data="records" v-loading="loading" stripe>
        <el-table-column prop="question" label="问题" min-width="200">
          <template #default="{ row }">
            <div class="question-cell">
              <span class="question-text">{{ row.question }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="answer" label="答案预览" min-width="200">
          <template #default="{ row }">
            <span class="answer-preview">{{ getAnswerPreview(row.answer) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="feedback" label="反馈" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.feedback" :type="getFeedbackType(row.feedback)" size="small">
              {{ getFeedbackText(row.feedback) }}
            </el-tag>
            <span v-else class="no-feedback">未反馈</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">查看</el-button>
            <el-button size="small" type="primary" @click="continueAsk(row)">继续问</el-button>
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
    <el-dialog v-model="detailVisible" title="问答详情" width="700px">
      <div v-if="currentRecord" class="qa-detail">
        <div class="detail-section">
          <h4>问题</h4>
          <p>{{ currentRecord.question }}</p>
        </div>
        <el-divider />
        <div class="detail-section">
          <h4>答案</h4>
          <div class="answer-content markdown-content" v-html="renderMarkdownSafe(currentRecord.answer)"></div>
        </div>
        <el-divider />
        <div class="detail-meta">
          <span>时间：{{ formatDate(currentRecord.created_at) }}</span>
          <span v-if="currentRecord.response_time">响应时间：{{ currentRecord.response_time.toFixed(2) }}秒</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="continueAsk(currentRecord)">继续问</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { qaAPI } from '@/api'
import { renderMarkdown } from '@/features/markdown/renderMarkdown'

const router = useRouter()
const loading = ref(false)
const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const detailVisible = ref(false)
const currentRecord = ref(null)

const getFeedbackType = (fb) => {
  const types = { good: 'success', neutral: 'info', bad: 'danger' }
  return types[fb]
}

const getFeedbackText = (fb) => {
  const texts = { good: '满意', neutral: '一般', bad: '不满意' }
  return texts[fb]
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getAnswerPreview = (answer) => {
  if (!answer) return '暂无答案'
  return answer.length > 100 ? answer.substring(0, 100) + '...' : answer
}

const renderMarkdownSafe = (content) => {
  return renderMarkdown(content)
}

const fetchHistory = async () => {
  loading.value = true
  try {
    const res = await qaAPI.getHistory({
      page: currentPage.value,
      per_page: pageSize.value,
      keyword: keyword.value || undefined
    })
    records.value = res.records || []
    total.value = res.total || 0
  } catch (error) {
    console.error('获取历史失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchHistory()
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchHistory()
}

const viewDetail = (row) => {
  currentRecord.value = row
  detailVisible.value = true
}

const continueAsk = (row) => {
  router.push({ path: '/qa', query: { topic: row.question } })
  detailVisible.value = false
}

onMounted(() => {
  fetchHistory()
})
</script>

<style lang="scss" scoped>
.history-page {
  :deep(.el-card) {
    .card-header {
      font-weight: 600;
    }
  }

  .toolbar {
    margin-bottom: 16px;
  }

  .question-cell {
    .question-text {
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }

  .answer-preview {
    color: #909399;
    font-size: 13px;
  }

  .no-feedback {
    color: #c0c4cc;
    font-size: 13px;
  }

  .pagination-wrapper {
    display: flex;
    justify-content: center;
    margin-top: 20px;
  }

  .qa-detail {
    .detail-section {
      h4 {
        margin: 0 0 12px;
        color: #303133;
      }

      p {
        margin: 0;
        color: #606266;
        line-height: 1.8;
      }
    }

    .detail-meta {
      display: flex;
      gap: 24px;
      color: #909399;
      font-size: 14px;
    }
  }
}
</style>
