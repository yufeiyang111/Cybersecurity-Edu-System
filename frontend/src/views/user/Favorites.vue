<template>
  <div class="favorites-page">
    <ProfileTabs
      :questions="questions"
      :favorites="favorites"
    />

    <section class="favorites-card">
      <div class="favorites-card__header">
        <div>
          <h3>我的收藏</h3>
          <span class="favorites-card__sub">{{ activeTab === 'qa' ? '收藏的问答' : '收藏的知识' }}</span>
        </div>
      </div>

      <el-tabs
        v-model="activeTab"
        class="favorites-tabs"
        @tab-change="handleTabChange"
      >
        <el-tab-pane label="问答收藏" name="qa">
          <div v-if="qaLoading" class="favorites-card__skeleton">
            <div v-for="index in 3" :key="index" class="skeleton-row" />
          </div>

          <div v-else-if="qaFavorites.length" class="favorites-card__list">
            <FavoriteQACard
              v-for="favorite in qaFavorites"
              :key="favorite.id"
              :favorite="favorite"
              @view="viewQADetail"
              @continue="continueAsk"
              @remove="removeQAFavorite"
            />
          </div>

          <el-empty
            v-else
            description="暂无问答收藏"
            :image-size="80"
            class="favorites-card__empty"
          />
        </el-tab-pane>

        <el-tab-pane label="知识收藏" name="knowledge">
          <div v-if="knowledgeLoading" class="favorites-card__skeleton">
            <div v-for="index in 3" :key="index" class="skeleton-row" />
          </div>

          <div v-else-if="knowledgeFavorites.length" class="favorites-card__list">
            <FavoriteKnowledgeCard
              v-for="item in knowledgeFavorites"
              :key="item.id"
              :item="item"
              @view="viewKnowledgeDetail"
              @remove="removeKnowledgeFavorite"
            />
          </div>

          <el-empty
            v-else
            description="暂无知识收藏"
            :image-size="80"
            class="favorites-card__empty"
          />
        </el-tab-pane>
      </el-tabs>

      <UserPagination
        v-model="currentPage"
        :total="total"
        :per-page="pageSize"
        @change="handlePageChange"
      />
    </section>

    <el-dialog v-model="qaDetailVisible" title="问答详情" width="min(700px, calc(100vw - 32px))">
      <div v-if="currentQARecord" class="qa-detail">
        <div class="qa-detail__section">
          <h4>问题</h4>
          <p>{{ currentQARecord.qa_record?.question }}</p>
        </div>
        <el-divider />
        <div class="qa-detail__section">
          <h4>答案</h4>
          <div
            class="qa-detail__answer markdown-content"
            v-html="renderMarkdownSafe(currentQARecord.qa_record?.answer)"
          ></div>
        </div>
      </div>
      <template #footer>
        <el-button @click="qaDetailVisible = false">关闭</el-button>
        <button
          type="button"
          class="row-btn row-btn--primary"
          @click="continueAsk"
        >
          继续问
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { qaAPI, knowledgeAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '@/features/markdown/renderMarkdown'
import ProfileTabs from '@/components/user/ProfileTabs.vue'
import FavoriteQACard from '@/components/user/FavoriteQACard.vue'
import FavoriteKnowledgeCard from '@/components/user/FavoriteKnowledgeCard.vue'
import UserPagination from '@/components/user/UserPagination.vue'
import { useProfileStats } from '@/composables/user/useProfileStats'

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

const { questions, favorites, load: loadStats } = useProfileStats()

const renderMarkdownSafe = (content) => {
  return renderMarkdown(content)
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
    loadStats()
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
    loadStats()
  } catch (error) {
    ElMessage.error('取消收藏失败')
  }
}

onMounted(() => {
  fetchQAFavorites()
  loadStats()
})
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;
@use '@/styles/user-cards' as *;

.favorites-page {
  min-width: 0;
}

.favorites-card {
  border: 1px solid $border-color;
  border-radius: 10px;
  background: $bg-white;
  overflow: hidden;
}

.favorites-card__header {
  display: flex;
  align-items: center;
  padding: 18px 20px;
  border-bottom: 1px solid $border-lighter;

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: $text-primary;
  }
}

.favorites-card__sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: $text-secondary;
}

.favorites-tabs {
  padding: 0 20px;

  :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }

  :deep(.el-tabs__nav-wrap::after) {
    background-color: $border-lighter;
  }

  :deep(.el-tabs__item) {
    color: $text-regular;
    font-size: 14px;

    &:hover {
      color: $brand-color;
    }

    &.is-active {
      color: $brand-color;
    }
  }

  :deep(.el-tabs__active-bar) {
    background-color: $brand-color;
  }
}

.favorites-card__skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
}

.favorites-card__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 0 16px;
}

.favorites-card__empty {
  padding: 48px 0;
}

.qa-detail__section {
  h4 {
    margin: 0 0 12px;
    color: $text-primary;
  }

  p {
    margin: 0;
    color: $text-regular;
    line-height: 1.8;
  }
}

.qa-detail__answer {
  color: $text-regular;
  line-height: 1.8;
}

@media (max-width: 640px) {
  .favorites-tabs {
    padding: 0 12px;
  }
}
</style>
