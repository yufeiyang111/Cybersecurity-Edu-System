<template>
  <section class="model-chart-panel">
    <header class="model-chart-head">
      <div class="model-chart-title">
        <BaseIcon name="chart" :size="17" />
        <strong>模型调用图</strong>
        <span>{{ modeLabel }}</span>
      </div>
    </header>
    <div v-if="loading" class="model-chart-loading">正在加载图表...</div>
    <div v-else-if="!hasData" class="model-chart-empty">当前时间范围暂无调用数据</div>
    <div v-else ref="chartRef" class="model-chart" />
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { BaseIcon } from '@/components/ui'
import { formatInteger } from '@/features/security/llm/format'

const props = defineProps({
  analytics: { type: Object, default: () => ({}) },
  mode: { type: String, default: 'trend' },
  loading: { type: Boolean, default: false }
})

const chartRef = ref(null)
let chart

const colors = ['#38bdf8', '#818cf8', '#fb923c', '#34d399', '#fbbf24']

const modeLabel = computed(() => ({
  trend: '调用趋势',
  distribution: '调用次数分布',
  ranking: '调用次数排行'
}[props.mode] || '调用趋势'))

const hasData = computed(() => {
  const analytics = props.analytics || {}
  if (props.mode === 'trend') return (analytics.trend || []).length > 0
  return (analytics.models || []).length > 0
})

const renderTrend = (chart, trend) => {
  const buckets = [...new Set(trend.map((item) => item.bucket))]
  const models = [...new Set(trend.map((item) => item.model || '未知模型'))]
  chart.setOption(
    {
      animationDuration: 900,
      animationDurationUpdate: 700,
      animationEasing: 'cubicOut',
      color: colors,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' }
      },
      legend: {
        bottom: 4,
        data: models,
        textStyle: { color: '#475569', fontSize: 12 }
      },
      grid: { top: 18, left: 48, right: 18, bottom: 52 },
      xAxis: {
        type: 'category',
        data: buckets,
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        splitLine: { lineStyle: { color: '#eef2f7' } }
      },
      series: models.map((model) => ({
        name: model,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.12 },
        data: buckets.map((bucket) => trend.find((item) => item.bucket === bucket && (item.model || '未知模型') === model)?.calls || 0)
      }))
    },
    true
  )
}

const renderDistribution = (chart, models) => {
  const rows = models.slice(0, 8).map((item) => ({
    name: item.model || '未知模型',
    value: Number(item.calls) || 0
  }))
  chart.setOption(
    {
      animationDuration: 900,
      color: colors,
      tooltip: {
        trigger: 'item',
        formatter: '{b}<br/>调用 {c} 次（{d}%）'
      },
      legend: {
        bottom: 4,
        textStyle: { color: '#475569', fontSize: 12 }
      },
      series: [
        {
          name: '模型调用次数',
          type: 'pie',
          radius: ['38%', '68%'],
          center: ['50%', '46%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            color: '#475569',
            fontSize: 12,
            formatter: '{b}\n{d}%'
          },
          labelLine: {
            length: 12,
            length2: 8
          },
          data: rows
        }
      ]
    },
    true
  )
}

const renderRanking = (chart, models) => {
  const rows = [...models]
    .sort((a, b) => (Number(b.calls) || 0) - (Number(a.calls) || 0))
    .slice(0, 10)
    .reverse()
  chart.setOption(
    {
      animationDuration: 900,
      color: ['#2563eb'],
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params) => {
          const item = params[0]
          return `${item.name}<br/>调用 ${formatInteger(item.value)} 次`
        }
      },
      grid: { top: 18, left: 8, right: 56, bottom: 8, containLabel: true },
      xAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        splitLine: { lineStyle: { color: '#eef2f7' } }
      },
      yAxis: {
        type: 'category',
        data: rows.map((item) => item.model || '未知模型'),
        axisLabel: { color: '#475569', fontSize: 11 },
        axisLine: { show: false },
        axisTick: { show: false }
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 18,
          itemStyle: { borderRadius: [0, 4, 4, 0] },
          data: rows.map((item) => Number(item.calls) || 0)
        }
      ]
    },
    true
  )
}

const render = async () => {
  await nextTick()
  if (!chartRef.value) return
  if (!chart || chart.getDom() !== chartRef.value) {
    chart?.dispose()
    chart = echarts.init(chartRef.value)
  }
  const analytics = props.analytics || {}
  if (props.mode === 'trend') {
    renderTrend(chart, analytics.trend || [])
  } else if (props.mode === 'distribution') {
    renderDistribution(chart, analytics.models || [])
  } else {
    renderRanking(chart, analytics.models || [])
  }
}

watch(
  () => [props.analytics, props.loading, props.mode],
  render,
  { deep: true }
)

const handleResize = () => chart?.resize()

onMounted(() => {
  render()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped lang="scss">
.model-chart-panel {
  margin-bottom: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.model-chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 13px 16px;
  border-bottom: 1px solid #e2e8f0;
}

.model-chart-title {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #0f172a;
  font-size: 15px;
}

.model-chart-title :deep(.ui-icon) {
  color: #2563eb;
}

.model-chart-title span {
  color: #475569;
  font-size: 12px;
  font-weight: 400;
}

.model-chart {
  height: 320px;
  width: 100%;
}

.model-chart-loading,
.model-chart-empty {
  height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
}

@media (max-width: 640px) {
  .model-chart {
    height: 270px;
  }
}
</style>
