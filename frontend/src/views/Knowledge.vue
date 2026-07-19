<template>
  <div class="knowledge-page">
    <header class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h1>
            <el-icon><Reading /></el-icon>
            网络安全知识库
          </h1>
          <p>系统化的网络安全知识分类，助您构建完整的知识体系</p>
        </div>
        <div class="header-right">
          <el-input
            v-model="keyword"
            placeholder="搜索知识..."
            prefix-icon="Search"
            clearable
            @keyup.enter="handleSearch"
            style="width: 300px;"
          />
        </div>
      </div>
    </header>

    <div class="knowledge-container">
      <aside class="category-sidebar">
        <div class="sidebar-header">
          <span>知识分类</span>
        </div>
        <el-menu :default-active="String(activeCategory)" @select="handleCategorySelect">
          <el-menu-item index="">
            <el-icon><Document /></el-icon>
            <span>全部知识</span>
          </el-menu-item>
          <el-menu-item
            v-for="cat in categories"
            :key="cat.id"
            :index="String(cat.id)"
          >
            <el-icon><Folder /></el-icon>
            <span>{{ cat.name }}</span>
            <span class="item-count">{{ cat.item_count }}</span>
          </el-menu-item>
        </el-menu>
      </aside>

      <main class="knowledge-main">
        <div class="toolbar">
          <div class="toolbar-left">
            <el-tag
              v-for="difficulty in difficulties"
              :key="difficulty.value"
              :type="activeDifficulty === difficulty.value ? 'primary' : 'info'"
              @click="handleDifficultyFilter(difficulty.value)"
              class="filter-tag"
            >
              {{ difficulty.label }}
            </el-tag>
          </div>
          <div class="toolbar-right">
            <span class="total-count">共 {{ total }} 条知识</span>
          </div>
        </div>

        <div v-loading="loading" class="knowledge-grid">
          <el-empty v-if="!loading && items.length === 0" description="暂无知识条目" />
          <div
            v-for="item in items"
            :key="item.id"
            class="knowledge-card"
            @click="goToDetail(item.id)"
          >
            <div class="card-header">
              <el-tag size="small" type="info">{{ item.category_name || '未分类' }}</el-tag>
              <el-tag size="small" :type="getDifficultyType(item.difficulty)">
                {{ getDifficultyText(item.difficulty) }}
              </el-tag>
            </div>
            <h3 class="card-title">{{ item.title }}</h3>
            <p class="card-summary">{{ item.summary || '暂无摘要' }}</p>
            <div class="card-footer">
              <div class="tags">
                <el-tag v-for="tag in item.tags?.slice(0, 3)" :key="tag" size="small">
                  {{ tag }}
                </el-tag>
              </div>
              <div class="meta">
                <span><el-icon><View /></el-icon> {{ item.view_count }}</span>
                <span><el-icon><Star /></el-icon> {{ item.favorite_count }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="pagination-wrapper" v-if="total > pageSize">
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
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { knowledgeAPI } from '@/api'

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

const getDifficultyType = (difficulty) => {
  const types = { easy: 'success', medium: 'warning', hard: 'danger' }
  return types[difficulty] || 'info'
}

const getDifficultyText = (difficulty) => {
  const texts = { easy: '入门', medium: '进阶', hard: '高级' }
  return texts[difficulty] || '普通'
}

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
  fetchItems()
}

const handleDifficultyFilter = (difficulty) => {
  activeDifficulty.value = difficulty
  currentPage.value = 1
  fetchItems()
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchItems()
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
  background: #f5f7fa;
}

.page-header {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  padding: 40px 0;
  color: #fff;
  
  .header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    p {
      margin: 0;
      opacity: 0.9;
    }
  }
}

.knowledge-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px;
  display: flex;
  gap: 24px;
}

.category-sidebar {
  width: 240px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  
  .sidebar-header {
    padding: 16px;
    font-weight: 600;
    color: #606266;
    border-bottom: 1px solid #e4e7ed;
  }
  
  .el-menu {
    border-right: none;
    
    .item-count {
      margin-left: auto;
      font-size: 12px;
      color: #909399;
    }
  }
}

.knowledge-main {
  flex: 1;
  
  .toolbar {
    background: #fff;
    padding: 16px;
    border-radius: 12px;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    
    .filter-tag {
      cursor: pointer;
      margin-right: 8px;
    }
    
    .total-count {
      color: #909399;
      font-size: 14px;
    }
  }
}

.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  
  .knowledge-card {
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    cursor: pointer;
    transition: transform 0.3s, box-shadow 0.3s;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
    
    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    }
    
    .card-header {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
    }
    
    .card-title {
      margin: 0 0 8px;
      font-size: 16px;
      color: #303133;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    
    .card-summary {
      margin: 0 0 12px;
      font-size: 13px;
      color: #909399;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    
    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      .tags {
        display: flex;
        gap: 4px;
        
        .el-tag {
          font-size: 11px;
        }
      }
      
      .meta {
        display: flex;
        gap: 12px;
        font-size: 12px;
        color: #c0c4cc;
        
        span {
          display: flex;
          align-items: center;
          gap: 4px;
        }
      }
    }
  }
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
