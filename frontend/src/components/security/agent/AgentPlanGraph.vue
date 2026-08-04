<template>
  <section class="plan-card">
    <div class="card-head">
      <h2>计划 DAG</h2>
      <div class="card-head__side">
        <el-tag v-if="plan" :type="plannerMeta.tagType" size="small">{{ plannerMeta.label }}</el-tag>
        <span v-if="plan" class="plan-version">v{{ plan.plan_version }}</span>
      </div>
    </div>
    <el-empty v-if="!loading && !plan" description="计划尚未生成" :image-size="64" />
    <div v-else ref="chartRef" class="plan-chart" />
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { plannerSourceLabel } from '@/features/security/agent/statusMeta'

const props = defineProps({
  plan: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const chartRef = ref(null)
let chart = null

const nodeStatusColor = {
  pending: '#c2ccd9',
  ready: '#94a3b8',
  running: '#2563eb',
  succeeded: '#16a34a',
  failed: '#dc2626',
  skipped: '#94a3b8',
  blocked: '#d97706',
  canceled: '#94a3b8',
  superseded: '#94a3b8'
}

const plannerMeta = computed(() => plannerSourceLabel(props.plan?.planner_source))

const nodeTitles = {
  inventory: '清点快照',
  baseline_scan: '基线扫描',
  coverage_analysis: '覆盖分析',
  risk_ranking: '风险排序',
  report: '运行摘要'
}

function buildOption() {
  const plan = props.plan
  if (!plan || !Array.isArray(plan.nodes)) return {}
  const nodes = plan.nodes.map((node) => ({
    id: node.node_key,
    name: nodeTitles[node.node_key] || node.title || node.node_key,
    category: 0,
    symbolSize: node.status === 'running' ? 34 : 26,
    itemStyle: { color: nodeStatusColor[node.status] || '#94a3b8' },
    label: { show: true, fontSize: 11, color: '#334155' }
  }))
  const edges = (plan.edges || []).map((edge) => ({
    source: edge.from_node,
    target: edge.to_node,
    lineStyle: { color: '#cbd5e1', width: 1.5, curveness: 0.12 }
  }))
  return {
    animationDurationUpdate: 300,
    animationEasingUpdate: 'quinticInOut',
    tooltip: {
      formatter: (params) => {
        const node = (plan.nodes || []).find((item) => item.node_key === params.data?.id)
        if (!node) return params.data?.name || ''
        return `${nodeTitles[node.node_key] || node.title}<br/>状态：${node.status}<br/>${node.description || ''}`
      }
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        draggable: true,
        data: nodes,
        links: edges,
        label: { show: true, position: 'bottom' },
        lineStyle: { color: '#cbd5e1' },
        emphasis: { focus: 'adjacency' }
      }
    ]
  }
}

function render() {
  if (!chart || !chartRef.value) return
  chart.setOption(buildOption(), true)
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  render()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})

watch(() => props.plan, render, { deep: true })
</script>

<style scoped lang="scss">
.plan-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head__side { display: flex; align-items: center; gap: 8px; }
.plan-version { color: #8494a8; font-size: 12px; }
.plan-chart { height: 240px; }
</style>
