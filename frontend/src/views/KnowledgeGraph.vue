<template>
  <div class="graph-page">
    <header class="page-header">
      <div class="header-orb"></div>
      <div class="header-grid"></div>
      <div class="header-inner">
        <button type="button" class="back-btn" @click="goBack">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5" />
            <path d="M12 19l-7-7 7-7" />
          </svg>
          返回
        </button>
        <div class="header-content">
          <div class="header-left">
            <div class="header-badge">
              <span class="badge-dot"></span>
              知识图谱
            </div>
            <h1 class="header-title">
              网络安全知识图谱
            </h1>
            <p class="header-desc">可视化展示知识点之间的关联关系，支持节点搜索、关系筛选与分类过滤</p>
          </div>
        </div>
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

        <div class="sidebar-section">
          <h3>社区视图</h3>
          <div class="community-control">
            <el-switch v-model="communityColorEnabled" @change="handleCommunityToggle" />
            <span class="community-control__label">按社区着色</span>
          </div>
          <el-button
            v-if="communityList.length"
            size="small"
            class="community-batch-btn"
            :loading="communityBatchLoading"
            @click="handleBatchSummarize"
          >
            预生成 Top 10 摘要
          </el-button>
          <div v-if="communityList.length" class="community-list">
            <div
              v-for="item in communityList"
              :key="item.id"
              class="community-item"
              :class="{ active: selectedCommunity === item.id }"
              @click="handleCommunityClick(item)"
            >
              <span class="community-dot" :style="{ background: communityColor(item.id) }"></span>
              <span class="community-name">
                社区 #{{ item.id }}
                <span class="community-sample">{{ item.sample.join('、') }}</span>
              </span>
              <span class="community-size">{{ item.size }}</span>
            </div>
          </div>
          <el-empty v-else-if="!communityLoading" description="暂无社区数据" :image-size="40" />
        </div>

        <div class="sidebar-section">
          <h3>中心性着色</h3>
          <div class="centrality-control">
            <el-switch v-model="centralityEnabled" @change="handleCentralityToggle" />
            <el-select
              v-model="centralityMetric"
              size="small"
              :disabled="!centralityEnabled"
              @change="loadCentralityScores"
            >
              <el-option label="PageRank 热度" value="pagerank" />
              <el-option label="连接数量" value="degree" />
            </el-select>
          </div>
          <div v-if="centralityEnabled && centralityScores" class="centrality-legend">
            <span class="legend-text">低</span>
            <div class="legend-gradient"></div>
            <span class="legend-text">高</span>
          </div>
        </div>

        <div v-if="userStore.isAdmin" class="sidebar-section">
          <h3>数据维护</h3>
          <p class="dedup-hint">
            合并同名同类型实体（如多个条目的「签名」），关系边迁移到保留节点，可减少重复节点
          </p>
          <el-popconfirm
            title="确认合并所有同名实体？此操作不可撤销"
            confirm-button-text="合并"
            cancel-button-text="取消"
            @confirm="runDeduplicate"
          >
            <template #reference>
              <el-button
                type="warning"
                size="small"
                :loading="deduplicating"
                block
              >
                合并同名实体
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </aside>

      <main class="graph-main">
        <div class="graph-toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="searchQuery"
              placeholder="搜索节点..."
              size="small"
              class="toolbar-search"
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
            <el-button size="small" @click="exportGraphImage">
              <el-icon><Download /></el-icon>
              导出图片
            </el-button>
            <el-button type="primary" size="small" @click="refreshGraph">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>

        <div class="graph-chart-wrapper">
          <ForceGraphCanvas
            ref="graphRef"
            :nodes="graphNodes"
            :edges="graphEdges"
            :node-color="nodeColorOf"
            :edge-color="edgeColorOf"
            :node-size="nodeSizeOf"
            :tooltip-title="tooltipTitleOf"
            :tooltip-fields="tooltipFieldsOf"
            :render-tick="renderTick"
            @node-click="handleNodeClick"
          />
        </div>

        <!-- 节点详情弹窗 -->
        <el-dialog v-model="nodeDialogVisible" title="节点详情" width="500px">
          <div v-if="selectedNode" class="node-detail">
            <h3>{{ selectedNode.name }}</h3>
            <div class="detail-info">
              <p><strong>类型：</strong>{{ getNodeTypeText(selectedNode.nodeType) }}</p>
              <p>
                <strong>分类：</strong>{{ selectedNodeCategory }}
                <span v-if="selectedNodeCategorySource" class="category-source">
                  （来源条目 #{{ selectedNodeCategorySource }}）
                </span>
              </p>
              <p><strong>关联数量：</strong>{{ selectedNode.degree || 0 }}</p>
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
                <span class="neighbor-rel">{{ getRelationText(neighbor.relation) || '相关' }}</span>
              </div>
              <el-empty v-if="!neighbors.length && !loadingNeighbors" description="暂无关联节点" />
            </div>

            <div v-if="nodeSources.length" class="detail-sources">
              <el-divider />
              <h4>来源文档（{{ nodeSources.length }}）</h4>
              <div class="sources-list">
                <div
                  v-for="source in nodeSources"
                  :key="source.id"
                  class="source-item"
                  @click="goToKnowledge(source.id)"
                >
                  <span class="source-title">{{ source.title }}</span>
                  <span class="source-cat">{{ source.category || '未分类' }}</span>
                </div>
              </div>
            </div>

            <el-divider />
            <h4>路径分析</h4>
            <div class="path-analyzer">
              <el-select
                v-model="pathTargetId"
                filterable
                placeholder="选择目标节点"
                size="small"
                class="path-target-select"
              >
                <el-option
                  v-for="node in allNodes"
                  :key="node.id"
                  :label="node.name"
                  :value="node.id"
                />
              </el-select>
              <el-button
                type="primary"
                size="small"
                :disabled="!pathTargetId"
                :loading="pathLoading"
                @click="runPathAnalysis"
              >
                查询路径
              </el-button>
            </div>
            <div v-if="pathNodes.length" class="path-result">
              <div class="path-meta">
                最短路径：{{ pathNodes.length }} 个节点 / {{ pathDistance }} 跳
                <el-button size="small" text type="primary" @click="clearPath">
                  清除
                </el-button>
              </div>
              <div class="path-list">
                <div
                  v-for="(node, index) in pathNodes"
                  :key="node.id"
                  class="path-item"
                  @click="focusNode(node.id)"
                >
                  <span class="path-index">{{ index + 1 }}</span>
                  <span class="path-name">{{ node.name }}</span>
                  <span class="path-type">{{ getNodeTypeText(node.type) }}</span>
                </div>
              </div>
            </div>

            <div v-if="userStore.isAdmin" class="merge-section">
              <el-divider />
              <h4>实体归并</h4>
              <p class="merge-hint">
                将当前节点合并到目标节点：关系边全部迁移，当前节点被删除（不可撤销）
              </p>
              <div class="merge-control">
                <el-select
                  v-model="mergeTargetId"
                  filterable
                  placeholder="选择目标节点"
                  size="small"
                  class="path-target-select"
                >
                  <el-option
                    v-for="node in allNodes"
                    :key="node.id"
                    :label="node.name"
                    :value="node.id"
                  />
                </el-select>
                <el-popconfirm
                  title="确认合并该节点？此操作不可撤销"
                  confirm-button-text="合并"
                  cancel-button-text="取消"
                  @confirm="runMerge"
                >
                  <template #reference>
                    <el-button
                      type="danger"
                      size="small"
                      :disabled="!mergeTargetId"
                      :loading="mergeLoading"
                    >
                      合并
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>

            <div class="detail-actions">
              <el-button v-if="selectedNode.nodeType === 'knowledge'" type="primary" @click="viewKnowledge">
                查看详情
              </el-button>
              <el-button v-else-if="nodeSources.length" type="primary" @click="viewKnowledge">
                查看来源文档
              </el-button>
              <el-button @click="startFromNode">以此节点开始</el-button>
            </div>
          </div>
        </el-dialog>

        <CommunitySummaryPanel
          v-model:visible="summaryPanelVisible"
          :community-id="selectedCommunitySummaryId"
          :community-sample="selectedCommunitySummarySample"
        />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { adminAPI, knowledgeAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { Search, Plus, Minus, Refresh, Aim, Back, Download } from '@element-plus/icons-vue'
import ForceGraphCanvas from '@/components/graph/ForceGraphCanvas.vue'
import CommunitySummaryPanel from '@/components/security/knowledgeGraph/CommunitySummaryPanel.vue'

const router = useRouter()
const userStore = useUserStore()

const goBack = () => {
  if (router.options.history.state.back) {
    router.back()
  } else {
    router.push('/')
  }
}

const graphRef = ref(null)
const graphNodes = ref([])
const graphEdges = ref([])
const allEdges = ref([])
const graphStats = ref({ node_count: 0, edge_count: 0, relation_types: {} })
const categories = ref([])
const selectedCategory = ref(null)
const selectedRelation = ref(null)
const selectedNode = ref(null)
const selectedNodeForFocus = ref(null)
const neighbors = ref([])
const nodeSources = ref([])
const loadingNeighbors = ref(false)
const nodeDialogVisible = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const allNodes = ref([])
const isSubgraphView = ref(false)

// 路径分析
const pathTargetId = ref(null)
const pathNodes = ref([])
const pathDistance = ref(0)
const pathLoading = ref(false)

// 实体归并
const mergeTargetId = ref(null)
const mergeLoading = ref(false)
const deduplicating = ref(false)

// 中心性着色
const centralityEnabled = ref(false)
const centralityMetric = ref('pagerank')
const centralityScores = ref(null)
const centralityRange = ref({ min: 0, max: 1 })
const renderTick = ref(0)

// 社区视图
const communityColorEnabled = ref(false)
const communityLoading = ref(false)
const communityData = ref(null) // { communities, node_community }
const selectedCommunity = ref(null)
const communityBatchLoading = ref(false)
const summaryPanelVisible = ref(false)
const selectedCommunitySummaryId = ref(null)
const selectedCommunitySummarySample = ref([])
const communityList = computed(() => {
  const data = communityData.value
  if (!data || !data.communities) return []
  return Object.entries(data.communities).map(([id, info]) => ({
    id,
    size: info.size,
    sample: info.sample || []
  }))
})

const communityColor = (communityId) => {
  // HSL 色相循环：社区 id 哈希到 0-360 色相，保证同社区同色、不同社区色差大
  let hash = 0
  const str = String(communityId)
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) % 360
  }
  return `hsl(${hash}, 65%, 55%)`
}

