<template>
  <div class="graphrag-search">
    <el-tabs v-model="mode" @tab-change="handleModeChange">
      <el-tab-pane label="全局问答" name="global">
        <p class="mode-hint">基于全部社区摘要回答整体性问题（如"知识库讲了哪些安全主题？"）</p>
      </el-tab-pane>
      <el-tab-pane label="实体问答" name="local">
        <p class="mode-hint">围绕图谱实体与关系回答具体问题（如"SQL注入如何防御？"）</p>
      </el-tab-pane>
    </el-tabs>

    <div class="search-row">
      <el-input
        v-model="query"
        :placeholder="mode === 'global' ? '输入全局性问题...' : '输入实体相关问题...'"
        clearable
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
    </div>

    <div v-if="loading" class="search-loading">
      <el-skeleton :rows="6" animated />
      <p class="loading-hint">正在检索知识图谱并生成答案（LLM 分析，约 10-30 秒）...</p>
    </div>

    <div v-else-if="error" class="search-error">
      <el-empty :description="error" :image-size="50" />
    </div>

    <div v-else-if="result" class="search-result">
      <div class="answer-block">
        <h4>回答</h4>
        <p class="answer-text">{{ result.answer }}</p>
      </div>

      <template v-if="mode === 'global'">
        <div v-if="result.used_communities && result.used_communities.length" class="source-block">
          <h4>参考社区（{{ result.used_communities.length }}）</h4>
          <div
            v-for="c in result.used_communities"
            :key="c.community_id"
            class="source-item"
          >
            <span class="source-title">社区 #{{ c.community_id }} {{ c.title }}</span>
            <p class="source-desc">{{ c.summary }}</p>
            <div v-if="c.key_topics && c.key_topics.length" class="source-topics">
              <el-tag
                v-for="t in c.key_topics.slice(0, 3)"
                :key="t"
                size="small"
                type="info"
                effect="plain"
              >
                {{ t }}
              </el-tag>
            </div>
          </div>
        </div>
        <div v-if="result.intermediate && result.intermediate.length" class="source-block">
          <h4>中间答案</h4>
          <div v-for="item in result.intermediate" :key="item.community_id" class="source-item">
            <span class="source-title">社区 #{{ item.community_id }} {{ item.title }}</span>
            <p class="source-desc">{{ item.answer }}</p>
          </div>
        </div>
      </template>

      <template v-else>
        <div v-if="result.entities && result.entities.length" class="source-block">
          <h4>匹配实体（{{ result.entities.length }}）</h4>
          <div v-for="e in result.entities" :key="e.id" class="source-item">
            <span class="source-title">
              {{ e.name }}
              <el-tag size="small" type="warning" effect="plain">{{ typeLabel(e.type) }}</el-tag>
            </span>
            <p v-if="e.description" class="source-desc">{{ e.description }}</p>
          </div>
        </div>
        <div v-if="result.relationships && result.relationships.length" class="source-block">
          <h4>相关关系（{{ result.relationships.length }}）</h4>
          <div v-for="(r, index) in result.relationships.slice(0, 12)" :key="index" class="rel-item">
            <span class="rel-node">{{ r.source_name }}</span>
            <span class="rel-edge">——{{ r.relation }}——></span>
            <span class="rel-node">{{ r.target_name }}</span>
          </div>
        </div>
        <div v-if="result.community_summaries && result.community_summaries.length" class="source-block">
          <h4>关联社区</h4>
          <div v-for="c in result.community_summaries" :key="c.community_id" class="source-item">
            <span class="source-title">社区 #{{ c.community_id }} {{ c.title }}</span>
            <p class="source-desc">{{ c.summary }}</p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { adminAPI } from '@/api'

const mode = ref('global')
const query = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)

const typeLabel = (type) => {
  const labels = {
    vulnerability: '漏洞',
    attack_technique: '攻击技术',
    defense_measure: '防御措施',
    security_tool: '安全工具',
    concept: '概念',
    regulation: '法规标准',
    threat_actor: '威胁行为体',
    knowledge: '知识条目'
  }
  return labels[type] || type || '未知'
}

const handleModeChange = () => {
  result.value = null
  error.value = ''
}

const handleSearch = async () => {
  const q = query.value.trim()
  if (!q) {
    ElMessage.warning('请输入问题')
    return
  }
  loading.value = true
  error.value = ''
  result.value = null
  try {
    if (mode.value === 'global') {
      result.value = await adminAPI.globalGraphSearch({ query: q, top_k: 10 })
    } else {
      result.value = await adminAPI.localGraphSearch({ query: q, max_depth: 2 })
    }
  } catch (err) {
    error.value = '检索失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.graphrag-search {
  .mode-hint {
    margin: 0 0 10px;
    font-size: 12px;
    color: #8c959f;
    line-height: 1.6;
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
    }
  }

  .search-error {
    padding: 20px 0;
  }

  .search-result {
    margin-top: 16px;

    .answer-block {
      h4 {
        margin: 0 0 8px;
        font-size: 13px;
        color: #374151;
        border-left: 3px solid #2563eb;
        padding-left: 8px;
      }

      .answer-text {
        margin: 0;
        font-size: 13px;
        line-height: 1.9;
        color: #1f2937;
        background: #f0f7ff;
        border-radius: 6px;
        padding: 10px 12px;
      }
    }

    .source-block {
      margin-top: 16px;

      h4 {
        margin: 0 0 8px;
        font-size: 13px;
        color: #374151;
        border-left: 3px solid #10b981;
        padding-left: 8px;
      }

      .source-item {
        padding: 8px 10px;
        background: #f9fafb;
        border-radius: 6px;
        margin-bottom: 8px;

        .source-title {
          font-size: 13px;
          font-weight: 600;
          color: #1f2937;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .source-desc {
          margin: 4px 0 0;
          font-size: 12px;
          line-height: 1.7;
          color: #6b7280;
        }

        .source-topics {
          margin-top: 6px;
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
      }
    }

    .rel-item {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 4px;
      padding: 6px 10px;
      background: #f9fafb;
      border-radius: 6px;
      margin-bottom: 6px;
      font-size: 12px;

      .rel-node {
        color: #1f2937;
        font-weight: 500;
      }

      .rel-edge {
        color: #2563eb;
        font-size: 11px;
      }
    }
  }
}
</style>
