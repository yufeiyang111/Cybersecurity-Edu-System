<template>
  <div class="graph-page">
    <header class="page-header">
      <div class="header-content">
        <h1>
          <el-icon><Connection /></el-icon>
          网络安全知识图谱
        </h1>
        <p>可视化展示知识点间的关联关系，探索网络安全知识体系</p>
      </div>
    </header>

    <div class="graph-container">
      <aside class="graph-sidebar">
        <div class="sidebar-section">
          <h3>图谱统计</h3>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-value">{{ graphStats.node_count }}</span>
              <span class="stat-label">节点数</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ graphStats.edge_count }}</span>
              <span class="stat-label">边数</span>
            </div>
          </div>
        </div>

        <div class="sidebar-section">
          <h3>节点搜索</h3>
          <el-input
            v-model="searchQuery"
            placeholder="搜索节点..."
            clearable
            @input="handleSearch"
            @clear="clearSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <div v-if="searchResults.length" class="search-results">
            <div
              v-for="result in searchResults"
              :key="result.id"
              class="search-result-item"
              @click="focusToNode(result)"
            >
              <span class="result-name">{{ result.name }}</span>
              <el-tag size="small" :type="getNodeTypeColor(result.nodeType)">{{ result.nodeType }}</el-tag>
            </div>
          </div>
        </div>

        <div class="sidebar-section">
          <h3>节点类型</h3>
          <div class="node-type-legend">
            <div v-for="(color, type) in nodeTypeColors" :key="type" class="legend-item">
              <span class="legend-dot" :style="{ background: color }"></span>
              <span class="legend-label">{{ getNodeTypeText(type) }}</span>
            </div>
          </div>
        </div>

        <div class="sidebar-section">
          <h3>关系类型</h3>
          <div class="relation-list">
            <div
              v-for="(count, rel) in graphStats.relation_types"
              :key="rel"
              class="relation-item"
              :class="{ active: selectedRelation === rel }"
              @click="filterByRelation(rel)"
            >
              <span class="relation-dot" :style="{ background: relationColors[rel] }"></span>
              <span class="relation-name">{{ getRelationText(rel) }}</span>
              <span class="relation-count">{{ count }}</span>
            </div>
          </div>
        </div>

        <div class="sidebar-section">
          <h3>筛选条件</h3>
          <el-select v-model="selectedCategory" placeholder="选择分类" clearable @change="handleFilter">
            <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
          </el-select>
        </div>
      </aside>

      <main class="graph-main">
        <div class="graph-toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="searchQuery"
              placeholder="搜索节点..."
              size="small"
              style="width: 200px;"
              clearable
              @input="handleSearch"
              @clear="clearSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
          <div class="toolbar-right">
            <el-button-group size="small">
              <el-button @click="zoomIn" title="放大">
                <el-icon><Plus /></el-icon>
              </el-button>
              <el-button @click="zoomOut" title="缩小">
                <el-icon><Minus /></el-icon>
              </el-button>
              <el-button @click="resetZoom" title="重置视图">
                <el-icon><Refresh /></el-icon>
              </el-button>
              <el-button @click="focusSelectedNode" title="聚焦选中节点" :disabled="!selectedNodeForFocus">
                <el-icon><Aim /></el-icon>
              </el-button>
            </el-button-group>
            <el-button v-if="isSubgraphView" type="warning" size="small" @click="resetToFullGraph">
              <el-icon><Back /></el-icon>
              返回完整图谱
            </el-button>
            <el-button type="primary" size="small" @click="refreshGraph">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>

        <div class="graph-chart-wrapper">
          <div ref="chartRef" class="graph-chart"></div>
          <div ref="minimapRef" class="graph-minimap"></div>
        </div>

        <!-- 节点详情弹窗 -->
        <el-dialog v-model="nodeDialogVisible" title="节点详情" width="500px">
          <div v-if="selectedNode" class="node-detail">
            <h3>{{ selectedNode.title }}</h3>
            <div class="detail-info">
              <p><strong>类型：</strong>{{ selectedNode.type }}</p>
              <p><strong>分类：</strong>{{ selectedNode.category }}</p>
              <p><strong>关联数量：</strong>{{ selectedNode.degree }}</p>
            </div>
            <el-divider />
            <h4>关联节点</h4>
            <div class="neighbors-list" v-loading="loadingNeighbors">
              <div
                v-for="neighbor in neighbors"
                :key="neighbor.node_id"
                class="neighbor-item"
                @click="focusNode(neighbor.node_id)"
              >
                <span class="neighbor-id">{{ neighbor.node_id }}</span>
                <span class="neighbor-rel">{{ neighbor.relation || '相关' }}</span>
              </div>
              <el-empty v-if="!neighbors.length && !loadingNeighbors" description="暂无关联节点" />
            </div>
            <div class="detail-actions">
              <el-button type="primary" @click="viewKnowledge">查看详情</el-button>
              <el-button @click="startFromNode">以此节点开始</el-button>
            </div>
          </div>
        </el-dialog>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { adminAPI, knowledgeAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { Connection, Search, Plus, Minus, Refresh, Aim, Back } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const router = useRouter()
const userStore = useUserStore()

const chartRef = ref(null)
const minimapRef = ref(null)
const chart = ref(null)
const minimap = ref(null)
const graphStats = ref({ node_count: 0, edge_count: 0, relation_types: {} })
const categories = ref([])
const selectedCategory = ref(null)
const selectedRelation = ref(null)
const selectedNode = ref(null)
const selectedNodeForFocus = ref(null)
const neighbors = ref([])
const loadingNeighbors = ref(false)
const nodeDialogVisible = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const allNodes = ref([])
const isSubgraphView = ref(false)

const relationColors = {
  'is_a': '#67c23a',
  'part_of': '#10b981',
  'uses': '#e6a23c',
  'caused_by': '#f56c6c',
  'related_to': '#909399',
  'depends_on': '#9c27b0',
  'contrasts_with': '#ff9800'
}

const nodeTypeColors = {
  'vulnerability': '#f56c6c',
  'concept': '#10b981',
  'technique': '#e6a23c',
  'tool': '#909399',
  'protocol': '#9c27b0',
  'domain': '#67c23a'
}

const getNodeTypeText = (type) => {
  const texts = {
    'vulnerability': '漏洞',
    'concept': '概念',
    'technique': '技术',
    'tool': '工具',
    'protocol': '协议',
    'domain': '领域'
  }
  return texts[type] || type || '未知'
}

const getNodeTypeColor = (type) => {
  const colorMap = {
    'vulnerability': 'danger',
    'concept': '',
    'technique': 'warning',
    'tool': 'info',
    'protocol': '',
    'domain': 'success'
  }
  return colorMap[type] || 'info'
}

const getRelationText = (rel) => {
  const texts = {
    'is_a': '包含关系',
    'part_of': '组成关系',
    'uses': '使用关系',
    'caused_by': '因果关系',
    'related_to': '相关关系',
    'depends_on': '依赖关系',
    'contrasts_with': '对比关系'
  }
  return texts[rel] || rel
}

const initChart = () => {
  if (!chartRef.value) return

  chart.value = echarts.init(chartRef.value)

  // 初始化 minimap
  if (minimapRef.value) {
    minimap.value = echarts.init(minimapRef.value)
  }

  chart.value.on('click', (params) => {
    if (params.dataType === 'node') {
      selectedNodeForFocus.value = params.data
      showNodeDetail(params.data)
    }
  })

  chart.value.on('mouseover', (params) => {
    if (params.dataType === 'node') {
      chart.value.dispatchAction({
        type: 'focusNodeAdjacency',
        dataIndex: params.dataIndex
      })
    }
  })

  window.addEventListener('resize', () => {
    chart.value?.resize()
    minimap.value?.resize()
  })
}

const loadGraphData = async () => {
  try {
    const [nodesRes, edgesRes, statsRes] = await Promise.all([
      adminAPI.getGraphNodes({ limit: 100 }),
      adminAPI.getGraphEdges(),
      adminAPI.getGraphStats()
    ])

    graphStats.value = statsRes.stats || { node_count: 0, edge_count: 0, relation_types: {} }

    const nodes = (nodesRes.nodes || []).map(node => ({
      id: node.id,
      name: node.title,
      category: node.category,
      nodeType: node.type,
      degree: node.degree,
      value: node.degree || 1
    }))

    allNodes.value = nodes

    const edges = (edgesRes.edges || []).map((edge, idx) => ({
      source: edge.source,
      target: edge.target,
      name: edge.relation || '相关',
      lineStyle: {
        color: relationColors[edge.relation] || '#909399'
      }
    }))

    renderChart(nodes, edges)
  } catch (error) {
    console.error('加载图谱数据失败', error)
    ElMessage.error('加载知识图谱失败，请刷新重试')
  }
}

const loadDemoGraph = () => {
  const nodes = [
    { id: '1', name: 'SQL注入', category: 'Web安全', nodeType: 'vulnerability', degree: 5, value: 5 },
    { id: '2', name: 'XSS攻击', category: 'Web安全', nodeType: 'vulnerability', degree: 4, value: 4 },
    { id: '3', name: 'CSRF攻击', category: 'Web安全', nodeType: 'vulnerability', degree: 3, value: 3 },
    { id: '4', name: 'Web安全', category: '安全领域', nodeType: 'concept', degree: 6, value: 6 },
    { id: '5', name: '网络扫描', category: '渗透测试', nodeType: 'technique', degree: 3, value: 3 },
    { id: '6', name: '密码学', category: '安全基础', nodeType: 'concept', degree: 5, value: 5 },
    { id: '7', name: 'AES加密', category: '密码学', nodeType: 'technique', degree: 3, value: 3 },
    { id: '8', name: 'HTTPS', category: '网络安全', nodeType: 'protocol', degree: 4, value: 4 },
    { id: '9', name: '防火墙', category: '系统安全', nodeType: 'tool', degree: 3, value: 3 },
    { id: '10', name: '渗透测试', category: '安全领域', nodeType: 'concept', degree: 4, value: 4 }
  ]

  const edges = [
    { source: '1', target: '4', name: 'part_of', lineStyle: { color: '#10b981' } },
    { source: '2', target: '4', name: 'part_of', lineStyle: { color: '#10b981' } },
    { source: '3', target: '4', name: 'part_of', lineStyle: { color: '#10b981' } },
    { source: '4', target: '10', name: 'uses', lineStyle: { color: '#e6a23c' } },
    { source: '5', target: '10', name: 'part_of', lineStyle: { color: '#10b981' } },
    { source: '6', target: '10', name: 'related_to', lineStyle: { color: '#909399' } },
    { source: '7', target: '6', name: 'part_of', lineStyle: { color: '#10b981' } },
    { source: '8', target: '4', name: 'uses', lineStyle: { color: '#e6a23c' } },
    { source: '9', target: '10', name: 'related_to', lineStyle: { color: '#909399' } },
    { source: '1', target: '5', name: 'uses', lineStyle: { color: '#e6a23c' } }
  ]

  graphStats.value = {
    node_count: nodes.length,
    edge_count: edges.length,
    relation_types: { 'part_of': 5, 'uses': 2, 'related_to': 2, 'is_a': 0, 'caused_by': 0, 'depends_on': 0, 'contrasts_with': 0 }
  }

  allNodes.value = nodes
  renderChart(nodes, edges)
}

const renderChart = (nodes, edges) => {
  if (!chart.value) return

  const categories = [...new Set(nodes.map(n => n.category))]
  const nodeTypes = [...new Set(nodes.map(n => n.nodeType).filter(Boolean))]

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'node') {
          return `<strong>${params.data.name}</strong><br/>类型: ${getNodeTypeText(params.data.nodeType)}<br/>分类: ${params.data.category || '未分类'}<br/>关联: ${params.data.degree || 0}个`
        }
        if (params.dataType === 'edge') {
          return `关系: ${getRelationText(params.data.name) || '相关'}`
        }
        return ''
      }
    },
    legend: [
      {
        data: categories,
        top: 10,
        left: 10,
        textStyle: { fontSize: 11 }
      },
      {
        data: nodeTypes.map(t => getNodeTypeText(t)),
        top: 10,
        right: 10,
        textStyle: { fontSize: 11 }
      }
    ],
    series: [{
      type: 'graph',
      layout: 'force',
      force: {
        repulsion: 1000,
        gravity: 0.05,
        edgeLength: [150, 400],
        layoutAnimation: true,
        friction: 0.9,
        alpha: 0.1,
        alphaDecay: 0.02
      },
      symbolSize: (val, params) => {
        const base = 30
        const degreeBonus = (params.data.degree || 1) * 4
        return base + degreeBonus
      },
      roam: true,
      draggable: true,
      label: {
        show: true,
        formatter: '{b}',
        fontSize: 12,
        color: '#333',
        fontWeight: 'normal'
      },
      lineStyle: {
        width: 2,
        curveness: 0.15,
        opacity: 0.6
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: {
          width: 4,
          opacity: 1
        },
        itemStyle: {
          borderWidth: 3,
          borderColor: '#fff',
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.3)'
        }
      },
      categories: categories.map((cat, idx) => ({
        name: cat,
        itemStyle: {
          color: ['#10b981', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#9c27b0', '#00BCD4', '#FF9800'][idx % 8]
        }
      })),
      nodeTypeCategories: nodeTypes.map((type, idx) => ({
        name: getNodeTypeText(type),
        itemStyle: {
          color: nodeTypeColors[type] || '#909399'
        }
      })),
      data: nodes.map(n => ({
        ...n,
        category: categories.indexOf(n.category),
        itemStyle: {
          color: nodeTypeColors[n.nodeType] || '#10b981'
        }
      })),
      links: edges
    }]
  };

  chart.value.setOption(option)

  // 更新 minimap
  if (minimap.value) {
    minimap.value.setOption({
      series: [{
        type: 'graph',
        layout: 'force',
        data: nodes.map(n => ({
          ...n,
          itemStyle: { color: nodeTypeColors[n.nodeType] || '#10b981' }
        })),
        links: edges,
        lineStyle: { opacity: 0.3 }
      }]
    })
  }
}

