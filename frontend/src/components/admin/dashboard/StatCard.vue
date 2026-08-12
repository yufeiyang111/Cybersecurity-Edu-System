<template>
  <el-card
    class="stat-card"
    shadow="never"
    :class="{ 'stat-card--clickable': to }"
    @click="handleClick"
  >
    <div class="stat-card__main">
      <div
        class="stat-card__icon"
        :style="{ background: iconBg, color: iconColor }"
      >
        <el-icon :size="24">
          <component :is="icon" />
        </el-icon>
      </div>
      <div class="stat-card__content">
        <span class="stat-card__value">{{ display }}</span>
        <span class="stat-card__label">{{ label }}</span>
      </div>
      <el-icon v-if="to" class="stat-card__arrow">
        <ArrowRight />
      </el-icon>
    </div>
    <div v-if="sub" class="stat-card__sub">
      <span
        class="stat-card__sub-dot"
        :style="{ background: iconColor }"
      />
      <span>{{ sub }}</span>
    </div>
  </el-card>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  icon: {
    type: [Object, Function],
    required: true
  },
  iconBg: {
    type: String,
    default: '#eef2ff'
  },
  iconColor: {
    type: String,
    default: '#4f46e5'
  },
  label: {
    type: String,
    required: true
  },
  display: {
    type: [String, Number],
    default: '0'
  },
  sub: {
    type: String,
    default: ''
  },
  to: {
    type: String,
    default: ''
  }
})

const router = useRouter()

const handleClick = () => {
  if (props.to) router.push(props.to)
}
</script>

<style lang="scss" scoped>
.stat-card {
  border-radius: 12px;
  border: 1px solid #e6e8eb;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;

  :deep(.el-card__body) {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 18px 20px;
  }

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
    border-color: #c8d2dd;
  }

  &--clickable {
    cursor: pointer;
  }
}

.stat-card__main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.stat-card__icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.3s ease;
}

.stat-card:hover .stat-card__icon {
  transform: scale(1.08) rotate(-6deg);
}

.stat-card__content {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.stat-card__value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  color: #1f2937;
  font-variant-numeric: tabular-nums;
}

.stat-card__label {
  margin-top: 2px;
  font-size: 13px;
  color: #909399;
}

.stat-card__arrow {
  color: #c8d2dd;
  font-size: 16px;
  flex-shrink: 0;
  transition: transform 0.2s ease, color 0.2s ease;
}

.stat-card:hover .stat-card__arrow {
  transform: translateX(3px);
  color: #2ea44f;
}

.stat-card__sub {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px dashed #e6e8eb;
  font-size: 12px;
  color: #909399;
}

.stat-card__sub-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stat-card:hover .stat-card__sub {
  color: #606266;
}

@media (prefers-reduced-motion: reduce) {
  .stat-card {
    transition: none;

    &:hover {
      transform: none;
    }
  }

  .stat-card__icon,
  .stat-card__arrow {
    transition: none;
  }
}
</style>
