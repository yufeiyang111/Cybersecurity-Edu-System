<template>
  <div class="heatmap-card">
    <div class="heatmap-card__header">
      <h3 class="heatmap-card__title">活跃记录</h3>
      <span class="heatmap-card__sub">最近一年 · {{ data.total }} 次使用</span>
    </div>

    <el-empty
      v-if="isEmpty"
      description="暂无活跃记录"
      :image-size="72"
    />

    <template v-else>
      <div class="heatmap-grid">
        <div v-for="(week, wi) in data.days" :key="wi" class="heatmap-week">
          <div
            v-for="(day, di) in week"
            :key="di"
            class="heatmap-cell"
            :style="{ backgroundColor: data.levels[day.level] }"
            :title="formatCell(day)"
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
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { buildHeatmapData } from '@/features/user/heatmap'

const props = defineProps({
  events: {
    type: Array,
    default: () => []
  }
})

const data = computed(() => buildHeatmapData(props.events))
const isEmpty = computed(() => data.value.total === 0)

const formatCell = (day) => {
  const d = day.date
  const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return `${dateStr}：${day.count} 次使用`
}
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.heatmap-card {
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
