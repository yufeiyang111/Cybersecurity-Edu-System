<template>
  <el-card class="knowledge-card" :body-style="{ padding: '0px' }" @click="$emit('click')">
    <div class="card-header" :class="`difficulty-${item.difficulty}`">
      <el-tag size="small" type="info">{{ item.category_name }}</el-tag>
      <el-tag size="small" :type="difficultyType">
        {{ difficultyText }}
      </el-tag>
    </div>
    <div class="card-body">
      <h3 class="card-title">{{ item.title }}</h3>
      <p class="card-summary">{{ item.summary }}</p>
      <div class="card-tags" v-if="item.tags?.length">
        <el-tag v-for="tag in item.tags.slice(0, 3)" :key="tag" size="small">
          {{ tag }}
        </el-tag>
      </div>
    </div>
    <div class="card-footer">
      <div class="meta">
        <span><el-icon><View /></el-icon> {{ item.view_count }}</span>
        <span><el-icon><Star /></el-icon> {{ item.favorite_count }}</span>
      </div>
      <el-button type="primary" size="small" text>查看详情</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: {
    type: Object,
    required: true
  }
})

defineEmits(['click'])

const difficultyType = computed(() => {
  const types = { easy: 'success', medium: 'warning', hard: 'danger' }
  return types[props.item.difficulty] || 'info'
})

const difficultyText = computed(() => {
  const texts = { easy: '入门', medium: '进阶', hard: '高级' }
  return texts[props.item.difficulty] || '普通'
})
</script>

<style lang="scss" scoped>
.knowledge-card {
  cursor: pointer;
  transition: transform 0.3s, box-shadow 0.3s;
  height: 100%;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  }

  .card-header {
    padding: 12px 16px;
    display: flex;
    gap: 8px;
    border-bottom: 1px solid #f0f0f0;

    &.difficulty-easy { background: linear-gradient(135deg, #f0f9eb, #e1f3d8); }
    &.difficulty-medium { background: linear-gradient(135deg, #fdf6ec, #faecd8); }
    &.difficulty-hard { background: linear-gradient(135deg, #fef0f0, #fee); }
  }

  .card-body {
    padding: 16px;

    .card-title {
      margin: 0 0 8px;
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .card-summary {
      margin: 0 0 12px;
      font-size: 13px;
      color: #909399;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .card-tags {
      display: flex;
      gap: 4px;
      flex-wrap: wrap;
    }
  }

  .card-footer {
    padding: 12px 16px;
    border-top: 1px solid #f0f0f0;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .meta {
      display: flex;
      gap: 16px;
      font-size: 12px;
      color: #c0c4cc;

      span {
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
  }
}
</style>
