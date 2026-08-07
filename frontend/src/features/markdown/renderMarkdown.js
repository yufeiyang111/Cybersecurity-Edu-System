import { Marked, Renderer } from 'marked'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'

const escapeHtml = (str) =>
  String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

const renderer = new Renderer()
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
    '<div class="chat-code">',
    `<div class="chat-code-head"><span class="chat-code-lang">${escapeHtml(label)}</span>`,
    `<button class="chat-code-copy" type="button" data-code="${encoded}">`,
    '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 012-2h10"/></svg>',
    '<span>复制</span></button></div>',
    `<pre><code class="hljs">${highlighted}</code></pre>`,
    '</div>'
  ].join('')
}

const marked = new Marked({
  gfm: true,
  breaks: true,
  renderer
})

const renderMarkdown = (content, { sanitize = true } = {}) => {
  if (!content) return ''
  const html = marked.parse(content)
  return sanitize ? DOMPurify.sanitize(html) : html
}

const handleCodeCopyClick = (e) => {
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

let copyHandlerInstalled = false
const installCodeCopy = () => {
  if (copyHandlerInstalled) return
  copyHandlerInstalled = true
  document.addEventListener('click', handleCodeCopyClick)
}

export { renderMarkdown, installCodeCopy }
