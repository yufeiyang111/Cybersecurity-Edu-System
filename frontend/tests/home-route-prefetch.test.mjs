import { test } from 'node:test'
import assert from 'node:assert/strict'

import { createRoutePrefetcher } from '../../frontend/src/features/home/routePrefetch.js'

test('同一路由的并发预加载只执行一次，并在成功后复用缓存', async () => {
  let calls = 0
  const prefetchRoute = createRoutePrefetcher({
    qa: async () => {
      calls += 1
    }
  })

  await Promise.all([
    prefetchRoute('qa'),
    prefetchRoute('qa')
  ])
  await prefetchRoute('qa')

  assert.equal(calls, 1)
})

test('预加载失败不会阻断点击导航，后续仍允许重新尝试', async () => {
  let calls = 0
  const prefetchRoute = createRoutePrefetcher({
    qa: async () => {
      calls += 1
      if (calls === 1) {
        throw new Error('transient chunk failure')
      }
    }
  })

  await assert.doesNotReject(prefetchRoute('qa'))
  await assert.doesNotReject(prefetchRoute('qa'))

  assert.equal(calls, 2)
})

test('未知路由不会触发加载器', async () => {
  let calls = 0
  const prefetchRoute = createRoutePrefetcher({
    qa: async () => {
      calls += 1
    }
  })

  await assert.doesNotReject(prefetchRoute('unknown'))

  assert.equal(calls, 0)
})