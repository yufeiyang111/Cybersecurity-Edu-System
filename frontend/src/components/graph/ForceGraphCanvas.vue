<template>
  <div ref="containerRef" class="fgc-root">
    <canvas
      ref="canvasRef"
      class="fgc-canvas"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerLeave"
      @wheel.prevent="onWheel"
    ></canvas>
    <canvas
      v-if="showMinimap"
      ref="minimapRef"
      class="fgc-minimap"
      :width="minimapWidth * dpr"
      :height="minimapHeight * dpr"
      @pointerdown="onMinimapPointerDown"
    ></canvas>
    <div
      v-if="tooltipVisible"
      class="fgc-tooltip"
      :style="{ left: `${tooltipX}px`, top: `${tooltipY}px` }"
    >
      <div class="fgc-tooltip__title">{{ tooltipTitle }}</div>
      <div v-for="field in tooltipFields" :key="field.label" class="fgc-tooltip__row">
        <span>{{ field.label }}</span>
        <strong>{{ field.value }}</strong>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import {
  DEFAULT_PARAMS,
  createSimNodes,
  createSimEdges,
  stepSim,
  computeBBox
} from './forceLayout'

const props = defineProps({
  nodes: {
    type: Array,
    default: () => []
  },
  edges: {
    type: Array,
    default: () => []
  },
  nodeColor: {
    type: Function,
    default: () => '#10b981'
  },
  edgeColor: {
    type: Function,
    default: () => '#909399'
  },
  nodeSize: {
    type: Function,
    default: (node) => 30 + (node.degree || node.value || 1) * 4
  },
  tooltipTitle: {
    type: Function,
    default: null
  },
  tooltipFields: {
    type: Function,
    default: null
  },
  showTooltip: {
    type: Boolean,
    default: true
  },
  showMinimap: {
    type: Boolean,
    default: true
  },
  minimapWidth: {
    type: Number,
    default: 150
  },
  minimapHeight: {
    type: Number,
    default: 100
  }
})

const emit = defineEmits(['node-click'])

const containerRef = ref(null)
const canvasRef = ref(null)
const minimapRef = ref(null)

const dpr = ref(Math.min(window.devicePixelRatio || 1, 2))
const tooltipVisible = ref(false)
const tooltipTitle = ref('')
const tooltipFields = ref([])
const tooltipX = ref(0)
const tooltipY = ref(0)

let width = 0
let height = 0
let ctx = null
let miniCtx = null
let simNodes = []
let simEdges = []
let view = { x: 0, y: 0, scale: 1 }
let rafId = 0
let viewTweenRaf = 0
let simTicks = 0
let simAlpha = 1
let fitted = false
let hoveredNodeId = null
let highlightedNodeId = null
let pulseStart = 0
let pressedNode = null
let dragNode = null
let panning = null
let downX = 0
let downY = 0
let moveThreshold = 5
let resizeObserver = null
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)

const resize = () => {
  const rect = containerRef.value?.getBoundingClientRect()
  if (!rect) return
  width = rect.width
  height = rect.height
  dpr.value = Math.min(window.devicePixelRatio || 1, 2)
  canvasRef.value.width = Math.round(width * dpr.value)
  canvasRef.value.height = Math.round(height * dpr.value)
  ctx = canvasRef.value.getContext('2d')
  if (minimapRef.value) {
    miniCtx = minimapRef.value.getContext('2d')
  }
  draw()
}

const hitTestNode = (sx, sy) => {
  const wx = (sx - view.x) / view.scale
  const wy = (sy - view.y) / view.scale
  const minHitRadius = 14 / view.scale
  for (let i = simNodes.length - 1; i >= 0; i--) {
    const node = simNodes[i]
    const dx = wx - node.x
    const dy = wy - node.y
    const r = Math.max(node.size / 2 + 6, minHitRadius)
    if (dx * dx + dy * dy <= r * r) return node
  }
  return null
}

const buildAdjacency = (focusId) => {
  const set = new Set([focusId])
  for (const edge of simEdges) {
    const a = simNodes[edge.sourceIdx]
    const b = simNodes[edge.targetIdx]
    if (a.id === focusId) set.add(b.id)
    else if (b.id === focusId) set.add(a.id)
  }
  return set
}

const drawEdges = () => {
  const focusId = hoveredNodeId || highlightedNodeId
  const focusSet = focusId ? buildAdjacency(focusId) : null
  ctx.lineWidth = 1.5
  for (const edge of simEdges) {
    const a = simNodes[edge.sourceIdx]
    const b = simNodes[edge.targetIdx]
    if (!isFinite(a.x) || !isFinite(a.y) || !isFinite(b.x) || !isFinite(b.y)) continue
    let alpha = 0.4
    if (focusSet) {
      alpha = focusSet.has(a.id) && focusSet.has(b.id) ? 0.85 : 0.08
    }
    ctx.strokeStyle = props.edgeColor(edge.raw)
    ctx.globalAlpha = alpha
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    ctx.stroke()
  }
  ctx.globalAlpha = 1
}