const showNodeDetail = async (nodeData) => {
  selectedNode.value = nodeData
  nodeDialogVisible.value = true
  loadingNeighbors.value = true
  
  if (userStore.isAdmin) {
    try {
      const res = await adminAPI.getRelatedNodes(nodeData.id, { depth: 1 })
      neighbors.value = res.neighbors || []
    } catch (error) {
      neighbors.value = []
    }
  } else {
    // 示例数据
    neighbors.value = [
      { node_id: '1', relation: 'part_of' },
      { node_id: '2', relation: 'uses' },
      { node_id: '5', relation: 'related_to' }
    ]
  }
  
  loadingNeighbors.value = false
}

const focusNode = (nodeId) => {
  chart.value.dispatchAction({
    type: 'focusNodeAdjacency',
    dataIndex: chart.value.getOption().series[0].data.findIndex(n => n.id === nodeId)
  })
}

const handleSearch = () => {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }
  const query = searchQuery.value.toLowerCase()
  searchResults.value = allNodes.value.filter(n =>
    n.name.toLowerCase().includes(query) ||
    (n.category && n.category.toLowerCase().includes(query))
  ).slice(0, 10)
}

const clearSearch = () => {
  searchResults.value = []
}

const focusToNode = (node) => {
  selectedNodeForFocus.value = node
  searchResults.value = []
  searchQuery.value = ''

  const option = chart.value.getOption()
  const dataIndex = option.series[0].data.findIndex(n => n.id === node.id)

  if (dataIndex >= 0) {
    chart.value.dispatchAction({ type: 'highlight', dataIndex })
    chart.value.dispatchAction({
      type: 'showTip',
      seriesIndex: 0,
      dataIndex
    })
  }

  ElMessage.success(`已聚焦到节点: ${node.name}`)
}

