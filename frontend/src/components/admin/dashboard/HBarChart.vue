<template>
  <div class="hbar-chart">
    <div
      v-for="(item, index) in items"
      :key="item.label"
      class="hbar-chart__row"
      :class="{ 'hbar-chart__row--active': hoverIndex === index }"
      @mouseenter="hoverIndex = index"
      @mouseleave="hoverIndex = null"
    >
      <span class="hbar-chart__label">{{ item.label }}</span>
      <div class="hbar-chart__track">
        <div
          class="hbar-chart__bar"
          :class="{ 'hbar-chart__bar--dim': isDim(index) }"
          :style="{
            width: `${barWidth(item)}%`,
            background: item.color
          }"
        />
      </div>
      <span class="hbar-chart__value">{{ item.value }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

const hoverIndex = ref(null)

const max = computed(() => {
  return Math.max(1, ...props.items.map((item) => item.value || 0))
})

const barWidth = (item) => {
  return Math.round((item.value || 0) / max.value * 100)
}

const isDim = (index) => {
  return hoverIndex.value !== null && hoverIndex.value !== index
}
</script>

<style lang="scss" scoped>
.hbar-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hbar-chart__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  margin: 0 -10px;
  border-radius: 8px;
  transition: background 0.2s ease;

  &--active {
    background: #f6f8fa;
  }
}

.hbar-chart__label {
  width: 64px;
  flex-shrink: 0;
  font-size: 13px;
  color: #606266;
  text-align: right;
}

.hbar-chart__track {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: #f0f2f5;
  overflow: hidden;
}

.hbar-chart__bar {
  height: 100%;
  border-radius: 999px;
  transition: width 0.7s ease, opacity 0.2s ease, filter 0.2s ease;

  &--dim {
    opacity: 0.4;
  }
}

.hbar-chart__value {
  width: 40px;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  font-variant-numeric: tabular-nums;
}

@media (prefers-reduced-motion: reduce) {
  .hbar-chart__row {
    transition: none;
  }

  .hbar-chart__bar {
    transition: none;
  }
}
</style>
