/**
 * Markdown 标题大纲提取与锚点 slug 生成
 *
 * - `extractMarkdownHeadings`：提取 # ~ #### 标题生成 TOC 条目
 * - `slugifyHeadingId`：标题文本 → 锚点 id（与 renderMarkdown 的 heading id 保持一致）
 */
export function extractMarkdownHeadings(markdown) {
  if (!markdown) return []
  const lines = markdown.split('\n')
  const items = []

  for (const line of lines) {
    const match = /^(#{1,4})\s+(.+?)\s*$/.exec(line)
    if (!match) continue
    const level = match[1].length
    const text = match[2].replace(/[*_`]/g, '').trim()
    if (!text) continue
    items.push({
      level,
      text,
      id: slugifyHeadingId(text)
    })
  }
  return items
}

export function slugifyHeadingId(text) {
  return String(text)
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u4e00-\u9fa5-]/g, '')
}
