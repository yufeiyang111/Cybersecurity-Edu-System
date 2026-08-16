import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const layoutUrl = new URL(
  '../../frontend/src/views/SecurityWorkbenchLayout.vue',
  import.meta.url
)

async function readLayoutSource() {
  return readFile(layoutUrl, 'utf8')
}

test('安全工作台在平板宽度收起顶部导航，避免逐字压缩', async () => {
  const source = await readLayoutSource()

  assert.match(
    source,
    /@media \(max-width: 1200px\) \{\s*\.topbar \.top-nav \{\s*display: none;/s
  )
})