<template>
  <section class="chart-panel"><header class="chart-head"><div class="chart-title"><BaseIcon name="chart" :size="17" /><strong>Token 消耗趋势</strong><span>总 Token：{{ formatInteger(analytics?.summary?.total_tokens || 0) }}</span></div><div class="chart-toggle"><button :class="{ active: chartType === 'bar' }" @click="chartType = 'bar'"><BaseIcon name="chart" :size="14" />柱状图</button><button :class="{ active: chartType === 'area' }" @click="chartType = 'area'"><BaseIcon name="area" :size="14" />面积图</button></div></header><div v-if="loading" class="chart-loading">正在加载图表...</div><div v-else-if="!analytics?.trend?.length" class="chart-empty">当前时间范围暂无调用数据</div><div v-else ref="chartRef" class="chart" /></section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { BaseIcon } from '@/components/ui'
import { formatInteger } from '@/features/security/llm/format'

const props = defineProps({ analytics: { type: Object, default: () => ({}) }, loading: { type: Boolean, default: false } })
const chartRef = ref(null)
const chartType = ref('bar')
let chart
const colors = ['#38bdf8', '#818cf8', '#fb923c']
const render = async () => { await nextTick(); if (!chartRef.value) return; if (!chart) chart = echarts.init(chartRef.value); const trend = props.analytics?.trend || []; const buckets = [...new Set(trend.map((item) => item.bucket))]; const models = [...new Set(trend.map((item) => item.model || '未知模型'))]; chart.setOption({ animationDuration: 900, animationDurationUpdate: 700, animationEasing: 'cubicOut', color: colors, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { bottom: 4, data: models, textStyle: { color: '#475569', fontSize: 12 } }, grid: { top: 18, left: 48, right: 18, bottom: 52 }, xAxis: { type: 'category', data: buckets, axisLabel: { color: '#94a3b8', fontSize: 11 }, axisLine: { lineStyle: { color: '#e2e8f0' } }, axisTick: { show: false } }, yAxis: { type: 'value', axisLabel: { color: '#94a3b8', fontSize: 11 }, splitLine: { lineStyle: { color: '#eef2f7' } } }, series: models.map((model, index) => ({ name: model, type: 'bar', stack: 'tokens', barMaxWidth: 28, smooth: chartType.value === 'area', areaStyle: chartType.value === 'area' ? { opacity: .22 } : undefined, data: buckets.map((bucket) => trend.find((item) => item.bucket === bucket && (item.model || '未知模型') === model)?.tokens || 0) })) }, true) }
watch(() => [props.analytics, props.loading, chartType.value], render, { deep: true })
const handleResize = () => chart?.resize()
onMounted(() => { render(); window.addEventListener('resize', handleResize) })
onBeforeUnmount(() => { window.removeEventListener('resize', handleResize); chart?.dispose(); chart = null })
</script>

<style scoped lang="scss">
.chart-panel{margin-bottom:20px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;background:#fff}.chart-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:13px 16px;border-bottom:1px solid #e2e8f0}.chart-title{display:flex;align-items:center;gap:9px;color:#0f172a;font-size:15px}.chart-title :deep(.ui-icon){color:#2563eb}.chart-title span{color:#475569;font-size:12px;font-weight:400}.chart-toggle{display:flex;gap:3px;padding:3px;border:1px solid #e2e8f0;border-radius:6px}.chart-toggle button{height:28px;display:inline-flex;align-items:center;gap:5px;padding:0 9px;border:0;border-radius:4px;background:transparent;color:#475569;font-size:12px}.chart-toggle button.active{background:#dbeafe;color:#2563eb;font-weight:600}.chart{height:320px;width:100%}.chart-loading,.chart-empty{height:320px;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:13px}@media(max-width:640px){.chart-head{align-items:flex-start;flex-direction:column}.chart{height:270px}}
</style>
