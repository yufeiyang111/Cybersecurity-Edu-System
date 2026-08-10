<template>
  <article class="user-card fav-knowledge-card">
    <div class="fav-knowledge-card__main">
      <div class="fav-knowledge-card__head">
        <span class="fav-knowledge-card__icon">
          <BaseIcon name="book" :size="16" />
        </span>
        <div class="fav-knowledge-card__title">
          {{ item.title }}
        </div>
        <span v-if="item.category_name" class="fav-knowledge-card__category">
          {{ item.category_name }}
        </span>
      </div>

      <div v-if="item.summary" class="fav-knowledge-card__summary">
        {{ summaryPreview }}
      </div>

      <div v-if="tags.length" class="fav-knowledge-card__tags">
        <span v-for="(tag, idx) in tags" :key="idx" class="fav-knowledge-card__tag">
          #{{ tag }}
        </span>
      </div>
    </div>

    <div class="fav-knowledge-card__foot">
      <div class="fav-knowledge-card__meta">
        <span class="meta-item">
          <BaseIcon name="eye" :size="13" />
          {{ item.view_count || 0 }} 次浏览
        </span>
        <span v-if="item.created_at" class="meta-item">
          {{ formatDate(item.created_at) }}
        </span>
      </div>

      <div class="fav-knowledge-card__actions">
        <button
          type="button"
          class="row-btn"
          @click="$emit('view', item)"
        >
          <BaseIcon name="eye" :size="14" />
          查看
        </button>
        <button
          type="button"
          class="row-btn row-btn--danger"
          @click="$emit('remove', item)"
        >
          <BaseIcon name="trash" :size="14" />
          取消
        </button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'

const props = defineProps({
  item: { type: Object, required: true }
})

defineEmits(['view', 'remove'])

const tags = computed(() => {
  return Array.isArray(props.item.tags) ? props.item.tags.slice(0, 4) : []
})

const summaryPreview = computed(() => {
  const summary = props.item.summary
  if (!summary) return ''
  return summary.length > 160 ? summary.substring(0, 160) + '...' : summary
})

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;
@use '@/styles/user-cards' as *;

.fav-knowledge-card {
  cursor: pointer;
}

.fav-knowledge-card__main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.fav-knowledge-card__head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.fav-knowledge-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 7px;
  background: $brand-light;
  color: $brand-color;
}

.fav-knowledge-card__title {
  font-size: 14px;
  font-weight: 600;
  color: $text-primary;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.fav-knowledge-card__category {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 999px;
  background: $bg-inset;
  color: $text-secondary;
  font-size: 11px;
  white-space: nowrap;
}

.fav-knowledge-card__summary {
  padding-left: 38px;
  font-size: 13px;
  color: $text-regular;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.fav-knowledge-card__tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding-left: 38px;
}

.fav-knowledge-card__tag {
  color: $brand-color;
  font-size: 12px;
}

.fav-knowledge-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid $border-lighter;
  flex-wrap: wrap;
}

.fav-knowledge-card__meta {
  display: flex;
  align-items: center;
  gap: 14px;
  color: $text-placeholder;
  font-size: 12px;
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.fav-knowledge-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
</style>
