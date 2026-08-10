<template>
  <article class="help-doc">
    <header class="help-doc__header">
      <h1 class="help-doc__title">{{ document.title }}</h1>
      <p v-if="document.summary" class="help-doc__summary">{{ document.summary }}</p>
      <div class="help-doc__meta">
        <span>最后更新：{{ formatDate(document.updated_at) }}</span>
        <template v-if="document.updated_by && document.updated_by !== 'system'">
          <span>· 维护：{{ document.updated_by }}</span>
        </template>
        <span v-if="document.version">· v{{ document.version }}</span>
      </div>
    </header>

    <div class="help-doc__body">
      <div class="help-doc__content">
        <MarkdownRenderer class="help-markdown" :content="document.content" />
      </div>

      <HelpToc v-if="tocItems.length > 1" :items="tocItems" :active-id="activeHeadingId" />
    </div>

    <footer v-if="prevDocument || nextDocument" class="help-doc__footer">
      <button
        v-if="prevDocument"
        type="button"
        class="help-doc__nav help-doc__nav--prev"
        @click="$emit('select-document', prevDocument.slug)"
      >
        <span class="help-doc__nav-label">← 上一篇</span>
        <span class="help-doc__nav-title">{{ prevDocument.title }}</span>
      </button>
      <span v-else class="help-doc__nav-spacer"></span>
      <button
        v-if="nextDocument"
        type="button"
        class="help-doc__nav help-doc__nav--next"
        @click="$emit('select-document', nextDocument.slug)"
      >
        <span class="help-doc__nav-label">下一篇 →</span>
        <span class="help-doc__nav-title">{{ nextDocument.title }}</span>
      </button>
      <span v-else class="help-doc__nav-spacer"></span>
    </footer>
  </article>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import HelpToc from '@/components/help/HelpToc.vue'
import { extractMarkdownHeadings } from '@/features/markdown/headings'

const props = defineProps({
  document: {
    type: Object,
    required: true
  },
  prevDocument: {
    type: Object,
    default: null
  },
  nextDocument: {
    type: Object,
    default: null
  }
})

defineEmits(['select-document'])

const tocItems = computed(() => extractMarkdownHeadings(props.document?.content || ''))
const activeHeadingId = ref('')

const formatDate = (iso) => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
}

let scrollObserver = null
let revealObserver = null

const observeHeadings = () => {
  scrollObserver?.disconnect()
  const ids = tocItems.value.map((item) => item.id)
  const elements = ids
    .map((id) => document.getElementById(id))
    .filter(Boolean)
  if (!elements.length) return

  scrollObserver = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      if (visible.length) {
        activeHeadingId.value = visible[0].target.id
      }
    },
    { rootMargin: '-80px 0px -70% 0px', threshold: 0 }
  )
  elements.forEach((el) => scrollObserver.observe(el))
}

// 正文块渐进显现：进入视口时依次 fade-in-up
const revealContentBlocks = () => {
  revealObserver?.disconnect()
  const container = document.querySelector('.help-doc__content')
  if (!container) return

  const selector = [
    'h2', 'h3', 'h4',
    'p',
    'ul', 'ol',
    'table',
    'blockquote',
    'hr',
    '.chat-code',
    'img'
  ].join(', ')

  const blocks = [...container.querySelectorAll(selector)]
  if (!blocks.length) return

  revealObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('revealed')
          revealObserver.unobserve(entry.target)
        }
      }
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.05 }
  )
  blocks.forEach((block, index) => {
    block.classList.add('reveal-item')
    block.style.transitionDelay = `${Math.min(index % 6, 5) * 30}ms`
    revealObserver.observe(block)
  })
}

const setupReveal = async () => {
  await nextTick()
  observeHeadings()
  setTimeout(revealContentBlocks, 30)
}

watch(
  () => props.document?.id,
  () => {
    setupReveal()
  }
)

onMounted(() => {
  setupReveal()
})

onBeforeUnmount(() => {
  scrollObserver?.disconnect()
  revealObserver?.disconnect()
})
</script>

<style scoped lang="scss">
.help-doc {
  max-width: 1100px;

  &__header {
    max-width: 760px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--chat-hairline);
    margin-bottom: 28px;
    animation: doc-fade-up 0.4s ease both;
  }

  &__title {
    margin: 0 0 12px;
    font-size: 30px;
    font-weight: 700;
    line-height: 1.3;
    color: var(--chat-ink);
    letter-spacing: -0.01em;
  }

  &__summary {
    margin: 0 0 14px;
    font-size: 16px;
    line-height: 1.7;
    color: var(--chat-muted);
  }

  &__meta {
    font-size: 12.5px;
    color: var(--chat-hollow);
    display: flex;
    gap: 4px;
  }

  &__body {
    display: flex;
    align-items: flex-start;
    gap: 48px;
  }

  &__content {
    flex: 1;
    min-width: 0;
    max-width: 760px;
  }

  &__footer {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    margin-top: 56px;
    padding-top: 24px;
    border-top: 1px solid var(--chat-hairline);
    animation: doc-fade-up 0.4s ease 0.15s both;
  }

  &__nav {
    flex: 1;
    max-width: 320px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 14px 18px;
    border: 1px solid var(--chat-hairline-strong);
    border-radius: var(--chat-radius);
    background: var(--chat-field);
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;

    &:hover {
      border-color: var(--chat-accent-border);
      background: var(--chat-hover);
      transform: translateY(-1px);

      .help-doc__nav-label {
        color: var(--chat-accent);
      }

      .help-doc__nav-title {
        color: var(--chat-accent);
      }
    }

    &--next {
      margin-left: auto;
      text-align: right;
      align-items: flex-end;
    }
  }

  &__nav-label {
    font-size: 12.5px;
    color: var(--chat-hollow);
    transition: color 0.18s ease;
  }

  &__nav-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--chat-ink);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
    transition: color 0.18s ease;
  }

  &__nav-spacer {
    flex: 1;
  }
}

