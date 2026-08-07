<template>
  <div class="knowledge-page">
    <header class="page-header">
      <div class="header-orb"></div>
      <div class="header-grid"></div>
      <div class="header-inner">
        <button type="button" class="back-btn" @click="goBack">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5" />
            <path d="M12 19l-7-7 7-7" />
          </svg>
          返回
        </button>
        <div class="header-content">
          <div class="header-left">
            <div class="header-badge">
              <span class="badge-dot"></span>
              知识库
            </div>
            <h1 class="header-title">
              网络安全知识库
            </h1>
            <p class="header-desc">浏览网络安全知识，支持分类筛选、关键词检索与难度筛选</p>
          </div>
          <div class="header-right">
            <div class="search-box">
              <div class="search-input">
                <el-input
                  v-model="keyword"
                  placeholder="搜索知识标题或内容..."
                  clearable
                  @keyup.enter="handleSearch"
                >
                  <template #prefix>
                    <el-icon>
                      <Search />
                    </el-icon>
                  </template>
                </el-input>
              </div>
              <button type="button" class="search-btn" @click="handleSearch">
                搜索
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <div class="knowledge-container">
      <KnowledgeSidebar
        :categories="categories"
        :active="activeCategory"
        :all-count="allCount"
        @select="handleCategorySelect"
      />

      <main class="knowledge-main">
        <div class="toolbar">
          <div class="difficulty-filters">
            <button
              v-for="difficulty in difficulties"
              :key="difficulty.value"
              type="button"
              class="chip"
              :class="{ active: activeDifficulty === difficulty.value }"
              @click="handleDifficultyFilter(difficulty.value)"
            >
              {{ difficulty.label }}
            </button>
          </div>
          <span class="total-count">
            <span class="total-dot"></span>
            共 {{ total }} 条知识
          </span>
        </div>

        <div v-if="loading" class="knowledge-grid">
          <div v-for="index in 6" :key="index" class="skeleton-card">
            <div class="sk sk-tags"></div>
            <div class="sk sk-title"></div>
            <div class="sk sk-line"></div>
            <div class="sk sk-line short"></div>
          </div>
        </div>

        <div v-else-if="items.length === 0" class="empty-box">
          <el-empty description="暂无知识条目" />
        </div>

        <div v-else class="knowledge-grid">
          <KnowledgeCard
            v-for="(item, index) in items"
            :key="item.id"
            :item="item"
            :delay="index * 60"
            @click="goToDetail(item.id)"
          />
        </div>

        <div v-if="total > pageSize" class="pagination-wrapper">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            @current-change="handlePageChange"
          />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { knowledgeAPI } from '@/api'
import KnowledgeCard from '@/components/knowledge/KnowledgeCard.vue'
import KnowledgeSidebar from '@/components/knowledge/KnowledgeSidebar.vue'

const router = useRouter()

const loading = ref(false)
const items = ref([])
const categories = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(12)
const keyword = ref('')
const activeCategory = ref('')
const activeDifficulty = ref('')

const difficulties = [
  { value: '', label: '全部难度' },
  { value: 'easy', label: '入门' },
  { value: 'medium', label: '进阶' },
  { value: 'hard', label: '高级' }
]

const allCount = computed(() => {
  return categories.value.reduce((sum, cat) => sum + (Number(cat.item_count) || 0), 0)
})

const fetchCategories = async () => {
  try {
    const res = await knowledgeAPI.getCategories()
    categories.value = res.categories || []
  } catch (error) {
    console.error('获取分类失败')
  }
}