const nodeCommunityId = (nodeId) => {
  const data = communityData.value
  if (!data || !data.node_community) return null
  return data.node_community[nodeId] || null
}

// 详情面板分类：实体节点显示其来源知识条目的分类
const selectedNodeCategory = computed(() => {
  const node = selectedNode.value
  if (!node) return '未分类'
  if (node.category) return node.category
  if (node.nodeType === 'knowledge') return '未分类'
  return selectedNodeCategorySource.value
    ? nodeSourceCategory.value || '未分类'
    : '实体节点（无知识分类）'
})

const selectedNodeCategorySource = computed(() => {
  const node = selectedNode.value
  if (!node || node.nodeType === 'knowledge') return ''
  return String(node.id).split('_')[0]
})

const nodeSourceCategory = computed(() => {
  const sourceItemId = selectedNodeCategorySource.value
  if (!sourceItemId) return ''
  const sourceItem = allNodes.value.find(
    node => String(node.id) === sourceItemId && node.nodeType === 'knowledge'
  )
  return sourceItem?.category || ''
})

const relationColors = {
  'is_a': '#67c23a',
  'part_of': '#10b981',
  'uses': '#e6a23c',
  'caused_by': '#f56c6c',
  'related_to': '#909399',
  'depends_on': '#9c27b0',
  'contrasts_with': '#ff9800',
  // LLM 图谱语义关系
  'exploits': '#f56c6c',
  'mitigates': '#67c23a',
  'detects': '#409eff',
  'prerequisite': '#9c27b0',
  'causes': '#ff9800',
  'belongs_to': '#10b981',
  'contains': '#c0c4cc'
}

