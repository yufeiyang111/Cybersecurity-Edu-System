<template>
  <div class="chat-markdown" v-html="renderedContent"></div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'

const props = defineProps({
  content: { type: String, default: '' }
})

const escapeHtml = (str) =>
  String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

const renderer = new marked.Renderer()
renderer.code = (code, infostring) => {
  const lang = (infostring || '').split(/\s+/)[0]
  let highlighted = escapeHtml(code)
  try {
    if (lang && hljs.getLanguage(lang)) {
      highlighted = hljs.highlight(code, { language: lang }).value
    } else if (code.trim()) {
      highlighted = hljs.highlightAuto(code).value
    }
  } catch (e) {
    highlighted = escapeHtml(code)
  }
  const label = lang || 'code'
  const encoded = encodeURIComponent(code)
  return [
    `<div class="chat-code">`,
    `<div class="chat-code-head"><span class="chat-code-lang">${escapeHtml(label)}</span>`,
    `<button class="chat-code-copy" type="button" data-code="${encoded}">`,
    `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 012-2h10"/></svg>`,
    `<span>复制</span></button></div>`,
    `<pre><code class="hljs">${highlighted}</code></pre>`,
    `</div>`
  ].join('')
}

marked.setOptions({
  gfm: true,
  breaks: true,
  renderer
})

const renderedContent = computed(() => {
  if (!props.content) return ''
  const html = marked(props.content)
  return DOMPurify.sanitize(html)
})

const handleClick = (e) => {
  const btn = e.target.closest('.chat-code-copy')
  if (!btn) return
  const code = decodeURIComponent(btn.dataset.code || '')
  if (!code) return
  navigator.clipboard.writeText(code).then(() => {
    const label = btn.querySelector('span')
    if (label) {
      label.textContent = '已复制'
      setTimeout(() => { label.textContent = '复制' }, 1500)
    }
  }).catch(() => {})
}

onMounted(() => document.addEventListener('click', handleClick))
onBeforeUnmount(() => document.removeEventListener('click', handleClick))
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
    border-left: 3px solid rgba(0, 0, 0, 0.15);
    color: var(--chat-muted);
    p { margin: 6px 0; }
  }

  code {
    background: rgba(0, 0, 0, 0.05);
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
      border: 1px solid rgba(0, 0, 0, 0.1);
      padding: 8px 12px;
      text-align: left;
    }
    th { background: rgba(0, 0, 0, 0.03); font-weight: 600; }
    tr:nth-child(even) td { background: rgba(0, 0, 0, 0.015); }
  }

  img { max-width: 100%; border-radius: var(--chat-radius); }
  hr { border: none; border-top: 1px solid rgba(0, 0, 0, 0.1); margin: 20px 0; }

  .chat-code {
    margin: 14px 0;
     border-radius: var(--chat-radius);
    overflow: hidden;
    background: #262624;
  }
  .chat-code-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 6px 12px; background: #2f2f2d;
  }
  .chat-code-lang {
    font-size: 12px; color: #9b9b98;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
  }
  .chat-code-copy {
    border: none; background: transparent; cursor: pointer; opacity: 0;
    transition: opacity .15s; padding: 4px 6px; border-radius: 6px;
    display: flex; align-items: center; gap: 5px;
    color: #b8b8b4; font-size: 12px; font-family: inherit;
    &:hover { background: rgba(255, 255, 255, 0.08); }
    svg { width: 13px; height: 13px; stroke: #b8b8b4; }
  }
  .chat-code:hover .chat-code-copy { opacity: 1; }
  .chat-code pre {
    margin: 0; padding: 14px 16px;
    overflow-x: auto;
    font-size: 14px; line-height: 1.6;
    font-family: ui-monospace, "Cascadia Code", Consolas, "Courier New", monospace;
    color: #e6e6e3;
    code { background: transparent; padding: 0; color: inherit; font-size: inherit; }
  }

  .hljs-keyword { color: #569cd6; }
  .hljs-string { color: #ce9178; }
  .hljs-number { color: #b5cea8; }
  .hljs-comment { color: #6a9955; }
  .hljs-function { color: #dcdcaa; }
  .hljs-class { color: #4ec9b0; }
  .hljs-variable { color: #9cdcfe; }
  .hljs-attr { color: #9cdcfe; }
  .hljs-built_in { color: #4fc1ff; }
  .hljs-title { color: #dcdcaa; }
  .hljs-params { color: #e6e6e3; }
  .hljs-literal { color: #b5cea8; }
  .hljs-type { color: #4ec9b0; }
}
</style>