const focusSelectedNode = () => {
  if (selectedNodeForFocus.value) {
    focusToNode(selectedNodeForFocus.value)
  }
}

const viewKnowledge = () => {
  if (selectedNode.value) {
    const nodeId = selectedNode.value.id
    // 实体节点 ID 格式是 "知识ID_实体名"，需要提取知识ID
    if (selectedNode.value.nodeType === 'knowledge') {
      router.push(`/knowledge/${nodeId}`)
    } else {
      // 实体节点，提取知识ID（格式如 "11_加密" -> "11"）
      const knowledgeId = nodeId.split('_')[0]
      if (knowledgeId) {
        router.push(`/knowledge/${knowledgeId}`)
      } else {
        ElMessage.error('无法跳转：该节点没有关联的知识条目')
      }
    }
  }
  nodeDialogVisible.value = false
}

const startFromNode = async () => {
  if (!selectedNode.value) return

  nodeDialogVisible.value = false

  try {
    // 获取以该节点为中心的子图（深度2）
    const res = await adminAPI.getRelatedNodes(selectedNode.value.id, { depth: 2 })

    if (!res.neighbors || res.neighbors.length === 0) {
      ElMessage.warning('该节点没有更多关联节点')
      return
    }

    // 收集子图中的所有节点ID
    const subgraphNodeIds = new Set([selectedNode.value.id])
    const subgraphEdges = []

    // 处理邻居节点
    for (const neighbor of res.neighbors) {
      subgraphNodeIds.add(neighbor.node_id)
      subgraphEdges.push({
        source: selectedNode.value.id,
        target: neighbor.node_id,
        name: neighbor.relation || '相关',
        lineStyle: {
          color: relationColors[neighbor.relation] || '#909399'
        }
      })

      // 处理更深层的邻居（如果API返回了path）
      if (neighbor.path && neighbor.path.length > 2) {
        for (let i = 0; i < neighbor.path.length - 1; i++) {
          subgraphNodeIds.add(neighbor.path[i])
          subgraphNodeIds.add(neighbor.path[i + 1])
          subgraphEdges.push({
            source: neighbor.path[i],
            target: neighbor.path[i + 1],
            name: '相关',
            lineStyle: { color: '#909399' }
          })
        }
      }
    }

    // 从 allNodes 中筛选子图节点
    const subgraphNodes = allNodes.value.filter(n => subgraphNodeIds.has(n.id))

    // 如果节点数据不全，尝试从邻居数据构建
    const missingNodes = subgraphNodeIds.size - subgraphNodes.length
    if (missingNodes > 0) {
      // 从邻居信息补充节点
      for (const neighbor of res.neighbors) {
        if (!subgraphNodes.find(n => n.id === neighbor.node_id)) {
          subgraphNodes.push({
            id: neighbor.node_id,
            name: neighbor.node_id.toString(),
            category: '未分类',
            nodeType: 'concept',
            degree: 1,
            value: 1
          })
        }
      }
    }

    // 渲染子图
    renderChart(subgraphNodes, subgraphEdges)

    // 标记为子图视图
    isSubgraphView.value = true

    ElMessage.success(`已展开以「${selectedNode.value.name}」为中心的知识网络`)
  } catch (error) {
    console.error('展开节点失败', error)
    ElMessage.error('展开节点失败')
  }
}