const nodeTypeColors = {
  'vulnerability': '#f56c6c',
  'attack_technique': '#e6a23c',
  'defense_measure': '#67c23a',
  'security_tool': '#409eff',
  'concept': '#10b981',
  'regulation': '#9c27b0',
  'threat_actor': '#ff5722',
  'knowledge': '#00bcd4',
  // 旧类型兼容
  'technique': '#e6a23c',
  'tool': '#409eff',
  'protocol': '#9c27b0',
  'domain': '#67c23a'
}

const getNodeTypeText = (type) => {
  const texts = {
    'vulnerability': '漏洞',
    'attack_technique': '攻击技术',
    'defense_measure': '防御措施',
    'security_tool': '安全工具',
    'concept': '概念',
    'regulation': '法规标准',
    'threat_actor': '威胁行为体',
    'knowledge': '知识条目',
    // 旧类型兼容
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
    'attack_technique': 'warning',
    'defense_measure': 'success',
    'security_tool': 'primary',
    'concept': '',
    'regulation': 'warning',
    'threat_actor': 'danger',
    'knowledge': 'primary',
    // 旧类型兼容
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
    'contrasts_with': '对比关系',
    // LLM 图谱语义关系
    'exploits': '被利用于',
    'mitigates': '缓解',
    'detects': '检测',
    'prerequisite': '前置知识',
    'causes': '导致',
    'belongs_to': '属于',
    'contains': '包含'
  }
  return texts[rel] || rel
}

const nodeColorOf = (node) => {
  if (centralityEnabled.value) {
    return centralityColorOf(node)
  }
  if (communityColorEnabled.value) {
    const cid = nodeCommunityId(node.id)
    if (cid !== null && cid !== undefined) {
      return communityColor(cid)
    }
  }
  return nodeTypeColors[node.nodeType] || '#10b981'
}