const fetchItems = async () => {
  loading.value = true
  try {
    const res = await knowledgeAPI.getKnowledgeList({
      page: currentPage.value,
      per_page: pageSize.value,
      category_id: activeCategory.value || undefined,
      difficulty: activeDifficulty.value || undefined,
      keyword: keyword.value || undefined
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

const handleCategorySelect = (categoryId) => {
  activeCategory.value = categoryId
  currentPage.value = 1
}

const handleDifficultyFilter = (difficulty) => {
  activeDifficulty.value = difficulty
  currentPage.value = 1
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchItems()
}

const goBack = () => {
  if (router.options.history.state.back) {
    router.back()
  } else {
    router.push('/')
  }
}

const goToDetail = (id) => {
  router.push(`/knowledge/${id}`)
}

watch([activeCategory, activeDifficulty], () => {
  currentPage.value = 1
  fetchItems()
})

onMounted(() => {
  fetchCategories()
  fetchItems()
})
</script>

<style lang="scss" scoped>
.knowledge-page {
  min-height: 100vh;
  background: #f6f8fa;
  font-family:
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    'Noto Sans',
    Helvetica,
    Arial,
    sans-serif;
}

/* ==================== 页头 ==================== */
.page-header {
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
  color: #c9d1d9;
  padding: 32px 0 52px;
}

.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  position: relative;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: 999px;
  border: 1px solid rgba(240, 246, 252, 0.22);
  background: rgba(255, 255, 255, 0.06);
  color: #c9d1d9;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  margin-bottom: 24px;
  opacity: 0;
  transform: translateY(14px);
  animation: kbUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  transition:
    background 0.25s,
    border-color 0.25s,
    color 0.25s;
}

.back-btn svg {
  width: 14px;
  height: 14px;
  transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.back-btn:hover {
  background: rgba(46, 164, 79, 0.14);
  border-color: rgba(46, 164, 79, 0.45);
  color: #fff;
}

.back-btn:hover svg {
  transform: translateX(-3px);
}

.header-orb {
  position: absolute;
  width: 460px;
  height: 460px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(46, 164, 79, 0.16), transparent 65%);
  top: -190px;
  right: -120px;
  animation: kbBreathe 7s ease-in-out infinite;
}

@keyframes kbBreathe {
  0%,
  100% {
    opacity: 0.7;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.12);
  }
}

.header-grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(240, 246, 252, 0.05) 1px, transparent 1px);
  background-size: 26px 26px;
  animation: kbDrift 36s linear infinite;
  pointer-events: none;
}

@keyframes kbDrift {
  to {
    transform: translateY(26px);
  }
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 32px;
  position: relative;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #7ee2a8;
  background: rgba(46, 164, 79, 0.1);
  border: 1px solid rgba(46, 164, 79, 0.35);
  padding: 5px 14px;
  border-radius: 999px;
  margin-bottom: 16px;
  opacity: 0;
  transform: translateY(18px);
  animation: kbUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) 0.05s forwards;
}

.badge-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #2ea44f;
  animation: kbBadgePing 2.2s ease-out infinite;
}

@keyframes kbBadgePing {
  0% {
    box-shadow: 0 0 0 0 rgba(46, 164, 79, 0.55);
  }
  70%,
  100% {
    box-shadow: 0 0 0 7px rgba(46, 164, 79, 0);
  }
}

.header-title {
  margin: 0 0 10px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.3;
  color: #f0f6fc;
  letter-spacing: -0.01em;
  opacity: 0;
  transform: translateY(24px);
  animation: kbUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) 0.15s forwards;
}

@keyframes kbUp {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.header-desc {
  margin: 0;
  font-size: 15px;
  line-height: 1.8;
  color: #8b949e;
  max-width: 46ch;
  opacity: 0;
  transform: translateY(20px);
  animation: kbUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) 0.3s forwards;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  opacity: 0;
  transform: translateY(20px);
  animation: kbUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) 0.42s forwards;
}

.search-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 999px;
  box-shadow: none;
  border: 1px solid transparent;
  padding: 2px 18px;
  height: 44px;
  transition:
    background 0.25s,
    border-color 0.25s,
    box-shadow 0.25s;
}

.search-input :deep(.el-input__wrapper:hover) {
  background: #fff;
}

.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: #2ea44f;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(46, 164, 79, 0.3);
}

.search-input :deep(.el-input__inner) {
  color: #24292f;
}

.search-input :deep(.el-input__prefix) {
  color: #57606a;
}