const resetToFullGraph = () => {
  isSubgraphView.value = false
  loadGraphData()
  ElMessage.success('已返回完整知识图谱')
}

const handleFilter = () => {
  loadGraphData()
}

const filterByRelation = (rel) => {
  selectedRelation.value = rel
  loadGraphData()
}

const zoomIn = () => {
  chart.value?.dispatchAction({ type: 'zoomIn' })
}

const zoomOut = () => {
  chart.value?.dispatchAction({ type: 'zoomOut' })
}

const resetZoom = () => {
  chart.value?.dispatchAction({ type: 'resetZoom' })
}

const refreshGraph = () => {
  isSubgraphView.value = false
  loadGraphData()
}

const loadCategories = async () => {
  try {
    const res = await knowledgeAPI.getCategories()
    categories.value = res.categories || []
  } catch (error) {
    console.error('加载分类失败')
  }
}

onMounted(() => {
  initChart()
  loadCategories()
  loadGraphData()
})

onUnmounted(() => {
  window.removeEventListener('resize', () => {
    chart.value?.resize()
    minimap.value?.resize()
  })
  chart.value?.dispose()
  minimap.value?.dispose()
})
</script>

<style lang="scss" scoped>
.graph-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  padding: 40px 0;
  color: #fff;
  
  .header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
    
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    p {
      margin: 0;
      opacity: 0.9;
    }
  }
}

