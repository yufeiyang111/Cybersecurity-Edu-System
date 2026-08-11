<template>
  <div class="graphrag-search">
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
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Files, Aim } from '@element-plus/icons-vue'
import { adminAPI } from '@/api'
import GraphRagAnswerCard from './GraphRagAnswerCard.vue'

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
  try {
    // 先展示"模型思考中"，LLM 调用期间保持
    thinkingVisible.value = true
    if (mode.value === 'global') {
      result.value = await adminAPI.globalGraphSearch({ query: q, top_k: 10 })
    } else {
      result.value = await adminAPI.localGraphSearch({ query: q, max_depth: 2 })
    }
  } catch (err) {
    error.value = '检索失败，请稍后重试'
  } finally {
    thinkingVisible.value = false
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.graphrag-search {
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
