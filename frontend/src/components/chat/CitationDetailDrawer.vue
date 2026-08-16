<template>
  <el-drawer
    class="citation-detail-drawer"
    :model-value="visible"
    direction="rtl"
    size="460px"
    :with-header="false"
    @close="$emit('close')"
  >
    <section
      v-if="citation"
      class="citation-detail"
    >
      <header class="detail-header">
        <div class="detail-header-top">
          <div class="detail-id" :data-accent="signal.level === 'low' ? 'warn' : (signal.level === 'high' ? 'ok' : '')">{{ citation.citationId }}</div>
          <span class="detail-eyebrow">引用详情</span>
          <button class="detail-close" title="关闭" @click="$emit('close')">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <h2 class="detail-title">{{ citation.title }}</h2>
        <p class="detail-source" v-if="citation.source">
          {{ citation.source }}
        </p>
      </header>

      <div class="detail-body">
        <div class="detail-grid">
          <div class="detail-metric">
            <span class="metric-label">文档定位</span>
            <strong class="metric-value">{{ lineLabel }}</strong>
          </div>
          <div class="detail-metric">
            <span class="metric-label">主张覆盖</span>
            <strong class="metric-value">{{ claimLabel }}</strong>
          </div>
          <div class="detail-metric">
            <span class="metric-label">检索辅助信号</span>
            <strong class="metric-value">{{ signal.label }}</strong>
          </div>
          <div class="detail-metric">
            <span class="metric-label">资料版本</span>
            <strong class="metric-value">{{ citation.corpusVersion || '未提供' }}</strong>
          </div>
        </div>

        <section class="preview-section" aria-labelledby="citation-preview-title">
          <h3 id="citation-preview-title" class="preview-title">原文预览</h3>
          <blockquote
            v-if="citation.preview?.text"
            class="preview-content"
          >
            {{ citation.preview.text }}
            <span v-if="citation.preview.isTruncated" class="preview-truncated">…（内容已截断）</span>
          </blockquote>
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

    <div v-else class="detail-empty">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6">
        <path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6z" />
        <path d="M14 3v6h6" />
      </svg>
      <p>请选择一条引用查看详情</p>
    </div>
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
.citation-detail-drawer {
  :deep(.el-drawer) {
    background: var(--chat-canvas);
    color: var(--chat-ink);
    border-left: 1px solid var(--chat-hairline);
  }

  :deep(.el-drawer__body) {
    padding: 0;
    display: flex;
    flex-direction: column;
  }
}

.citation-detail {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  height: 100%;
}

.detail-header {
  flex: 0 0 auto;
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--chat-hairline);
  background: linear-gradient(180deg, var(--chat-bubble) 0%, transparent 100%);
}

.detail-header-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-id {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: var(--chat-ink);
  background: var(--chat-accent-soft, rgba(37, 99, 235, 0.12));
  font-size: calc(11px * var(--chat-font-scale));
  font-weight: 700;
  flex: 0 0 auto;

  &[data-accent='warn'] {
    background: var(--chat-warning-bg, rgba(245, 158, 11, 0.15));
    color: var(--chat-warning-ink, #b45309);
  }

  &[data-accent='ok'] {
    background: rgba(34, 197, 94, 0.15);
    color: #15803d;
  }
}

.detail-eyebrow {
  color: var(--chat-hollow);
  font-size: calc(11px * var(--chat-font-scale));
  letter-spacing: 0.02em;
}

.detail-close {
  margin-left: auto;
  border: none;
  background: transparent;
  cursor: pointer;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: var(--chat-hollow);

  &:hover {
    background: var(--chat-hover);
    color: var(--chat-ink);
  }

  svg {
    width: 16px;
    height: 16px;
    stroke: currentColor;
  }
}

.detail-title {
  margin: 14px 0 0;
  color: var(--chat-ink);
  font-size: calc(18px * var(--chat-font-scale));
  font-weight: 650;
  line-height: 1.5;
  word-break: break-word;
}

.detail-source {
  margin: 6px 0 0;
  color: var(--chat-hollow);
  font-size: calc(12px * var(--chat-font-scale));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-body {
  flex: 1 1 auto;
  padding: 18px 20px 24px;
  overflow-y: auto;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.detail-metric {
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid var(--chat-hairline);
  border-radius: 10px;
  background: var(--chat-canvas);

  .metric-label,
  .metric-value {
    display: block;
  }

  .metric-label {
    margin-bottom: 6px;
    color: var(--chat-hollow);
    font-size: calc(11px * var(--chat-font-scale));
  }

  .metric-value {
    overflow: hidden;
    color: var(--chat-ink);
    font-size: calc(13px * var(--chat-font-scale));
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.preview-section {
  margin-top: 20px;

  .preview-title {
    margin: 0 0 10px;
    color: var(--chat-ink);
    font-size: calc(13px * var(--chat-font-scale));
    font-weight: 600;
  }
}

.preview-content {
  margin: 0;
  padding: 14px 16px;
  border-left: 3px solid var(--chat-accent);
  border-radius: 0 10px 10px 0;
  color: var(--chat-muted);
  background: var(--chat-bubble);
  font-size: calc(13px * var(--chat-font-scale));
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
}

.preview-truncated {
  color: var(--chat-hollow);
  font-size: calc(12px * var(--chat-font-scale));
}

.preview-unavailable {
  margin: 0;
  padding: 14px 16px;
  border-left: 3px solid var(--chat-hairline-strong);
  border-radius: 0 10px 10px 0;
  color: var(--chat-hollow);
  background: var(--chat-bubble);
  font-size: calc(13px * var(--chat-font-scale));
}

.signal-note {
  margin: 14px 0 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--chat-bubble);
  color: var(--chat-hollow);
  font-size: calc(12px * var(--chat-font-scale));
  line-height: 1.6;
}

.open-document {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  margin-top: 18px;
  padding: 9px 14px;
  border: none;
  border-radius: 8px;
  color: #fff;
  background: var(--chat-accent);
  font: inherit;
  font-size: calc(13px * var(--chat-font-scale));
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);

  &:hover:not(:disabled) {
    filter: brightness(0.94);
  }

  &:disabled {
    color: var(--chat-hollow);
    background: var(--chat-bubble);
    box-shadow: none;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid var(--chat-link);
    outline-offset: 2px;
  }
}

.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  color: var(--chat-hollow);
  font-size: calc(13px * var(--chat-font-scale));

  svg {
    width: 42px;
    height: 42px;
    stroke: var(--chat-hairline-strong);
  }
}

@media (min-width: 768px) and (max-width: 1200px) {
  .citation-detail-drawer {
    :deep(.el-drawer) {
      width: min(400px, 75vw) !important;
    }
  }
}

@media (max-width: 767px) {
  .citation-detail-drawer {
    :deep(.el-drawer) {
      width: 100% !important;
    }
  }

  .detail-header,
  .detail-body {
    padding-left: 14px;
    padding-right: 14px;
  }
}
</style>