.graph-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px;
  display: flex;
  gap: 24px;
}

.graph-sidebar {
  width: 280px;

  .sidebar-section {
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    h3 {
      margin: 0 0 16px;
      font-size: 16px;
      color: #303133;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;

      .stat-item {
        text-align: center;

        .stat-value {
          display: block;
          font-size: 24px;
          font-weight: 600;
          color: #409eff;
        }

        .stat-label {
          font-size: 12px;
          color: #909399;
        }
      }
    }

    .search-results {
      margin-top: 12px;
      max-height: 200px;
      overflow-y: auto;

      .search-result-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        border-radius: 6px;
        cursor: pointer;
        transition: background 0.2s;

        &:hover {
          background: #f5f7fa;
        }

        .result-name {
          font-size: 13px;
          color: #303133;
        }
      }
    }

    .node-type-legend {
      .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 0;

        .legend-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }

        .legend-label {
          font-size: 13px;
          color: #606266;
        }
      }
    }

    .relation-list {
      .relation-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
        border-radius: 6px;
        cursor: pointer;
        transition: background 0.3s;

        &:hover, &.active {
          background: #f5f7fa;
        }

        &.active {
          background: #ecf5ff;
        }

        .relation-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
        }

        .relation-name {
          flex: 1;
          font-size: 14px;
          color: #606266;
        }

        .relation-count {
          font-size: 14px;
          color: #409eff;
          font-weight: 600;
        }
      }
    }
  }
}

