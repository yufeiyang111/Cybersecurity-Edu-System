import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const testDirectory = dirname(fileURLToPath(import.meta.url))
const layoutPath = join(testDirectory, '..', 'src', 'views', 'SecurityWorkbenchLayout.vue')
const layoutSource = await readFile(layoutPath, 'utf8')

test('移动端导航提供独立的侧栏关闭按钮，避免遮罩中心命中侧栏链接', () => {
  assert.match(layoutSource, /class="sidebar-mobile-header"/)
  assert.match(
    layoutSource,
    /class="sidebar-close-btn"[\s\S]*?aria-label="关闭导航"[\s\S]*?@click\.stop="mobileSidebarOpen = false"/
  )
  assert.match(
    layoutSource,
    /class="sidebar-backdrop"[\s\S]*?aria-label="关闭导航遮罩"[\s\S]*?@click="mobileSidebarOpen = false"/
  )
  assert.doesNotMatch(
    layoutSource,
    /class="sidebar-backdrop"[^>]*aria-label="关闭导航"[^>]*\/>/
  )
})

test('移动端遮罩只覆盖侧栏外区域，不能覆盖侧栏自身的命中区域', () => {
  const mobileBlock = layoutSource.match(/@media \(max-width: 768px\)[\s\S]*?<\/style>/)?.[0] || ''

  assert.match(mobileBlock, /\.sidebar\s*\{[\s\S]*?width:\s*min\(280px, 86vw\)/)
  assert.match(mobileBlock, /\.sidebar-backdrop\s*\{[\s\S]*?left:\s*min\(280px, 86vw\)/)
  assert.doesNotMatch(mobileBlock, /\.sidebar-backdrop\s*\{[\s\S]*?inset:\s*60px 0 0/)
})

test('侧栏导航项仍然在路由跳转时关闭移动端抽屉', () => {
  const navigationLinks = layoutSource.match(/<router-link[\s\S]*?@click="mobileSidebarOpen = false"[\s\S]*?<\/router-link>/g) || []

  assert.ok(navigationLinks.length >= 3)
  assert.ok(navigationLinks.some((link) => link.includes('to="/security/llm/logs"')))
})