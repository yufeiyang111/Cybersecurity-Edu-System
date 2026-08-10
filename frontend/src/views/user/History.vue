<template>
  <div class="history-page">
    <ProfileTabs
      :questions="questions"
      :favorites="favorites"
    />

    <section class="history-card">
      <div class="history-card__header">
        <div>
          <h3>问答历史</h3>
          <span class="history-card__sub">共 {{ total }} 条问答记录</span>
        </div>
        <el-input
          v-model="keyword"
          placeholder="搜索问题..."
          clearable
          class="history-card__search"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon>
              <Search />
            </el-icon>
          </template>
        </el-input>
      </div>

      <div v-if="loading" class="history-card__skeleton">
        <div v-for="index in 3" :key="index" class="skeleton-row" />
      </div>

      <div v-else-if="records.length" class="history-card__list">
        <HistoryRecordCard
          v-for="record in records"
          :key="record.id"
          :record="record"
          @view="viewDetail"
          @continue="continueAsk"
        />
      </div>

      <el-empty
        v-else
        description="暂无问答记录，快去提问吧"
        :image-size="80"
        class="history-card__empty"
      />

      <UserPagination
        v-model="currentPage"
        :total="total"
        :per-page="pageSize"
        @change="handlePageChange"
      />
    </section>

    <el-dialog v-model="detailVisible" title="问答详情" width="min(700px, calc(100vw - 32px))">
      <div v-if="currentRecord" class="qa-detail">
        <div class="qa-detail__section">
          <h4>问题</h4>
          <p>{{ currentRecord.question }}</p>
        </div>
        <el-divider />
        <div class="qa-detail__section">
          <h4>答案</h4>
          <div
            class="qa-detail__answer markdown-content"
            v-html="renderMarkdownSafe(currentRecord.answer)"
          ></div>
        </div>
        <el-divider />
        <div class="qa-detail__meta">
          <span>时间：{{ formatDate(currentRecord.created_at) }}</span>
          <span v-if="currentRecord.response_time">响应时间：{{ currentRecord.response_time.toFixed(2) }}秒</span>
          <span v-if="currentRecord.model_name">模型：{{ currentRecord.model_name }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <button
          type="button"
          class="row-btn row-btn--primary"
          @click="continueAsk(currentRecord)"
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
import { qaAPI } from '@/api'
import { renderMarkdown } from '@/features/markdown/renderMarkdown'
import ProfileTabs from '@/components/user/ProfileTabs.vue'
import HistoryRecordCard from '@/components/user/HistoryRecordCard.vue'
import UserPagination from '@/components/user/UserPagination.vue'
import { useProfileStats } from '@/composables/user/useProfileStats'

const router = useRouter()
const loading = ref(false)
const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(5)
const keyword = ref('')
const detailVisible = ref(false)
const currentRecord = ref(null)

const { questions, favorites, load: loadStats } = useProfileStats()

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
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
  if (!row) return
  router.push({ path: '/qa', query: { topic: row.question } })
  detailVisible.value = false
}

onMounted(() => {
  fetchHistory()
  loadStats()
})
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;
@use '@/styles/user-cards' as *;

.history-page {
  min-width: 0;
}

.history-card {
  border: 1px solid $border-color;
  border-radius: 10px;
  background: $bg-white;
  overflow: hidden;
}

.history-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid $border-lighter;

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: $text-primary;
  }
}

.history-card__sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: $text-secondary;
}

.history-card__search {
  width: 260px;
}

.history-card__skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
}

.history-card__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
}

.history-card__empty {
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

.qa-detail__meta {
  display: flex;
  gap: 24px;
  color: $text-secondary;
  font-size: 14px;
}

@media (max-width: 640px) {
  .history-card__header {
    flex-direction: column;
    align-items: stretch;
  }

  .history-card__search {
    width: 100%;
  }

  .history-card__list {
    padding: 12px;
  }
}
</style>
