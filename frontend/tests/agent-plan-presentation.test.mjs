import { test } from 'node:test'
import assert from 'node:assert/strict'

import { isInternalRuntimeNode, presentPlanNodes } from '../../frontend/src/features/security/agent/planPresentation.js'

test('运行时 loop 节点被识别为技术细节，业务计划节点保持可见', () => {
  assert.equal(isInternalRuntimeNode({ node_key: 'loop_3_call_7' }), true)
  assert.equal(isInternalRuntimeNode({ node_key: 'baseline_scan' }), false)
  assert.equal(isInternalRuntimeNode({ node_key: 'loopback_check' }), false)
})

test('计划展示层收纳内部节点并保留原有节点顺序和对象引用', () => {
  const visible = { node_key: "baseline_scan", title: "基线扫描" }
  const internal = { node_key: "loop_2_reasoning", title: "内部推理" }
  const result = presentPlanNodes([visible, internal, null])

  assert.deepEqual(result.nodes, [visible])
  assert.equal(result.technicalNodeCount, 1)
})

test('未知或空计划安全降级为空列表', () => {
  assert.deepEqual(presentPlanNodes(null), { nodes: [], technicalNodeCount: 0 })
})