const centralityColorOf = (node) => {
  if (!centralityScores.value) return nodeTypeColors[node.nodeType] || '#10b981'
  const score = centralityScores.value[node.id]
  if (score === undefined || score === null) {
    return nodeTypeColors[node.nodeType] || '#10b981'
  }
  const { min, max } = centralityRange.value
  const normalized = max > min ? (score - min) / (max - min) : 1
  const from = [209, 250, 229]
  const to = [6, 95, 70]
  const r = Math.round(from[0] + (to[0] - from[0]) * normalized)
  const g = Math.round(from[1] + (to[1] - from[1]) * normalized)
  const b = Math.round(from[2] + (to[2] - from[2]) * normalized)
  return `rgb(${r}, ${g}, ${b})`
}

const edgeColorOf = (edge) => relationColors[edge.relation] || '#909399'

const nodeSizeOf = (node) => {
  const count = graphNodes.value.length
  const densityFactor = count > 120 ? 0.55 : count > 60 ? 0.75 : 1
  return Math.max(10, Math.min((30 + (node.degree || node.value || 1) * 4) * densityFactor, 64))
}

const tooltipTitleOf = (node) => node.name || String(node.id)

const tooltipFieldsOf = (node) => [
  { label: '类型', value: getNodeTypeText(node.nodeType) },
  { label: '分类', value: node.category || '未分类' },
  { label: '关联数量', value: `${node.degree || 0} 个` }
]

const handleNodeClick = (node) => {
  selectedNodeForFocus.value = node
  showNodeDetail(node)
}

const loadGraphData = async () => {
  try {
    const [nodesRes, edgesRes, communitiesRes] = await Promise.allSettled([
      adminAPI.getGraphNodes({ limit: 150 }),
      adminAPI.getGraphEdges({ limit: 3000 }),
      adminAPI.getGraphCommunities()
    ])

    const nodesResOk = nodesRes.status === 'fulfilled' ? nodesRes.value : { nodes: [] }
    const edgesResOk = edgesRes.status === 'fulfilled' ? edgesRes.value : { edges: [] }
    if (communitiesRes.status === 'fulfilled') {
      communityData.value = communitiesRes.value || null
    }

    const nodes = (nodesResOk.nodes || []).map(node => ({
      id: node.id,
      name: node.title,
      category: node.category,
      nodeType: node.type,
      degree: node.degree,
      value: node.degree || 1
    }))

    allNodes.value = nodes

    // 只保留两端节点都在当前视图内的边，避免无关边拖慢力导向布局
    const nodeIds = new Set(nodes.map(n => n.id))
    const candidateEdges = (edgesResOk.edges || []).filter(
      edge => nodeIds.has(edge.source) && nodeIds.has(edge.target)
    )

    const edges = candidateEdges.map((edge, idx) => ({
      source: edge.source,
      target: edge.target,
      name: edge.relation || '相关',
      lineStyle: {
        color: relationColors[edge.relation] || '#909399'
      }
    }))

    allEdges.value = edges
    applyFilters()

    loadGraphStats()
  } catch (error) {
    console.error('加载图谱数据失败', error)
    ElMessage.error('加载知识图谱失败，请刷新重试')
  }
}

const applyFilters = () => {
  let filteredNodes = allNodes.value
  // 社区筛选：只保留选中社区的节点（含知识节点，若其归属社区）
  if (selectedCommunity.value !== null) {
    const cid = String(selectedCommunity.value)
    filteredNodes = filteredNodes.filter(node => {
      const nodeCid = nodeCommunityId(node.id)
      return nodeCid === cid
    })
    if (!filteredNodes.length) {
      // 知识节点可能不在 node_community 映射（只含实体），退化为原图
      filteredNodes = allNodes.value
    }
  }
  if (selectedCategory.value !== null && selectedCategory.value !== '') {
    const catName = categories.value.find(
      cat => String(cat.id) === String(selectedCategory.value)
    )?.name
    if (catName) {
      // 该分类的知识节点 + 一阶关联实体，保证筛选后图上有内容
      const catIds = new Set(
        allNodes.value
          .filter(node => node.category === catName)
          .map(node => node.id)
      )
      for (const edge of allEdges.value) {
        if (catIds.has(edge.source)) catIds.add(edge.target)
        if (catIds.has(edge.target)) catIds.add(edge.source)
      }
      filteredNodes = allNodes.value.filter(node => catIds.has(node.id))
    }
  }

  const visibleIds = new Set(filteredNodes.map(node => node.id))
  let filteredEdges = allEdges.value.filter(
    edge => visibleIds.has(edge.source) && visibleIds.has(edge.target)
  )
  if (selectedRelation.value) {
    filteredEdges = filteredEdges.filter(edge => edge.name === selectedRelation.value)
  }

  graphNodes.value = filteredNodes
  graphEdges.value = filteredEdges
}

