<template>
  <div class="answer-card">
    <div class="answer-head">
      <span class="answer-label">回答</span>
      <el-tag
        v-if="modelLabel"
        size="small"
        type="info"
        effect="plain"
        class="model-tag"
      >
        {{ modelLabel }}
      </el-tag>
    </div>

    <div v-if="thinking" class="thinking-block">
      <div class="thinking-toggle" @click="thinkingOpen = !thinkingOpen">
        <el-icon :class="{ 'is-open': thinkingOpen }">
          <ArrowDown />
        </el-icon>
        <span>模型思考过程</span>
        <span v-if="!thinkingOpen" class="thinking-preview">
          {{ thinking.slice(0, 40) }}...
        </span>
      </div>
      <div v-if="thinkingOpen" class="thinking-body">
        {{ thinking }}
      </div>
    </div>

    <div
      v-if="renderedHtml"
      class="answer-markdown"
      v-html="renderedHtml"
    ></div>
    <p v-else class="answer-text">{{ answer }}</p>

    <div v-if="mode === 'local' && entities && entities.length" class="entities-block">
      <h5>本次检索到的实体（点击在图谱中高亮）</h5>
      <div class="entity-chips">
        <el-tag
          v-for="e in entities"
          :key="e.id"
          class="entity-chip"
          size="small"
          :color="typeTagColor(e.type)"
          effect="dark"
          :closable="false"
          @click="$emit('focus-node', e.id)"
        >
          {{ e.name }}
        </el-tag>
      </div>
    </div>

    <el-collapse v-model="openSections" class="source-collapse">
      <el-collapse-item v-if="mode === 'global'" title="参考社区" name="global">
        <div v-if="usedCommunities && usedCommunities.length">
          <div
            v-for="c in usedCommunities"
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
        <el-empty
          v-else
          description="暂无社区摘要，请先在社区面板生成"
          :image-size="40"
        />
      </el-collapse-item>

      <el-collapse-item
        v-if="mode === 'global' && intermediates && intermediates.length"
        title="中间推理答案"
        name="intermediate"
      >
        <div v-for="item in intermediates" :key="item.community_id" class="source-item">
          <span class="source-title">社区 #{{ item.community_id }} {{ item.title }}</span>
          <p class="source-desc">{{ item.answer }}</p>
        </div>
      </el-collapse-item>

      <el-collapse-item
        v-if="mode === 'local' && relationships && relationships.length"
        title="相关关系"
        name="relations"
      >
        <div
          v-for="(r, index) in relationships.slice(0, 12)"
          :key="index"
          class="rel-item"
        >
          <span class="rel-node">{{ r.source_name }}</span>
          <span class="rel-edge">——{{ r.relation }}——></span>
          <span class="rel-node">{{ r.target_name }}</span>
        </div>
      </el-collapse-item>

      <el-collapse-item
        v-if="mode === 'local' && communitySummaries && communitySummaries.length"
        title="关联社区摘要"
        name="communities"
      >
        <div v-for="c in communitySummaries" :key="c.community_id" class="source-item">
          <span class="source-title">社区 #{{ c.community_id }} {{ c.title }}</span>
          <p class="source-desc">{{ c.summary }}</p>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { renderMarkdown, installCodeCopy } from '@/features/markdown/renderMarkdown'

const props = defineProps({
  mode: { type: String, required: true },
  answer: { type: String, default: '' },
  thinking: { type: String, default: null },
  provider: { type: String, default: null },
  model: { type: String, default: null },
  entities: { type: Array, default: () => [] },
  relationships: { type: Array, default: () => [] },
  communitySummaries: { type: Array, default: () => [] },
  usedCommunities: { type: Array, default: () => [] },
  intermediates: { type: Array, default: () => [] }
})
const emit = defineEmits(['focus-node'])

const thinkingOpen = ref(false)
const openSections = ref([])

onMounted(() => {
  installCodeCopy()
})

const renderedHtml = computed(() => renderMarkdown(props.answer))

const modelLabel = computed(() => {
  if (props.model) {
    return `由 ${props.model} 生成`
  }
  if (props.provider === 'minimax') {
    return '由 MiniMax 生成'
  }
  if (props.provider === 'fallback') {
    return '由备用模型生成'
  }
  return ''
})

const typeTagColor = (type) => {
  const colors = {
    vulnerability: '#f56c6c',
    attack_technique: '#e6a23c',
    defense_measure: '#67c23a',
    security_tool: '#409eff',
    concept: '#10b981',
    regulation: '#9c27b0',
    threat_actor: '#ff5722',
    knowledge: '#00bcd4'
  }
  return colors[type] || '#909399'
}
</script>

<style scoped lang="scss">
.answer-card {
  .answer-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;

    .answer-label {
      font-size: 13px;
      font-weight: 600;
      color: #1f2937;
      border-left: 3px solid #2563eb;
      padding-left: 8px;
    }

    .model-tag {
      margin-left: auto;
    }
  }

  .thinking-block {
    margin-bottom: 10px;
    border: 1px dashed #cbd5e1;
    border-radius: 6px;
    overflow: hidden;

    .thinking-toggle {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      cursor: pointer;
      font-size: 12px;
      color: #6b7280;
      background: #f8fafc;
      user-select: none;

      .el-icon {
        transition: transform 0.2s;
        font-size: 12px;

        &.is-open {
          transform: rotate(180deg);
        }
      }

      .thinking-preview {
        color: #9ca3af;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .thinking-body {
      padding: 10px 12px;
      font-size: 12px;
      line-height: 1.8;
      color: #6b7280;
      white-space: pre-wrap;
      max-height: 220px;
      overflow-y: auto;
    }
  }

  .answer-markdown {
    font-size: 13px;
    line-height: 1.9;
    color: #1f2937;
    background: #f0f7ff;
    border-radius: 6px;
    padding: 10px 12px;

    :deep(p) {
      margin: 0 0 8px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    :deep(ul),
    :deep(ol) {
      margin: 0 0 8px;
      padding-left: 20px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    :deep(li + li) {
      margin-top: 4px;
    }

    :deep(strong) {
      color: #1d4ed8;
    }

    :deep(code:not(.hljs)) {
      background: #e5e7eb;
      border-radius: 4px;
      padding: 1px 5px;
      font-size: 12px;
      color: #b91c1c;
    }
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

  .entities-block {
    margin-top: 12px;

    h5 {
      margin: 0 0 8px;
      font-size: 12px;
      font-weight: 600;
      color: #374151;
    }

    .entity-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;

      .entity-chip {
        cursor: pointer;
        border-radius: 999px;
        border: none;

        &:hover {
          opacity: 0.85;
        }
      }
    }
  }

  .source-collapse {
    margin-top: 12px;

    :deep(.el-collapse-item__header) {
      font-size: 12px;
      font-weight: 600;
      color: #374151;
      height: 36px;
      background: transparent;
      border-bottom: none;
    }

    :deep(.el-collapse-item__content) {
      padding-bottom: 8px;
    }

    .source-item {
      padding: 8px 10px;
      background: #f9fafb;
      border-radius: 6px;
      margin-bottom: 8px;

      .source-title {
        font-size: 12px;
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
