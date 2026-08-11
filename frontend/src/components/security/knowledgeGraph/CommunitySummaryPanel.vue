<template>
  <el-drawer
    :model-value="visible"
    :title="drawerTitle"
    size="480px"
    :close-on-click-modal="true"
    @update:model-value="$emit('update:visible', $event)"
    @open="handleOpen"
  >
    <div v-if="loading" class="summary-loading">
      <el-skeleton :rows="12" animated />
      <p class="summary-hint">正在生成社区摘要（LLM 分析社区实体与关系，约 10-30 秒）...</p>
    </div>

    <div v-else-if="error" class="summary-error">
      <el-empty :description="error" :image-size="60">
        <el-button type="primary" size="small" @click="handleRegenerate">重试生成</el-button>
      </el-empty>
    </div>

    <div v-else-if="summary" class="summary-body">
      <h4 class="summary-title">{{ summary.title }}</h4>
      <p class="summary-updated">
        生成时间：{{ formatTime(summary.updated_at) }}
        <el-tag v-if="summary.algorithm" size="small" type="info">{{ summary.algorithm }}</el-tag>
      </p>

      <section class="summary-section">
        <h5>社区总结</h5>
        <p class="summary-text">{{ summary.summary }}</p>
      </section>

      <section v-if="summary.key_topics && summary.key_topics.length" class="summary-section">
        <h5>关键主题</h5>
        <div class="topic-tags">
          <el-tag
            v-for="topic in summary.key_topics"
            :key="topic"
            size="small"
            type="warning"
            effect="plain"
          >
            {{ topic }}
          </el-tag>
        </div>
      </section>

      <section
        v-if="summary.representative_entities && summary.representative_entities.length"
        class="summary-section"
      >
        <h5>代表性实体</h5>
        <ul class="entity-list">
          <li v-for="entity in summary.representative_entities" :key="entity.name">
            <span class="entity-name">{{ entity.name }}</span>
            <span class="entity-type">{{ typeLabel(entity.type) }}</span>
            <p v-if="entity.role" class="entity-role">{{ entity.role }}</p>
          </li>
        </ul>
      </section>

      <section
        v-if="summary.key_relationships && summary.key_relationships.length"
        class="summary-section"
      >
        <h5>关键关系</h5>
        <ul class="relation-list">
          <li v-for="(rel, index) in summary.key_relationships" :key="index">
            <div class="relation-line">
              <span class="relation-node">{{ rel.source }}</span>
              <span class="relation-edge">——{{ rel.relation }}——></span>
              <span class="relation-node">{{ rel.target }}</span>
            </div>
            <p v-if="rel.description" class="relation-desc">{{ rel.description }}</p>
          </li>
        </ul>
      </section>

      <section v-if="summary.security_implications" class="summary-section">
        <h5>安全启示</h5>
        <p class="summary-text">{{ summary.security_implications }}</p>
      </section>

      <section v-if="summary.defensive_measures && summary.defensive_measures.length" class="summary-section">
        <h5>防御建议</h5>
        <ul class="defense-list">
          <li v-for="measure in summary.defensive_measures" :key="measure">
            {{ measure }}
          </li>
        </ul>
      </section>
    </div>

    <template #footer>
      <el-button :disabled="loading" @click="$emit('update:visible', false)">
        关闭
      </el-button>
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!summary"
        @click="handleRegenerate"
      >
        重新生成
      </el-button>
    </template>
  </el-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { adminAPI } from '@/api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  communityId: { type: [String, Number], default: null },
  communitySample: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:visible'])

const loading = ref(false)
const error = ref('')
const summary = ref(null)

const drawerTitle = computed(() => {
  if (props.communityId === null || props.communityId === undefined) return '社区摘要'
  const sample = (props.communitySample || []).slice(0, 2).join('、')
  return `社区 #${props.communityId} 摘要${sample ? `（${sample}...）` : ''}`
})

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

const formatTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

const loadSummary = async () => {
  if (props.communityId === null || props.communityId === undefined) return
  loading.value = true
  error.value = ''
  try {
    const res = await adminAPI.getCommunitySummary(props.communityId)
    summary.value = res
  } catch (err) {
    const status = err?.response?.status
    if (status === 404) {
      // 未生成：自动触发一次生成
      await generate()
      return
    }
    error.value = '加载摘要失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const generate = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await adminAPI.generateCommunitySummary(props.communityId, { force: false })
    summary.value = res
    ElMessage.success('社区摘要生成完成')
  } catch (err) {
    error.value = '摘要生成失败（LLM 不可用或解析失败）'
  } finally {
    loading.value = false
  }
}

const handleRegenerate = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await adminAPI.generateCommunitySummary(props.communityId, { force: true })
    summary.value = res
    ElMessage.success('已重新生成社区摘要')
  } catch (err) {
    error.value = '摘要重新生成失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const handleOpen = () => {
  summary.value = null
  error.value = ''
  if (props.communityId !== null && props.communityId !== undefined) {
    loadSummary()
  }
}
</script>

<style scoped lang="scss">
.summary-loading {
  .summary-hint {
    margin-top: 16px;
    font-size: 12px;
    color: #8c959f;
    text-align: center;
  }
}

.summary-error {
  padding: 40px 0;
}

.summary-body {
  .summary-title {
    margin: 0 0 8px;
    font-size: 16px;
    color: #1f2937;
  }

  .summary-updated {
    margin: 0 0 16px;
    font-size: 12px;
    color: #8c959f;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .summary-section {
    margin-bottom: 20px;

    h5 {
      margin: 0 0 8px;
      font-size: 13px;
      color: #374151;
      border-left: 3px solid #2563eb;
      padding-left: 8px;
    }
  }

  .summary-text {
    margin: 0;
    font-size: 13px;
    line-height: 1.8;
    color: #4b5563;
  }

  .topic-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .entity-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;

    li {
      padding: 8px 10px;
      background: #f9fafb;
      border-radius: 6px;

      .entity-name {
        font-size: 13px;
        font-weight: 600;
        color: #1f2937;
      }

      .entity-type {
        margin-left: 8px;
        font-size: 11px;
        color: #2563eb;
        background: #eff6ff;
        border-radius: 999px;
        padding: 1px 8px;
      }

      .entity-role {
        margin: 4px 0 0;
        font-size: 12px;
        color: #6b7280;
      }
    }
  }

  .relation-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;

    li {
      padding: 8px 10px;
      background: #f9fafb;
      border-radius: 6px;

      .relation-line {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 4px;
        font-size: 12px;
      }

      .relation-node {
        color: #1f2937;
        font-weight: 500;
      }

      .relation-edge {
        color: #2563eb;
        font-size: 11px;
      }

      .relation-desc {
        margin: 4px 0 0;
        font-size: 12px;
        color: #6b7280;
      }
    }
  }

  .defense-list {
    margin: 0;
    padding-left: 18px;
    font-size: 13px;
    line-height: 1.8;
    color: #4b5563;

    li + li {
      margin-top: 4px;
    }
  }
}
</style>
