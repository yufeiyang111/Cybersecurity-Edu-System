import { computed, ref } from 'vue'
import { agentAPI } from '@/api'

const NODE_TYPE_META = {
  route: { label: '路由', color: '#2563eb', symbol: 'circle' },
  middleware: { label: '中间件', color: '#9333ea', symbol: 'diamond' },
  service: { label: '服务', color: '#0d9488', symbol: 'circle' },
  repository: { label: '仓储', color: '#c2410c', symbol: 'circle' },
  model: { label: '模型', color: '#16a34a', symbol: 'circle' },
  function: { label: '函数', color: '#6b7280', symbol: 'circle' },
  dependency: { label: '依赖', color: '#b45309', symbol: 'diamond' },
  external_call: { label: '外部调用', color: '#dc2626', symbol: 'diamond' },
  file: { label: '文件', color: '#64748b', symbol: 'rect' }
}

const EDGE_TYPE_LABELS = {
  calls: '调用',
  imports: '导入',
  inherits: '继承',
  decorated_by: '装饰',
  route_handles: '路由处理',
  contains: '包含',
  has_dependency: '依赖',
  calls_into: '跨文件调用'
}

const CONFIDENCE_LABELS = {
  exact: '精确',
  heuristic: '启发式',
  partial: '部分'
}

function nodeMeta(nodeType) {
  return NODE_TYPE_META[nodeType] || NODE_TYPE_META.function
}

export function useProjectSecurityGraph(runIdGetter) {
  const summary = ref(null)
  const entryNodes = ref([])
  const total = ref(0)
  const loading = ref(false)
  const building = ref(false)
  const neighbors = ref({})
  const codeSlice = ref(null)
  const errorMessage = ref('')

  const hasGraph = computed(() => summary.value !== null)

  async function loadGraph() {
    const runId = runIdGetter()
    if (!runId) return
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await agentAPI.getGraph(runId, { limit: 50, offset: 0 })
      summary.value = response.graph || null
      entryNodes.value = response.entry_nodes || []
      total.value = response.pagination?.total || 0
    } catch (error) {
      errorMessage.value = error?.response?.data?.error || '图数据加载失败'
    } finally {
      loading.value = false
    }
  }

  async function buildGraph() {
    const runId = runIdGetter()
    if (!runId || building.value) return
    building.value = true
    errorMessage.value = ''
    try {
      const response = await agentAPI.buildGraph(runId)
      if (response.status === 'built' || response.status === 'cached') {
        await loadGraph()
        return response
      }
      errorMessage.value = response.message || '建图失败'
      return null
    } catch (error) {
      errorMessage.value = error?.response?.data?.error || '建图请求失败'
      return null
    } finally {
      building.value = false
    }
  }

  async function loadNeighbors(nodeId, { limit = 20, offset = 0 } = {}) {
    const runId = runIdGetter()
    if (!runId) return { edges: [], total: 0 }
    try {
      const response = await agentAPI.getGraphNeighbors(runId, nodeId, { limit, offset })
      const key = String(nodeId)
      const existing = neighbors.value[key] || []
      const merged = offset === 0 ? response.edges : [...existing, ...response.edges]
      neighbors.value[key] = merged
      return { edges: response.edges, total: response.pagination?.total || 0 }
    } catch (error) {
      errorMessage.value = error?.response?.data?.error || '邻居加载失败'
      return { edges: [], total: 0 }
    }
  }

  async function loadCodeSlice({ filePath, startLine, endLine, reason }) {
    const runId = runIdGetter()
    if (!runId) return null
    try {
      const response = await agentAPI.getGraphCodeSlice(runId, {
        file: filePath,
        start_line: startLine,
        end_line: endLine,
        reason
      })
      codeSlice.value = response
      return response
    } catch (error) {
      errorMessage.value = error?.response?.data?.error || '源码读取失败'
      return null
    }
  }

  function toEChartsGraph() {
    const nodes = [...entryNodes.value]
    const edges = []
    const nodeIds = new Set(nodes.map((node) => node.id))
    Object.values(neighbors.value).forEach((list) => {
      list.forEach((edge) => {
        const source = edge.source_node_id
        const target = edge.target_node_id
        if (!nodeIds.has(source)) {
          nodeIds.add(source)
          nodes.push(edge.source_node ? {
            id: source,
            node_type: edge.source_node.node_type,
            label: edge.source_node.label,
            file_path: edge.source_node.file_path
          } : { id: source, node_type: 'function', label: `#${source}` })
        }
        if (!nodeIds.has(target)) {
          nodeIds.add(target)
          nodes.push(edge.target_node ? {
            id: target,
            node_type: edge.target_node.node_type,
            label: edge.target_node.label,
            file_path: edge.target_node.file_path
          } : { id: target, node_type: 'function', label: `#${target}` })
        }
        edges.push({
          source,
          target,
          label: EDGE_TYPE_LABELS[edge.edge_type] || edge.edge_type,
          edgeType: edge.edge_type,
          confidence: edge.confidence,
          extractor: edge.extractor
        })
      })
    })
    return {
      seriesNodes: nodes.map((node) => {
        const meta = nodeMeta(node.node_type)
        return {
          id: node.id,
          name: node.label,
          label: { show: true, fontSize: 11 },
          category: node.node_type,
          symbol: meta.symbol,
          itemStyle: { color: meta.color },
          nodeType: node.node_type,
          filePath: node.file_path
        }
      }),
      seriesEdges: edges
    }
  }

  return {
    summary,
    entryNodes,
    total,
    loading,
    building,
    neighbors,
    codeSlice,
    errorMessage,
    hasGraph,
    loadGraph,
    buildGraph,
    loadNeighbors,
    loadCodeSlice,
    toEChartsGraph,
    nodeMeta,
    edgeTypeLabel: (type) => EDGE_TYPE_LABELS[type] || type,
    confidenceLabel: (level) => CONFIDENCE_LABELS[level] || level
  }
}
