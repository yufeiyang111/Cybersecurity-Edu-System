<template>
  <div class="graphrag-search">
    <div class="panel-tools">
      <el-button
        text
        size="small"
        class="history-btn"
        :class="{ active: showHistory }"
        @click="toggleHistory"
      >
        <el-icon><Clock /></el-icon>
        历史记录
        <span v-if="history.length" class="history-badge">{{ history.length }}</span>
      </el-button>
    </div>

    <!-- 历史列表视图 -->
    <GraphRagHistoryList
      v-if="showHistory"
      :items="history"
      @select="viewHistoryItem"
      @remove="removeHistoryItem"
      @clear="clearHistory"
    />

    <!-- 查看单条历史记录 -->
    <template v-else-if="viewingItem">
      <div class="viewing-head">
        <el-button text size="small" @click="backToAsk">
          <el-icon><Back /></el-icon>
          返回问答
        </el-button>
        <span class="viewing-query">{{ viewingItem.query }}</span>
        <el-tag
          size="small"
          :type="viewingItem.mode === 'global' ? 'info' : 'warning'"
          effect="plain"
        >
          {{ viewingItem.mode === 'global' ? '全局' : '实体' }}
        </el-tag>
      </div>
      <GraphRagAnswerCard
        :mode="viewingItem.mode"
        :answer="viewingItem.answer"
        :thinking="viewingItem.thinking"
        :provider="viewingItem.provider"
        :model="viewingItem.model"
        :entities="viewingItem.entities"
        :relationships="viewingItem.relationships"
        :community-summaries="viewingItem.community_summaries"
        :used-communities="viewingItem.used_communities"
        :intermediates="viewingItem.intermediate"
        @focus-node="$emit('focus-node', $event)"
      />
    </template>

    <!-- 正常问答视图 -->
    <template v-else>
      <div class="mode-cards">
        <div
          class="mode-card"
          :class="{ active: mode === 'global' }"
          @click="switchMode('global')"
        >
          <div class="mode-card-head">
            <el-icon class="mode-icon"><Files /></el-icon>
            <span class="mode-name">全局问答</span>
          </div>
          <p class="mode-desc">
            面向整个知识库的整体性问题，基于社区摘要归纳回答，适合问"有哪些主题/总体趋势"
          </p>
          <div class="example-tags">
            <el-tag
              v-for="q in globalExamples"
              :key="q"
              size="small"
              type="info"
              effect="plain"
              class="example-tag"
              @click.stop="fillQuery(q, 'global')"
            >
              {{ q }}
            </el-tag>
          </div>
        </div>

        <div
          class="mode-card"
          :class="{ active: mode === 'local' }"
          @click="switchMode('local')"
        >
          <div class="mode-card-head">
            <el-icon class="mode-icon"><Aim /></el-icon>
            <span class="mode-name">实体问答</span>
          </div>
          <p class="mode-desc">
            围绕某个具体实体/漏洞/工具提问，沿关系链展开回答，适合问"XX是什么/如何防御"
          </p>
          <div class="example-tags">
            <el-tag
              v-for="q in localExamples"
              :key="q"
              size="small"
              type="warning"
              effect="plain"
              class="example-tag"
              @click.stop="fillQuery(q, 'local')"
            >
              {{ q }}
            </el-tag>
          </div>
        </div>
      </div>

      <div class="search-row">
        <el-input
          v-model="query"
          :placeholder="mode === 'global' ? '输入全局性问题，如：知识库讲了哪些安全主题？' : '输入实体相关问题，如：SQL注入如何防御？'"
          clearable
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :loading="loading" @click="handleSearch">
          查询
        </el-button>
      </div>

      <div v-if="loading" class="search-loading">
        <el-skeleton :rows="6" animated />
        <p class="loading-hint">
          <span v-if="thinkingVisible" class="loading-thinking">模型思考中...</span>
          <span v-else>正在检索知识图谱并生成答案（约 10-30 秒）...</span>
        </p>
      </div>

      <div v-else-if="error" class="search-error">
        <el-empty :description="error" :image-size="50" />
      </div>

      <GraphRagAnswerCard
        v-else-if="result"
        :mode="result.mode"
        :answer="result.answer"
        :thinking="result.thinking"
        :provider="result.provider"
        :model="result.model"
        :entities="result.entities"
        :relationships="result.relationships"
        :community-summaries="result.community_summaries"
        :used-communities="result.used_communities"
        :intermediates="result.intermediate"
        @focus-node="$emit('focus-node', $event)"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Files, Aim, Clock, Back } from '@element-plus/icons-vue'
import { adminAPI } from '@/api'
import GraphRagAnswerCard from './GraphRagAnswerCard.vue'
import GraphRagHistoryList from './GraphRagHistoryList.vue'

const props = defineProps({
  initialMode: { type: String, default: 'global' }
})
const emit = defineEmits(['focus-node'])

const mode = ref(props.initialMode)
const query = ref('')
const loading = ref(false)
const thinkingVisible = ref(false)
const error = ref('')
const result = ref(null)

