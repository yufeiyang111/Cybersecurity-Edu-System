<template>
  <div v-if="sources.length" class="chat-sources">
    <div class="cs-title">{{ t('sources.title') }}</div>
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
        <div class="cs-name">{{ source.title || source.source || t('sources.unnamed') }}</div>
        <div class="cs-sub">
          <span v-if="source.source" class="cs-url">{{ source.source }}</span>
          <span v-if="source.similarity != null" class="cs-sim">
            {{ t('sources.similarity') }}{{ (source.similarity * 100).toFixed(0) }}%
          </span>
          <span v-if="source.start_line" class="cs-lines">
            {{ t('sources.lines', { start: source.start_line, end: source.end_line }) }}
          </span>
        </div>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="t('sources.detailTitle')" width="560px" append-to-body>
      <div v-if="current" class="cs-detail">
        <div class="cs-detail-title">{{ current.title || t('sources.unnamed') }}</div>
        <div class="cs-detail-meta">
          <span v-if="current.source">{{ t('sources.source') }}{{ current.source }}</span>
          <span v-if="current.similarity != null">{{ t('sources.similarity') }}{{ (current.similarity * 100).toFixed(1) }}%</span>
        </div>
        <div class="cs-detail-content">{{ current.content || t('sources.noContent') }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { knowledgeAPI } from '@/api'
import { useI18n } from '@/features/chat/i18n'

const props = defineProps({
  sources: { type: Array, default: () => [] }
})

const dialogVisible = ref(false)
const current = ref(null)
const { t } = useI18n()

const openDetail = async (source) => {
  current.value = { ...source }
  if (source.id) {
    try {
      const res = await knowledgeAPI.getKnowledge(source.id)
      current.value = { ...current.value, content: res.item?.content }
    } catch (e) {
      current.value.content = t('sources.noContent')
    }
  } else {
    current.value.content = t('sources.noContent')
  }
  dialogVisible.value = true
}
</script>

<style lang="scss" scoped>
.chat-sources { margin-top: 24px; }
.cs-title { font-size: calc(13px * var(--chat-font-scale)); font-weight: 600; color: var(--chat-ink); margin-bottom: 10px; }
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
  background: var(--chat-accent-soft);
  display: flex; align-items: center; justify-content: center;
  svg { width: 11px; height: 11px; stroke: var(--chat-accent); }
}
.cs-meta { min-width: 0; }
.cs-name {
  font-size: calc(13.5px * var(--chat-font-scale)); font-weight: 500; margin-bottom: 1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  color: var(--chat-ink);
}
.cs-sub {
  font-size: calc(12px * var(--chat-font-scale)); color: var(--chat-hollow);
  display: flex; gap: 8px; white-space: nowrap; overflow: hidden;
  .cs-url { overflow: hidden; text-overflow: ellipsis; }
  .cs-lines { flex-shrink: 0; color: var(--chat-accent); }
}

.cs-detail-title { font-size: calc(15px * var(--chat-font-scale)); font-weight: 600; margin-bottom: 10px; color: var(--chat-ink); }
.cs-detail-meta {
  display: flex; gap: 20px; color: var(--chat-hollow); font-size: calc(13px * var(--chat-font-scale));
  padding-bottom: 12px; margin-bottom: 12px; border-bottom: 1px solid var(--chat-hairline);
}
.cs-detail-content {
  max-height: 380px; overflow-y: auto;
  font-size: calc(14px * var(--chat-font-scale)); line-height: 1.8; color: var(--chat-ink);
  white-space: pre-wrap;
}
</style>