.graph-main {
  flex: 1;

  .graph-toolbar {
    background: #fff;
    padding: 12px 16px;
    border-radius: 12px;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);

    .toolbar-left, .toolbar-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  }

  .graph-chart-wrapper {
    position: relative;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    overflow: hidden;
  }

  .graph-chart {
    height: 600px;
  }

  .graph-minimap {
    position: absolute;
    bottom: 10px;
    right: 10px;
    width: 150px;
    height: 100px;
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    opacity: 0.8;
    transition: opacity 0.3s;

    &:hover {
      opacity: 1;
    }
  }
}

.node-detail {
  h3 {
    margin: 0 0 16px;
    color: #303133;
  }
  
  .detail-info {
    p {
      margin: 8px 0;
      font-size: 14px;
      color: #606266;
    }
  }
  
  h4 {
    margin: 16px 0 12px;
    font-size: 14px;
    color: #606266;
  }
  
  .neighbors-list {
    max-height: 200px;
    overflow-y: auto;
    
    .neighbor-item {
      display: flex;
      justify-content: space-between;
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 6px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: background 0.3s;
      
      &:hover {
        background: #ecf5ff;
      }
      
      .neighbor-id {
        color: #409eff;
      }
      
      .neighbor-rel {
        color: #909399;
        font-size: 12px;
      }
    }
  }
  
  .detail-actions {
    margin-top: 16px;
    display: flex;
    gap: 12px;
  }
}
</style>