const drawNodes = () => {
  const focusId = hoveredNodeId || highlightedNodeId
  const focusSet = focusId ? buildAdjacency(focusId) : null
  const showLabels = simNodes.length <= 40 || view.scale > 0.8
  const labelFontSize = 13 / view.scale

  for (const node of simNodes) {
    if (!isFinite(node.x) || !isFinite(node.y)) continue
    const inFocus = !focusSet || node.id === focusId || focusSet.has(node.id)
    ctx.globalAlpha = inFocus ? 1 : 0.15
    ctx.fillStyle = props.nodeColor(node.raw)
    ctx.beginPath()
    ctx.arc(node.x, node.y, node.size / 2, 0, Math.PI * 2)
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = '#ffffff'
    ctx.stroke()

    if (showLabels || node.id === focusId) {
      ctx.globalAlpha = inFocus ? 0.95 : 0.15
      ctx.fillStyle = node.id === focusId ? '#2c974b' : '#24292f'
      ctx.font = `600 ${labelFontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(node.label, node.x, node.y + node.size / 2 + labelFontSize * 0.9)
    }
  }
  ctx.globalAlpha = 1

  if (highlightedNodeId) {
    const pulseNode = simNodes.find(node => node.id === highlightedNodeId)
    if (pulseNode) {
      const elapsed = performance.now() - pulseStart
      if (elapsed < 1200) {
        const t = elapsed / 1200
        ctx.strokeStyle = '#2ea44f'
        ctx.globalAlpha = (1 - t) * 0.7
        ctx.lineWidth = 3
        ctx.beginPath()
        ctx.arc(pulseNode.x, pulseNode.y, pulseNode.size / 2 + 6 + t * 30, 0, Math.PI * 2)
        ctx.stroke()
        ctx.globalAlpha = 1
        rafId = requestAnimationFrame(draw)
      } else {
        highlightedNodeId = null
      }
    }
  }
}

const drawMinimap = () => {
  if (!miniCtx || !simNodes.length) return
  const mw = props.minimapWidth
  const mh = props.minimapHeight
  const bbox = computeBBox(simNodes)
  const scale = Math.min((mw - 10) / bbox.w, (mh - 10) / bbox.h)
  const ox = (mw - bbox.w * scale) / 2 - bbox.minX * scale
  const oy = (mh - bbox.h * scale) / 2 - bbox.minY * scale

  miniCtx.setTransform(dpr.value, 0, 0, dpr.value, 0, 0)
  miniCtx.clearRect(0, 0, mw, mh)

  miniCtx.strokeStyle = 'rgba(22, 27, 34, 0.18)'
  miniCtx.lineWidth = 1
  miniCtx.beginPath()
  for (const edge of simEdges) {
    const a = simNodes[edge.sourceIdx]
    const b = simNodes[edge.targetIdx]
    miniCtx.moveTo(a.x * scale + ox, a.y * scale + oy)
    miniCtx.lineTo(b.x * scale + ox, b.y * scale + oy)
  }
  miniCtx.stroke()

  miniCtx.fillStyle = '#2ea44f'
  for (const node of simNodes) {
    miniCtx.beginPath()
    miniCtx.arc(node.x * scale + ox, node.y * scale + oy, 2, 0, Math.PI * 2)
    miniCtx.fill()
  }

  const vx0 = -view.x / view.scale
  const vy0 = -view.y / view.scale
  const vx1 = vx0 + width / view.scale
  const vy1 = vy0 + height / view.scale
  miniCtx.strokeStyle = 'rgba(46, 164, 79, 0.75)'
  miniCtx.lineWidth = 1
  miniCtx.strokeRect(
    vx0 * scale + ox,
    vy0 * scale + oy,
    (vx1 - vx0) * scale,
    (vy1 - vy0) * scale
  )
}

const draw = () => {
  if (!ctx) return
  ctx.setTransform(dpr.value, 0, 0, dpr.value, 0, 0)
  ctx.clearRect(0, 0, width, height)
  ctx.save()
  ctx.translate(view.x, view.y)
  ctx.scale(view.scale, view.scale)
  drawEdges()
  drawNodes()
  ctx.restore()
  drawMinimap()
}

const computeFit = () => {
  if (!simNodes.length) {
    return { x: width / 2, y: height / 2, scale: 1 }
  }
  const bbox = computeBBox(simNodes)
  if (!isFinite(bbox.w) || !isFinite(bbox.h) || bbox.w <= 0 || bbox.h <= 0) {
    return { x: width / 2, y: height / 2, scale: 1 }
  }
  const pad = 80
  const fitScale = Math.min(
    (width - pad * 2) / bbox.w,
    (height - pad * 2) / bbox.h,
    1.6
  )
  const scale = Math.max(fitScale, 0.15)
  return {
    x: width / 2 - (bbox.minX + bbox.w / 2) * scale,
    y: height / 2 - (bbox.minY + bbox.h / 2) * scale,
    scale
  }
}

const fitView = () => {
  const target = computeFit()
  view.x = target.x
  view.y = target.y
  view.scale = target.scale
}

const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3)

const animateViewTo = (targetX, targetY, targetScale, duration = 600) => {
  cancelAnimationFrame(viewTweenRaf)
  const from = { x: view.x, y: view.y, scale: view.scale }
  const start = performance.now()
  const step = (now) => {
    const t = Math.min((now - start) / duration, 1)
    const e = easeOutCubic(t)
    view.x = from.x + (targetX - from.x) * e
    view.y = from.y + (targetY - from.y) * e
    view.scale = from.scale + (targetScale - from.scale) * e
    draw()
    if (t < 1) viewTweenRaf = requestAnimationFrame(step)
  }
  viewTweenRaf = requestAnimationFrame(step)
}

const runSim = () => {
  cancelAnimationFrame(rafId)
  simTicks = 0
  if (!simNodes.length) {
    draw()
    return
  }
  if (reducedMotion) {
    for (let i = 0; i < DEFAULT_PARAMS.maxTicks; i++) {
      stepSim(simNodes, simEdges, DEFAULT_PARAMS, simAlpha)
      simAlpha *= (1 - DEFAULT_PARAMS.alphaDecay)
      if (simAlpha < DEFAULT_PARAMS.alphaMin) break
    }
    if (!fitted) {
      fitView()
      fitted = true
    }
    draw()
    return
  }
  const loop = () => {
    simTicks++
    stepSim(simNodes, simEdges, DEFAULT_PARAMS, simAlpha)
    simAlpha *= (1 - DEFAULT_PARAMS.alphaDecay)
    draw()
    if (simTicks > DEFAULT_PARAMS.maxTicks || simAlpha < DEFAULT_PARAMS.alphaMin) {
      if (!fitted) {
        fitted = true
        const target = computeFit()
        animateViewTo(target.x, target.y, target.scale)
      }
      return
    }
    rafId = requestAnimationFrame(loop)
  }
  rafId = requestAnimationFrame(loop)
}

const resetSim = () => {
  simNodes = createSimNodes(props.nodes, simNodes)
  simEdges = createSimEdges(props.edges, simNodes)
  for (const node of simNodes) {
    node.size = clamp(props.nodeSize(node.raw), 6, 64)
  }
  simAlpha = 1
  fitted = false
  hoveredNodeId = null
  tooltipVisible.value = false
  fitView()
  runSim()
}

const zoomAt = (sx, sy, factor) => {
  const nextScale = clamp(view.scale * factor, 0.2, 8)
  const wx = (sx - view.x) / view.scale
  const wy = (sy - view.y) / view.scale
  view.scale = nextScale
  view.x = sx - wx * nextScale
  view.y = sy - wy * nextScale
  draw()
}

const onWheel = (event) => {
  const rect = canvasRef.value.getBoundingClientRect()
  const sx = event.clientX - rect.left
  const sy = event.clientY - rect.top
  zoomAt(sx, sy, Math.exp(-event.deltaY * 0.0015))
}

const onPointerDown = (event) => {
  const rect = canvasRef.value.getBoundingClientRect()
  downX = event.clientX - rect.left
  downY = event.clientY - rect.top
  pressedNode = hitTestNode(downX, downY)
  if (!pressedNode) {
    panning = { lastX: downX, lastY: downY }
  }
  canvasRef.value.setPointerCapture(event.pointerId)
}

const onPointerMove = (event) => {
  const rect = canvasRef.value.getBoundingClientRect()
  const sx = event.clientX - rect.left
  const sy = event.clientY - rect.top

  if (dragNode) {
    dragNode.x = (sx - view.x) / view.scale
    dragNode.y = (sy - view.y) / view.scale
    draw()
    return
  }

  if (pressedNode && !dragNode) {
    const dx = sx - downX
    const dy = sy - downY
    if (dx * dx + dy * dy > moveThreshold * moveThreshold) {
      dragNode = pressedNode
      dragNode.fixed = true
      cancelAnimationFrame(rafId)
    }
  }

  if (dragNode) {
    dragNode.x = (sx - view.x) / view.scale
    dragNode.y = (sy - view.y) / view.scale
    draw()
    return
  }

  if (panning) {
    view.x += sx - panning.lastX
    view.y += sy - panning.lastY
    panning.lastX = sx
    panning.lastY = sy
    draw()
    return
  }

  const node = hitTestNode(sx, sy)
  hoveredNodeId = node ? node.id : null
  if (node) {
    tooltipTitle.value = props.tooltipTitle ? props.tooltipTitle(node.raw) : node.label
    tooltipFields.value = props.tooltipFields ? props.tooltipFields(node.raw) : []
    tooltipVisible.value = props.showTooltip
    const tipWidth = 220
    tooltipX.value = sx + 14 + tipWidth > width ? Math.max(sx - tipWidth - 10, 4) : sx + 14
    tooltipY.value = sy + 16
    canvasRef.value.style.cursor = 'pointer'
  } else {
    tooltipVisible.value = false
    canvasRef.value.style.cursor = 'grab'
  }
  draw()
}

const onPointerUp = () => {
  if (dragNode) {
    dragNode.fixed = false
    dragNode = null
    simAlpha = Math.max(simAlpha, 0.08)
    runSim()
  } else if (pressedNode) {
    emit('node-click', pressedNode.raw)
  }
  pressedNode = null
  panning = null
}

const onPointerLeave = () => {
  hoveredNodeId = null
  tooltipVisible.value = false
}

const onMinimapPointerDown = (event) => {
  if (!simNodes.length) return
  const rect = minimapRef.value.getBoundingClientRect()
  const sx = event.clientX - rect.left
  const sy = event.clientY - rect.top
  const bbox = computeBBox(simNodes)
  const scale = Math.min((props.minimapWidth - 10) / bbox.w, (props.minimapHeight - 10) / bbox.h)
  const ox = (props.minimapWidth - bbox.w * scale) / 2 - bbox.minX * scale
  const oy = (props.minimapHeight - bbox.h * scale) / 2 - bbox.minY * scale
  const wx = (sx - ox) / scale
  const wy = (sy - oy) / scale
  view.x = width / 2 - wx * view.scale
  view.y = height / 2 - wy * view.scale
  draw()
}

const zoomIn = () => zoomAt(width / 2, height / 2, 1.25)
const zoomOut = () => zoomAt(width / 2, height / 2, 0.8)
const resetZoom = () => {
  const target = computeFit()
  animateViewTo(target.x, target.y, target.scale)
}
const highlightNode = (id) => {
  highlightedNodeId = id
  pulseStart = performance.now()
  draw()
}
const focusNode = (id) => {
  const node = simNodes.find(item => item.id === id)
  if (!node) return
  view.x = width / 2 - node.x * view.scale
  view.y = height / 2 - node.y * view.scale
  highlightNode(id)
}
const exportPng = (filename = 'knowledge-graph.png') => {
  if (!canvasRef.value) return
  const link = document.createElement('a')
  link.download = filename
  link.href = canvasRef.value.toDataURL('image/png')
  link.click()
}

defineExpose({
  zoomIn,
  zoomOut,
  resetZoom,
  highlightNode,
  focusNode,
  exportPng
})

watch(() => props.nodes, resetSim)
watch(() => props.edges, resetSim)

onMounted(() => {
  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(containerRef.value)
  resize()
  resetSim()
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  cancelAnimationFrame(rafId)
  cancelAnimationFrame(viewTweenRaf)
})
</script>

<style lang="scss" scoped>
.fgc-root {
  position: relative;
  height: var(--fgc-height, 600px);
  overflow: hidden;
}

.fgc-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  touch-action: none;
  cursor: grab;
}

.fgc-minimap {
  position: absolute;
  right: 10px;
  bottom: 10px;
  width: 150px;
  height: 100px;
  border: 1px solid #d8dee4;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  opacity: 0.8;
  transition: opacity 0.3s;
  cursor: pointer;
}

.fgc-minimap:hover {
  opacity: 1;
}

.fgc-tooltip {
  position: absolute;
  z-index: 10;
  pointer-events: none;
  background: #fff;
  border: 1px solid #d8dee4;
  border-radius: 8px;
  box-shadow: 0 6px 20px rgba(22, 27, 34, 0.12);
  padding: 8px 12px;
  font-size: 12px;
  color: #57606a;
  max-width: 260px;
  line-height: 1.5;
}

.fgc-tooltip__title {
  font-weight: 600;
  color: #24292f;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fgc-tooltip__row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.fgc-tooltip__row strong {
  color: #24292f;
  font-weight: 600;
}
</style>
