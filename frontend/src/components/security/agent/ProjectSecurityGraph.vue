<template>
  <section class="graph-card">
    <div class="card-head">
      <h2>项目安全图</h2>
      <el-button
        v-if="!hasGraph"
        size="small"
        :loading="building"
        @click="handleBuild"
      >
        建图
      </el-button>
    </div>
    <div v-if="loading && !summary" class="graph-card__empty">图数据加载中…</div>
    <template v-else-if="hasGraph">
      <div class="graph-stats">
        <span>{{ summary.node_count }} 节点</span>
        <span>{{ summary.edge_count }} 边</span>
        <span>{{ summary.file_count }} 文件</span>
      </div>
      <div v-if="summary.node_types" class="graph-types">
        <el-tag
          v-for="(count, type) in summary.node_types"
          :key="type"
          size="small"
          :type="typeTag(type)"
        >
          {{ typeLabel(type) }} {{ count }}
        </el-tag>
      </div>
      <div ref="chartRef" class="graph-chart" />
      <p v-if="errorMessage" class="graph-card__error">{{ errorMessage }}</p>
    </template>
    <div v-else class="graph-card__empty">
      <p v-if="errorMessage">{{ errorMessage }}</p>
      <p v-else>运行 map_repository 工具或点击"建图"生成项目安全图</p>
    </div>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { useProjectSecurityGraph } from '@/composables/security/useProjectSecurityGraph'

const props = defineProps({
  runId: { type: Number, default: null }
})

const emit = defineEmits(['select-node', 'error'])

const {
  summary,
  loading,
  building,
  errorMessage,
  hasGraph,
  loadGraph,
  buildGraph,
  loadNeighbors,
  toEChartsGraph,
  nodeMeta
} = useProjectSecurityGraph(() => props.runId)

const chartRef = ref(null)
let chart = null
let currentGraph = null

const TYPE_TAG = {
  route: 'primary',
  middleware: 'warning',
  service: 'success',
  repository: 'warning',
  model: 'success',
  function: 'info',
  dependency: 'warning',
  external_call: 'danger',
  file: 'info'
}

function typeTag(type) {
  return TYPE_TAG[type] || 'info'
}

function typeLabel(type) {
  return nodeMeta(type).label
}

async function handleBuild() {
  const response = await buildGraph()
  if (!response) emit('error', errorMessage.value || '建图失败')
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const data = toEChartsGraph()
  currentGraph = data
  const categories = Object.entries(nodeMeta).map(([key, meta]) => ({
    name: key,
    itemStyle: { color: meta.color }
  }))
  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'edge') {
          return [
            `${params.data.sourceLabel || ''} → ${params.data.targetLabel || ''}`,
            `关系：${params.data.label}`,
            `置信度：${confidenceLabel(params.data.confidence)}（${params.data.extractor}）`
          ].join('<br/>')
        }
        return `${params.data.name}<br/>类型：${typeLabel(params.data.nodeType)}`
      }
    },
    legend: { show: false },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: data.seriesNodes,
        edges: data.seriesEdges.map((edge) => ({
          ...edge,
          lineStyle: { color: edge.confidence === 'exact' ? '#94a3b8' : '#cbd5e1', width: 1 }
        })),
        categories,
        force: { repulsion: 160, edgeLength: 90 },
        roam: true,
        draggable: true,
        emphasis: { focus: 'adjacency' }
      }
    ]
  })
  chart.off('click')
  chart.on('click', async (params) => {
    if (params.dataType !== 'node') return
    const nodeId = params.data.id
    emit('select-node', { id: nodeId, label: params.data.name, nodeType: params.data.nodeType, filePath: params.data.filePath })
    await loadNeighbors(nodeId, { limit: 20, offset: 0 })
    renderChart()
  })
}

function confidenceLabel(level) {
  return level === 'exact' ? '精确' : level === 'heuristic' ? '启发式' : '部分'
}

watch(() => props.runId, () => {
  if (props.runId) loadGraph()
})

watch(summary, (value) => {
  if (value) renderChart()
})

onMounted(() => {
  if (props.runId) loadGraph()
})

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
})
</script>

<style scoped lang="scss">
.graph-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.graph-card__empty {
  color: #8494a8;
  font-size: 12.5px;
  padding: 8px 0;
}
.graph-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #52627a;
  font-size: 12.5px;
  margin-bottom: 8px;
}
.graph-types {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.graph-chart {
  width: 100%;
  height: 300px;
}
.graph-card__error { color: #b91c1c; font-size: 12.5px; margin: 8px 0 0; }
</style>
