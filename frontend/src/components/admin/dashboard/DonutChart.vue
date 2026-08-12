<template>
  <div class="donut-chart">
    <div
      class="donut-chart__visual"
      :style="{ width: `${size}px`, height: `${size}px` }"
    >
      <svg :viewBox="`0 0 ${size} ${size}`" :width="size" :height="size">
        <circle
          :cx="size / 2"
          :cy="size / 2"
          :r="radius"
          fill="none"
          stroke="#f0f2f5"
          :stroke-width="thickness"
        />
        <circle
          v-for="(segment, index) in segments"
          :key="index"
          :cx="size / 2"
          :cy="size / 2"
          :r="radius"
          fill="none"
          :stroke="segment.color"
          :stroke-width="hoverIndex === index ? thickness + 6 : thickness"
          :class="{ 'donut-chart__segment--dim': isDim(index) }"
          :style="segmentStyle(segment, index)"
          @mouseenter="hoverIndex = index"
          @mouseleave="hoverIndex = null"
        />
      </svg>
      <div class="donut-chart__center">
        <template v-if="hoverSegment">
          <span class="donut-chart__value">{{ hoverSegment.percent }}%</span>
          <span class="donut-chart__label">{{ hoverSegment.label }}</span>
        </template>
        <template v-else>
          <span class="donut-chart__value">{{ centerValue }}</span>
          <span class="donut-chart__label">{{ centerLabel }}</span>
        </template>
      </div>
    </div>

    <div class="donut-chart__legend">
      <div
        v-for="(segment, index) in segments"
        :key="segment.label"
        class="donut-chart__legend-item"
        :class="{ 'donut-chart__legend-item--active': hoverIndex === index }"
        @mouseenter="hoverIndex = index"
        @mouseleave="hoverIndex = null"
      >
        <i :style="{ background: segment.color }" />
        <span class="donut-chart__legend-label">{{ segment.label }}</span>
        <span class="donut-chart__legend-value">{{ segment.value }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  segments: {
    type: Array,
    default: () => []
  },
  size: {
    type: Number,
    default: 120
  },
  thickness: {
    type: Number,
    default: 14
  },
  centerValue: {
    type: [String, Number],
    default: ''
  },
  centerLabel: {
    type: String,
    default: ''
  }
})

const hoverIndex = ref(null)
const animated = ref(false)

const radius = computed(() => (props.size - props.thickness) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const total = computed(() => props.segments.reduce((sum, s) => sum + (s.value || 0), 0))

// 各段弧长、偏移与百分比（从 12 点方向顺时针排列）
const segments = computed(() => {
  let cursor = 0
  return props.segments.map((segment) => {
    const fraction = total.value === 0 ? 0 : (segment.value || 0) / total.value
    const length = fraction * circumference.value
    const offset = cursor
    cursor += length
    return {
      ...segment,
      length,
      offset,
      percent: total.value === 0 ? 0 : Math.round((segment.value || 0) / total.value * 100)
    }
  })
})

const hoverSegment = computed(() => {
  if (hoverIndex.value === null) return null
  return segments.value[hoverIndex.value] || null
})

const isDim = (index) => {
  return hoverIndex.value !== null && hoverIndex.value !== index
}

// 数据到达后触发弧线生长动画
watch(
  () => props.segments,
  () => {
    animated.value = false
    nextTick(() => {
      animated.value = true
    })
  },
  { immediate: true }
)

// 弧线通过 CSS stroke-dasharray 过渡实现生长动画（SVG 属性变化不会触发 transition）
const segmentStyle = (segment, index) => {
  const target = `${segment.length} ${circumference.value - segment.length}`
  return {
    strokeDasharray: animated.value ? target : `0 ${circumference.value}`,
    strokeDashoffset: -segment.offset,
    transitionDelay: `${index * 0.12}s`
  }
}
</script>

<style lang="scss" scoped>
.donut-chart {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
  padding: 4px 0;
}

.donut-chart__visual {
  position: relative;
  flex-shrink: 0;

  svg {
    display: block;
  }

  circle {
    transition: stroke-width 0.2s ease, opacity 0.2s ease,
      stroke-dasharray 0.7s ease;
  }
}

.donut-chart__segment--dim {
  opacity: 0.35;
}

.donut-chart__center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.donut-chart__value {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
  font-variant-numeric: tabular-nums;
}

.donut-chart__label {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}

.donut-chart__legend {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 128px;
}

.donut-chart__legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  cursor: default;
  transition: background 0.2s ease;

  &:hover,
  &--active {
    background: #f6f8fa;
  }

  i {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    flex-shrink: 0;
  }
}

.donut-chart__legend-label {
  flex: 1;
  font-size: 13px;
  color: #606266;
}

.donut-chart__legend-value {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  font-variant-numeric: tabular-nums;
}

@media (prefers-reduced-motion: reduce) {
  .donut-chart__visual circle {
    transition: none;
  }

  .donut-chart__legend-item {
    transition: none;
  }
}
</style>
