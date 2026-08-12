<template>
  <div class="detail-page">
    <header class="page-header">
      <div class="header-content">
        <el-button text @click="$router.back()">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
      </div>
    </header>

    <div class="detail-container" v-loading="loading">
      <article v-if="item" class="knowledge-article">
        <header class="article-header">
          <div class="tags">
            <el-tag>{{ item.category_name || '未分类' }}</el-tag>
            <el-tag :type="getDifficultyType(item.difficulty)">
              {{ getDifficultyText(item.difficulty) }}
            </el-tag>
          </div>
          <h1>{{ item.title }}</h1>
          <div class="meta">
            <span v-if="item.author">作者：{{ item.author }}</span>
            <span>浏览：{{ item.view_count || 0 }}</span>
            <span>收藏：{{ item.favorite_count || 0 }}</span>
            <span>发布时间：{{ formatDate(item.created_at) }}</span>
          </div>
          <div class="source" v-if="item.source">
            <el-icon><Link /></el-icon>
            来源：{{ item.source }}
          </div>
        </header>

        <div class="article-tags" v-if="item.tags?.length">
          <el-tag v-for="tag in item.tags" :key="tag" size="small">
            {{ tag }}
          </el-tag>
        </div>

        <div class="article-content markdown-content" v-html="renderContent"></div>

        <footer class="article-footer">
          <div class="actions">
            <el-button @click="handleFavorite" :type="isFavorited ? 'warning' : ''">
              <el-icon><Star /></el-icon>
              {{ isFavorited ? '已收藏' : '收藏' }}
            </el-button>
            <el-button @click="handleAsk">
              <el-icon><ChatDotRound /></el-icon>
              相关问答
            </el-button>
          </div>
          <div class="related" v-if="relatedItems.length">
            <h3>相关知识</h3>
            <div class="related-list">
              <div
                v-for="rel in relatedItems"
                :key="rel.id"
                class="related-item"
                @click="goToDetail(rel.id)"
              >
                {{ rel.title }}
              </div>
            </div>
          </div>
        </footer>
      </article>

      <el-empty v-else-if="!loading" description="知识不存在" />
    </div>

    <!-- 相关问答弹窗 -->
    <el-dialog v-model="relatedQADialogVisible" title="相关问答" width="700px">
      <div v-loading="relatedQALoading">
        <el-table v-if="relatedQA.length" :data="relatedQA" stripe>
          <el-table-column prop="question" label="问题" min-width="200">
            <template #default="{ row }">
              <div class="question-cell">{{ row.question }}</div>
              <div class="matched-kw" v-if="row.matched_keywords?.length">
                <el-tag size="small" v-for="kw in row.matched_keywords" :key="kw">{{ kw }}</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="answer_preview" label="答案预览" min-width="200">
            <template #default="{ row }">
              <span class="answer-preview">{{ row.answer_preview }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="viewQA(row)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无相关问答" />
      </div>
      <template #footer>
        <el-button @click="relatedQADialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="goToQA">进入问答</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { knowledgeAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '@/features/markdown/renderMarkdown'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const item = ref(null)
const relatedItems = ref([])
const isFavorited = ref(false)
const relatedQADialogVisible = ref(false)
const relatedQALoading = ref(false)
const relatedQA = ref([])

const renderContent = computed(() => {
  return renderMarkdown(item.value?.content)
})

const getDifficultyType = (difficulty) => {
  const types = { easy: 'success', medium: 'warning', hard: 'danger' }
  return types[difficulty] || 'info'
}

const getDifficultyText = (difficulty) => {
  const texts = { easy: '入门', medium: '进阶', hard: '高级' }
  return texts[difficulty] || '普通'
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const fetchDetail = async () => {
  loading.value = true
  try {
    const res = await knowledgeAPI.getKnowledge(route.params.id)
    item.value = res.item
    // 正文不依赖推荐结果，先展示内容；推荐和收藏状态在后台加载。
    loading.value = false

    // 获取相关知识（使用混合推荐算法）
    const relatedPromise = knowledgeAPI.getRelatedKnowledge(route.params.id, { top_k: 4 })
      .then((relatedRes) => {
        relatedItems.value = relatedRes.items || []
      })
      .catch((e) => {
        console.error('获取相关知识失败', e)
        relatedItems.value = []
      })

    // 获取收藏状态
    const favoritePromise = userStore.isLoggedIn
      ? knowledgeAPI.getFavoriteStatus(route.params.id)
        .then((favRes) => {
          isFavorited.value = favRes.is_favorited
        })
        .catch((e) => {
          console.error('获取收藏状态失败', e)
        })
      : Promise.resolve()

    await Promise.all([relatedPromise, favoritePromise])
  } catch (error) {
    ElMessage.error('获取知识详情失败')
  } finally {
    loading.value = false
  }
}

const handleFavorite = async () => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }

  try {
    if (isFavorited.value) {
      await knowledgeAPI.removeFavorite(route.params.id)
      isFavorited.value = false
      if (item.value) {
        item.value.favorite_count = Math.max(0, (item.value.favorite_count || 1) - 1)
      }
      ElMessage.success('已取消收藏')
    } else {
      await knowledgeAPI.addFavorite(route.params.id)
      isFavorited.value = true
      if (item.value) {
        item.value.favorite_count = (item.value.favorite_count || 0) + 1
      }
      ElMessage.success('收藏成功')
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleAsk = async () => {
  if (!item.value) return

  relatedQADialogVisible.value = true
  relatedQALoading.value = true
  relatedQA.value = []

  try {
    const res = await knowledgeAPI.getRelatedQA(route.params.id, { limit: 10 })
    relatedQA.value = res.questions || []
  } catch (error) {
    console.error('获取相关问答失败', error)
    ElMessage.error('获取相关问答失败')
  } finally {
    relatedQALoading.value = false
  }
}

const viewQA = (qa) => {
  relatedQADialogVisible.value = false
  router.push({ path: '/qa', query: { topic: qa.question } })
}

const goToQA = () => {
  relatedQADialogVisible.value = false
  if (item.value) {
    router.push({ path: '/qa', query: { topic: item.value.title } })
  }
}

const goToDetail = (id) => {
  router.push(`/knowledge/${id}`)
}

onMounted(() => {
  fetchDetail()
})
</script>

<style lang="scss" scoped>
.detail-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  background: #fff;
  padding: 12px 0;
  border-bottom: 1px solid #e4e7ed;
  
  .header-content {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 20px;
  }
}

.detail-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 20px;
}

.knowledge-article {
  background: #fff;
  border-radius: 12px;
  padding: 32px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.article-header {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid #e4e7ed;
  
  .tags {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }
  
  h1 {
    margin: 0 0 16px;
    font-size: 28px;
    color: #303133;
    line-height: 1.4;
  }
  
  .meta {
    display: flex;
    gap: 24px;
    color: #909399;
    font-size: 14px;
  }
  
  .source {
    margin-top: 12px;
    color: #10b981;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.article-tags {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.article-content {
  line-height: 1.8;
  font-size: 15px;
  color: #606266;

  :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    font-weight: 600;
    color: #303133;
  }

  :deep(h1) { font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
  :deep(h2) { font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
  :deep(h3) { font-size: 1.3em; }
  :deep(h4) { font-size: 1.1em; }

  :deep(p) {
    margin: 1em 0;
  }

  :deep(code) {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
    color: #e83e8c;
  }

  :deep(blockquote) {
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 4px solid #409eff;
    background: #f5f7fa;
    color: #606266;

    :deep(p) {
      margin: 0.5em 0;
    }
  }

  :deep(ul), :deep(ol) {
    padding-left: 2em;
    margin: 1em 0;

    :deep(li) {
      margin: 0.5em 0;
    }
  }

  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;

    :deep(th), :deep(td) {
      border: 1px solid #dcdfe6;
      padding: 8px 12px;
      text-align: left;
    }

    :deep(th) {
      background: #f5f7fa;
      font-weight: 600;
    }

    :deep(tr:nth-child(even)) {
      background: #fafafa;
    }
  }

  :deep(a) {
    color: #409eff;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  :deep(img) {
    max-width: 100%;
    border-radius: 8px;
  }

  :deep(hr) {
    border: none;
    border-top: 1px solid #eee;
    margin: 2em 0;
  }
}

.article-footer {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid #e4e7ed;

  .actions {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
  }

  .related {
    h3 {
      margin: 0 0 16px;
      font-size: 16px;
      color: #303133;
    }

    .related-list {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;

      .related-item {
        padding: 12px 16px;
        background: #f5f7fa;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.3s;

        &:hover {
          background: #ecf5ff;
          color: #10b981;
        }
      }
    }
  }
}

.question-cell {
  font-weight: 500;
  margin-bottom: 6px;
}

.matched-kw {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;

  .el-tag {
    margin-right: 4px;
  }
}

.answer-preview {
  color: #909399;
  font-size: 13px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
