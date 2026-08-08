<template>
  <div v-if="sources.length" class="chat-sources">
    <div class="cs-title">来源</div>
    <div
      v-for="(source, idx) in sources"
      :key="idx"
      class="cs-card"
      @click="openDetail(source)"
    >
      <div class="cs-favicon">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8">
        <template v-if="source.source_type === 'knowledge'">
          <path d="M9 12l2 2 4-4" />
          <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" />
        </template>
        <template v-else>
          <rect x="4" y="3" width="16" height="18" rx="2" />
          <path d="M8 8h8M8 12h8M8 16h5" />
        </template>
        </svg>
      </div>
      <div class="cs-meta">
        <div class="cs-name">{{ source.title || source.source || '未命名来源' }}</div>
        <div class="cs-sub">
          <span v-if="source.source" class="cs-url">{{ source.source }}</span>
          <span v-if="source.similarity != null" class="cs-sim">
            相似度 {{ (source.similarity * 100).toFixed(0) }}%
          </span>
          <span v-if="source.start_line" class="cs-lines">
            第 {{ source.start_line }}-{{ source.end_line }} 行
          </span>
        </div>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="来源详情" width="560px" append-to-body>
      <div v-if="current" class="cs-detail">
        <div class="cs-detail-title">{{ current.title || '未命名来源' }}</div>
        <div class="cs-detail-meta">
          <span v-if="current.source">来源：{{ current.source }}</span>
          <span v-if="current.similarity != null">相似度：{{ (current.similarity * 100).toFixed(1) }}%</span>
        </div>
        <div class="cs-detail-content">{{ current.content || '暂无详细内容' }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { knowledgeAPI } from '@/api'

const props = defineProps({
  sources: { type: Array, default: () => [] }
})

const dialogVisible = ref(false)
const current = ref(null)

const openDetail = async (source) => {
  current.value = { ...source }
  if (source.id) {
    try {
      const res = await knowledgeAPI.getKnowledge(source.id)
      current.value = { ...current.value, content: res.item?.content }
    } catch (e) {
      current.value.content = '暂无详细内容'
    }
  } else {
    current.value.content = '暂无详细内容'
  }
  dialogVisible.value = true
}
</script>

<style lang="scss" scoped>
.chat-sources { margin-top: 24px; }
.cs-title { font-size: 13px; font-weight: 600; color: var(--chat-ink); margin-bottom: 10px; }
.cs-card {
  display: flex; gap: 10px; align-items: flex-start;
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background .15s;
  &:hover { background: var(--chat-hover); }
}
.cs-favicon {
  width: 20px; height: 20px; border-radius: 5px; flex-shrink: 0;
  background: #e8e8e6; display: flex; align-items: center; justify-content: center;
  svg { width: 11px; height: 11px; stroke: #555; }
}
.cs-meta { min-width: 0; }
.cs-name {
  font-size: 13.5px; font-weight: 500; margin-bottom: 1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  color: var(--chat-ink);
}
.cs-sub {
  font-size: 12px; color: var(--chat-hollow);
  display: flex; gap: 8px; white-space: nowrap; overflow: hidden;
  .cs-url { overflow: hidden; text-overflow: ellipsis; }
  .cs-lines { flex-shrink: 0; color: var(--chat-accent); }
}

.cs-detail-title { font-size: 15px; font-weight: 600; margin-bottom: 10px; color: var(--chat-ink); }
.cs-detail-meta {
  display: flex; gap: 20px; color: var(--chat-hollow); font-size: 13px;
  padding-bottom: 12px; margin-bottom: 12px; border-bottom: 1px solid var(--chat-hairline);
}
.cs-detail-content {
  max-height: 380px; overflow-y: auto;
  font-size: 14px; line-height: 1.8; color: var(--chat-ink);
  white-space: pre-wrap;
}
</style>