@keyframes doc-fade-up {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.help-markdown {
  color: var(--chat-ink);
  font-size: 15.5px;
  line-height: 1.85;

  // 正文块滚动渐进显现（由 JS 添加 .reveal-item / .revealed）
  :deep(.reveal-item) {
    opacity: 0;
    transform: translateY(14px);
    transition: opacity 0.45s ease, transform 0.45s ease;

    &.revealed {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    :deep(.reveal-item) {
      opacity: 1;
      transform: none;
      transition: none;
    }
  }

  :deep(h1) {
    font-size: 26px;
    border-bottom: none;
    margin-top: 0;
    padding-bottom: 0;
  }

  :deep(h2) {
    font-size: 21px;
    border-bottom: 1px solid var(--chat-hairline);
    padding-bottom: 8px;
    margin-top: 44px;
  }

  :deep(h3) {
    font-size: 17.5px;
    margin-top: 32px;
  }

  :deep(h4) {
    font-size: 16px;
    margin-top: 24px;
  }

  :deep(p) {
    margin: 14px 0;
  }

  :deep(ul), :deep(ol) {
    padding-left: 1.6em;
    margin: 14px 0;

    li {
      margin: 6px 0;

      &::marker {
        color: var(--chat-accent);
      }
    }
  }

  :deep(table) {
    border-collapse: collapse;
    border: 1px solid var(--chat-hairline-strong);
    border-radius: var(--chat-radius);
    overflow: hidden;
    margin: 20px 0;
    font-size: 14px;
    transition: box-shadow 0.2s ease;

    &:hover {
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
    }

    th {
      background: var(--chat-sidebar);
      color: var(--chat-ink);
      font-weight: 600;
      border-color: var(--chat-hairline-strong);
      padding: 10px 14px;
    }

    td {
      border-color: var(--chat-hairline-strong);
      color: var(--chat-muted);
      padding: 10px 14px;
    }

    tr:nth-child(even) td {
      background: var(--chat-accent-soft);
    }

    tr:hover td {
      background: var(--chat-hover);
    }
  }

  :deep(blockquote) {
    border-left: 4px solid var(--chat-accent);
    background: var(--chat-accent-soft);
    color: var(--chat-muted);
    border-radius: 0 var(--chat-radius) var(--chat-radius) 0;
    padding: 12px 16px;
    margin: 20px 0;

    p {
      margin: 4px 0;
    }
  }

  :deep(a) {
    color: var(--chat-link);
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  :deep(code) {
    background: var(--chat-hover);
    color: var(--chat-accent);
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 13.5px;
  }

  :deep(pre) {
    background: var(--chat-code-bg);
    border-radius: var(--chat-radius);
    padding: 18px 20px;
    overflow-x: auto;
    margin: 20px 0;

    code {
      background: transparent;
      color: inherit;
      padding: 0;
      font-size: 13.5px;
      line-height: 1.7;
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    }
  }

  :deep(.chat-code-head) {
    background: var(--chat-code-head);
    border-radius: var(--chat-radius) var(--chat-radius) 0 0;
  }

  :deep(.chat-code) {
    margin: 20px 0;
    border-radius: var(--chat-radius);
    overflow: hidden;
    transition: transform 0.2s ease, box-shadow 0.2s ease;

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    }
  }

  :deep(.chat-code pre) {
    margin: 0;
    border-radius: 0;
  }

  :deep(hr) {
    border: none;
    border-top: 1px solid var(--chat-hairline);
    margin: 36px 0;
  }

  :deep(img) {
    max-width: 100%;
    border-radius: var(--chat-radius);
    border: 1px solid var(--chat-hairline-strong);
  }

  :deep(strong) {
    font-weight: 600;
  }
}

@media (max-width: 1200px) {
  .help-doc__body {
    gap: 24px;
  }
}

@media (max-width: 1024px) {
  .help-doc__title {
    font-size: 26px;
  }
}

@media (max-width: 768px) {
  .help-doc__header {
    padding-bottom: 16px;
  }

  .help-doc__title {
    font-size: 22px;
  }

  .help-doc__footer {
    flex-direction: column;
  }

  .help-doc__nav {
    max-width: none;
  }
}
</style>