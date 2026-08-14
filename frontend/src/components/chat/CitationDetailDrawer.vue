<template>
  <el-drawer
    class="citation-detail-drawer"
    :model-value="visible"
    direction="rtl"
    size="420px"
    :with-header="false"
    @close="$emit('close')"
  >
    <section
      v-if="citation"
      class="citation-detail"
    >
      <header class="detail-header">
        <div class="detail-id">{{ citation.citationId }}</div>
        <div class="detail-heading">
          <p>引用详情</p>
          <h2>{{ citation.title }}</h2>
        </div>
      </header>

      <div class="detail-body">
        <div class="detail-grid">
          <div class="detail-metric">
            <span>文档定位</span>
            <strong>{{ lineLabel }}</strong>
          </div>
          <div class="detail-metric">
            <span>主张覆盖</span>
            <strong>{{ claimLabel }}</strong>
          </div>
          <div class="detail-metric">
            <span>检索辅助信号</span>
            <strong>{{ signal.label }}</strong>
          </div>
          <div class="detail-metric">
            <span>资料版本</span>
            <strong>{{ citation.corpusVersion || '未提供' }}</strong>
          </div>
        </div>

        <section class="preview-section" aria-labelledby="citation-preview-title">
          <h3 id="citation-preview-title">原文预览</h3>
          <p
            v-if="citation.preview?.text"
            class="preview-content"
          >
            {{ citation.preview.text }}
            <span v-if="citation.preview.isTruncated">…</span>
          </p>
          <p
            v-else
            class="preview-unavailable"
          >
            当前无法提供该引用的原文预览。
          </p>
        </section>

        <p class="signal-note">
          {{ signal.description }}
        </p>

        <button
          class="open-document"
          type="button"
          :disabled="!hasNavigableDocument(citation)"
          @click="$emit('open-original', { citation, trigger: $event.currentTarget })"
        >
          <BaseIcon name="file-text" :size="15" />
          <span>在知识库中阅读全文</span>
          <BaseIcon name="arrow-right" :size="14" />
        </button>
      </div>
    </section>
  </el-drawer>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'
import {
  hasNavigableDocument,
  retrievalSignalPresentation
} from '@/features/chat/citationPresentation'

const props = defineProps({
  visible: { type: Boolean, default: false },
  citation: { type: Object, default: null },
  retrievalSignal: { type: Object, default: null }
})

defineEmits(['close', 'open-original'])

const signal = computed(() => {
  return retrievalSignalPresentation(props.retrievalSignal)
})

const lineLabel = computed(() => {
  if (!props.citation?.startLine) {
    return '未提供'
  }
  return `第 ${props.citation.startLine}-${props.citation.endLine || props.citation.startLine} 行`
})

const claimLabel = computed(() => {
  const count = props.citation?.claimCount || 0
  return count > 0 ? `${count} 个关键主张` : '未提供'
})
</script>

<style scoped lang="scss">
:deep(.el-drawer) {
  background: var(--chat-canvas);
  color: var(--chat-ink);
}

:deep(.el-drawer__body) {
  padding: 0;
}

.citation-detail {
  min-height: 100%;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 18px;
  border-bottom: 1px solid var(--chat-hairline);
}

.detail-id {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: var(--chat-ink);
  background: var(--chat-bubble);
  font-size: calc(11px * var(--chat-font-scale));
  font-weight: 700;
}

.detail-heading {
  min-width: 0;

  p {
    margin: 0;
    color: var(--chat-hollow);
    font-size: calc(11px * var(--chat-font-scale));
  }

  h2 {
    margin: 4px 0 0;
    color: var(--chat-ink);
    font-size: calc(16px * var(--chat-font-scale));
    line-height: 1.45;
    word-break: break-word;
  }
}

.detail-body {
  padding: 18px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.detail-metric {
  min-width: 0;
  padding: 9px;
  border-radius: 8px;
  background: var(--chat-bubble);

  span,
  strong {
    display: block;
  }

  span {
    margin-bottom: 4px;
    color: var(--chat-hollow);
    font-size: calc(11px * var(--chat-font-scale));
  }

  strong {
    overflow: hidden;
    color: var(--chat-ink);
    font-size: calc(12px * var(--chat-font-scale));
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.preview-section {
  margin-top: 18px;

  h3 {
    margin: 0 0 8px;
    color: var(--chat-ink);
    font-size: calc(13px * var(--chat-font-scale));
  }
}

.preview-content,
.preview-unavailable {
  margin: 0;
  padding: 11px 12px;
  border-left: 2px solid var(--chat-ink);
  border-radius: 0 7px 7px 0;
  color: var(--chat-muted);
  background: var(--chat-bubble);
  font-size: calc(13px * var(--chat-font-scale));
  line-height: 1.7;
  white-space: pre-wrap;
}

.preview-unavailable {
  border-left-color: var(--chat-hairline-strong);
  color: var(--chat-hollow);
}

.signal-note {
  margin: 12px 0 0;
  color: var(--chat-hollow);
  font-size: calc(12px * var(--chat-font-scale));
  line-height: 1.55;
}

.open-document {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 38px;
  margin-top: 18px;
  padding: 8px 12px;
  border: 1px solid var(--chat-accent);
  border-radius: 7px;
  color: var(--chat-field);
  background: var(--chat-accent);
  font: inherit;
  font-size: calc(13px * var(--chat-font-scale));
  font-weight: 650;
  cursor: pointer;

  &:hover:not(:disabled) {
    filter: brightness(0.92);
  }

  &:disabled {
    border-color: var(--chat-hairline-strong);
    color: var(--chat-hollow);
    background: var(--chat-bubble);
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid var(--chat-link);
    outline-offset: 2px;
  }
}

@media (min-width: 768px) and (max-width: 1200px) {
  :deep(.el-drawer) {
    width: min(390px, 70vw) !important;
  }
}

@media (max-width: 767px) {
  :deep(.el-drawer) {
    width: 100% !important;
  }

  .detail-header,
  .detail-body {
    padding: 16px 14px;
  }
}
</style>