const loadGraphStats = async () => {
  try {
    const res = await adminAPI.getGraphStats()
    graphStats.value = res.stats || { node_count: 0, edge_count: 0, relation_types: {} }
  } catch (error) {
    console.error('加载图谱统计失败')
  }
}

const showNodeDetail = async (nodeData) => {
  selectedNode.value = nodeData
  nodeDialogVisible.value = true
  loadingNeighbors.value = true
  pathTargetId.value = null
  mergeTargetId.value = null
  clearPath()

  if (userStore.isAdmin) {
    try {
      const res = await adminAPI.getRelatedNodes(nodeData.id, { depth: 1 })
      neighbors.value = res.neighbors || []
      nodeSources.value = res.sources || []
    } catch (error) {
      neighbors.value = []
      nodeSources.value = []
    }
  } else {
    // 示例数据
    neighbors.value = [
      { node_id: '1', relation: 'part_of' },
      { node_id: '2', relation: 'uses' },
      { node_id: '5', relation: 'related_to' }
    ]
    nodeSources.value = []
  }

  loadingNeighbors.value = false
}

const loadNodeSources = async (nodeId) => {
  if (!userStore.isAdmin) return
  try {
    const res = await adminAPI.getRelatedNodes(nodeId, { depth: 1 })
    nodeSources.value = res.sources || []
    return nodeSources.value
  } catch (error) {
    nodeSources.value = []
    return []
  }
}

const focusNode = (nodeId) => {
  graphRef.value?.highlightNode(nodeId)
}

const runPathAnalysis = async () => {
  if (!selectedNode.value || !pathTargetId.value) return
  pathLoading.value = true
  try {
    const res = await adminAPI.getGraphPath({
      source: selectedNode.value.id,
      target: pathTargetId.value
    })
    const path = res.nodes || []
    if (!path.length) {
      ElMessage.warning('图中不存在连接路径：这两个节点位于图谱的不同区域')
      pathNodes.value = []
      pathDistance.value = 0
      graphRef.value?.clearPathHighlight()
      return
    }

    // 路径可能包含当前视图未加载的节点/边，补充进视图保证完整显示
    const renderedIds = new Set(graphNodes.value.map(node => node.id))
    const missingNodes = path.filter(node => !renderedIds.has(node.id))
    if (missingNodes.length) {
      graphNodes.value = [
        ...graphNodes.value,
        ...missingNodes.map(node => ({
          id: node.id,
          name: node.name,
          category: node.category || '未分类',
          nodeType: node.type,
          degree: 1,
          value: 1
        }))
      ]
      const edgeKeys = new Set(graphEdges.value.map(edge => `${edge.source}-${edge.target}`))
      const missingEdges = (res.edges || []).filter(
        edge => !edgeKeys.has(`${edge.source}-${edge.target}`)
      ).map(edge => ({
        source: edge.source,
        target: edge.target,
        name: edge.relation || '相关',
        lineStyle: { color: relationColors[edge.relation] || '#909399' }
      }))
      if (missingEdges.length) {
        graphEdges.value = [...graphEdges.value, ...missingEdges]
      }
    }

    pathNodes.value = path
    pathDistance.value = res.distance || 0
    await nextTick()
    graphRef.value?.highlightPath(path.map(node => node.id))
    ElMessage.success(`已找到最短路径（${path.length} 个节点 / ${res.distance || 0} 跳）`)
  } catch (error) {
    console.error('路径分析失败', error)
    ElMessage.error('路径分析失败，请重试')
  } finally {
    pathLoading.value = false
  }
}

const clearPath = () => {
  pathNodes.value = []
  pathDistance.value = 0
  graphRef.value?.clearPathHighlight()
}

const runMerge = async () => {
  if (!selectedNode.value || !mergeTargetId.value) return
  if (mergeTargetId.value === selectedNode.value.id) {
    ElMessage.warning('不能合并到自身')
    return
  }
  mergeLoading.value = true
  const mergedId = mergeTargetId.value
  try {
    const res = await adminAPI.mergeGraphNodes({
      source_id: selectedNode.value.id,
      target_id: mergedId
    })
    ElMessage.success(`合并成功，迁移 ${res.moved_edges} 条关系`)
    nodeDialogVisible.value = false
    clearPath()
    await refreshGraph()
    await nextTick()
    graphRef.value?.highlightNode(mergedId)
  } catch (error) {
    console.error('合并失败', error)
  } finally {
    mergeLoading.value = false
  }
}

const runDeduplicate = async () => {
  deduplicating.value = true
  try {
    const res = await adminAPI.deduplicateGraph()
    ElMessage.success(
      `合并完成：${res.groups} 组同名实体，移除 ${res.removed_nodes} 个重复节点，迁移 ${res.merged_edges} 条关系`
    )
    isSubgraphView.value = false
    await loadGraphData()
  } catch (error) {
    console.error('合并同名实体失败', error)
  } finally {
    deduplicating.value = false
  }
}

