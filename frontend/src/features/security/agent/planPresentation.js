const INTERNAL_RUNTIME_NODE_PREFIX = /^loop_[a-z0-9]/i

export function isInternalRuntimeNode(node) {
  if (!node || typeof node !== 'object') {
    return false
  }

  if (node.runtime_internal === true) {
    return true
  }

  const key = String(node.node_key || '')
  return INTERNAL_RUNTIME_NODE_PREFIX.test(key)
}

export function presentPlanNodes(nodes) {
  if (!Array.isArray(nodes)) {
    return { nodes: [], technicalNodeCount: 0 }
  }

  const visibleNodes = []
  let technicalNodeCount = 0

  for (const node of nodes) {
    if (!node || typeof node !== 'object') {
      continue
    }
    if (isInternalRuntimeNode(node)) {
      technicalNodeCount += 1
      continue
    }
    visibleNodes.push(node)
  }

  return {
    nodes: visibleNodes,
    technicalNodeCount
  }
}