.search-btn {
  position: relative;
  overflow: hidden;
  height: 44px;
  padding: 0 22px;
  border: none;
  border-radius: 999px;
  background: #2ea44f;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition:
    background 0.25s,
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.search-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -80%;
  width: 60%;
  height: 100%;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.28), transparent);
  transform: skewX(-20deg);
  transition: left 0.55s cubic-bezier(0.22, 1, 0.36, 1);
}

.search-btn:hover {
  background: #2c974b;
  transform: translateY(-1px);
}

.search-btn:hover::before {
  left: 120%;
}

/* ==================== 主体 ==================== */
.knowledge-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  display: flex;
  gap: 24px;
}

.knowledge-main {
  flex: 1;
  min-width: 0;
}

.toolbar {
  background: #fff;
  border: 1px solid #d8dee4;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  transition: box-shadow 0.3s;
}

.toolbar:hover {
  box-shadow: 0 8px 24px rgba(22, 27, 34, 0.06);
}

.difficulty-filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  padding: 6px 16px;
  border-radius: 999px;
  border: 1px solid #d0d7de;
  background: #fff;
  color: #57606a;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition:
    border-color 0.25s,
    color 0.25s,
    background 0.25s,
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s;
}

.chip:hover {
  border-color: rgba(46, 164, 79, 0.5);
  color: #2c974b;
  transform: translateY(-1px);
}

.chip.active {
  background: #2ea44f;
  border-color: #2ea44f;
  color: #fff;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(46, 164, 79, 0.3);
}

.total-count {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #8c959f;
  font-size: 13px;
  white-space: nowrap;
}

.total-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2ea44f;
}

/* ==================== 卡片网格 ==================== */
.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.skeleton-card {
  background: #fff;
  border: 1px solid #e6e8eb;
  border-radius: 12px;
  padding: 20px;
}

.sk {
  background: linear-gradient(90deg, #eef1f4 25%, #f6f8fa 50%, #eef1f4 75%);
  background-size: 200% 100%;
  animation: kbShimmer 1.2s ease-in-out infinite;
  border-radius: 6px;
}

@keyframes kbShimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.sk-tags {
  width: 45%;
  height: 22px;
  border-radius: 999px;
  margin-bottom: 16px;
}

.sk-title {
  width: 85%;
  height: 18px;
  margin-bottom: 12px;
}

.sk-line {
  width: 100%;
  height: 13px;
  margin-bottom: 8px;
}

.sk-line.short {
  width: 65%;
}

.empty-box {
  background: #fff;
  border: 1px solid #d8dee4;
  border-radius: 12px;
  padding: 40px 0;
}

/* ==================== 分页 ==================== */
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 28px;
}

.pagination-wrapper :deep(.el-pagination) {
  --el-pagination-hover-color: #2ea44f;
}

.pagination-wrapper :deep(.el-pager li) {
  border-radius: 8px;
  border: 1px solid transparent;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}

.pagination-wrapper :deep(.el-pager li:hover) {
  color: #2c974b;
  background: rgba(46, 164, 79, 0.08);
}

.pagination-wrapper :deep(.el-pager li.is-active) {
  background: #2ea44f;
  border-color: #2ea44f;
  color: #fff;
}

.pagination-wrapper :deep(.el-pagination button) {
  border-radius: 8px;
  transition: background 0.2s, color 0.2s;
}

.pagination-wrapper :deep(.el-pagination button:hover) {
  color: #2ea44f;
  background: rgba(46, 164, 79, 0.08);
}

/* ==================== 响应式 ==================== */
@media (max-width: 1024px) {
  .knowledge-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .knowledge-container {
    gap: 16px;
  }
}

@media (max-width: 768px) {
  .page-header {
    padding: 24px 0 36px;
  }

  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 20px;
  }

  .header-title {
    font-size: 24px;
  }

  .search-box {
    width: 100%;
  }

  .search-input {
    flex: 1;
  }

  .knowledge-container {
    flex-direction: column;
    padding: 16px 12px 40px;
  }

  .knowledge-grid {
    grid-template-columns: 1fr;
  }

  .toolbar {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}
</style>