const handleCentralityToggle = (enabled) => {
  if (enabled) {
    loadCentralityScores()
  } else {
    renderTick.value++
  }
}

const loadCentralityScores = async () => {
  try {
    const res = await adminAPI.getGraphCentrality({ metric: centralityMetric.value })
    centralityScores.value = res.scores || {}
    const values = Object.values(centralityScores.value)
    centralityRange.value = {
      min: values.length ? Math.min(...values) : 0,
      max: values.length ? Math.max(...values) : 1
    }
    renderTick.value++
  } catch (error) {
    console.error('加载中心性分数失败', error)
  }
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
  graphRef.value?.highlightNode(node.id)
  ElMessage.success(`已聚焦到节点: ${node.name}`)
}

const focusSelectedNode = () => {
  if (selectedNodeForFocus.value) {
    focusToNode(selectedNodeForFocus.value)
  }
}

const goToKnowledge = (id) => {
  nodeDialogVisible.value = false
  router.push(`/knowledge/${id}`)
}

const viewKnowledge = () => {
  if (!selectedNode.value) return
  const nodeId = selectedNode.value.id
  // 知识节点直接跳转知识详情
  if (selectedNode.value.nodeType === 'knowledge') {
    goToKnowledge(nodeId)
    return
  }
  // 实体节点：跳转到来源文档（可能有多个，取第一个；LLM 图谱实体为全局共享节点，无 source_item）
  if (nodeSources.value.length) {
    goToKnowledge(nodeSources.value[0].id)
    return
  }
  // 来源未加载完成时，按需查询一次（避免异步竞态导致空跳转）
  loadNodeSources(nodeId).then(() => {
    if (nodeSources.value.length) {
      goToKnowledge(nodeSources.value[0].id)
    } else {
      ElMessage.error('无法跳转：该节点没有关联的知识条目')
    }
  })
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

    graphNodes.value = subgraphNodes
    graphEdges.value = subgraphEdges

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
  applyFilters()
}

const filterByRelation = (rel) => {
  selectedRelation.value = selectedRelation.value === rel ? null : rel
  applyFilters()
}

const handleCommunityToggle = () => {
  // 社区着色与中心性着色互斥（中心性优先级更高，关闭中心性才生效）
  if (communityColorEnabled.value) {
    centralityEnabled.value = false
  }
  renderTick.value++
}

const filterByCommunity = (communityId) => {
  if (selectedCommunity.value === communityId) {
    selectedCommunity.value = null
    applyFilters()
    return
  }
  selectedCommunity.value = communityId
  applyFilters()
}

const handleCommunityClick = (item) => {
  // 点击社区：筛选子图 + 打开摘要面板（未生成时自动生成）
  filterByCommunity(item.id)
  selectedCommunitySummaryId.value = item.id
  selectedCommunitySummarySample.value = item.sample || []
  summaryPanelVisible.value = true
}

const handleBatchSummarize = async () => {
  communityBatchLoading.value = true
  try {
    const res = await adminAPI.generateCommunitySummaries({ limit: 10, force: false })
    const { generated, cached, failed } = res
    ElMessage.success(
      `批量预生成完成：新增 ${generated} 个，复用缓存 ${cached} 个${failed ? `，失败 ${failed} 个` : ''}`
    )
  } catch (error) {
    console.error('批量生成社区摘要失败', error)
    ElMessage.error('批量生成失败，请稍后重试')
  } finally {
    communityBatchLoading.value = false
  }
}

const exportGraphImage = () => {
  graphRef.value?.exportPng()
}

const zoomIn = () => {
  graphRef.value?.zoomIn()
}

const zoomOut = () => {
  graphRef.value?.zoomOut()
}

const resetZoom = () => {
  graphRef.value?.resetZoom()
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
  loadCategories()
  loadGraphData()
})
</script>

<style lang="scss" scoped>
.graph-page {
  min-height: 100vh;
  background: #f6f8fa;
}

/* ==================== 页头 ==================== */
.page-header {
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
  color: #c9d1d9;
  padding: 32px 0 52px;
}

.header-orb {
  position: absolute;
  width: 460px;
  height: 460px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(46, 164, 79, 0.16), transparent 65%);
  top: -190px;
  right: -120px;
  animation: kbBreathe 7s ease-in-out infinite;
}

@keyframes kbBreathe {
  0%,
  100% {
    opacity: 0.7;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.12);
  }
}

.header-grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(240, 246, 252, 0.05) 1px, transparent 1px);
  background-size: 26px 26px;
  animation: kbDrift 36s linear infinite;
  pointer-events: none;
}

@keyframes kbDrift {
  to {
    transform: translateY(26px);
  }
}

