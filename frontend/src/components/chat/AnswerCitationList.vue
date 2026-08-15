<template>
  <section class="answer-citation-list" :aria-label="usage.ariaLabel">
    <header class="citation-list-header">
      <div>
        <h3>{{ usage.title }}</h3>
        <p>{{ usage.description }}</p>
      </div>
      <span
        class="retrieval-signal"
        :title="signal.description"
      >
        检索辅助信号：{{ signal.label }}
      </span>
    </header>

    <div
      v-if="citations.length"
      class="citation-list"
    >
      <article
        v-for="(citation, index) in citations"
        :key="citation.citationId"
        class="citation-card"
      >
        <div
          class="citation-id"
          :title="citation.citationId"
          :aria-label="`引用 ${index + 1}`"
        >
          C-{{ index + 1 }}
        </div>
        <div class="citation-copy">
          <button
            class="citation-title"
            type="button"
            @click="$emit('open-detail', { citation, trigger: $event.currentTarget })"
          >
            <span>{{ citation.title }}</span>
            <BaseIcon name="arrow-right" :size="13" />
          </button>
          <p
            v-if="citation.titlePath"
            class="citation-path"
          >
            {{ citation.titlePath }}
          </p>
          <div class="citation-meta">
            <span class="citation-verified">{{ usage.itemLabel }}</span>
            <span v-if="lineLabel">{{ lineLabel(citation) }}</span>
            <span
              v-if="usage.showClaimCount && citation.claimCount > 0"
            >
              覆盖 {{ citation.claimCount }} 个主张
            </span>
          </div>
          <p
            v-if="citation.preview?.text"
            class="citation-preview"
          >
            {{ citation.preview.text }}
            <span v-if="citation.preview.isTruncated">…</span>
          </p>
          <p
            v-else
            class="citation-preview citation-preview--unavailable"
          >
            当前无法提供该引用的原文预览。
          </p>
        </div>
        <button
          class="citation-original"
          type="button"
          :disabled="!hasNavigableDocument(citation)"
          @click="$emit('open-original', { citation, trigger: $event.currentTarget })"
        >
          查看原文
        </button>
      </article>
    </div>

    <p
      v-else
      class="citation-empty"
    >
      当前回答没有可展开的受控引用详情。
    </p>

    <p
      v-if="detailsTruncated"
      class="citation-truncated"
    >
      仅展示前 {{ citations.length }} 条引用详情，其余引用未展开。
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'
import {
  hasNavigableDocument,
  retrievalSignalPresentation,
  citationUsagePresentation
} from '@/features/chat/citationPresentation'

const props = defineProps({
  citations: { type: Array, default: () => [] },
  retrievalSignal: { type: Object, default: null },
  detailsTruncated: { type: Boolean, default: false },
  answerStatus: { type: String, default: null }
})

defineEmits(['open-detail', 'open-original'])

const usage = computed(() => {
  return citationUsagePresentation(props.answerStatus, props.citations.length)
})

const signal = computed(() => {
  return retrievalSignalPresentation(props.retrievalSignal)
})

const lineLabel = (citation) => {
  if (!citation.startLine) {
    return ''
  }
  const endLine = citation.endLine || citation.startLine
  return `第 ${citation.startLine}-${endLine} 行`
}
</script>

<style scoped lang="scss">
.answer-citation-list {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: var(--chat-radius);
  background: var(--chat-field);
}

.citation-list-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;

  h3 {
    margin: 0;
    color: var(--chat-ink);
    font-size: calc(13px * var(--chat-font-scale));
  }

  p {
    margin: 3px 0 0;
    color: var(--chat-hollow);
    font-size: calc(12px * var(--chat-font-scale));
    line-height: 1.45;
  }
}

.retrieval-signal {
  flex: 0 0 auto;
  padding: 4px 6px;
  border-radius: 999px;
  color: var(--chat-muted);
  background: var(--chat-bubble);
  font-size: calc(11px * var(--chat-font-scale));
  white-space: nowrap;
}

.citation-list {
  display: grid;
  gap: 8px;
}

.citation-card {
  display: grid;
  min-width: 0;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  gap: 9px;
  align-items: flex-start;
  padding: 10px 0;
  border-top: 1px solid var(--chat-hairline);

  &:first-child {
    padding-top: 0;
    border-top: 0;
  }

  &:last-child {
    padding-bottom: 0;
  }
}

.citation-id {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 28px;
  border-radius: 7px;
  color: var(--chat-ink);
  background: var(--chat-bubble);
  font-size: calc(10px * var(--chat-font-scale));
  font-weight: 700;
  white-space: nowrap;
}

.citation-copy {
  min-width: 0;
}

.citation-title {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: 0;
  color: var(--chat-link);
  background: transparent;
  font: inherit;
  font-size: calc(13px * var(--chat-font-scale));
  font-weight: 650;
  line-height: 1.45;
  text-align: left;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;

  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &:focus-visible {
    outline: 2px solid var(--chat-link);
    outline-offset: 2px;
  }
}

.citation-path {
  margin: 4px 0 0;
  overflow: hidden;
  color: var(--chat-hollow);
  font-size: calc(11px * var(--chat-font-scale));
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;

  span {
    padding: 2px 5px;
    border-radius: 999px;
    color: var(--chat-muted);
    background: var(--chat-bubble);
    font-size: calc(10px * var(--chat-font-scale));
  }

  .citation-verified {
    color: var(--chat-success-ink);
    background: var(--chat-success-bg);
  }
}

.citation-preview {
  display: -webkit-box;
  margin: 6px 0 0;
  overflow: hidden;
  color: var(--chat-muted);
  font-size: calc(12px * var(--chat-font-scale));
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.citation-preview--unavailable {
  color: var(--chat-hollow);
}

.citation-original {
  min-height: 28px;
  padding: 5px 8px;
  border: 1px solid var(--chat-accent-border);
  border-radius: 7px;
  color: var(--chat-ink);
  background: var(--chat-field);
  font: inherit;
  font-size: calc(11px * var(--chat-font-scale));
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--chat-hover);
  }

  &:disabled {
    color: var(--chat-hollow);
    cursor: not-allowed;
    opacity: 0.7;
  }

  &:focus-visible {
    outline: 2px solid var(--chat-link);
    outline-offset: 2px;
  }
}

.citation-empty,
.citation-truncated {
  margin: 0;
  color: var(--chat-hollow);
  font-size: calc(12px * var(--chat-font-scale));
  line-height: 1.5;
}

.citation-truncated {
  margin-top: 9px;
}

@media (min-width: 768px) and (max-width: 1200px) {
  .answer-citation-list {
    padding: 11px;
  }
}

@media (max-width: 767px) {
  .answer-citation-list {
    margin-top: 10px;
    padding: 10px;
  }

  .citation-list-header p {
    display: none;
  }

  .retrieval-signal {
    max-width: 132px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .citation-card {
    grid-template-columns: 34px minmax(0, 1fr);
  }

  .citation-original {
    grid-column: 2;
    justify-self: start;
  }
}
</style>
