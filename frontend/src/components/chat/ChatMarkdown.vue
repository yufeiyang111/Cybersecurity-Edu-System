<template>
  <div class="chat-markdown" v-html="renderedContent"></div>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '@/features/markdown/renderMarkdown'

const props = defineProps({
  content: { type: String, default: '' }
})

const renderedContent = computed(() => renderMarkdown(props.content))
</script>

<style lang="scss">
.chat-markdown {
  font-size: 16px;
  line-height: 1.6;
  color: var(--chat-ink);
  word-break: break-word;

  p { margin: 12px 0; }
  p:first-child { margin-top: 0; }
  p:last-child { margin-bottom: 0; }

  h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    color: var(--chat-ink);
    margin: 20px 0 10px;
    line-height: 1.4;
  }
  h1 { font-size: 1.6em; }
  h2 { font-size: 1.35em; }
  h3 { font-size: 1.15em; }
  h4 { font-size: 1.05em; }
  h5, h6 { font-size: 1em; color: var(--chat-muted); }

  ul, ol { padding-left: 24px; margin: 12px 0; }
  li { margin: 6px 0; }

  strong { font-weight: 600; }
  em { font-style: italic; }

  a {
    color: var(--chat-link);
    text-decoration: underline;
    text-underline-offset: 3px;
    &:hover { opacity: 0.85; }
  }

  blockquote {
    margin: 12px 0;
    padding: 2px 0 2px 14px;
    border-left: 3px solid var(--chat-hairline-strong);
    color: var(--chat-muted);
    p { margin: 6px 0; }
  }

  code {
    background: var(--chat-hover);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: ui-monospace, "Cascadia Code", Consolas, "Courier New", monospace;
    font-size: 0.88em;
    color: var(--chat-ink);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    th, td {
      border: 1px solid var(--chat-hairline);
      padding: 8px 12px;
      text-align: left;
    }
    th { background: var(--chat-hover); font-weight: 600; }
    tr:nth-child(even) td { background: var(--chat-hairline); }
  }

  img { max-width: 100%; border-radius: var(--chat-radius); }
  hr { border: none; border-top: 1px solid var(--chat-hairline); margin: 20px 0; }
}
</style>
