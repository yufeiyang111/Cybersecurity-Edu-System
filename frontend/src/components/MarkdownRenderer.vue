<template>
  <div class="markdown-renderer" v-html="renderedContent"></div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'

marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
  gfm: true
})

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  sanitize: {
    type: Boolean,
    default: false
  }
})

const renderedContent = computed(() => {
  if (!props.content) return ''
  const html = marked(props.content)
  return props.sanitize ? DOMPurify.sanitize(html) : html
})
</script>

<style lang="scss">
.markdown-renderer {
  line-height: 1.8;
  color: #606266;

  h1, h2, h3, h4, h5, h6 {
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    font-weight: 600;
    color: #303133;
  }

  h1 { font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
  h2 { font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
  h3 { font-size: 1.3em; }
  h4 { font-size: 1.1em; }

  p {
    margin: 1em 0;
  }

  code {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
    color: #e83e8c;
  }

  pre {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 1em 0;

    code {
      background: transparent;
      padding: 0;
      color: inherit;
    }
  }

  blockquote {
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 4px solid #409eff;
    background: #f5f7fa;
    color: #606266;

    p {
      margin: 0.5em 0;
    }
  }

  ul, ol {
    padding-left: 2em;
    margin: 1em 0;

    li {
      margin: 0.5em 0;
    }
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;

    th, td {
      border: 1px solid #dcdfe6;
      padding: 8px 12px;
      text-align: left;
    }

    th {
      background: #f5f7fa;
      font-weight: 600;
    }

    tr:nth-child(even) {
      background: #fafafa;
    }
  }

  a {
    color: #409eff;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  img {
    max-width: 100%;
    border-radius: 8px;
  }

  hr {
    border: none;
    border-top: 1px solid #eee;
    margin: 2em 0;
  }

  // 代码高亮主题
  .hljs-keyword { color: #569cd6; }
  .hljs-string { color: #ce9178; }
  .hljs-number { color: #b5cea8; }
  .hljs-comment { color: #6a9955; }
  .hljs-function { color: #dcdcaa; }
  .hljs-class { color: #4ec9b0; }
  .hljs-variable { color: #9cdcfe; }
  .hljs-attr { color: #9cdcfe; }
  .hljs-built_in { color: #4fc1ff; }
}
</style>