// 问答历史（localStorage 持久化，上限 50 条）
const HISTORY_KEY = 'kg-graph-rag-history'
const MAX_HISTORY = 50
const history = ref([])
const showHistory = ref(false)
const viewingItem = ref(null)

const globalExamples = [
  '知识库主要讲了哪些安全主题？',
  '哪些漏洞类型最受关注？',
  '知识库对防御措施有哪些总体建议？'
]

const localExamples = [
  'SQL注入如何防御？',
  'mimikatz 是干什么的？',
  '什么是票据攻击？'
]

const loadHistory = () => {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        history.value = parsed
      }
    }
  } catch (e) {
    history.value = []
  }
}

const persistHistory = () => {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
  } catch (e) {
    // 存储满（配额）时静默丢弃最旧记录再试一次
    history.value = history.value.slice(0, Math.floor(MAX_HISTORY / 2))
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
    } catch (e2) {
      // 仍失败则仅保留会话内历史
    }
  }
}

const saveHistory = (q, item) => {
  const entry = {
    id: Date.now(),
    createdAt: new Date().toISOString(),
    mode: item.mode,
    query: q,
    answer: item.answer,
    thinking: item.thinking,
    provider: item.provider,
    model: item.model,
    entities: item.entities || [],
    relationships: item.relationships || [],
    community_summaries: item.community_summaries || [],
    used_communities: item.used_communities || [],
    intermediate: item.intermediate || []
  }
  history.value.unshift(entry)
  if (history.value.length > MAX_HISTORY) {
    history.value = history.value.slice(0, MAX_HISTORY)
  }
  persistHistory()
}

const toggleHistory = () => {
  if (showHistory.value) {
    showHistory.value = false
    return
  }
  viewingItem.value = null
  showHistory.value = true
}

const viewHistoryItem = (item) => {
  showHistory.value = false
  viewingItem.value = item
}

const backToAsk = () => {
  viewingItem.value = null
}

const removeHistoryItem = (id) => {
  history.value = history.value.filter((h) => h.id !== id)
  persistHistory()
}

const clearHistory = () => {
  history.value = []
  persistHistory()
  ElMessage.success('已清空问答历史')
}

const switchMode = (nextMode) => {
  if (mode.value === nextMode) return
  mode.value = nextMode
  result.value = null
  error.value = ''
  query.value = ''
}

const fillQuery = (q, targetMode) => {
  // 点示例问题：切到对应模式 + 填入问题
  if (targetMode && mode.value !== targetMode) {
    switchMode(targetMode)
  }
  query.value = q
}

const handleSearch = async () => {
  const q = query.value.trim()
  if (!q) {
    ElMessage.warning('请输入问题')
    return
  }
  loading.value = true
  thinkingVisible.value = false
  error.value = ''
  result.value = null
  viewingItem.value = null
  showHistory.value = false
  try {
    // 先展示"模型思考中"，LLM 调用期间保持
    thinkingVisible.value = true
    if (mode.value === 'global') {
      result.value = await adminAPI.globalGraphSearch({ query: q, top_k: 10 })
    } else {
      result.value = await adminAPI.localGraphSearch({ query: q, max_depth: 2 })
    }
    saveHistory(q, result.value)
  } catch (err) {
    error.value = '检索失败，请稍后重试'
  } finally {
    thinkingVisible.value = false
    loading.value = false
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped lang="scss">
.graphrag-search {
  .panel-tools {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;

    .history-btn {
      color: #6b7280;

      &.active {
        color: #2563eb;
      }

      .history-badge {
        min-width: 16px;
        height: 16px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-left: 2px;
        padding: 0 5px;
        border-radius: 999px;
        background: #2563eb;
        color: #fff;
        font-size: 10px;
        line-height: 1;
      }
    }
  }

  .viewing-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;

    .viewing-query {
      flex: 1;
      min-width: 0;
      font-size: 13px;
      font-weight: 600;
      color: #1f2937;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .mode-cards {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;

    .mode-card {
      padding: 10px 12px;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s;

      &:hover {
        border-color: #93c5fd;
      }

      &.active {
        border-color: #2563eb;
        background: #eff6ff;
      }

      .mode-card-head {
        display: flex;
        align-items: center;
        gap: 6px;

        .mode-icon {
          color: #2563eb;
          font-size: 15px;
        }

        .mode-name {
          font-size: 13px;
          font-weight: 600;
          color: #1f2937;
        }
      }

      .mode-desc {
        margin: 6px 0 8px;
        font-size: 12px;
        line-height: 1.6;
        color: #6b7280;
      }

      .example-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;

        .example-tag {
          cursor: pointer;

          &:hover {
            opacity: 0.8;
          }
        }
      }
    }
  }

  .search-row {
    display: flex;
    gap: 8px;
  }

  .search-loading {
    margin-top: 16px;

    .loading-hint {
      margin-top: 12px;
      font-size: 12px;
      color: #8c959f;
      text-align: center;

      .loading-thinking {
        color: #2563eb;
      }
    }
  }

  .search-error {
    padding: 20px 0;
  }
}
</style>