.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  position: relative;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: 999px;
  border: 1px solid rgba(240, 246, 252, 0.22);
  background: rgba(255, 255, 255, 0.06);
  color: #c9d1d9;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  margin-bottom: 24px;
  opacity: 0;
  transform: translateY(14px);
  animation: kbUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  transition:
    background 0.25s,
    border-color 0.25s,
    color 0.25s;
}

.back-btn svg {
  width: 14px;
  height: 14px;
  transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.back-btn:hover {
  background: rgba(46, 164, 79, 0.14);
  border-color: rgba(46, 164, 79, 0.45);
  color: #fff;
}

.back-btn:hover svg {
  transform: translateX(-3px);
}

.header-content {
  position: relative;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #7ee2a8;
  background: rgba(46, 164, 79, 0.1);
  border: 1px solid rgba(46, 164, 79, 0.35);
  padding: 5px 14px;
  border-radius: 999px;
  margin-bottom: 16px;
  opacity: 0;
  transform: translateY(18px);
  animation: kbUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) 0.05s forwards;
}

.badge-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #2ea44f;
  animation: kbBadgePing 2.2s ease-out infinite;
}

@keyframes kbBadgePing {
  0% {
    box-shadow: 0 0 0 0 rgba(46, 164, 79, 0.55);
  }
  70%,
  100% {
    box-shadow: 0 0 0 7px rgba(46, 164, 79, 0);
  }
}

.header-title {
  margin: 0 0 10px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.3;
  color: #f0f6fc;
  letter-spacing: -0.01em;
  opacity: 0;
  transform: translateY(24px);
  animation: kbUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) 0.15s forwards;
}

@keyframes kbUp {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.header-desc {
  margin: 0;
  font-size: 15px;
  line-height: 1.8;
  color: #8b949e;
  max-width: 52ch;
  opacity: 0;
  transform: translateY(20px);
  animation: kbUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) 0.3s forwards;
}

/* ==================== 主体 ==================== */
.graph-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  display: flex;
  gap: 24px;
}

.graph-sidebar {
  width: 280px;
  flex-shrink: 0;

  .sidebar-section {
    background: #fff;
    border: 1px solid #d8dee4;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
    transition: box-shadow 0.3s;

    &:hover {
      box-shadow: 0 8px 24px rgba(22, 27, 34, 0.06);
    }

    h3 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 14px;
      font-size: 14px;
      font-weight: 600;
      color: #24292f;
    }

    h3::before {
      content: '';
      width: 4px;
      height: 14px;
      border-radius: 2px;
      background: #2ea44f;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;

      .stat-item {
        text-align: center;
        padding: 8px 0;
        border-radius: 8px;
        transition: background 0.25s;

        &:hover {
          background: rgba(46, 164, 79, 0.06);
        }

        .stat-value {
          display: block;
          font-size: 24px;
          font-weight: 600;
          color: #2ea44f;
          font-variant-numeric: tabular-nums;
        }

        .stat-label {
          font-size: 12px;
          color: #8c959f;
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
        gap: 8px;
        padding: 8px 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.2s;

        &:hover {
          background: rgba(46, 164, 79, 0.08);
        }

        .result-name {
          font-size: 13px;
          color: #24292f;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    .node-type-legend {
      .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 0;
        transition: transform 0.2s;

        &:hover {
          transform: translateX(3px);
        }

        .legend-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          transition: transform 0.2s;
        }

        &:hover .legend-dot {
          transform: scale(1.15);
        }

        .legend-label {
          font-size: 13px;
          color: #57606a;
        }
      }
    }

    .relation-list {
      .relation-item {
        position: relative;
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 9px 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.25s, color 0.25s;

        &:hover {
          background: rgba(46, 164, 79, 0.08);
        }

        &.active {
          background: rgba(46, 164, 79, 0.12);
        }

        .relation-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          flex-shrink: 0;
          transition: transform 0.25s;
        }

        &:hover .relation-dot,
        &.active .relation-dot {
          transform: scale(1.2);
        }

        .relation-name {
          flex: 1;
          font-size: 13px;
          color: #57606a;
          transition: color 0.25s;
        }

        &:hover .relation-name,
        &.active .relation-name {
          color: #2c974b;
          font-weight: 500;
        }

        .relation-count {
          font-size: 12px;
          color: #2ea44f;
          font-weight: 600;
          font-variant-numeric: tabular-nums;
          background: rgba(46, 164, 79, 0.08);
          border-radius: 999px;
          padding: 0 8px;
          line-height: 18px;
        }
      }
    }
  }
}

