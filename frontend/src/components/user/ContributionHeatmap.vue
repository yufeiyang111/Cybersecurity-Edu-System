<template>
  <div ref="cardRef" class="heatmap-card">
    <div class="heatmap-card__header">
      <h3 class="heatmap-card__title">{{ title }}</h3>
      <span class="heatmap-card__sub">最近一年 · {{ data.total }} 次使用</span>
    </div>

    <el-empty
      v-if="isEmpty"
      description="暂无活跃记录"
      :image-size="72"
    />

    <template v-else>
      <div
        ref="gridRef"
        class="heatmap-grid"
        @mousemove="onCellMove"
        @mouseleave="hideTip"
      >
        <div v-for="(week, wi) in data.days" :key="wi" class="heatmap-week">
          <div
            v-for="(day, di) in week"
            :key="di"
            class="heatmap-cell"
            :data-count="day.count"
            :data-date="day.date.toISOString()"
            :style="{ backgroundColor: data.levels[day.level] }"
          />
        </div>
      </div>

      <div class="heatmap-legend">
        <span>更少</span>
        <span
          v-for="(color, i) in data.levels"
          :key="i"
          class="heatmap-legend__cell"
          :style="{ backgroundColor: color }"
        />
        <span>更多</span>
      </div>
    </template>

    <Transition name="tip">
      <div
        v-if="tip"
        class="heatmap-tip"
        :style="tipStyle"
      >
        <div class="heatmap-tip__date">{{ tip.dateText }}</div>
        <div class="heatmap-tip__count">{{ tip.count }} 次使用</div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { buildHeatmapData } from '@/features/user/heatmap'

const props = defineProps({
  title: {
    type: String,
    default: '活跃记录'
  },
  events: {
    type: Array,
    default: () => []
  }
})

const data = computed(() => buildHeatmapData(props.events))
const isEmpty = computed(() => data.value.total === 0)

const cardRef = ref(null)
const gridRef = ref(null)
const tip = ref(null)
const tipStyle = ref({})

const TIP_OFFSET = 14
const TIP_WIDTH = 132
const TIP_HEIGHT = 56

// 首次渲染（或数据到达）后滚动到最右侧，让最新日期立即可见
watch(
  () => props.events,
  () => {
    if (!props.events.length) return
    nextTick(() => {
      const el = gridRef.value
      if (el) el.scrollLeft = el.scrollWidth
    })
  },
  { immediate: true }
)

const formatDateText = (d) => {
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

const onCellMove = (event) => {
  const cell = event.target.closest('.heatmap-cell')
  if (!cell) return
  const date = new Date(cell.dataset.date)
  if (isNaN(date.getTime())) return

  tip.value = {
    dateText: formatDateText(date),
    count: Number(cell.dataset.count) || 0
  }

  const cardRect = cardRef.value.getBoundingClientRect()
  const pointerX = event.clientX - cardRect.left
  const pointerY = event.clientY - cardRect.top

  let left = pointerX + TIP_OFFSET
  if (left + TIP_WIDTH > cardRect.width) {
    left = pointerX - TIP_OFFSET - TIP_WIDTH
  }
  let top = pointerY + TIP_OFFSET
  if (top + TIP_HEIGHT > cardRect.height) {
    top = pointerY - TIP_OFFSET - TIP_HEIGHT
  }
  tipStyle.value = { left: `${left}px`, top: `${top}px` }
}

const hideTip = () => {
  tip.value = null
}
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.heatmap-card {
  position: relative;
  padding: 20px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 8px;
  box-shadow: $shadow-soft;
}

.heatmap-card__header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 20px;
}

.heatmap-card__title {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
  margin: 0;
}

.heatmap-card__sub {
  font-size: 12px;
  color: $text-secondary;
}

.heatmap-grid {
  display: flex;
  gap: 3px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.heatmap-week {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.heatmap-cell {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  transition: transform 0.15s ease;

  &:hover {
    transform: scale(1.1);
    outline: 1px solid rgba(27, 31, 36, 0.6);
    outline-offset: 1px;
  }
}

.heatmap-legend {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 12px;
  font-size: 12px;
  color: $text-secondary;

  &__cell {
    width: 12px;
    height: 12px;
    border-radius: 2px;
  }
}

.heatmap-tip {
  position: absolute;
  z-index: 10;
  width: 132px;
  padding: 8px 10px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  pointer-events: none;
}

.heatmap-tip__date {
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
  white-space: nowrap;
}

.heatmap-tip__count {
  margin-top: 4px;
  font-size: 12px;
  color: $text-secondary;
}

.tip-enter-active,
.tip-leave-active {
  transition: opacity 0.15s ease;
}

.tip-enter-from,
.tip-leave-to {
  opacity: 0;
}

@include respond-to('xs') {
  .heatmap-cell {
    width: 9px;
    height: 9px;
  }

  .heatmap-week {
    gap: 2px;
  }

  .heatmap-grid {
    gap: 2px;
  }
}
</style>
