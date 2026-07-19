<template>
  <div class="favorites-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>我的收藏</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="问答收藏" name="qa">
          <el-table :data="qaFavorites" v-loading="qaLoading" stripe>
            <el-table-column prop="question" label="问题" min-width="200">
              <template #default="{ row }">
                <div class="question-cell">
                  <span class="question-text">{{ row.qa_record?.question }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="answer" label="答案预览" min-width="200">
              <template #default="{ row }">
                <span class="answer-preview">{{ getAnswerPreview(row.qa_record?.answer) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="收藏时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="viewQADetail(row)">查看</el-button>
                <el-button size="small" type="danger" @click="removeQAFavorite(row)">取消</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!qaLoading && !qaFavorites.length" description="暂无问答收藏" />
        </el-tab-pane>

        <el-tab-pane label="知识收藏" name="knowledge">
          <el-table :data="knowledgeFavorites" v-loading="knowledgeLoading" stripe>
            <el-table-column prop="title" label="标题" min-width="200">
              <template #default="{ row }">
                <div class="title-cell">
                  <span class="title-text">{{ row.title }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="category_name" label="分类" width="120" />
            <el-table-column prop="summary" label="摘要" min-width="200">
              <template #default="{ row }">
                <span class="summary-preview">{{ getSummaryPreview(row.summary) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="view_count" label="浏览" width="80" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="viewKnowledgeDetail(row)">查看</el-button>
                <el-button size="small" type="danger" @click="removeKnowledgeFavorite(row)">取消</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!knowledgeLoading && !knowledgeFavorites.length" description="暂无知识收藏" />
        </el-tab-pane>
      </el-tabs>

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

    <!-- QA详情弹窗 -->
    <el-dialog v-model="qaDetailVisible" title="问答详情" width="700px">
      <div v-if="currentQARecord" class="qa-detail">
        <div class="detail-section">
          <h4>问题</h4>
          <p>{{ currentQARecord.qa_record?.question }}</p>
        </div>
        <el-divider />
        <div class="detail-section">
          <h4>答案</h4>
          <div class="answer-content markdown-content" v-html="renderMarkdown(currentQARecord.qa_record?.answer)"></div>
        </div>
      </div>
      <template #footer>
        <el-button @click="qaDetailVisible = false">关闭</el-button>
        <el-button type="primary" @click="continueAsk">继续问</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { qaAPI, knowledgeAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'

const router = useRouter()
const activeTab = ref('qa')
const qaLoading = ref(false)
const knowledgeLoading = ref(false)
const qaFavorites = ref([])
const knowledgeFavorites = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const qaDetailVisible = ref(false)
const currentQARecord = ref(null)

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getAnswerPreview = (answer) => {
  if (!answer) return '暂无答案'
  return answer.length > 100 ? answer.substring(0, 100) + '...' : answer
}

const getSummaryPreview = (summary) => {
  if (!summary) return '暂无摘要'
  return summary.length > 100 ? summary.substring(0, 100) + '...' : summary
}

const renderMarkdown = (content) => {
  if (!content) return ''
  return marked(content)
}

const fetchQAFavorites = async () => {
  qaLoading.value = true
  try {
    const res = await qaAPI.getFavorites({
      page: currentPage.value,
      per_page: pageSize.value
    })
    qaFavorites.value = res.favorites || []
    total.value = res.total || 0
  } catch (error) {
    console.error('获取收藏失败')
  } finally {
    qaLoading.value = false
  }
}

const fetchKnowledgeFavorites = async () => {
  knowledgeLoading.value = true
  try {
    const res = await knowledgeAPI.getMyFavorites({
      page: currentPage.value,
      per_page: pageSize.value
    })
    knowledgeFavorites.value = res.items || []
    total.value = res.total || 0
  } catch (error) {
    console.error('获取知识收藏失败')
  } finally {
    knowledgeLoading.value = false
  }
}

const handleTabChange = (tabName) => {
  currentPage.value = 1
  if (tabName === 'qa') {
    fetchQAFavorites()
  } else {
    fetchKnowledgeFavorites()
  }
}

const handlePageChange = (page) => {
  currentPage.value = page
  if (activeTab.value === 'qa') {
    fetchQAFavorites()
  } else {
    fetchKnowledgeFavorites()
  }
}

const viewQADetail = (row) => {
  currentQARecord.value = row
  qaDetailVisible.value = true
}

const continueAsk = () => {
  if (currentQARecord.value?.qa_record) {
    router.push({ path: '/qa', query: { topic: currentQARecord.value.qa_record.question } })
  }
  qaDetailVisible.value = false
}

const removeQAFavorite = async (row) => {
  try {
    await qaAPI.removeFavorite(row.id)
    ElMessage.success('已取消收藏')
    fetchQAFavorites()
  } catch (error) {
    ElMessage.error('取消收藏失败')
  }
}

const viewKnowledgeDetail = (row) => {
  router.push(`/knowledge/${row.id}`)
}

const removeKnowledgeFavorite = async (row) => {
  try {
    await knowledgeAPI.removeFavorite(row.id)
    ElMessage.success('已取消收藏')
    fetchKnowledgeFavorites()
  } catch (error) {
    ElMessage.error('取消收藏失败')
  }
}

onMounted(() => {
  fetchQAFavorites()
})
</script>

<style lang="scss" scoped>
.favorites-page {
  :deep(.el-card) {
    .card-header {
      font-weight: 600;
    }
  }

  .question-cell, .title-cell {
    .question-text, .title-text {
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }

  .answer-preview, .summary-preview {
    color: #909399;
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
  }
}
</style>