.graph-main {
  flex: 1;
  min-width: 0;

  .graph-toolbar {
    background: #fff;
    border: 1px solid #d8dee4;
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    transition: box-shadow 0.3s;

    &:hover {
      box-shadow: 0 8px 24px rgba(22, 27, 34, 0.06);
    }

    .toolbar-search {
      width: 200px;
    }

    .toolbar-left,
    .toolbar-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  }

  .graph-chart-wrapper {
    --fgc-height: 600px;
    position: relative;
    background: #fff;
    border: 1px solid #d8dee4;
    border-radius: 12px;
    transition: box-shadow 0.3s;
    overflow: hidden;

    &:hover {
      box-shadow: 0 8px 24px rgba(22, 27, 34, 0.06);
    }
  }
}

.node-detail {
  h3 {
    margin: 0 0 16px;
    color: #24292f;
  }

  .detail-info {
    p {
      margin: 8px 0;
      font-size: 14px;
      color: #57606a;

      strong {
        color: #24292f;
      }
    }
  }

  h4 {
    margin: 16px 0 12px;
    font-size: 14px;
    color: #57606a;
  }

  .neighbors-list {
    max-height: 200px;
    overflow-y: auto;

    .neighbor-item {
      display: flex;
      justify-content: space-between;
      padding: 8px 12px;
      background: #f6f8fa;
      border: 1px solid #e6e8eb;
      border-radius: 8px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: background 0.25s, border-color 0.25s;

      &:hover {
        background: rgba(46, 164, 79, 0.08);
        border-color: rgba(46, 164, 79, 0.3);
      }

      .neighbor-id {
        color: #2ea44f;
        font-size: 13px;
      }

      .neighbor-rel {
        color: #8c959f;
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

.path-analyzer,
.merge-control {
  display: flex;
  align-items: center;
  gap: 8px;

  .path-target-select {
    flex: 1;
    min-width: 0;
  }
}

.path-result {
  margin-top: 12px;

  .path-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: #ea580c;
    margin-bottom: 8px;
  }

  .path-list {
    max-height: 180px;
    overflow-y: auto;

    .path-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 7px 10px;
      border-radius: 8px;
      cursor: pointer;
      transition: background 0.2s;

      &:hover {
        background: rgba(249, 115, 22, 0.08);
      }

      .path-index {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #f97316;
        color: #fff;
        font-size: 11px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .path-name {
        flex: 1;
        font-size: 13px;
        color: #24292f;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .path-type {
        font-size: 12px;
        color: #8c959f;
      }
    }
  }
}

.merge-section {
  .merge-hint {
    margin: 0 0 10px;
    font-size: 12px;
    line-height: 1.6;
    color: #8c959f;
  }
}

.category-source {
  font-size: 12px;
  color: #8c959f;
}

.detail-sources {
  .sources-list {
    max-height: 180px;
    overflow-y: auto;

    .source-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      background: #f6f8fa;
      border: 1px solid #e6e8eb;
      border-radius: 8px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: background 0.25s, border-color 0.25s;

      &:hover {
        background: rgba(46, 164, 79, 0.08);
        border-color: rgba(46, 164, 79, 0.3);
      }

      .source-title {
        flex: 1;
        font-size: 13px;
        color: #24292f;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .source-cat {
        font-size: 12px;
        color: #8c959f;
        flex-shrink: 0;
      }
    }
  }
}

.dedup-hint {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.6;
  color: #8c959f;
}

.centrality-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.community-control {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;

  &__label {
    font-size: 13px;
    color: #606266;
  }
}

.community-batch-btn {
  width: 100%;
  margin-bottom: 10px;
}

.community-list {
  max-height: 260px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;

  .community-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    color: #606266;
    transition: background 0.2s ease;

    &:hover {
      background: #f5f7fa;
    }

    &.active {
      background: #eff6ff;
      border: 1px solid #2563eb;
      color: #1d4ed8;
    }
  }

  .community-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .community-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .community-sample {
    color: #a0a6ad;
    font-size: 11px;
  }

  .community-size {
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
    color: #8c959f;
  }
}

.centrality-legend {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;

  .legend-text {
    font-size: 12px;
    color: #8c959f;
  }

  .legend-gradient {
    flex: 1;
    height: 8px;
    border-radius: 999px;
    background: linear-gradient(to right, #d1fae5, #065f46);
  }
}

/* ==================== 响应式 ==================== */
@media (max-width: 1024px) {
  .graph-container {
    gap: 16px;
  }

  .graph-sidebar {
    width: 220px;
  }
}

@media (max-width: 768px) {
  .page-header {
    padding: 24px 0 36px;
  }

  .header-title {
    font-size: 24px;
  }

  .graph-container {
    flex-direction: column;
    padding: 16px 12px 40px;
  }

  .graph-sidebar {
    width: 100%;
  }

  .graph-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .toolbar-search {
    width: 100%;
  }

  .graph-chart-wrapper {
    --fgc-height: 420px;
  }
}
</style>
