<template>
  <section
    v-if="sources.length"
    class="legacy-source-list"
    aria-label="历史检索来源"
  >
    <header class="legacy-source-header">
      <div>
        <h3>历史检索来源</h3>
        <p>旧记录仅保留来源摘要，不能作为可核验引用，也不支持原文预览或跳转。</p>
      </div>
      <span class="legacy-source-badge">兼容信息</span>
    </header>

    <div class="legacy-source-items">
      <article
        v-for="(source, index) in sources"
        :key="`${source.title}-${source.source || 'unknown'}-${index}`"
        class="legacy-source-card"
      >
        <div
          class="legacy-source-icon"
          aria-hidden="true"
        >
          <BaseIcon
            name="file-text"
            :size="14"
          />
        </div>
        <div class="legacy-source-copy">
          <p class="legacy-source-title">{{ source.title }}</p>
          <div class="legacy-source-meta">
            <span>历史来源</span>
            <span v-if="source.source">{{ source.source }}</span>
            <span v-if="lineLabel(source)">{{ lineLabel(source) }}</span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { BaseIcon } from '@/components/ui'

defineProps({
  sources: { type: Array, default: () => [] }
})

const lineLabel = (source) => {
  if (!source.startLine) {
    return ''
  }
  const endLine = source.endLine || source.startLine
  return `第 ${source.startLine}-${endLine} 行`
}
</script>

<style scoped lang="scss">
.legacy-source-list {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: var(--chat-radius);
  background: var(--chat-field);
}

.legacy-source-header {
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

.legacy-source-badge {
  flex: 0 0 auto;
  padding: 4px 6px;
  border-radius: 999px;
  color: var(--chat-muted);
  background: var(--chat-bubble);
  font-size: calc(11px * var(--chat-font-scale));
  white-space: nowrap;
}

.legacy-source-items {
  display: grid;
  gap: 8px;
}

.legacy-source-card {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
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

.legacy-source-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 7px;
  color: var(--chat-hollow);
  background: var(--chat-bubble);
}

.legacy-source-copy {
  min-width: 0;
}

.legacy-source-title {
  margin: 0;
  overflow: hidden;
  color: var(--chat-ink);
  font-size: calc(13px * var(--chat-font-scale));
  font-weight: 650;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legacy-source-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;

  span {
    max-width: 100%;
    padding: 2px 5px;
    overflow: hidden;
    border-radius: 999px;
    color: var(--chat-muted);
    background: var(--chat-bubble);
    font-size: calc(10px * var(--chat-font-scale));
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

@media (min-width: 768px) and (max-width: 1200px) {
  .legacy-source-list {
    padding: 11px;
  }
}

@media (max-width: 767px) {
  .legacy-source-list {
    margin-top: 10px;
    padding: 10px;
  }

  .legacy-source-header p {
    display: none;
  }

  .legacy-source-badge {
    max-width: 96px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
</style>